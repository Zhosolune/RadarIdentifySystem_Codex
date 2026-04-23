"""识别（聚类）工作线程。"""

from __future__ import annotations

import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.cluster_result import ClusteringResult
from core.clustering import cluster_single_slice


LOGGER = logging.getLogger(__name__)


class IdentifyWorker(QThread):
    """识别（目前仅聚类）后台工作线程。

    在子线程中执行对所有切片的级联聚类分析，防止阻塞主界面。
    目前只完成 CF 和 PW 维度的聚类，不包含深度学习模型推理。

    Attributes:
        finished_signal (pyqtSignal): 任务完成或失败时发出的信号，签名 `(session_id, success, error_msg)`。
        progress_signal (pyqtSignal): 进度更新信号，签名 `(session_id, current, total)`。
    """

    finished_signal = pyqtSignal(str, bool, str)
    progress_signal = pyqtSignal(str, int, int)

    def __init__(
        self,
        session: ProcessingSession,
        slice_index: int,
        eps_cf: float = 2.0,
        eps_pw: float = 0.2,
        min_pts: int = 1,
        min_cluster_size: int = 8,
        parent: QObject | None = None,
    ) -> None:
        """初始化识别（聚类）工作线程。

        Args:
            session (ProcessingSession): 当前流程所依附的会话上下文。
            slice_index (int): 需要进行识别聚类的切片索引。
            eps_cf (float): CF维度的 DBSCAN 邻域半径。
            eps_pw (float): PW维度的 DBSCAN 邻域半径。
            min_pts (int): DBSCAN 核心点最小样本数。
            min_cluster_size (int): 簇的最小有效点数。
            parent (QObject | None): 挂载的 Qt 父节点。
        """
        super().__init__(parent)
        self._session = session
        self._slice_index = slice_index
        self._eps_cf = eps_cf
        self._eps_pw = eps_pw
        self._min_pts = min_pts
        self._min_cluster_size = min_cluster_size

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
            
            # 如果 session 中还没有 cluster_result，则初始化一个
            with self._session.lock:
                if self._session.cluster_result is None:
                    self._session.cluster_result = ClusteringResult()
                # 标记当前切片状态
                self._session.mark_slice_cluster_running(self._slice_index)

            self.progress_signal.emit(session_id, 0, 1)
            
            # 对当前切片执行聚类
            slice_cluster_res = cluster_single_slice(
                slice_data=target_slice,
                eps_cf=self._eps_cf,
                eps_pw=self._eps_pw,
                min_pts=self._min_pts,
                min_cluster_size=self._min_cluster_size
            )
            
            with self._session.lock:
                # 写入当前切片聚类结果
                self._session.cluster_result.slice_results[self._slice_index] = slice_cluster_res
                # 更新当前切片聚类状态
                self._session.mark_slice_cluster_succeeded(self._slice_index)

                # 仅在全量切片均完成后推进全局阶段
                if self._session.are_all_slices_clustered():
                    self._session.stage = ProcessingStage.CLUSTERED
                else:
                    self._session.stage = ProcessingStage.SLICED
            
            LOGGER.info("切片 %d 聚类处理完成，产生 %d 个有效簇", 
                        self._slice_index, len(slice_cluster_res.clusters), extra={"session_id": session_id})
            
            self.finished_signal.emit(session_id, True, "")

        except Exception as e:
            if self._slice_index >= 0:
                with self._session.lock:
                    # 记录当前切片失败状态
                    self._session.mark_slice_cluster_failed(self._slice_index, str(e))
            LOGGER.error("聚类过程失败: %s", e, exc_info=True, extra={"session_id": session_id})
            self.finished_signal.emit(session_id, False, str(e))
