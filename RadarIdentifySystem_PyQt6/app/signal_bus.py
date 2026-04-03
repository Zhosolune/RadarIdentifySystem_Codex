"""核心全局信号总线。"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from core.models.processing_session import ProcessingSession
from infra.plotting.types import RenderedImageBundle


class _SignalBus(QObject):
    """全局单例事件总线。

    用于隔离各个UI组件与业务核心的工作流之间的直接耦合。
    所有的生命周期事件及处理结果都在此发布和订阅。
    """

    # -------------------------------------------------------------------
    # 生命周期事件 (携带 session_id 等元信息)
    # -------------------------------------------------------------------
    session_created = pyqtSignal(str)          # session_id
    stage_started = pyqtSignal(str, str)         # session_id, stage_name
    stage_finished = pyqtSignal(str, str)        # session_id, stage_name
    stage_failed = pyqtSignal(str, str, str)     # session_id, stage_name, error_msg

    # -------------------------------------------------------------------
    # 结果数据事件
    # -------------------------------------------------------------------
    # 当数据导入完成后发出，携带整个 session 的最新状态供 UI 刷新摘要
    import_completed = pyqtSignal(ProcessingSession)

    # 当一个切片的 5 维原始图像渲染完成后发出
    # 参数：session_id, slice_index, image_bundle
    slice_image_ready = pyqtSignal(str, int, RenderedImageBundle)


signal_bus = _SignalBus()
