"""核心全局信号总线。"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from core.models.data_package import DataPackage


class _SignalBus(QObject):
    """全局单例事件总线。

    用于隔离各个UI组件与业务核心的工作流之间的直接耦合。
    所有的生命周期事件及处理结果都在此发布和订阅。
    """

    # -------------------------------------------------------------------
    # 生命周期事件 (携带 session_id、stage_name、slice_index 等元信息)
    # -------------------------------------------------------------------
    session_created = pyqtSignal(str)          # session_id
    session_registered = pyqtSignal(str)       # session_id，确认注册到会话系统
    session_activated = pyqtSignal(str)        # session_id，切换为当前活动会话
    session_closed = pyqtSignal(str)           # session_id，关闭会话
    session_metadata_changed = pyqtSignal(str) # session_id，会话元数据变更
    stage_started = pyqtSignal(str, str, object)      # session_id, stage_name, slice_index|None
    stage_finished = pyqtSignal(str, str, object)     # session_id, stage_name, slice_index|None
    stage_failed = pyqtSignal(str, str, object, str)  # session_id, stage_name, slice_index|None, error_msg

    # -------------------------------------------------------------------
    # 结果数据事件
    # -------------------------------------------------------------------
    # 解析完成后携带只读数据包，由主页注册到数据池。
    data_package_parsed = pyqtSignal(DataPackage)
    # 全速任务配置、进度或终态变化后发出，主页据此刷新对应卡片。
    full_speed_session_changed = pyqtSignal(str)


signal_bus = _SignalBus()
