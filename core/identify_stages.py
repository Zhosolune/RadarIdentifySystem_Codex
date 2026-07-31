"""识别流程可复用阶段算子。

功能描述：
    承载 CF/PW/DOA 级联识别流程中可跨算法复用的中间步骤，包括：
    - 阶段执行上下文 ``IdentifyPipelineContext``；
    - 结果装配器 ``IdentifyResultBuilder``；
    - 复用性算子集合 ``IdentifyStageOps``：识别调用、DOA 子簇生成、DOA 复检结果追加；
    - 结果收敛与索引合并等纯工具函数。
    模块只依赖 ``core`` 内部能力，不感知具体流程编排（例如 CF→PW→DOA 顺序），
    可被不同上层编排（``core.identify_pipeline`` 等）组合复用。

Example:
    典型的使用场景：
    >>> from core.identify_stages import IdentifyPipelineContext, IdentifyStageOps
    >>> ctx = IdentifyPipelineContext()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from core.clustering import clip_doa_clusters_by_size, process_dimension_clustering
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.pulse_batch import COL_DOA
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import extract_cluster_params
from core.recognition import InferenceService, recognize_clusters_parallel


# 阶段常量，供上层在异常时判定失败归属。
PHASE_CLUSTERING = "clustering"
PHASE_RECOGNITION = "recognition"

# 模块日志器，用于输出识别流程的分层缩进日志。
LOGGER = logging.getLogger(__name__)


@dataclass
class IdentifyPipelineContext:
    """识别流程执行上下文。

    功能描述：
        用于在流程内部标记当前所处阶段，并在首次进入识别阶段时通过可选回调
        通知外部（例如线程层的进度信号）。上层线程可在流程抛出异常后读取
        ``current_phase`` 来判定失败归属。

    Attributes:
        current_phase [str]: 当前阶段名称，取值为 ``"clustering"`` 或 ``"recognition"``。
        on_recognition_started [Callable[[], None] | None]: 首次进入识别阶段的通知回调。
    """

    current_phase: str = PHASE_CLUSTERING
    on_recognition_started: Callable[[], None] | None = None
    # 内部标记，避免多轮 DOA 复检时重复触发识别阶段回调。
    _recognition_notified: bool = False

    def enter_clustering(self) -> None:
        """标记流程进入聚类阶段。"""
        # 每次进入聚类阶段都重置阶段名，方便异常时定位失败归属。
        self.current_phase = PHASE_CLUSTERING

    def enter_recognition(self) -> None:
        """标记流程进入识别阶段并按需触发一次通知回调。"""
        # 每次进入识别阶段都刷新当前阶段名，供异常路径读取。
        self.current_phase = PHASE_RECOGNITION
        if not self._recognition_notified:
            # 首次进入识别阶段时同步触发通知，避免多轮复检重复刷状态。
            self._recognition_notified = True
            if self.on_recognition_started is not None:
                self.on_recognition_started()


class IdentifyStageOps:
    """识别流程阶段算子集合。

    功能描述：
        把 CF/PW/DOA 级联识别流程中可复用的中间步骤集中封装：
        - ``recognize``：并发识别一组簇并触发上下文识别阶段回调；
        - ``cluster_doa_children``：对父簇执行 DOA 聚类并按规模限幅；
        - ``append_doa_results``：对一次识别通过的父簇执行 DOA 复检并写入结果装配器。

        依赖统一由构造注入，避免上层编排在每个方法调用点重复传参。
        本类只承载算子调用逻辑，不关心 CF→PW→DOA 的调度顺序，可被多套编排复用。

    Attributes:
        inference_service [InferenceService]: 推理服务实现，供识别方法调用。
        cluster_params [ClusteringParams]: 聚类参数，供 DOA 二次聚类和限幅使用。
        recognize_params [RecognitionParams]: 识别参数，供 ``recognize`` 使用。
        context [IdentifyPipelineContext]: 阶段执行上下文，供阶段迁移与识别回调使用。
        recognition_max_workers [int | None]: 簇级识别并发线程上限。
    """

    def __init__(
        self,
        inference_service: InferenceService,
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
        context: IdentifyPipelineContext,
        recognition_max_workers: int | None = None,
    ) -> None:
        """
        Args:
            inference_service [InferenceService]: 推理服务实现。
            cluster_params [ClusteringParams]: 聚类参数快照。
            recognize_params [RecognitionParams]: 识别参数快照。
            context [IdentifyPipelineContext]: 阶段执行上下文。
            recognition_max_workers [int | None]: 簇级识别并发线程上限。
        """
        # 保存注入依赖，供后续算子方法直接读取。
        self.inference_service = inference_service
        self.cluster_params = cluster_params
        self.recognize_params = recognize_params
        self.context = context
        self.recognition_max_workers = recognition_max_workers

    def recognize(
        self,
        clusters: list[ClusterItem],
        start_index: int,
        write_summary_log: bool = True,
    ) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
        """执行簇识别并在首次识别前触发上下文识别阶段回调。

        Args:
            clusters [list[ClusterItem]]: 待识别簇列表。
            start_index [int]: 有效簇起始索引，用于分配 valid_cluster_idx。
            write_summary_log [bool]: 是否输出内置的“簇 X (维度) 预测结果”汇总日志。

        Returns:
            tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
            有效簇、无效簇、识别记录列表、下一个可用有效簇索引。
        """
        # 标记当前进入识别阶段，供上层在失败时区分状态写回。
        self.context.enter_recognition()
        return recognize_clusters_parallel(
            clusters,
            self.inference_service,
            self.recognize_params,
            start_index,
            max_workers=self.recognition_max_workers,
            write_summary_log=write_summary_log,
        )

    def cluster_doa_children(
        self,
        parent_cluster: ClusterItem,
        parent_dim_name: str = "",
    ) -> list[ClusterItem]:
        """对父簇执行 DOA 聚类并按规模限幅。

        Args:
            parent_cluster [ClusterItem]: 待做 DOA 复检的父簇。
            parent_dim_name [str]: 父簇所属维度名称，用于日志分层。

        Returns:
            list[ClusterItem]: 限幅后保留的 DOA 子簇列表。
        """
        # DOA 子簇生成仍属于聚类阶段，异常时需要按 clustering 归类。
        self.context.enter_clustering()
        doa_clusters, doa_unprocessed = process_dimension_clustering(
            points=parent_cluster.points,
            dim_name="DOA",
            dim_idx=COL_DOA,
            epsilon=self.cluster_params.eps_doa,
            min_pts=self.cluster_params.min_pts_doa,
            min_cluster_size=self.cluster_params.min_cluster_size,
            slice_idx=parent_cluster.slice_idx,
            time_range=parent_cluster.time_ranges,
            start_cluster_id=parent_cluster.cluster_idx,
        )
        for cluster in doa_clusters:
            # DOA 聚类输入是父簇点集，需要把局部索引映射回原始切片数据索引。
            cluster.points_indices = parent_cluster.points_indices[cluster.points_indices]
        # 记录 DOA 聚类原始输出与限幅前每个子簇点数，供后续对齐限幅前后差异。
        LOGGER.info(
            "  ├─ [%s→DOA] 父簇 %d 聚类：拆出子簇=%d，未聚类点=%d，父簇点数=%d",
            parent_dim_name or parent_cluster.dim_name,
            parent_cluster.cluster_idx,
            len(doa_clusters),
            len(doa_unprocessed),
            len(parent_cluster.points),
        )
        for offset, cluster in enumerate(doa_clusters, start=1):
            LOGGER.info(
                "  │   ├─ 限幅前 DOA 子簇 %d：点数=%d",
                offset,
                cluster.cluster_size,
            )
        kept_clusters = clip_doa_clusters_by_size(
            clusters=doa_clusters,
            total_points=len(parent_cluster.points),
            clip_threshold_percent=self.cluster_params.clip_threshold_doa,
        )
        # 记录限幅后的保留结果，便于对比限幅规则的实际生效情况。
        dropped = len(doa_clusters) - len(kept_clusters)
        LOGGER.info(
            "  ├─ [%s→DOA] 父簇 %d 限幅：阈值=%.2f%%，保留子簇=%d，丢弃=%d",
            parent_dim_name or parent_cluster.dim_name,
            parent_cluster.cluster_idx,
            self.cluster_params.clip_threshold_doa,
            len(kept_clusters),
            dropped,
        )
        for offset, cluster in enumerate(kept_clusters, start=1):
            LOGGER.info(
                "  │   ├─ 保留 DOA 子簇 %d：点数=%d",
                offset,
                cluster.cluster_size,
            )
        return kept_clusters

    def append_doa_results(
        self,
        builder: "IdentifyResultBuilder",
        valid_clusters: list[ClusterItem],
        source_recognition_map: dict[int, ClusterRecognition],
        recycle_failed_children: bool,
        parent_dim_name: str,
    ) -> tuple[set[int], int, int, int]:
        """对一次识别通过的簇执行 DOA 复检并追加最终结果。

        Args:
            builder [IdentifyResultBuilder]: 最终结果装配器。
            valid_clusters [list[ClusterItem]]: 一次识别通过的父簇列表。
            source_recognition_map [dict[int, ClusterRecognition]]: 一次识别记录映射。
            recycle_failed_children [bool]: DOA 失败子簇是否回收到下一阶段。
            parent_dim_name [str]: 父簇所属维度名称，用于日志分层。

        Returns:
            tuple[set[int], int, int, int]: 依次为回收点索引集合、
            未拆多子簇被直接保留为最终有效的父簇数、DOA 拆分后二次识别通过的子簇数、
            DOA 拆分后二次识别未通过的子簇数。
        """
        recycled_indices: set[int] = set()
        # 累计当前维度下 DOA 二次识别通过与未通过的子簇数量。
        doa_valid_total = 0
        doa_invalid_total = 0
        # 未拆多子簇的父簇个数，供上层汇总"最终通过簇数"使用。
        parent_kept_as_valid = 0
        # 按当前簇编号顺序处理，保持最终编号分配和 UI 浏览顺序稳定。
        for cluster in sorted(valid_clusters, key=lambda item: item.cluster_idx):
            source_rec = source_recognition_map.get(cluster.cluster_idx)
            if source_rec is None:
                # 没有找到一次识别记录时，跳过该簇以避免构造不完整最终结果。
                continue

            LOGGER.info(
                "[%s→DOA] 父簇 %d 进入 DOA 复检：父簇点数=%d",
                parent_dim_name,
                cluster.cluster_idx,
                cluster.cluster_size,
            )
            # 基于父簇点集再次执行 DOA 聚类，判断是否存在需要拆分的方位子类。
            doa_children = self.cluster_doa_children(
                cluster,
                parent_dim_name=parent_dim_name,
            )
            if len(doa_children) <= 1:
                # 未拆出多个子簇时，保留父簇作为最终有效结果。
                LOGGER.info(
                    "  └─ %s 父簇 %d 未拆出多子簇（DOA 子簇数=%d），保留父簇为最终有效",
                    parent_dim_name,
                    cluster.cluster_idx,
                    len(doa_children),
                )
                builder.append_valid(cluster, source_rec)
                # 记录未拆分父簇数量，供上层汇总维度整体通过簇数使用。
                parent_kept_as_valid += 1
                continue

            for offset, child in enumerate(doa_children):
                # 临时索引用于本轮复识别结果映射，最终追加时会重新分配连续索引。
                child.cluster_idx = builder.next_cluster_id + offset
            # 对拆出的 DOA 子簇再次识别，筛选真正保留的最终子簇；关闭内置日志改由本层缩进输出。
            doa_valid, doa_invalid, doa_recognitions, _ = self.recognize(
                clusters=doa_children,
                start_index=len(builder.valid_recognitions),
                write_summary_log=False,
            )
            doa_rec_map = recognition_map(doa_recognitions)
            # 输出 DOA 子簇的预测结果，缩进体现从父簇继承的关系。
            for child_offset, child in enumerate(doa_children, start=1):
                rec = doa_rec_map.get(child.cluster_idx)
                if rec is None:
                    LOGGER.info(
                        "  ├─ 子簇 %d (DOA)：点数=%d，识别记录缺失",
                        child_offset,
                        child.cluster_size,
                    )
                    continue
                # 先输出 PA 各类别概率，保留完整分布便于溯源模型判定过程。
                LOGGER.info(
                    "  ├─ 子簇 %d (DOA)：父簇=%s#%d，点数=%d，PA 各类别概率=%s",
                    child_offset,
                    parent_dim_name,
                    cluster.cluster_idx,
                    child.cluster_size,
                    format_conf_dict(rec.pa_conf_dict),
                )
                # 再输出 DTOA 各类别概率，与 PA 对齐同一子簇的两组分布。
                LOGGER.info(
                    "  │   ├─ DTOA 各类别概率=%s",
                    format_conf_dict(rec.dtoa_conf_dict),
                )
                # 最后输出总结性预测结果，方便快速识别 label 与置信度。
                LOGGER.info(
                    "  │   └─ 预测结果 PA=%d(%.4f), DTOA=%d(%.4f)，识别%s",
                    rec.pa_label,
                    rec.pa_confidence,
                    rec.dtoa_label,
                    rec.dtoa_confidence,
                    "通过" if rec.is_valid else "未通过",
                )
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
                    # 上游阶段的 DOA 失败子簇不能直接判死，需要回收到下一阶段再试。
                    recycled_indices.update(int(index) for index in child.points_indices)
                    continue
                # 末轮阶段的 DOA 失败子簇直接进入最终无效结果。
                builder.append_invalid(child, rec)
                # 同步记录回收点，避免这些点再被误算成“未处理点”。
                recycled_indices.update(int(index) for index in child.points_indices)

            # 累加当前父簇的 DOA 通过/未通过统计，供维度级二次识别汇总。
            doa_valid_total += len(doa_valid)
            doa_invalid_total += len(doa_invalid)

            LOGGER.info(
                "  └─ %s 父簇 %d 复检小结：DOA 子簇通过=%d，未通过=%d，回收点=%d",
                parent_dim_name,
                cluster.cluster_idx,
                len(doa_valid),
                len(doa_invalid),
                sum(int(child.cluster_size) for child in doa_invalid) if recycle_failed_children else 0,
            )

        # 输出维度级二次识别汇总，仅统计 DOA 拆分后再次识别的子簇通过/未通过。
        LOGGER.info(
            "[%s] 二次识别完成：识别通过=%d，识别未通过=%d",
            parent_dim_name,
            doa_valid_total,
            doa_invalid_total,
        )

        return recycled_indices, parent_kept_as_valid, doa_valid_total, doa_invalid_total


class IdentifyResultBuilder:
    """维护识别流程单切片最终输出的索引和结果列表。

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
            >>> builder = IdentifyResultBuilder()
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
            >>> builder = IdentifyResultBuilder()
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
        extracted_params = extract_cluster_params(cluster.points, self.extract_params)
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
            >>> builder = IdentifyResultBuilder()
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
        extracted_params: Any = None,
    ) -> ClusterRecognition:
        """复制识别记录，并替换为最终簇索引与最终有效序号。"""
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


def format_conf_dict(conf_dict: dict[int, float]) -> str:
    """将各类别置信度字典格式化为稳定顺序的字符串。

    Args:
        conf_dict [dict[int, float]]: 类别标签到置信度的映射。

    Returns:
        str: 形如 ``"{0: 0.1234, 1: 0.5678}"`` 的字符串，按标签升序输出。

    Raises:
        无显式抛出异常。

    Example:
        >>> format_conf_dict({1: 0.7, 0: 0.3})
        '{0: 0.3000, 1: 0.7000}'
    """
    if not conf_dict:
        # 空字典时输出占位符，避免日志出现空花括号引发歧义。
        return "{}"
    # 按类别标签升序输出，保证多次运行日志顺序稳定。
    formatted = ", ".join(
        f"{label}: {conf_dict[label]:.4f}" for label in sorted(conf_dict)
    )
    return "{" + formatted + "}"


def merge_stage_input_indices(
    unprocessed_idx: np.ndarray,
    invalid_clusters: list[ClusterItem],
    recycled_indices: set[int],
) -> np.ndarray:
    """合并下一阶段需要继续处理的原始点索引。

    Args:
        unprocessed_idx [np.ndarray]: 上一阶段的未聚类点索引数组。
        invalid_clusters [list[ClusterItem]]: 上一阶段一次识别失败的簇列表。
        recycled_indices [set[int]]: 上一阶段 DOA 复检回收的点索引集合。

    Returns:
        np.ndarray: 排序后的候选点索引数组，供下一阶段聚类稳定使用。
    """
    # 合并三类输入：未聚类点、一次识别失败簇、DOA 复检失败子簇。
    merged = (
        set(int(index) for index in unprocessed_idx.tolist())
        | collect_cluster_indices(invalid_clusters)
        | recycled_indices
    )
    # 返回排序后的 numpy 索引数组，保证后续聚类输入稳定可复现。
    return np.array(sorted(merged), dtype=int)


def recognition_map(
    recognitions: list[ClusterRecognition],
) -> dict[int, ClusterRecognition]:
    """按簇索引构建识别记录映射。"""
    # 使用簇编号作为键，供各阶段快速回查原识别记录。
    return {rec.cluster_index: rec for rec in recognitions}


def collect_cluster_indices(clusters: list[ClusterItem]) -> set[int]:
    """收集簇内点在原始切片数据中的索引。"""
    indices: set[int] = set()
    for cluster in clusters:
        # 把簇内所有点索引拍平成集合，供下一阶段输入合并使用。
        indices.update(int(index) for index in cluster.points_indices)
    return indices


def collect_valid_indices(clusters: list[ClusterItem]) -> set[int]:
    """收集最终有效簇点在原始切片数据中的索引。"""
    indices: set[int] = set()
    for cluster in clusters:
        if cluster.state is ClusterState.VALID:
            # 仅统计最终有效簇覆盖的点，用于反推未处理点集合。
            indices.update(int(index) for index in cluster.points_indices)
    return indices


def build_slice_results(
    slice_index: int,
    points: np.ndarray,
    builder: IdentifyResultBuilder,
) -> tuple[SliceClusterResult, SliceRecognitionResult]:
    """根据结果收集器构建单切片最终输出。

    Args:
        slice_index [int]: 切片索引。
        points [np.ndarray]: 切片全量点集，用于抽取未处理点与回收点。
        builder [IdentifyResultBuilder]: 装配好最终簇的结果收集器。

    Returns:
        tuple[SliceClusterResult, SliceRecognitionResult]: 单切片最终聚类结果与识别结果。
    """
    # 收集最终有效簇覆盖的原始点索引，用于反推出真正未处理点。
    valid_indices = collect_valid_indices(builder.clusters)
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
