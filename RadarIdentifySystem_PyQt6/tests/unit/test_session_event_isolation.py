# -*- coding: utf-8 -*-
"""session 事件隔离测试。

验证解析完成、确认导入和 session 生命周期信号之间保持独立，避免解析结果渲染
和后续 session 注册流程混用同一个事件入口。

Example:
    >>> from core.models.processing_session import ProcessingSession
    >>> isinstance(ProcessingSession(), ProcessingSession)
    True
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QObject

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingSession
from runtime.workflows.import_workflow import ImportWorkflow


class _SessionEventReceiver(QObject):
    """记录测试期间收到的 session 事件。"""

    def __init__(self) -> None:
        """初始化事件记录容器。"""
        super().__init__()
        self.parsed_sessions: list[ProcessingSession] = []
        self.imported_sessions: list[ProcessingSession] = []
        self.session_ids: list[str] = []

    def receive_parse(self, session: ProcessingSession) -> None:
        """记录解析完成事件。"""
        self.parsed_sessions.append(session)

    def receive_import(self, session: ProcessingSession) -> None:
        """记录确认导入事件。"""
        self.imported_sessions.append(session)

    def receive_session_id(self, session_id: str) -> None:
        """记录 session 生命周期事件 ID。"""
        self.session_ids.append(session_id)


class _FakeImportWorker:
    """模拟导入工作流完成时持有的 worker。"""

    def __init__(self, session: ProcessingSession) -> None:
        """初始化假 worker。"""
        self.session = session
        self.delete_later_called = False

    def deleteLater(self) -> None:
        """记录释放请求。"""
        self.delete_later_called = True


def test_parse_completed_does_not_emit_import_completed() -> None:
    """解析完成信号不会触发确认导入接收器。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无显式抛出异常。

    Example:
        >>> callable(test_parse_completed_does_not_emit_import_completed)
        True
    """
    receiver = _SessionEventReceiver()
    session = ProcessingSession(source_path="demo.xlsx", source_type="excel")
    parse_connected = False
    import_connected = False

    try:
        signal_bus.parse_completed.connect(receiver.receive_parse)
        parse_connected = True
        signal_bus.import_completed.connect(receiver.receive_import)
        import_connected = True

        # 只发解析完成事件，确认导入接收器应保持空列表。
        signal_bus.parse_completed.emit(session)

        assert receiver.parsed_sessions == [session]
        assert receiver.imported_sessions == []
    finally:
        if parse_connected:
            signal_bus.parse_completed.disconnect(receiver.receive_parse)
        if import_connected:
            signal_bus.import_completed.disconnect(receiver.receive_import)


def test_import_completed_still_emits_import_receiver() -> None:
    """确认导入信号仍可独立通知导入接收器。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无显式抛出异常。

    Example:
        >>> callable(test_import_completed_still_emits_import_receiver)
        True
    """
    receiver = _SessionEventReceiver()
    session = ProcessingSession(source_path="demo.xlsx", source_type="excel")

    try:
        signal_bus.import_completed.connect(receiver.receive_import)

        # 用户确认导入时，旧信号仍作为下游流程入口保留。
        signal_bus.import_completed.emit(session)

        assert receiver.imported_sessions == [session]
        assert receiver.parsed_sessions == []
    finally:
        signal_bus.import_completed.disconnect(receiver.receive_import)


def test_import_workflow_finished_emits_only_parse_completed() -> None:
    """导入工作流成功完成时只发解析完成事件。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无显式抛出异常。

    Example:
        >>> callable(test_import_workflow_finished_emits_only_parse_completed)
        True
    """
    receiver = _SessionEventReceiver()
    session = ProcessingSession(source_path="demo.xlsx", source_type="excel")
    fake_worker = _FakeImportWorker(session)
    workflow = ImportWorkflow()
    parse_connected = False
    import_connected = False

    try:
        signal_bus.parse_completed.connect(receiver.receive_parse)
        parse_connected = True
        signal_bus.import_completed.connect(receiver.receive_import)
        import_connected = True
        workflow._worker = cast(Any, fake_worker)

        # 直接驱动工作流完成回调，锁定成功路径的事件分发语义。
        workflow._on_worker_finished(session.session_id, True, "ok")

        assert [item.session_id for item in receiver.parsed_sessions] == [
            session.session_id
        ]
        assert receiver.imported_sessions == []
        assert fake_worker.delete_later_called is True
        assert workflow._worker is None
    finally:
        if parse_connected:
            signal_bus.parse_completed.disconnect(receiver.receive_parse)
        if import_connected:
            signal_bus.import_completed.disconnect(receiver.receive_import)


def test_session_lifecycle_signals_emit_session_id() -> None:
    """session 生命周期占位信号按 session_id 传递。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无显式抛出异常。

    Example:
        >>> callable(test_session_lifecycle_signals_emit_session_id)
        True
    """
    receiver = _SessionEventReceiver()
    connected_signals = []

    try:
        for signal in (
            signal_bus.session_registered,
            signal_bus.session_activated,
            signal_bus.session_closed,
            signal_bus.session_metadata_changed,
        ):
            signal.connect(receiver.receive_session_id)
            connected_signals.append(signal)

        # 四个生命周期占位信号都应透传字符串 session_id。
        signal_bus.session_registered.emit("registered-session")
        signal_bus.session_activated.emit("active-session")
        signal_bus.session_closed.emit("closed-session")
        signal_bus.session_metadata_changed.emit("metadata-session")

        assert receiver.session_ids == [
            "registered-session",
            "active-session",
            "closed-session",
            "metadata-session",
        ]
    finally:
        for signal in connected_signals:
            signal.disconnect(receiver.receive_session_id)
