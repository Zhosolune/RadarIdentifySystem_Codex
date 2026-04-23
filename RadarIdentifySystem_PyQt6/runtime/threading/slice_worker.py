"""切片工作线程。"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.models.processing_session import ProcessingSession, ProcessingStage
from core.slicing import slice_by_toa


LOGGER = logging.getLogger(__name__)


class SliceWorker(QThread):
    """切片后台工作线程。

    在子线程中执行预处理、切片与渲染计算，防止阻塞主界面。
    使用单一职责原则，专门负责切片相关的繁重计算任务。

    Attributes:
        finished_signal (pyqtSignal): 任务完成或失败时发出的信号，签名 `(session_id, success, error_msg)`。
    """

    # 信号：(session_id, success, error_msg)
    finished_signal = pyqtSignal(str, bool, str)

    def __init__(
        self,
        session: ProcessingSession,
        slice_length_ms: float = 250.0,
        parent: QObject | None = None,
    ) -> None:
        """初始化切片工作线程。

        保存当前正在处理的 session 实例与切片容差时长参数。

        Args:
            session (ProcessingSession): 当前流程所依附的会话上下文。
            slice_length_ms (float, optional): 数据切分默认时长(ms)，默认为 250.0。
            parent (QObject | None, optional): 挂载的 Qt 父节点。
        """
        super().__init__(parent)
        self._session = session
        self._slice_length_ms = slice_length_ms

    def run(self) -> None:
        """执行切片逻辑。

        依序调用数据预处理、时间轴切片计算和首图渲染的流程，
        并将过程中的状态变更写入 session 对象中，最后抛出结果信号。

        Args:
            无。

        Returns:
            None

        Raises:
            无。捕获内部所有异常后通过 finished_signal 抛出错误消息。
        """
        session_id = self._session.session_id
        try:
            # 1. 检查数据与预处理结果
            if not self._session.is_imported or self._session.raw_batch is None:
                LOGGER.error("数据尚未导入，无法切片", extra={"session_id": session_id})
                raise RuntimeError("数据尚未导入，无法切片")
                
            if self._session.preprocess_result is None:
                LOGGER.error("数据预处理结果缺失，无法切片", extra={"session_id": session_id})
                raise ValueError("数据预处理结果缺失，无法切片")

            preprocess_res = self._session.preprocess_result

            # 2. 切片
            LOGGER.info("开始切片", extra={"session_id": session_id})
            slice_res = slice_by_toa(
                preprocess_res.data,
                slice_length_ms=self._slice_length_ms,
                session_id=session_id,
            )
            with self._session.lock:
                # 写入切片结果
                self._session.slice_result = slice_res
                # 重置切片级局部状态
                self._session.reset_slice_processing_states(slice_res.slice_count)
                # 推进全局阶段
                self._session.stage = ProcessingStage.SLICED

            self.finished_signal.emit(session_id, True, "")

        except Exception as e:
            LOGGER.error("切片过程失败: %s", e, exc_info=True, extra={"session_id": session_id})
            self.finished_signal.emit(session_id, False, str(e))
