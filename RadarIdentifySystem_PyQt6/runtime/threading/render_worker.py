"""渲染工作线程。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from app.signal_bus import signal_bus
from infra.plotting import render_slice_images, render_cluster_images

if TYPE_CHECKING:
    from core.models.processing_session import ProcessingSession

LOGGER = logging.getLogger(__name__)


class RenderWorker(QThread):
    """单切片/单类别渲染后台工作线程。

    功能描述：
        在子线程中执行特定切片或聚类类别的渲染计算，防止阻塞主界面。
        完成后通过 signal_bus 发射对应的 ready 信号。
    """
    # session_id, success, error_msg
    finished_signal = pyqtSignal(str, bool, str)

    def __init__(
        self, 
        session: ProcessingSession, 
        slice_index: int, 
        cluster_index: int = 0, 
        is_cluster_render: bool = False,
        parent=None
    ) -> None:
        """初始化渲染线程。
        
        Args:
            session: 当前会话。
            slice_index: 切片索引。
            cluster_index: 聚类类别索引。当渲染切片时该参数无意义。
            is_cluster_render: 标志位。为 False 时渲染原始切片，为 True 时渲染聚类类别。
        """
        super().__init__(parent)
        self._session = session
        self._slice_index = slice_index
        self._cluster_index = cluster_index
        self._is_cluster_render = is_cluster_render

    def run(self) -> None:
        """执行后台渲染任务。"""
        session_id = self._session.session_id
        try:
            if self.isInterruptionRequested():
                return
                
            if not self._is_cluster_render:
                self._render_slice(session_id)
            else:
                self._render_cluster(session_id)

            if self.isInterruptionRequested():
                return

            self.finished_signal.emit(session_id, True, "")

        except Exception as e:
            LOGGER.error("渲染过程失败: %s", e, exc_info=True, extra={"session_id": session_id})
            self.finished_signal.emit(session_id, False, str(e))

    def _render_slice(self, session_id: str) -> None:
        """执行原始切片图像的渲染。

        Args:
            session_id (str): 会话ID，用于日志和事件发射。
            
        Raises:
            ValueError: 切片数据无效或索引越界时抛出。
        """
        with self._session.lock:
            slice_res = self._session.slice_result
            preprocess_res = self._session.preprocess_result
            
        if not slice_res or self._slice_index < 0 or self._slice_index >= slice_res.slice_count:
            err_msg = f"切片索引 {self._slice_index} 无效或越界"
            LOGGER.error(err_msg, extra={"session_id": session_id})
            raise ValueError(err_msg)

        target_slice = slice_res.slices[self._slice_index]

        image_bundle = render_slice_images(
            target_slice.data,
            band=preprocess_res.band,
            time_range=target_slice.time_range,
        )
        signal_bus.slice_image_ready.emit(session_id, self._slice_index, image_bundle)

    def _render_cluster(self, session_id: str) -> None:
        """执行聚类类别图像的渲染。

        Args:
            session_id (str): 会话ID，用于日志和事件发射。
            
        Raises:
            RuntimeError: 尚未完成聚类时抛出。
            ValueError: 聚类结果无效或类别索引越界时抛出。
        """
        with self._session.lock:
            is_clustered = self._session.is_clustered
            cluster_result = self._session.cluster_result
            band = self._session.band
            
        if not is_clustered:
            err_msg = "数据尚未完成聚类"
            LOGGER.error(err_msg, extra={"session_id": session_id})
            raise RuntimeError(err_msg)
            
        cluster_res = cluster_result.slice_results.get(self._slice_index)
        if not cluster_res or not cluster_res.clusters:
            err_msg = f"切片 {self._slice_index} 无有效聚类结果"
            LOGGER.error(err_msg, extra={"session_id": session_id})
            raise ValueError(err_msg)
            
        if self._cluster_index < 0 or self._cluster_index >= len(cluster_res.clusters):
            err_msg = f"聚类索引 {self._cluster_index} 无效或越界"
            LOGGER.error(err_msg, extra={"session_id": session_id})
            raise ValueError(err_msg)
            
        target_cluster = cluster_res.clusters[self._cluster_index]
        
        image_bundle = render_cluster_images(
            cluster_points=target_cluster.points,
            band=band,
            time_range=target_cluster.time_ranges
        )
        signal_bus.cluster_image_ready.emit(session_id, self._slice_index, self._cluster_index, image_bundle)
