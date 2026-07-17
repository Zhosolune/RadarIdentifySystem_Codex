"""导入数据后台线程。"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.logger import bind_session_log_context, unbind_session_log_context
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.preprocess import preprocess
from infra.parsers import ExcelDataFormat, ExcelPulseParser

LOGGER = logging.getLogger(__name__)


class ImportWorker(QThread):
    """Excel数据导入与预处理后台线程。

    功能描述：
        在子线程中调用 infra 解析器读取 Excel 文件，随后调用
        core/preprocess.py 中的纯函数进行数据清洗与修正，并将结果装配到
        指定的 Session 对象中。

    参数说明：
        session (ProcessingSession): 需要写入数据的会话对象。
        file_path (str): Excel 文件路径。
        data_format (ExcelDataFormat): Excel 原始列格式。
        parent (QObject | None): 挂载的 Qt 父节点。

    属性说明：
        finished_signal (pyqtSignal): 导入完成信号，携带 session_id、成功标志和消息。
    """

    finished_signal = pyqtSignal(str, bool, str)

    def __init__(
        self,
        session: ProcessingSession,
        file_path: str,
        data_format: ExcelDataFormat = "old",
        parent: QObject | None = None
    ) -> None:
        """初始化导入工作线程。

        参数说明：
            session (ProcessingSession): 会话实例。
            file_path (str): 文件路径。
            data_format (ExcelDataFormat): Excel 原始列格式，默认使用旧格式。
            parent (QObject | None): 挂载的 Qt 父节点。
        """
        super().__init__(parent)
        self._session = session
        self._file_path = file_path
        self._data_format = data_format

    @property
    def session(self) -> ProcessingSession:
        """返回当前线程写入的处理会话。

        Args:
            无。

        Returns:
            当前导入线程持有的处理会话对象。

        Raises:
            无显式抛出异常。

        Example:
            >>> from core.models.processing_session import ProcessingSession
            >>> worker = ImportWorker(ProcessingSession(), "demo.xlsx")
            >>> worker.session is not None
            True
        """
        return self._session

    def run(self) -> None:
        """执行导入与预处理任务。

        功能描述：
            调用 ExcelPulseParser 读取并归一化 Excel 数据。
            调用 preprocess() 获取清洗后的 PreprocessResult。
            将结果赋给 Session，并发送完成信号。
        """
        # 绑定会话日志上下文，使本线程内下层模块日志自动带上 session_id
        log_token = bind_session_log_context(self._session.session_id)
        try:
            LOGGER.info("开始导入并预处理数据", extra={"session_id": self._session.session_id})
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
                session_id=self._session.session_id
            )

            # 将预处理结果写入 Session
            with self._session.lock:
                self._session.raw_batch = batch
                self._session.preprocess_result = preprocess_res
                self._session.dashboard_info = preprocess_res.dashboard_info
                # 推进全局阶段
                self._session.stage = ProcessingStage.PREPROCESSED

            LOGGER.info("数据导入与预处理完成", extra={"session_id": self._session.session_id})
            self.finished_signal.emit(self._session.session_id, True, f"导入成功，共 {preprocess_res.total_pulses} 条脉冲")

        except Exception as e:
            LOGGER.error("数据导入失败: %s", str(e), extra={"session_id": self._session.session_id})
            self.finished_signal.emit(self._session.session_id, False, f"导入失败: {str(e)}")
        finally:
            # 复位会话日志上下文，防止线程复用导致 session_id 泄漏
            unbind_session_log_context(log_token)
