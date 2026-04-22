"""渲染工作线程。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from app.signal_bus import signal_bus
from infra.plotting import render_slice_images

if TYPE_CHECKING:
    from core.models.processing_session import ProcessingSession

LOGGER = logging.getLogger(__name__)


class RenderWorker(QThread):
    """单切片渲染后台工作线程。

    功能描述：
        在子线程中执行特定切片的渲染计算，防止阻塞主界面。
        完成后通过 signal_bus 发射 slice_image_ready 信号。
    """
    # session_id, success, error_msg
    finished_signal = pyqtSignal(str, bool, str)

    def __init__(self, session: ProcessingSession, slice_index: int, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self._slice_index = slice_index

    def run(self) -> None:
        """执行后台渲染任务。"""
        session_id = self._session.session_id
        try:
            slice_res = self._session.slice_result
            if not slice_res or self._slice_index < 0 or self._slice_index >= slice_res.slice_count:
                raise ValueError(f"切片索引 {self._slice_index} 无效或越界")

            target_slice = slice_res.slices[self._slice_index]
            preprocess_res = self._session.preprocess_result

            # 渲染切片图像
            image_bundle = render_slice_images(
                target_slice.data,
                band=preprocess_res.band,
                time_range=target_slice.time_range,
            )
            
            # 发射就绪信号，携带渲染结果
            signal_bus.slice_image_ready.emit(session_id, self._slice_index, image_bundle)
            self.finished_signal.emit(session_id, True, "")

        except Exception as e:
            LOGGER.error("渲染过程失败: %s", e, exc_info=True, extra={"session_id": session_id})
            self.finished_signal.emit(session_id, False, str(e))
