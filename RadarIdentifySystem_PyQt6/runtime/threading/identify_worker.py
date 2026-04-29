"""识别（聚类）工作线程。"""

from __future__ import annotations

import logging
import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.models.algorithm_params import ClusteringParams, RecognitionParams
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.cluster_result import ClusterItem, ClusteringResult, SliceClusterResult
from core.models.recognition_result import ClusterRecognition, RecognitionResult, SliceRecognitionResult
from core.clustering import process_dimension_clustering
from core.recognition import InferenceService, recognize_clusters
from runtime.algorithm_params import get_clustering_params, get_recognition_params


LOGGER = logging.getLogger(__name__)


class IdentifyWorker(QThread):
    """识别（聚类+识别）后台工作线程。

    在子线程中执行对所有切片的级联聚类与识别分析，防止阻塞主界面。
    """

    finished_signal = pyqtSignal(str, bool, str)
    progress_signal = pyqtSignal(str, int, int)

    def __init__(
        self,
        session: ProcessingSession,
        slice_index: int,
        inference_service: InferenceService,
        parent: QObject | None = None,
    ) -> None:
        """初始化识别（聚类）工作线程。

        Args:
            session: 当前流程所依附的会话上下文。
            slice_index: 需要进行识别聚类的切片索引。
            inference_service: 注入的防腐层推理服务。
            parent: 挂载的 Qt 父节点。
        """
        super().__init__(parent)
        self._session = session
        self._slice_index = slice_index
        self._inference_service = inference_service

    def run(self) -> None:
        """执行级联聚类逻辑。

        对指定的切片数据进行 CF/PW 维度的密度聚类。
        将结果存入 ClusteringResult 中并更新 session。
        """
        session_id = self._session.session_id
        try:
            if not self._session.is_sliced or self._session.slice_result is None:
                raise RuntimeError("数据尚未完成切片，无法进行聚类/识别")

            slices = self._session.slice_result.slices
            if self._slice_index < 0 or self._slice_index >= len(slices):
                raise ValueError(f"切片索引 {self._slice_index} 无效或越界")
                
            target_slice = slices[self._slice_index]
            
            LOGGER.info("开始聚类处理，当前切片: %d", self._slice_index, extra={"session_id": session_id})

            # 内部自行获取运行参数
            clustering_params = get_clustering_params()
            recognition_params = get_recognition_params()

            # 记录聚类参数快照，便于问题排查与回放分析。
            LOGGER.info(
                "参数: eps_cf=%.4f, eps_pw=%.4f, min_pts=%d, min_cluster_size=%d, tol=%.2f, min_conf=%.2f, slice_index=%d",
                clustering_params.eps_cf,
                clustering_params.eps_pw,
                clustering_params.min_pts,
                clustering_params.min_cluster_size,
                recognition_params.tolerance,
                recognition_params.min_confidence,
                self._slice_index,
                extra={"session_id": session_id},
            )
            
            # 如果 session 中还没有结果容器，则初始化
            with self._session.lock:
                if self._session.cluster_result is None:
                    self._session.cluster_result = ClusteringResult()
                if self._session.recognition_result is None:
                    self._session.recognition_result = RecognitionResult()
                # 标记当前切片状态
                self._session.mark_slice_cluster_running(self._slice_index)
                self._session.mark_slice_recognition_running(self._slice_index)

            self.progress_signal.emit(session_id, 0, 1)
            
            # 对当前切片执行级联聚类与识别
            slice_cluster_res, slice_recognition_res = self._cluster_and_recognize_slice(
                slice_data=target_slice,
                inference_service=self._inference_service,
                cluster_params=clustering_params,
                recognize_params=recognition_params,
            )
            
            with self._session.lock:
                # 写入当前切片聚类和识别结果
                self._session.cluster_result.slice_results[self._slice_index] = slice_cluster_res
                self._session.recognition_result.slice_results[self._slice_index] = slice_recognition_res
                
                # 更新当前切片状态
                self._session.mark_slice_cluster_succeeded(self._slice_index)
                self._session.mark_slice_recognition_succeeded(self._slice_index)

                # 仅在全量切片均完成后推进全局阶段
                if self._session.are_all_slices_clustered() and self._session.is_recognized:
                    self._session.stage = ProcessingStage.RECOGNIZED
                else:
                    self._session.stage = ProcessingStage.SLICED
            
            LOGGER.info("切片 %d 聚类与识别处理完成，产生 %d 个有效簇", 
                        self._slice_index, len(slice_recognition_res.valid_clusters), extra={"session_id": session_id})
            
            self.finished_signal.emit(session_id, True, "")

        except Exception as e:
            if self._slice_index >= 0:
                with self._session.lock:
                    # 记录当前切片失败状态
                    self._session.mark_slice_cluster_failed(self._slice_index, str(e))
                    self._session.mark_slice_recognition_failed(self._slice_index, str(e))
            LOGGER.error("聚类与识别过程失败: %s", e, exc_info=True, extra={"session_id": session_id})
            self.finished_signal.emit(session_id, False, str(e))

    def _cluster_and_recognize_slice(
        self,
        slice_data,
        inference_service: InferenceService,
        cluster_params: ClusteringParams | None = None,
        recognize_params: RecognitionParams | None = None,
    ) -> tuple[SliceClusterResult, SliceRecognitionResult]:
        """对单个切片执行级联聚类与识别编排。

        编排逻辑：
            1. CF 维度聚类 -> 产出 CF 簇。
            2. CF 簇识别 -> 成功簇保留；失败簇打散。
            3. CF 未聚类点 + CF 失败簇散点 -> PW 维度聚类 -> 产出 PW 簇。
            4. PW 簇识别 -> 成功簇保留；失败簇打散。
            5. 最终组装聚类结果和识别结果。

        Args:
            slice_data: 单个切片数据。
            inference_service: 推理服务实现。
            cluster_params: 聚类参数。
            recognize_params: 识别参数。

        Returns:
            包含聚类结果与识别结果的元组。

        Raises:
            无。
        """
        cluster_params = cluster_params or ClusteringParams()
        recognize_params = recognize_params or RecognitionParams()

        all_valid_clusters: list[ClusterItem] = []
        all_recognitions: list[ClusterRecognition] = []
        recycled_indices = set()

        points = slice_data.data
        if len(points) == 0:
            return (
                SliceClusterResult(slice_data.index, [], np.array([]), np.array([])),
                SliceRecognitionResult(slice_data.index, [], []),
            )

        current_cluster_id = 1
        current_valid_idx = 0

        # ── 1. CF 维度聚类 ──
        cf_clusters, cf_unprocessed_idx = process_dimension_clustering(
            points=points,
            dim_name="CF",
            dim_idx=0,
            epsilon=cluster_params.eps_cf,
            min_pts=cluster_params.min_pts,
            min_cluster_size=cluster_params.min_cluster_size,
            slice_idx=slice_data.index,
            time_range=slice_data.time_range,
            start_cluster_id=current_cluster_id,
        )
        current_cluster_id += len(cf_clusters)

        # ── 2. CF 维度识别 ──
        cf_valid, cf_invalid, cf_recs, current_valid_idx = recognize_clusters(
            cf_clusters, inference_service, recognize_params, current_valid_idx
        )
        all_valid_clusters.extend(cf_valid)
        all_recognitions.extend(cf_recs)

        # 收集 CF 识别失败的点，准备汇入 PW
        for c in cf_invalid:
            recycled_indices.update(c.points_indices)

        # ── 3. 准备 PW 维度的点云 ──
        # PW 聚类的输入点 = CF 未能聚类的点 + CF 识别失败被拆散的点
        pw_input_indices = list(set(cf_unprocessed_idx) | recycled_indices)

        if len(pw_input_indices) > 0:
            pw_input_indices = np.array(pw_input_indices)
            pw_points = points[pw_input_indices]

            # ── 4. PW 维度聚类 ──
            pw_clusters, pw_unprocessed_local_idx = process_dimension_clustering(
                points=pw_points,
                dim_name="PW",
                dim_idx=1,
                epsilon=cluster_params.eps_pw,
                min_pts=cluster_params.min_pts,
                min_cluster_size=cluster_params.min_cluster_size,
                slice_idx=slice_data.index,
                time_range=slice_data.time_range,
                start_cluster_id=current_cluster_id,
            )
            current_cluster_id += len(pw_clusters)

            # 映射回原始 points 的全局索引
            for cluster in pw_clusters:
                cluster.points_indices = pw_input_indices[cluster.points_indices]

            # ── 5. PW 维度识别 ──
            pw_valid, pw_invalid, pw_recs, current_valid_idx = recognize_clusters(
                pw_clusters, inference_service, recognize_params, current_valid_idx
            )
            all_valid_clusters.extend(pw_valid)
            all_recognitions.extend(pw_recs)

            for c in pw_invalid:
                recycled_indices.update(c.points_indices)

            # 计算最终无用点
            valid_indices = set()
            for c in all_valid_clusters:
                valid_indices.update(c.points_indices)

            final_unprocessed_idx = list(
                set(range(len(points))) - valid_indices - recycled_indices
            )
        else:
            final_unprocessed_idx = list(cf_unprocessed_idx)

        # 组装聚类结果
        cluster_result = SliceClusterResult(
            slice_idx=slice_data.index,
            clusters=all_valid_clusters
            + cf_invalid
            + (pw_invalid if "pw_invalid" in locals() else []),
            unprocessed_points=points[final_unprocessed_idx]
            if len(final_unprocessed_idx) > 0
            else np.array([]),
            recycled_points=points[list(recycled_indices)]
            if len(recycled_indices) > 0
            else np.array([]),
        )

        # 组装识别结果
        valid_recs = [r for r in all_recognitions if r.is_valid]
        invalid_recs = [r for r in all_recognitions if not r.is_valid]

        recognition_result = SliceRecognitionResult(
            slice_index=slice_data.index,
            valid_clusters=valid_recs,
            invalid_clusters=invalid_recs,
        )

        return cluster_result, recognition_result
