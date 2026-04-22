"""单切片渲染编排层。"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSlot

from app.signal_bus import signal_bus
from runtime.threading.render_worker import RenderWorker

if TYPE_CHECKING:
    from core.models.processing_session import ProcessingSession


LOGGER = logging.getLogger(__name__)


class RenderWorkflow(QObject):
    """单切片渲染工作流编排。

    负责按需启动渲染线程，处理切片图像生成任务。
    严格遵守单一职责原则，只负责调度，不负责具体线程计算。

    Attributes:
        _worker (RenderWorker | None): 绑定的后台渲染任务子线程实例。
    """

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化工作流实例。

        Args:
            parent (QObject | None, optional): Qt 挂载父节点。
        """
        super().__init__(parent)
        self._worker: Optional[RenderWorker] = None

    @pyqtSlot(object, int, int, bool)
    def start_render(
        self, 
        session: ProcessingSession, 
        slice_index: int, 
        cluster_index: int = 0, 
        is_cluster_render: bool = False
    ) -> None:
        """启动渲染工作流。

        如果正在运行，将停止上一次的渲染，立即开始新的渲染（保证高响应性）。

        Args:
            session (ProcessingSession): 当前待处理的会话实例。
            slice_index (int): 需要渲染的切片索引。
            cluster_index (int): 聚类类别索引。当渲染切片时该参数无意义。
            is_cluster_render (bool): 标志位，指示是渲染原始切片（False）还是聚类类别（True）。
            
        Returns:
            None
        """
        # 若已有渲染任务，先停止/丢弃它，防止 UI 卡滞在过期的任务上
        if self._worker is not None and self._worker.isRunning():
            try:
                self._worker.finished_signal.disconnect()
            except TypeError:
                pass
            self._worker.requestInterruption()
            self._worker.deleteLater()
            self._worker = None

        # 挂载计算线程，并在线程结束时挂接回调
        self._worker = RenderWorker(
            session=session, 
            slice_index=slice_index, 
            cluster_index=cluster_index, 
            is_cluster_render=is_cluster_render,
            parent=self
        )
        self._worker.finished_signal.connect(self._on_worker_finished)
        self._worker.start()

    @pyqtSlot(str, bool, str)
    def _on_worker_finished(self, session_id: str, success: bool, error_msg: str) -> None:
        """子线程完成回调。

        解析后台任务发送过来的处理结果并释放线程资源。

        Args:
            session_id (str): 执行会话的唯一ID。
            success (bool): 标志线程执行是否成功。
            error_msg (str): 如果执行失败附带的报错信息。
            
        Returns:
            None
        """
        # 释放线程对象
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None


# 全局工作流实例（简化生命周期管理）
render_workflow = RenderWorkflow()
