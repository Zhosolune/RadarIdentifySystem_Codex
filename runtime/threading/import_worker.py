"""导入数据后台线程。"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import uuid

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.logger import bind_session_log_context, unbind_session_log_context
from core.models.data_package import DataPackage
from core.preprocess import preprocess
from infra.parsers import ExcelDataFormat, ExcelPulseParser

LOGGER = logging.getLogger(__name__)


class ImportWorker(QThread):
    """Excel 数据解析与预处理后台线程。

    线程完成后生成 ``DataPackage``，不再创建或修改临时 Session。

    Attributes:
        finished_signal: 导入终态信号，携带数据包 ID 和
            :class:`ImportWorkerResult`。
    """

    finished_signal = pyqtSignal(str, object)

    def __init__(
        self,
        file_path: str,
        data_format: ExcelDataFormat = "old",
        package_id: str | None = None,
        parent: QObject | None = None
    ) -> None:
        """初始化导入工作线程。

        Args:
            file_path [str]: 文件路径。
            data_format [ExcelDataFormat]: Excel 原始列格式，默认使用旧格式。
            package_id [str | None]: 预分配的数据包 ID。
            parent [QObject | None]: 挂载的 Qt 父节点。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self._file_path = file_path
        self._data_format = data_format
        self._package_id = package_id or uuid.uuid4().hex

    def run(self) -> None:
        """执行导入与预处理任务。

        功能描述：
            调用 ExcelPulseParser 读取并归一化 Excel 数据。
            调用 preprocess() 获取清洗后的 PreprocessResult。
            将结果封装为数据池数据包，并发送完成信号。

        Returns:
            None: 结果通过 ``finished_signal`` 发出。

        Raises:
            无。内部异常统一转换为失败结果。
        """
        # 绑定会话日志上下文，使本线程内下层模块日志自动带上 session_id
        log_token = bind_session_log_context(self._package_id)
        try:
            LOGGER.debug("开始导入并预处理数据", extra={"session_id": self._package_id})
            batch = ExcelPulseParser().parse(
                self._file_path,
                data_format=self._data_format,
            )

            # 调用 core 中的预处理纯函数
            preprocess_res = preprocess(
                data=batch.data,
                source_path=self._file_path,
                source_type="excel",
                slice_length=2_500_000,  # 250ms = 2,500,000 × 0.1us
                session_id=self._package_id
            )

            package = DataPackage(
                package_id=self._package_id,
                raw_batch=batch,
                preprocess_result=preprocess_res,
                dashboard_info=preprocess_res.dashboard_info,
                data_format=self._data_format,
            )

            LOGGER.debug("数据导入与预处理完成", extra={"session_id": self._package_id})
            self.finished_signal.emit(
                self._package_id,
                ImportWorkerResult(
                    success=True,
                    package=package,
                    message=f"导入成功，共 {preprocess_res.total_pulses} 条脉冲",
                ),
            )

        except Exception as e:
            LOGGER.error("数据导入失败: %s", str(e), extra={"session_id": self._package_id})
            self.finished_signal.emit(
                self._package_id,
                ImportWorkerResult(
                    success=False,
                    message=f"导入失败: {str(e)}",
                ),
            )
        finally:
            # 复位会话日志上下文，防止线程复用导致 session_id 泄漏
            unbind_session_log_context(log_token)


@dataclass(frozen=True, slots=True)
class ImportWorkerResult:
    """导入线程结果。

    Attributes:
        success: 是否成功完成解析和预处理。
        package: 成功时生成的只读数据包。
        message: 成功摘要或失败原因。
    """

    success: bool
    package: DataPackage | None = None
    message: str = ""
