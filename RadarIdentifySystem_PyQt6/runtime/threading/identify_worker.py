"""识别（聚类）工作线程。"""

from __future__ import annotations

import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.models.algorithm_params import ClusteringParams, RecognitionParams
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.cluster_result import ClusteringResult
from core.models.recognition_result import RecognitionResult
from core.clustering import cluster_and_recognize_slice
from core.recognition import InferenceService


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
        clustering_params: ClusteringParams | None = None,
        recognition_params: RecognitionParams | None = None,
        parent: QObject | None = None,
    ) -> None:
        """初始化识别（聚类）工作线程。

        Args:
            session: 当前流程所依附的会话上下文。
            slice_index: 需要进行识别聚类的切片索引。
            inference_service: 注入的防腐层推理服务。
            clustering_params: 聚类参数对象。
            recognition_params: 识别参数对象。
            parent: 挂载的 Qt 父节点。
        """
        super().__init__(parent)
        self._session = session
        self._slice_index = slice_index
        self._inference_service = inference_service
        self._clustering_params = clustering_params or ClusteringParams()
        self._recognition_params = recognition_params or RecognitionParams()

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
            # 记录聚类参数快照，便于问题排查与回放分析。
            LOGGER.info(
                "参数: eps_cf=%.4f, eps_pw=%.4f, min_pts=%d, min_cluster_size=%d, tol=%.2f, min_conf=%.2f, slice_index=%d",
                self._clustering_params.eps_cf,
                self._clustering_params.eps_pw,
                self._clustering_params.min_pts,
                self._clustering_params.min_cluster_size,
                self._recognition_params.tolerance,
                self._recognition_params.min_confidence,
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
            slice_cluster_res, slice_recognition_res = cluster_and_recognize_slice(
                slice_data=target_slice,
                inference_service=self._inference_service,
                cluster_params=self._clustering_params,
                recognize_params=self._recognition_params,
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
