"""导入数据工作流编排。"""

from __future__ import annotations

import logging
from typing import Optional
import uuid

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from infra.parsers import supports_source_type
from runtime.threading.import_worker import (
    ImportExecutionRequest,
    ImportWorker,
    ImportWorkerResult,
)

LOGGER = logging.getLogger(__name__)


class ImportWorkflow(QObject):
    """通用脉冲文件导入工作流控制器。

    功能描述：
        负责启动数据导入后台线程，并对接全局信号总线通知 UI。
        这是单例对象，被绑定在 app 级别。

    属性说明：
        _worker (ImportWorker | None): 后台导入线程引用。
    """

    def __init__(self) -> None:
        """初始化工作流控制器。"""
        super().__init__()
        self._worker: Optional[ImportWorker] = None

    def is_running(self) -> bool:
        """返回导入线程是否仍处于完整生命周期内。"""
        return self._worker is not None

    def supports_source_type(self, source_type: str) -> bool:
        """判断来源类型是否已经配置解析器。

        Args:
            source_type [str]: 来源类型键。

        Returns:
            bool: 已支持返回 True，否则返回 False。
        """
        return supports_source_type(source_type)

    def start_import(
        self,
        file_path: str,
        source_type: str = "excel",
        data_format: str | None = None,
    ) -> str:
        """启动导入工作流。

        功能描述：
            构建 ImportWorker 线程对象并启动。
            触发 stage_started 信号。

        参数说明：
            file_path (str): 要导入的脉冲文件路径。
            source_type (str): 来源类型，如 ``excel`` 或 ``bin``。
            data_format (str | None): 来源内部解析规则。

        返回值说明：
            str: 本次导入任务 ID。

        异常说明：
            RuntimeError: 当已有任务在运行时抛出。
        """
        if self._worker is not None:
            raise RuntimeError("正在导入中，无法启动新任务")

        import_id = uuid.uuid4().hex
        LOGGER.info("启动导入工作流", extra={"session_id": import_id})
        signal_bus.stage_started.emit(import_id, "importing", None)

        self._worker = ImportWorker(
            ImportExecutionRequest(
                import_id=import_id,
                file_path=file_path,
                source_type=source_type,
                data_format=data_format,
            ),
            parent=self,
        )
        self._worker.finished_signal.connect(self._on_worker_finished)
        # 自定义结果信号在 run() 返回前发出，此时底层线程仍可能处于 finally
        # 清理阶段；只能等待 QThread 原生 finished 后再销毁 QObject。
        self._worker.finished.connect(self._on_worker_thread_finished)
        self._worker.start()
        return import_id

    def _on_worker_finished(
        self,
        import_id: str,
        result: ImportWorkerResult,
    ) -> None:
        """接收业务结果并分发事件，不在此处释放线程对象。"""
        LOGGER.info(
            "导入工作流完成: %s",
            result.message,
            extra={"session_id": import_id},
        )

        if result.success and result.packages:
            signal_bus.stage_finished.emit(import_id, "importing", None)
            signal_bus.data_packages_parsed.emit(import_id, result.packages)
        else:
            signal_bus.stage_failed.emit(
                import_id,
                "importing",
                None,
                result.message,
            )
            
    def _on_worker_thread_finished(self) -> None:
        """在 QThread 完全退出后释放 Worker 引用和 Qt 对象。"""
        worker = self._worker
        if worker is None:
            return
        worker.deleteLater()
        self._worker = None


# 单例工作流实例
import_workflow = ImportWorkflow()
