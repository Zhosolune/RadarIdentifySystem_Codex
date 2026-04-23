"""核心全局信号总线。"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from core.models.processing_session import ProcessingSession


class _SignalBus(QObject):
    """全局单例事件总线。

    用于隔离各个UI组件与业务核心的工作流之间的直接耦合。
    所有的生命周期事件及处理结果都在此发布和订阅。
    """

    # -------------------------------------------------------------------
    # 生命周期事件 (携带 session_id、stage_name、slice_index 等元信息)
    # -------------------------------------------------------------------
    session_created = pyqtSignal(str)          # session_id
    stage_started = pyqtSignal(str, str, object)      # session_id, stage_name, slice_index|None
    stage_finished = pyqtSignal(str, str, object)     # session_id, stage_name, slice_index|None
    stage_failed = pyqtSignal(str, str, object, str)  # session_id, stage_name, slice_index|None, error_msg

    # -------------------------------------------------------------------
    # 结果数据事件
    # -------------------------------------------------------------------
    # 当数据导入完成后发出，携带整个 session 的最新状态供 UI 刷新摘要
    import_completed = pyqtSignal(ProcessingSession)


signal_bus = _SignalBus()
