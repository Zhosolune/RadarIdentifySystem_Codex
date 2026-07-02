"""识别（聚类）工作线程。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import logging
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.logger import bind_session_log_context, unbind_session_log_context
from core.clustering import process_dimension_clustering
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.extraction_result import ExtractedClusterParams
from core.models.pulse_batch import COL_CF, COL_DOA, COL_PW, COL_TOA
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import extract_grouped_values
from core.recognition import InferenceService, recognize_clusters_parallel


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentifyWorkerResult:
    """识别线程执行结果。

    Attributes:
        success [bool]: 线程是否执行成功。
        cluster_result [SliceClusterResult | None]: 当前切片的聚类结果，失败时为 None。
        recognition_result [SliceRecognitionResult | None]: 当前切片的识别结果，失败时为 None。
        failed_phase [str]: 失败发生的阶段名称，成功时为空字符串。
        error_message [str]: 失败消息，成功时为空字符串。
    """

    success: bool
    cluster_result: SliceClusterResult | None = None
    recognition_result: SliceRecognitionResult | None = None
    failed_phase: str = ""
    error_message: str = ""


class IdentifyWorker(QThread):
    """识别（聚类+识别）后台工作线程。

    功能描述：
        作为 runtime/threading 层的具体执行单元，在子线程中编排单个切片的
        CF/PW/DOA 聚类与识别流程，并把结果交回当前 session。该类只调用
        core 暴露的聚类与识别能力，不直接实现 DBSCAN 或模型判定算法。

    Attributes:
        finished_signal [pyqtSignal]: 线程完成信号，参数为 session_id 和执行结果对象。
        progress_signal [pyqtSignal]: 线程进度信号，参数为 session_id、阶段名、当前进度和总进度。
    """

    finished_signal = pyqtSignal(str, object)
    progress_signal = pyqtSignal(str, str, int, int)

    def __init__(
        self,
        session_id: str,
        slice_index: int,
        slice_data: Any,
        inference_service: InferenceService,
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
        extract_params: ExtractParams | None = None,
        parent: QObject | None = None,
    ) -> None:
        """初始化识别（聚类）工作线程。

        Args:
            session_id [str]: 当前流程所属的会话 ID，仅用于日志和回调归属。
            slice_index [int]: 需要进行识别聚类的切片索引。
            slice_data [Any]: 需要执行聚类与识别的单切片数据对象。
            inference_service [InferenceService]: 注入的防腐层推理服务。
            cluster_params [ClusteringParams]: 当前 session 的聚类参数快照。
            recognize_params [RecognitionParams]: 当前 session 的识别参数快照。
            extract_params [ExtractParams | None]: 当前 session 的参数提取快照；为 None 时使用默认值。
            parent [QObject | None]: 挂载的 Qt 父节点。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self._session_id = session_id
        self._slice_index = slice_index
        self._slice_data = slice_data
        self._inference_service = inference_service
        self._cluster_params = cluster_params
        self._recognize_params = recognize_params
        self._extract_params = extract_params or ExtractParams()
        self._current_phase = "validation"
        self._recognition_progress_emitted = False

    def run(self) -> None:
        """执行当前切片的聚类与识别线程任务。

        功能描述：
            校验 session 切片状态，读取 workflow 注入的参数快照，调用本线程内
            的单切片流程编排方法生成聚类与识别结果，并在持锁状态下写回 session。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            RuntimeError: 当 session 尚未完成切片时抛出，并由本方法捕获后发出失败信号。
            ValueError: 当目标切片索引越界时抛出，并由本方法捕获后发出失败信号。

        Example:
            >>> hasattr(IdentifyWorker, "finished_signal")
            True
        """
        session_id = self._session_id
        # 绑定会话日志上下文，使本线程内 clustering/recognition/onnx_service 日志自动带上 session_id
        log_token = bind_session_log_context(session_id)
        try:
            # 校验切片数据存在，避免线程空跑。
            if self._slice_data is None:
                raise RuntimeError("目标切片数据为空，无法进行聚类/识别")
            # 校验切片索引合法，避免后续日志和结果落位错乱。
            if self._slice_index < 0:
                raise ValueError(f"切片索引 {self._slice_index} 无效或越界")

            LOGGER.info("开始聚类处理，当前切片: %d", self._slice_index + 1, extra={"session_id": session_id})

            # 使用 workflow 注入的 session 参数，避免读取全局配置。
            clustering_params = self._cluster_params
            recognition_params = self._recognize_params

            # 记录聚类参数快照，便于问题排查与回放分析。
            LOGGER.info(
                "参数: eps_cf=%.4f, min_pts_cf=%d, eps_pw=%.4f, min_pts_pw=%d, eps_doa=%.4f, min_pts_doa=%d, clip_doa=%.2f, min_cluster_size=%d, tol=%.2f, min_conf=%.2f, slice_index=%d",
                clustering_params.eps_cf,
                clustering_params.min_pts_cf,
                clustering_params.eps_pw,
                clustering_params.min_pts_pw,
                clustering_params.eps_doa,
                clustering_params.min_pts_doa,
                clustering_params.clip_threshold_doa,
                clustering_params.min_cluster_size,
                recognition_params.tolerance,
                recognition_params.min_confidence,
                self._slice_index,
                extra={"session_id": session_id},
            )
            
            # 标记当前阶段为聚类，用于异常时回传失败阶段。
            self._current_phase = "clustering"
            # 发射流程起始进度，通知 workflow 当前已进入聚类阶段。
            self.progress_signal.emit(session_id, "clustering", 0, 2)
            
            # 对当前切片执行级联聚类与识别
            slice_cluster_res, slice_recognition_res = self._cluster_and_recognize_slice(
                slice_data=self._slice_data,
                inference_service=self._inference_service,
                cluster_params=clustering_params,
                recognize_params=recognition_params,
            )
            # 记录聚类阶段输出规模，便于观察不同参数下的聚类密度。
            LOGGER.info("切片 %d 聚类完成，产生 %d 个簇", 
                        self._slice_index + 1, len(slice_cluster_res.clusters), extra={"session_id": session_id})
            
            # 记录最终有效簇数量，便于和 UI 展示及 session 结果核对。
            LOGGER.info("切片 %d 聚类与识别处理完成，产生 %d 个有效簇", 
                        self._slice_index + 1, len(slice_recognition_res.valid_clusters), extra={"session_id": session_id})

            # 发射完成进度，通知 workflow 可以进入写回与阶段推进。
            self.progress_signal.emit(session_id, "done", 2, 2)
            self.finished_signal.emit(
                session_id,
                IdentifyWorkerResult(
                    success=True,
                    cluster_result=slice_cluster_res,
                    recognition_result=slice_recognition_res,
                ),
            )

        except Exception as e:
            LOGGER.error("聚类与识别过程失败: %s", e, exc_info=True, extra={"session_id": session_id})
            self.finished_signal.emit(
                session_id,
                IdentifyWorkerResult(
                    success=False,
                    failed_phase=self._current_phase,
                    error_message=str(e),
                ),
            )
        finally:
            # 复位会话日志上下文，防止线程复用导致 session_id 泄漏
            unbind_session_log_context(log_token)

    def _cluster_and_recognize_slice(
        self,
        slice_data: Any,
        inference_service: InferenceService,
        cluster_params: ClusteringParams | None = None,
        recognize_params: RecognitionParams | None = None,
    ) -> tuple[SliceClusterResult, SliceRecognitionResult]:
        """编排单切片 CF/PW/DOA 聚类与识别流程。

        Args:
            slice_data [Any]: 单切片数据对象，需提供 ``index``、``data`` 和 ``time_range`` 字段。
            inference_service [InferenceService]: 推理服务实现，用于 PA/DTOA 识别。
            cluster_params [ClusteringParams | None]: 聚类参数；为 ``None`` 时使用默认参数。
            recognize_params [RecognitionParams | None]: 识别参数；为 ``None`` 时使用默认参数。

        Returns:
            tuple[SliceClusterResult, SliceRecognitionResult]: 当前切片聚类结果和识别结果。

        Raises:
            无显式抛出异常，底层聚类或识别异常会向上透传。

        Example:
            >>> from types import SimpleNamespace
            >>> data = SimpleNamespace(index=0, data=np.empty((0, 5)), time_range=(0.0, 1.0))
            >>> worker = IdentifyWorker("demo", 0, data, object(), ClusteringParams(), RecognitionParams())
            >>> cluster_res, rec_res = worker._cluster_and_recognize_slice(data, object())
            >>> cluster_res.slice_idx, rec_res.slice_index
            (0, 0)
        """
        cluster_params = cluster_params or ClusteringParams()
        recognize_params = recognize_params or RecognitionParams()
        points = slice_data.data
        # 空切片直接返回空结果，避免后续聚类函数对空矩阵做无意义处理。
        if len(points) == 0:
            return (
                SliceClusterResult(slice_data.index, [], np.array([]), np.array([])),
                SliceRecognitionResult(slice_data.index, [], []),
            )

        # 创建结果装配器，统一维护最终 cluster_idx、识别记录和回收点索引。
        builder = _IdentifyResultBuilder(self._extract_params)
        # CF维度聚类与识别
        next_cluster_id, pw_input_indices = self._process_cf_stage(
            points=points,
            slice_index=slice_data.index,
            time_range=slice_data.time_range,
            builder=builder,
            inference_service=inference_service,
            cluster_params=cluster_params,
            recognize_params=recognize_params,
            start_cluster_id=1,
        )
        # PW维度聚类与识别
        self._process_pw_stage(
            points=points,
            slice_index=slice_data.index,
            time_range=slice_data.time_range,
            pw_input_indices=pw_input_indices,
            builder=builder,
            inference_service=inference_service,
            cluster_params=cluster_params,
            recognize_params=recognize_params,
            start_cluster_id=next_cluster_id,
        )

        return self._build_slice_results(
            slice_index=slice_data.index,
            points=points,
            builder=builder,
        )

    def _process_cf_stage(
        self,
        points: np.ndarray,
        slice_index: int,
        time_range: tuple[float, float],
        builder: "_IdentifyResultBuilder",
        inference_service: InferenceService,
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
        start_cluster_id: int,
    ) -> tuple[int, np.ndarray]:
        """执行 CF 聚类、一次识别和 CF-DOA 复检。

        Args:
            points [np.ndarray]: 当前切片的全量点集。
            slice_index [int]: 当前切片索引。
            time_range [tuple[float, float]]: 当前切片时间范围。
            builder [_IdentifyResultBuilder]: 最终结果装配器。
            inference_service [InferenceService]: 推理服务实现。
            cluster_params [ClusteringParams]: 当前 session 聚类参数快照。
            recognize_params [RecognitionParams]: 当前 session 识别参数快照。
            start_cluster_id [int]: 当前阶段起始簇编号。

        Returns:
            tuple[int, np.ndarray]: 下一阶段起始簇编号和 PW 阶段输入点索引数组。

        Raises:
            无显式抛出异常，底层聚类或识别异常会向上透传。
        """
        # 进入 CF 聚类阶段，后续若失败则可明确标记为 clustering 阶段失败。
        self._current_phase = "clustering"
        cf_clusters, cf_unprocessed_idx = process_dimension_clustering(
            points=points,
            dim_name="CF",
            dim_idx=0,
            epsilon=cluster_params.eps_cf,
            min_pts=cluster_params.min_pts_cf,
            min_cluster_size=cluster_params.min_cluster_size,
            slice_idx=slice_index,
            time_range=time_range,
            start_cluster_id=start_cluster_id,
        )
        # 预留下一阶段起始簇编号，避免 PW 阶段沿用已分配的临时编号。
        next_cluster_id = start_cluster_id + len(cf_clusters)
        # 对 CF 聚类结果做第一次识别，区分有效簇与无效簇。
        cf_valid, cf_invalid, cf_recognitions, _ = self._recognize_clusters(
            clusters=cf_clusters,
            inference_service=inference_service,
            recognize_params=recognize_params,
            start_index=len(builder.valid_recognitions),
        )
        # 对 CF 一次识别通过的簇继续做 DOA 复检，并回收 DOA 失败子簇点。
        cf_doa_recycled_indices = self._append_doa_results_for_valid_clusters(
            builder=builder,
            valid_clusters=cf_valid,
            source_recognition_map=self._recognition_map(cf_recognitions),
            inference_service=inference_service,
            cluster_params=cluster_params,
            recognize_params=recognize_params,
            recycle_failed_children=True,
        )
        # 合并 CF 阶段未走通的所有点，作为 PW 阶段的输入。
        pw_input_indices = self._merge_pw_input_indices(
            cf_unprocessed_idx=cf_unprocessed_idx,
            cf_invalid_clusters=cf_invalid,
            cf_doa_recycled_indices=cf_doa_recycled_indices,
        )
        return next_cluster_id, pw_input_indices

    def _process_pw_stage(
        self,
        points: np.ndarray,
        slice_index: int,
        time_range: tuple[float, float],
        pw_input_indices: np.ndarray,
        builder: "_IdentifyResultBuilder",
        inference_service: InferenceService,
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
        start_cluster_id: int,
    ) -> None:
        """执行 PW 聚类、一次识别和 PW-DOA 复检。

        Args:
            points [np.ndarray]: 当前切片的全量点集。
            slice_index [int]: 当前切片索引。
            time_range [tuple[float, float]]: 当前切片时间范围。
            pw_input_indices [np.ndarray]: 需要进入 PW 阶段的原始点索引数组。
            builder [_IdentifyResultBuilder]: 最终结果装配器。
            inference_service [InferenceService]: 推理服务实现。
            cluster_params [ClusteringParams]: 当前 session 聚类参数快照。
            recognize_params [RecognitionParams]: 当前 session 识别参数快照。
            start_cluster_id [int]: 当前阶段起始簇编号。

        Returns:
            None: 无返回值，结果会直接写入 builder。

        Raises:
            无显式抛出异常，底层聚类或识别异常会向上透传。
        """
        # 如果 CF 阶段已经吃掉全部有效点，则无需再进入 PW。
        if len(pw_input_indices) == 0:
            return

        # 从原始切片点集中抽取 PW 需要继续处理的子集。
        pw_points = points[pw_input_indices]
        # 标记重新进入聚类阶段，便于异常时区分失败来源。
        self._current_phase = "clustering"
        pw_clusters, _ = process_dimension_clustering(
            points=pw_points,
            dim_name="PW",
            dim_idx=1,
            epsilon=cluster_params.eps_pw,
            min_pts=cluster_params.min_pts_pw,
            min_cluster_size=cluster_params.min_cluster_size,
            slice_idx=slice_index,
            time_range=time_range,
            start_cluster_id=start_cluster_id,
        )
        for cluster in pw_clusters:
            # PW 输入是回收点子集，需要把局部索引映射回原始切片数据索引。
            cluster.points_indices = pw_input_indices[cluster.points_indices]

        # 对 PW 聚类结果做一次识别，后续再按原始 PW 顺序处理最终输出。
        pw_valid, pw_invalid, pw_recognitions, _ = self._recognize_clusters(
            clusters=pw_clusters,
            inference_service=inference_service,
            recognize_params=recognize_params,
            start_index=len(builder.valid_recognitions),
        )
        self._append_final_pw_results(
            builder=builder,
            pw_clusters=pw_clusters,
            pw_valid=pw_valid,
            pw_invalid=pw_invalid,
            pw_recognitions=pw_recognitions,
            inference_service=inference_service,
            cluster_params=cluster_params,
            recognize_params=recognize_params,
        )

    def _merge_pw_input_indices(
        self,
        cf_unprocessed_idx: np.ndarray,
        cf_invalid_clusters: list[ClusterItem],
        cf_doa_recycled_indices: set[int],
    ) -> np.ndarray:
        """合并 PW 阶段需要继续处理的原始点索引。

        Args:
            cf_unprocessed_idx [np.ndarray]: CF 聚类后仍未进入任何簇的点索引。
            cf_invalid_clusters [list[ClusterItem]]: CF 一次识别失败簇列表。
            cf_doa_recycled_indices [set[int]]: CF-DOA 复检失败后回收的点索引集合。

        Returns:
            np.ndarray: 排序后的 PW 阶段输入点索引数组。

        Raises:
            无显式抛出异常。
        """
        # 合并三类输入：CF 未聚类点、CF 一次识别失败簇、CF-DOA 复检失败子簇。
        pw_input_indices = (
            set(int(index) for index in cf_unprocessed_idx.tolist())
            | self._collect_cluster_indices(cf_invalid_clusters)
            | cf_doa_recycled_indices
        )
        # 返回排序后的 numpy 索引数组，保证后续 PW 聚类输入稳定可复现。
        return np.array(sorted(pw_input_indices), dtype=int)

    def _append_final_pw_results(
        self,
        builder: "_IdentifyResultBuilder",
        pw_clusters: list[ClusterItem],
        pw_valid: list[ClusterItem],
        pw_invalid: list[ClusterItem],
        pw_recognitions: list[ClusterRecognition],
        inference_service: InferenceService,
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
    ) -> None:
        """按 PW 聚类原始顺序追加 PW 识别和 PW-DOA 结果。

        Args:
            builder [_IdentifyResultBuilder]: 最终结果装配器。
            pw_clusters [list[ClusterItem]]: PW 聚类产生的原始簇列表。
            pw_valid [list[ClusterItem]]: PW 一次识别通过的簇列表。
            pw_invalid [list[ClusterItem]]: PW 一次识别失败的簇列表。
            pw_recognitions [list[ClusterRecognition]]: PW 一次识别记录列表。
            inference_service [InferenceService]: 推理服务实现。
            cluster_params [ClusteringParams]: 当前 session 聚类参数快照。
            recognize_params [RecognitionParams]: 当前 session 识别参数快照。

        Returns:
            None: 无返回值，结果会直接写入 builder。

        Raises:
            无显式抛出异常，底层 DOA 聚类或识别异常会向上透传。
        """
        # 先构建查询映射，避免在循环中反复线性查找识别结果。
        pw_rec_map = self._recognition_map(pw_recognitions)
        pw_valid_map = {cluster.cluster_idx: cluster for cluster in pw_valid}
        pw_invalid_map = {cluster.cluster_idx: cluster for cluster in pw_invalid}
        # 按 PW 聚类原始编号顺序输出，保持“展示全部聚类结果”时的浏览顺序稳定。
        for cluster in sorted(pw_clusters, key=lambda item: item.cluster_idx):
            if cluster.cluster_idx in pw_invalid_map:
                rec = pw_rec_map.get(cluster.cluster_idx)
                if rec is not None:
                    # PW 一次识别失败已经处于末轮流程，直接作为最终无效结果。
                    builder.append_invalid(cluster, rec)
                continue

            valid_cluster = pw_valid_map.get(cluster.cluster_idx)
            if valid_cluster is None:
                # 忽略没有识别记录的异常分支，避免污染最终输出。
                continue
            # PW 识别通过簇仍需执行 DOA 检查，保持 CF/PW 两段流程对称。
            pw_doa_recycled = self._append_doa_results_for_valid_clusters(
                builder=builder,
                valid_clusters=[valid_cluster],
                source_recognition_map=pw_rec_map,
                inference_service=inference_service,
                cluster_params=cluster_params,
                recognize_params=recognize_params,
                recycle_failed_children=False,
            )
            builder.recycled_indices.update(pw_doa_recycled)

    def _append_doa_results_for_valid_clusters(
        self,
        builder: "_IdentifyResultBuilder",
        valid_clusters: list[ClusterItem],
        source_recognition_map: dict[int, ClusterRecognition],
        inference_service: InferenceService,
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
        recycle_failed_children: bool,
    ) -> set[int]:
        """对一次识别通过的簇执行 DOA 复检并追加最终结果。

        Args:
            builder [_IdentifyResultBuilder]: 最终结果装配器。
            valid_clusters [list[ClusterItem]]: 当前维度一次识别通过的簇列表。
            source_recognition_map [dict[int, ClusterRecognition]]: 当前维度一次识别记录映射。
            inference_service [InferenceService]: 推理服务实现。
            cluster_params [ClusteringParams]: 当前 session 聚类参数快照。
            recognize_params [RecognitionParams]: 当前 session 识别参数快照。
            recycle_failed_children [bool]: 是否把 DOA 识别失败子簇回收到下一阶段输入。

        Returns:
            set[int]: 需要回收的原始点索引集合。

        Raises:
            无显式抛出异常，底层聚类或识别异常会向上透传。
        """
        recycled_indices: set[int] = set()
        # 按当前簇编号顺序处理，保持最终编号分配和 UI 浏览顺序稳定。
        for cluster in sorted(valid_clusters, key=lambda item: item.cluster_idx):
            source_rec = source_recognition_map.get(cluster.cluster_idx)
            if source_rec is None:
                # 没有找到一次识别记录时，跳过该簇以避免构造不完整最终结果。
                continue

            # 基于父簇点集再次执行 DOA 聚类，判断是否存在需要拆分的方位子类。
            doa_children = self._cluster_doa_children(cluster, cluster_params)
            if len(doa_children) <= 1:
                # 未拆出多个子簇时，保留父簇作为最终有效结果。
                builder.append_valid(cluster, source_rec)
                continue

            for offset, child in enumerate(doa_children):
                # 临时索引用于本轮复识别结果映射，最终追加时会重新分配连续索引。
                child.cluster_idx = builder.next_cluster_id + offset
            # 对拆出的 DOA 子簇再次识别，筛选真正保留的最终子簇。
            doa_valid, doa_invalid, doa_recognitions, _ = self._recognize_clusters(
                clusters=doa_children,
                inference_service=inference_service,
                recognize_params=recognize_params,
                start_index=len(builder.valid_recognitions),
            )
            doa_rec_map = self._recognition_map(doa_recognitions)
            for child in doa_valid:
                rec = doa_rec_map.get(child.cluster_idx)
                if rec is not None:
                    # 仅把二次识别通过的 DOA 子簇写入最终有效结果。
                    builder.append_valid(child, rec)

            for child in doa_invalid:
                rec = doa_rec_map.get(child.cluster_idx)
                if rec is None:
                    # 没有识别记录时忽略，避免写入缺失标签的无效簇。
                    continue
                if recycle_failed_children:
                    # CF 阶段的 DOA 失败子簇不能直接判死，需要回收到 PW 再试一次。
                    recycled_indices.update(int(index) for index in child.points_indices)
                    continue
                # PW 阶段已经是末轮，DOA 失败子簇直接进入最终无效结果。
                builder.append_invalid(child, rec)
                # 同步记录回收点，避免这些点再被误算成“未处理点”。
                recycled_indices.update(int(index) for index in child.points_indices)

        return recycled_indices

    def _cluster_doa_children(
        self,
        parent_cluster: ClusterItem,
        cluster_params: ClusteringParams,
    ) -> list[ClusterItem]:
        """复用核心单维聚类函数生成 DOA 子簇。

        Args:
            parent_cluster [ClusterItem]: 已通过一次识别的 CF 或 PW 父簇。
            cluster_params [ClusteringParams]: 当前 session 聚类参数快照。

        Returns:
            list[ClusterItem]: DOA 维度聚类得到的子簇列表，点索引已映射回原始切片。

        Raises:
            无显式抛出异常，底层聚类异常会向上透传。

        Example:
            >>> worker = IdentifyWorker("demo", 0, object(), object(), ClusteringParams(), RecognitionParams())
            >>> isinstance(worker._cluster_doa_children, object)
            True
        """
        # DOA 子簇生成仍属于聚类阶段，异常时需要按 clustering 归类。
        self._current_phase = "clustering"
        doa_clusters, _ = process_dimension_clustering(
            points=parent_cluster.points,
            dim_name="DOA",
            dim_idx=COL_DOA,
            epsilon=cluster_params.eps_doa,
            min_pts=cluster_params.min_pts_doa,
            min_cluster_size=cluster_params.min_cluster_size,
            slice_idx=parent_cluster.slice_idx,
            time_range=parent_cluster.time_ranges,
            start_cluster_id=parent_cluster.cluster_idx,
        )
        for cluster in doa_clusters:
            # DOA 聚类输入是父簇点集，需要把局部索引映射回原始切片数据索引。
            cluster.points_indices = parent_cluster.points_indices[cluster.points_indices]
        return self._clip_doa_clusters_by_size(
            clusters=doa_clusters,
            total_points=len(parent_cluster.points),
            clip_threshold_percent=cluster_params.clip_threshold_doa,
        )

    def _clip_doa_clusters_by_size(
        self,
        clusters: list[ClusterItem],
        total_points: int,
        clip_threshold_percent: float,
    ) -> list[ClusterItem]:
        """按点数规模裁剪 DOA 子簇。"""
        if not clusters or total_points <= 0:
            return []

        # 先按点数由多到少排序，点数相同时保留底层聚类返回的相对顺序。
        sorted_clusters = sorted(
            clusters,
            key=lambda cluster: cluster.cluster_size,
            reverse=True,
        )
        threshold_points = total_points * clip_threshold_percent / 100.0
        kept_clusters: list[ClusterItem] = []
        accumulated_points = 0

        for cluster in sorted_clusters:
            # 累加当前大簇后再判断停止条件，确保触发阈值的簇会被保留。
            kept_clusters.append(cluster)
            accumulated_points += cluster.cluster_size
            if accumulated_points > threshold_points or len(kept_clusters) >= 3:
                break

        return kept_clusters

    def _recognize_clusters(
        self,
        clusters: list[ClusterItem],
        inference_service: InferenceService,
        recognize_params: RecognitionParams,
        start_index: int,
    ) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
        """执行簇识别并在首次识别前发出阶段进度。

        Args:
            clusters [list[ClusterItem]]: 当前阶段待识别的簇列表。
            inference_service [InferenceService]: 推理服务实现。
            recognize_params [RecognitionParams]: 当前 session 识别参数快照。
            start_index [int]: 当前阶段有效簇起始编号。

        Returns:
            tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
                识别通过簇、识别失败簇、识别记录列表以及下一个有效簇起始编号。

        Raises:
            无显式抛出异常，底层识别异常会向上透传。
        """
        # 标记当前进入识别阶段，供 workflow 在失败时区分状态写回。
        self._current_phase = "recognition"
        if not self._recognition_progress_emitted:
            # 首次进入识别阶段时发一次进度，避免多轮 DOA 复检重复刷状态。
            self.progress_signal.emit(self._session_id, "recognition", 1, 2)
            self._recognition_progress_emitted = True
        return recognize_clusters_parallel(
            clusters,
            inference_service,
            recognize_params,
            start_index,
        )

    def _build_slice_results(
        self,
        slice_index: int,
        points: np.ndarray,
        builder: "_IdentifyResultBuilder",
    ) -> tuple[SliceClusterResult, SliceRecognitionResult]:
        """根据结果收集器构建单切片最终输出。

        Args:
            slice_index [int]: 当前切片索引。
            points [np.ndarray]: 当前切片的全量点集。
            builder [_IdentifyResultBuilder]: 已完成装配的最终结果收集器。

        Returns:
            tuple[SliceClusterResult, SliceRecognitionResult]: 单切片最终聚类结果和识别结果。

        Raises:
            无显式抛出异常。
        """
        # 收集最终有效簇覆盖的原始点索引，用于反推出真正未处理点。
        valid_indices = self._collect_valid_indices(builder.clusters)
        # 从全量点中扣除有效点和回收点，剩余部分才是最终未处理点。
        final_unprocessed_idx = sorted(
            set(range(len(points))) - valid_indices - builder.recycled_indices
        )
        # 构造最终聚类结果，供 session 和 UI 直接消费。
        cluster_result = SliceClusterResult(
            slice_idx=slice_index,
            clusters=builder.clusters,
            unprocessed_points=points[final_unprocessed_idx]
            if final_unprocessed_idx
            else np.array([]),
            recycled_points=points[sorted(builder.recycled_indices)]
            if builder.recycled_indices
            else np.array([]),
        )
        # 构造最终识别结果，区分最终有效和最终无效两类识别记录。
        recognition_result = SliceRecognitionResult(
            slice_index=slice_index,
            valid_clusters=builder.valid_recognitions,
            invalid_clusters=builder.invalid_recognitions,
        )
        return cluster_result, recognition_result

    @staticmethod
    def _recognition_map(
        recognitions: list[ClusterRecognition],
    ) -> dict[int, ClusterRecognition]:
        """按簇索引构建识别记录映射。

        Args:
            recognitions [list[ClusterRecognition]]: 识别记录列表。

        Returns:
            dict[int, ClusterRecognition]: 以簇编号为键的识别记录映射。

        Raises:
            无显式抛出异常。
        """
        # 使用簇编号作为键，供 CF/PW/DOA 各阶段快速回查原识别记录。
        return {rec.cluster_index: rec for rec in recognitions}

    @staticmethod
    def _collect_cluster_indices(clusters: list[ClusterItem]) -> set[int]:
        """收集簇内点在原始切片数据中的索引。

        Args:
            clusters [list[ClusterItem]]: 聚类簇列表。

        Returns:
            set[int]: 簇内所有原始点索引集合。

        Raises:
            无显式抛出异常。
        """
        indices: set[int] = set()
        for cluster in clusters:
            # 把簇内所有点索引拍平成集合，供 PW 输入合并使用。
            indices.update(int(index) for index in cluster.points_indices)
        return indices

    @staticmethod
    def _collect_valid_indices(clusters: list[ClusterItem]) -> set[int]:
        """收集最终有效簇点在原始切片数据中的索引。

        Args:
            clusters [list[ClusterItem]]: 最终聚类簇列表。

        Returns:
            set[int]: 最终有效簇覆盖的原始点索引集合。

        Raises:
            无显式抛出异常。
        """
        indices: set[int] = set()
        for cluster in clusters:
            if cluster.state is ClusterState.VALID:
                # 仅统计最终有效簇覆盖的点，用于反推未处理点集合。
                indices.update(int(index) for index in cluster.points_indices)
        return indices


class _IdentifyResultBuilder:
    """维护识别线程单切片最终输出的索引和结果列表。

    功能描述：
        该辅助类只负责最终结果装配：为最终保留的有效/无效簇分配连续
        ``cluster_idx``，同步重建 ``ClusterRecognition``，并收集最终回收点索引。

    Attributes:
        clusters [list[ClusterItem]]: 最终展示用聚类簇列表，顺序即 UI 浏览顺序。
        valid_recognitions [list[ClusterRecognition]]: 最终识别通过的识别记录列表。
        invalid_recognitions [list[ClusterRecognition]]: 最终识别未通过的识别记录列表。
        recycled_indices [set[int]]: 最终确认无效并回收的原始切片点索引集合。
        next_cluster_id [int]: 下一个可分配的最终簇编号。
        extract_params [ExtractParams]: 识别通过类的参数提取配置。
    """

    def __init__(self, extract_params: ExtractParams | None = None) -> None:
        """初始化结果收集器。

        Args:
            extract_params [ExtractParams | None]: 参数提取配置；为 None 时使用默认值。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> builder = _IdentifyResultBuilder()
            >>> builder.next_cluster_id
            1
        """
        # 收集最终展示簇列表，顺序即最终浏览顺序。
        self.clusters: list[ClusterItem] = []
        # 收集最终有效识别记录，顺序与最终有效簇编号一致。
        self.valid_recognitions: list[ClusterRecognition] = []
        # 收集最终无效识别记录，供“展示全部聚类结果”模式使用。
        self.invalid_recognitions: list[ClusterRecognition] = []
        # 记录已经被判定为无效并回收的原始点索引。
        self.recycled_indices: set[int] = set()
        # 维护最终连续簇编号，避免中间阶段编号出现空洞。
        self.next_cluster_id: int = 1
        # 保存提取配置，确保最终有效类装配时可同步提取参数。
        self.extract_params = extract_params or ExtractParams()

    def append_valid(
        self,
        cluster: ClusterItem,
        recognition: ClusterRecognition,
    ) -> ClusterRecognition:
        """追加最终有效簇，并重建最终识别记录。

        Args:
            cluster [ClusterItem]: 需要作为最终有效结果保留的簇。
            recognition [ClusterRecognition]: 与该簇对应的最近一次识别记录。

        Returns:
            ClusterRecognition: 按最终簇编号和有效序号重建后的识别记录。

        Raises:
            无显式抛出异常。

        Example:
            >>> builder = _IdentifyResultBuilder()
            >>> builder.next_cluster_id
            1
        """
        # 计算当前有效簇在最终有效结果中的顺序编号。
        valid_idx = len(self.valid_recognitions)
        # 最终簇编号只在结果装配阶段分配，避免中间失败子类造成编号空洞。
        cluster.cluster_idx = self.next_cluster_id
        cluster.valid_cluster_idx = valid_idx
        cluster.state = ClusterState.VALID
        cluster.pa_label = recognition.pa_label
        cluster.dtoa_label = recognition.dtoa_label
        cluster.joint_prob = recognition.joint_prob
        # 先把簇对象写入最终簇列表，再同步重建对应识别记录。
        self.clusters.append(cluster)
        # 仅对最终识别通过类提取参数，避免无效类污染后续合并和导出。
        extracted_params = self._extract_valid_cluster_params(cluster)
        shifted_rec = self._shift_recognition_index(
            recognition,
            new_cluster_index=self.next_cluster_id,
            valid_cluster_index=valid_idx,
            is_valid=True,
            extracted_params=extracted_params,
        )
        self.valid_recognitions.append(shifted_rec)
        # 推进最终簇编号，为下一个最终结果预留编号。
        self.next_cluster_id += 1
        return shifted_rec

    def _extract_valid_cluster_params(
        self,
        cluster: ClusterItem,
    ) -> ExtractedClusterParams:
        """从最终识别通过类中提取 CF、PW、PRI、DOA 参数。"""
        # 结果装配阶段只处理最终保留的类，避免中间簇或无效簇进入参数结果。
        points = cluster.points
        if points.size == 0:
            return ExtractedClusterParams()

        # CF 使用配置中的邻域半径、最小点数和门限率，底层仅负责一维数值聚类。
        cf_values = extract_grouped_values(
            points[:, COL_CF],
            eps=self.extract_params.eps_cf,
            min_samples=self.extract_params.min_pts_cf,
            threshold_ratio=self.extract_params.threshold_ratio_cf / 100.0,
        )
        # PW 与 CF 共享同一类典型值算法，但使用独立的 PW 参数配置。
        pw_values = extract_grouped_values(
            points[:, COL_PW],
            eps=self.extract_params.eps_pw,
            min_samples=self.extract_params.min_pts_pw,
            threshold_ratio=self.extract_params.threshold_ratio_pw / 100.0,
        )
        # PRI 是 TOA 的派生量，单位转换和业务过滤留在工作线程内完成。
        pri_values = self._extract_pri_values(points[:, COL_TOA])
        # DOA 使用循环均值处理 0°/360° 边界；仍用列表返回以保持四类参数契约一致。
        doa_values = self._extract_doa_values(points[:, COL_DOA])
        return ExtractedClusterParams(
            cf_values=cf_values,
            pw_values=pw_values,
            pri_values=pri_values,
            doa_values=doa_values,
        )

    def _extract_pri_values(self, toa_values: np.ndarray) -> list[float]:
        """从 TOA 序列提取 PRI 典型值。"""
        if len(toa_values) < 2:
            return []

        # 保持当前类内脉冲顺序，按相邻 TOA 差分得到 DTOA/PRI 序列。
        toa_array = np.asarray(toa_values, dtype=float)
        # TOA 在项目内保持 0.1us 单位，PRI 对外展示与配置统一使用 us。
        pri_values = np.diff(toa_array) * 0.1
        # 补齐一个尾值，使 PRI 序列长度与原始脉冲数保持一致。
        pri_values = np.append(pri_values, 0.0)
        # 先对 PRI 序列执行一维典型值提取，后续再做业务过滤。
        grouped_values = extract_grouped_values(
            pri_values,
            eps=self.extract_params.eps_pri,
            min_samples=self.extract_params.min_pts_pri,
            threshold_ratio=self.extract_params.threshold_ratio_pri / 100.0,
        )
        if not grouped_values:
            return []

        # 多个典型 PRI 之间可能存在谐波或组合和值，需要按旧流程做关系过滤。
        if len(grouped_values) > 1:
            grouped_values = self._filter_related_numbers(
                grouped_values,
                tolerance=self.extract_params.harmonic_tolerance_pri,
            )

        # 单个 PRI 低于门限时视为无效结果，避免输出异常短周期。
        if len(grouped_values) == 1 and grouped_values[0] < self.extract_params.filter_threshold_pri:
            return []
        return grouped_values

    @staticmethod
    def _extract_doa_values(doa_values: np.ndarray) -> list[float]:
        """从 DOA 序列提取循环均值列表。"""
        if len(doa_values) == 0:
            return []

        # 先排序并去掉两端值，降低方位角离群点对最终均值的影响。
        sorted_doa = np.array(sorted(np.asarray(doa_values, dtype=float)))
        trimmed_doa = sorted_doa[1:-1] if len(sorted_doa) > 2 else sorted_doa
        if len(trimmed_doa) == 0:
            return []

        # 循环均值天然处理 0°/360° 边界，结果固定到 4 位用于稳定展示。
        return [float(np.round(_IdentifyResultBuilder._circular_mean(trimmed_doa), 4))]

    @staticmethod
    def _circular_mean(angles: np.ndarray) -> float:
        """计算循环均值，正确处理跨越 0°/360° 边界的情况。"""
        if len(angles) == 0:
            return 0.0

        # 将每个角度转换为单位向量，求平均方向后再转换回角度。
        angles_rad = np.radians(angles, dtype=np.float64)
        sin_sum = np.sum(np.sin(angles_rad))
        cos_sum = np.sum(np.cos(angles_rad))
        mean_rad = np.arctan2(sin_sum, cos_sum)
        mean_deg = float(np.degrees(mean_rad))
        result = mean_deg % 360.0
        if np.isclose(result, 360.0):
            result = 0.0

        # 当算术均值和循环均值差异较大时，记录跨边界分布线索。
        arith_mean = float(np.mean(angles))
        diff = abs(result - arith_mean)
        if diff > 5.0:
            LOGGER.info(
                "[circular_mean] 角度可能跨越0°/360°边界，n=%d, min=%.2f°, max=%.2f°, 算术均值=%.2f°, 循环均值=%.2f°, 偏差=%.2f°",
                len(angles),
                float(np.min(angles)),
                float(np.max(angles)),
                arith_mean,
                result,
                diff,
            )
        else:
            LOGGER.debug(
                "[circular_mean] n=%d, min=%.2f°, max=%.2f°, 算术均值=%.2f°, 循环均值=%.2f°",
                len(angles),
                float(np.min(angles)),
                float(np.max(angles)),
                arith_mean,
                result,
            )
        return result

    @staticmethod
    def _filter_related_numbers(
        values: list[float],
        tolerance: float,
    ) -> list[float]:
        """按容差过滤整数倍、两数和、三数和相关的 PRI 值。"""
        if tolerance <= 0 or len(values) <= 1:
            return values

        sorted_values = sorted(float(value) for value in values)
        removed_indices: set[int] = set()

        # 先过滤整数倍关系，较小值作为基准，较大相关值被移除。
        for base_index, base_value in enumerate(sorted_values):
            if base_index in removed_indices or base_value <= 0:
                continue
            for target_index in range(base_index + 1, len(sorted_values)):
                if target_index in removed_indices:
                    continue
                target_value = sorted_values[target_index]
                multiple = round(target_value / base_value)
                if multiple >= 2 and abs(target_value - base_value * multiple) <= tolerance:
                    removed_indices.add(target_index)

        # 再过滤两数和、三数和关系，避免组合周期作为独立 PRI 输出。
        for target_index, target_value in enumerate(sorted_values):
            if target_index in removed_indices:
                continue
            base_values = [
                value
                for index, value in enumerate(sorted_values[:target_index])
                if index not in removed_indices
            ]
            if _IdentifyResultBuilder._is_sum_of_related_values(
                target_value,
                base_values,
                tolerance,
            ):
                removed_indices.add(target_index)

        return [
            value
            for index, value in enumerate(sorted_values)
            if index not in removed_indices
        ]

    @staticmethod
    def _is_sum_of_related_values(
        value: float,
        base_values: list[float],
        tolerance: float,
    ) -> bool:
        """判断当前 PRI 是否近似等于已有 PRI 的两数和或三数和。"""
        for combination_size in (2, 3):
            for candidate_values in combinations(base_values, combination_size):
                # 使用绝对容差判断组合和值，容差单位与 PRI 配置保持一致。
                if abs(value - sum(candidate_values)) <= tolerance:
                    return True
        return False

    def append_invalid(
        self,
        cluster: ClusterItem,
        recognition: ClusterRecognition,
    ) -> ClusterRecognition:
        """追加最终无效簇，并重建最终识别记录。

        Args:
            cluster [ClusterItem]: 需要作为最终无效结果保留的簇。
            recognition [ClusterRecognition]: 与该簇对应的最近一次识别记录。

        Returns:
            ClusterRecognition: 按最终簇编号重建后的无效识别记录。

        Raises:
            无显式抛出异常。

        Example:
            >>> builder = _IdentifyResultBuilder()
            >>> builder.invalid_recognitions
            []
        """
        # 无效簇也进入最终展示列表，供“展示全部聚类结果”模式浏览。
        cluster.cluster_idx = self.next_cluster_id
        cluster.valid_cluster_idx = None
        cluster.state = ClusterState.INVALID
        cluster.pa_label = recognition.pa_label
        cluster.dtoa_label = recognition.dtoa_label
        cluster.joint_prob = recognition.joint_prob
        # 无效簇也要保留到最终簇列表，供全部结果浏览模式使用。
        self.clusters.append(cluster)
        shifted_rec = self._shift_recognition_index(
            recognition,
            new_cluster_index=self.next_cluster_id,
            valid_cluster_index=None,
            is_valid=False,
        )
        self.invalid_recognitions.append(shifted_rec)
        # 无效结果对应点进入回收集合，避免再被标记为未处理点。
        self.recycled_indices.update(int(index) for index in cluster.points_indices)
        # 推进最终簇编号，保持有效/无效簇共用同一套连续编号。
        self.next_cluster_id += 1
        return shifted_rec

    @staticmethod
    def _shift_recognition_index(
        recognition: ClusterRecognition,
        new_cluster_index: int,
        valid_cluster_index: int | None,
        is_valid: bool,
        extracted_params: ExtractedClusterParams | None = None,
    ) -> ClusterRecognition:
        """复制识别记录，并替换为最终簇索引与最终有效序号。

        Args:
            recognition [ClusterRecognition]: 原始识别记录。
            new_cluster_index [int]: 重排后的最终簇编号。
            valid_cluster_index [int | None]: 重排后的最终有效簇序号；无效簇时为 None。
            is_valid [bool]: 当前结果是否属于最终有效簇。
            extracted_params [ExtractedClusterParams | None]: 当前最终记录绑定的参数提取结果。

        Returns:
            ClusterRecognition: 重建后的最终识别记录对象。

        Raises:
            无显式抛出异常。
        """
        # 复制识别记录并重写索引字段，避免修改中间阶段原始识别对象。
        return ClusterRecognition(
            slice_index=recognition.slice_index,
            dim_name=recognition.dim_name,
            cluster_index=new_cluster_index,
            valid_cluster_index=valid_cluster_index,
            pa_label=recognition.pa_label,
            pa_confidence=recognition.pa_confidence,
            dtoa_label=recognition.dtoa_label,
            dtoa_confidence=recognition.dtoa_confidence,
            is_valid=is_valid,
            joint_prob=recognition.joint_prob,
            pa_conf_dict=dict(recognition.pa_conf_dict),
            dtoa_conf_dict=dict(recognition.dtoa_conf_dict),
            extracted_params=extracted_params or recognition.extracted_params,
        )
