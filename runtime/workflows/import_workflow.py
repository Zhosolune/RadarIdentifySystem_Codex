"""导入数据工作流编排。"""

from __future__ import annotations

import logging
from typing import Optional
import uuid

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from infra.parsers import ExcelDataFormat
from runtime.threading.import_worker import ImportWorker, ImportWorkerResult

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

    def start_import(
        self,
        file_path: str,
        data_format: ExcelDataFormat = "old",
    ) -> str:
        """启动导入工作流。

        功能描述：
            构建 ImportWorker 线程对象并启动。
            触发 stage_started 信号。

        参数说明：
            file_path (str): 要导入的 Excel 文件路径。
            data_format (ExcelDataFormat): Excel 原始列格式，默认使用旧格式。

        返回值说明：
            str: 本次解析预分配的数据包 ID。

        异常说明：
            RuntimeError: 当已有任务在运行时抛出。
        """
        if self._worker is not None and self._worker.isRunning():
            raise RuntimeError("正在导入中，无法启动新任务")

        package_id = uuid.uuid4().hex
        LOGGER.info("启动导入工作流", extra={"session_id": package_id})
        signal_bus.stage_started.emit(package_id, "importing", None)

        self._worker = ImportWorker(
            file_path,
            data_format=data_format,
            package_id=package_id,
            parent=self,
        )
        self._worker.finished_signal.connect(self._on_worker_finished)
        self._worker.start()
        return package_id

    def _on_worker_finished(
        self,
        package_id: str,
        result: ImportWorkerResult,
    ) -> None:
        """接收线程完成信号并分发全局事件。

        功能描述：
            工作线程完成后，释放引用并发出 stage_finished 信号，同时记录日志。

        参数说明：
            package_id (str): 数据包 ID。
            result (ImportWorkerResult): 线程执行结果。
        """
        LOGGER.info(
            "导入工作流完成: %s",
            result.message,
            extra={"session_id": package_id},
        )

        if result.success and result.package is not None:
            signal_bus.stage_finished.emit(package_id, "importing", None)
            signal_bus.data_package_parsed.emit(result.package)
        else:
            signal_bus.stage_failed.emit(
                package_id,
                "importing",
                None,
                result.message,
            )
            
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None


# 单例工作流实例
import_workflow = ImportWorkflow()
