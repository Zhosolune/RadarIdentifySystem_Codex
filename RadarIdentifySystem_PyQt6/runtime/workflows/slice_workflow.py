"""核心编排层。"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSlot

from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingSession
from runtime.threading.slice_worker import SliceWorker


LOGGER = logging.getLogger(__name__)


class SliceWorkflow(QObject):
    """切片工作流编排。

    负责统筹从“数据导入完成”到“切片完成”之间的流程调度，
    包括启动子线程、写入 Session 状态以及发布全局事件。
    严格遵守单一职责原则，只负责调度，不负责具体线程计算。

    Attributes:
        _worker (SliceWorker | None): 绑定的后台切片任务子线程实例。
    """

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化工作流实例。

        Args:
            parent (QObject | None, optional): Qt 挂载父节点。
        """
        super().__init__(parent)
        self._worker: Optional[SliceWorker] = None

    def is_running(self) -> bool:
        """返回工作流当前是否正在运行。"""
        return self._worker is not None and self._worker.isRunning()

    @pyqtSlot(ProcessingSession)
    def start_slice(self, session: ProcessingSession) -> None:
        """启动切片工作流。

        检查当前是否空闲，发射启动事件，并启动后台切片线程开始执行流程。

        Args:
            session (ProcessingSession): 当前待处理的会话实例。
            
        Returns:
            None
            
        Raises:
            无。如果已经在运行中则直接返回（忽略请求）。
        """
        if self._worker is not None and self._worker.isRunning():
            LOGGER.warning("切片工作流正在运行，忽略本次请求", extra={"session_id": session.session_id})
            return

        # 发送流程开始全局信号
        signal_bus.stage_started.emit(session.session_id, "slicing")
        
        # 挂载计算线程，并在线程结束时挂接回调
        self._worker = SliceWorker(session, parent=self)
        self._worker.finished_signal.connect(self._on_worker_finished)
        self._worker.start()

    @pyqtSlot(str, bool, str)
    def _on_worker_finished(self, session_id: str, success: bool, error_msg: str) -> None:
        """子线程完成回调。

        解析后台任务发送过来的处理结果并向全局发送相应的流程终态事件，
        并释放线程资源。

        Args:
            session_id (str): 执行会话的唯一ID。
            success (bool): 标志线程执行是否成功。
            error_msg (str): 如果执行失败附带的报错信息。
            
        Returns:
            None
        """
        # 发送处理结果相关的生命周期信号
        if success:
            signal_bus.stage_finished.emit(session_id, "slicing")
        else:
            signal_bus.stage_failed.emit(session_id, "slicing", error_msg)
        
        # 释放线程对象
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None


# 全局工作流实例（简化生命周期管理）
slice_workflow = SliceWorkflow()
