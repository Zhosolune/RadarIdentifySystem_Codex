"""导入数据工作流编排。"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingSession, ProcessingStage
from runtime.threading.import_worker import ImportWorker

LOGGER = logging.getLogger(__name__)


class ImportWorkflow(QObject):
    """Excel 导入工作流控制器。

    功能描述：
        负责启动 Excel 数据导入后台线程，并对接全局信号总线通知 UI。
        这是单例对象，被绑定在 app 级别。

    属性说明：
        _worker (ImportWorker | None): 后台导入线程引用。
    """

    def __init__(self) -> None:
        """初始化工作流控制器。"""
        super().__init__()
        self._worker: Optional[ImportWorker] = None

    def is_running(self) -> bool:
        """返回工作流当前是否正在运行。"""
        return self._worker is not None and self._worker.isRunning()

    def start_import(self, session: ProcessingSession, file_path: str) -> None:
        """启动导入工作流。

        功能描述：
            构建 ImportWorker 线程对象并启动。
            触发 stage_started 信号。

        参数说明：
            session (ProcessingSession): 处理会话实例。
            file_path (str): 要导入的 Excel 文件路径。

        返回值说明：
            None: 无返回值。

        异常说明：
            RuntimeError: 当已有任务在运行时抛出。
        """
        if self._worker is not None and self._worker.isRunning():
            raise RuntimeError("正在导入中，无法启动新任务")

        LOGGER.info("启动导入工作流", extra={"session_id": session.session_id})
        signal_bus.stage_started.emit(session.session_id, "importing", None)

        self._worker = ImportWorker(session, file_path, parent=self)
        self._worker.finished_signal.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self, session_id: str, success: bool, message: str) -> None:
        """接收线程完成信号并分发全局事件。

        功能描述：
            工作线程完成后，释放引用并发出 stage_finished 信号，同时记录日志。

        参数说明：
            session_id (str): 会话 ID。
            success (bool): 是否成功。
            message (str): 结果信息。
        """
        LOGGER.info("导入工作流完成: %s", message, extra={"session_id": session_id})

        if success:
            signal_bus.stage_finished.emit(session_id, "importing", None)
        else:
            signal_bus.stage_failed.emit(session_id, "importing", None, message)
            
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None


# 单例工作流实例
import_workflow = ImportWorkflow()
