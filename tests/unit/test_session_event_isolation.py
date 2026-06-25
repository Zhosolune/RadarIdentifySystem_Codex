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
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.signal_bus import signal_bus
from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from runtime.workflows.import_workflow import ImportWorkflow
from ui.controllers.home_controller import HomeController


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


class _SignalStub:
    """提供测试用 connect 接口的轻量信号替身。"""

    def __init__(self) -> None:
        """初始化回调列表。"""
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """记录连接的回调。"""
        self.callbacks.append(callback)


class _ActionStub:
    """提供 triggered 信号的测试动作替身。"""

    def __init__(self) -> None:
        """初始化 triggered 信号。"""
        self.triggered = _SignalStub()


class _ButtonStub:
    """提供 clicked 信号与状态记录的测试按钮替身。"""

    def __init__(self) -> None:
        """初始化按钮状态。"""
        self.clicked = _SignalStub()
        self.enabled: bool = True
        self.text: str = ""

    def setEnabled(self, enabled: bool) -> None:
        """记录按钮可用状态。"""
        self.enabled = enabled

    def setText(self, text: str) -> None:
        """记录按钮文本。"""
        self.text = text


class _ImportPanelStub:
    """提供 HomeController 所需导入列表接口的测试替身。"""

    def __init__(self) -> None:
        """初始化动作与按钮替身。"""
        self.refresh_action = _ActionStub()
        self.remove_action = _ActionStub()
        self.nameAction = _ActionStub()
        self.sizeAction = _ActionStub()
        self.dateAction = _ActionStub()
        self.ascendAction = _ActionStub()
        self.descendAction = _ActionStub()
        self.parseButton = _ButtonStub()
        self.files_by_type: object | None = None

    def set_files_by_type(self, files_by_type: object) -> None:
        """记录渲染到列表的数据。"""
        self.files_by_type = files_by_type


class _DashboardPanelStub:
    """提供 HomeController 所需仪表盘接口的测试替身。"""

    def __init__(self) -> None:
        """初始化仪表盘记录。"""
        self.importSessionRequested = _SignalStub()
        self.pages: list[object] = []
        self.clear_count = 0

    def clear_dashboard_pages(self) -> None:
        """记录清空仪表盘次数。"""
        self.clear_count += 1
        self.pages = []

    def set_dashboard_pages(self, pages: list[object]) -> None:
        """记录渲染的仪表盘页。"""
        self.pages = pages


class _HomeViewStub(QObject):
    """提供 HomeController 初始化所需的最小主页视图。"""

    def __init__(self) -> None:
        """初始化主页子组件替身。"""
        super().__init__()
        self.import_panel = _ImportPanelStub()
        self.dashboard_panel = _DashboardPanelStub()


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


def test_home_controller_parse_completed_renders_dashboard() -> None:
    """HomeController 应通过 parse_completed 渲染主页仪表盘。"""
    view = _HomeViewStub()
    controller = HomeController(view)
    session = ProcessingSession(session_id="dashboard_session", source_type="excel")
    session.dashboard_info = ExcelDashboardInfo(
        total_pulses=120,
        removed_pulses=5,
        amplitude_dropped_pulses=3,
        duration=10_000,
        band="C波段",
        estimated_slice_count=7,
    )
    controller._active_parse_session_id = session.session_id

    try:
        signal_bus.parse_completed.emit(session)

        assert controller._last_import_session is session
        assert controller._active_parse_session_id is None
        assert view.import_panel.parseButton.enabled is True
        assert view.import_panel.parseButton.text == "解析"
        assert len(view.dashboard_panel.pages) == 1
        page = view.dashboard_panel.pages[0]
        assert page.route_key == "excel_info"
        assert page.title == "C波段"
        assert [(metric.label, metric.value) for metric in page.metrics] == [
            ("总脉冲", "120"),
            ("剔除脉冲", "5"),
            ("幅度丢弃", "3"),
            ("持续时间", "1.00 ms"),
            ("波段", "C波段"),
            ("预计切片数", "7"),
        ]
    finally:
        signal_bus.parse_completed.disconnect(controller.render_import_dashboard)
        signal_bus.stage_failed.disconnect(controller._on_parse_stage_failed)


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


def test_home_import_action_delegates_to_window_session_creation(
    monkeypatch: MonkeyPatch,
) -> None:
    """主页导入按钮应委托窗口创建 session 页面。"""

    class _FakeCreateSessionDialog:
        """测试用创建 Session 对话框桩对象。"""

        def __init__(self, default_display_name: str, parent=None) -> None:
            """记录默认名称和父组件。"""
            self.default_display_name = default_display_name
            self.parent = parent

        def exec(self) -> bool:
            """返回确认结果。"""
            return True

        def get_session_name(self) -> str:
            """返回自定义名称。"""
            return ""

        def get_session_remark(self) -> str:
            """返回自定义备注。"""
            return "测试备注"

    class _Window:
        """记录主页控制器委托创建的 session。"""

        def __init__(self) -> None:
            """初始化记录容器。"""
            self.created: list[ProcessingSession] = []

        def add_session_from_import(self, session: ProcessingSession) -> None:
            """记录被委托创建的 session。"""
            self.created.append(session)

    class _View(QObject):
        """提供 HomeController 所需的最小窗口接口。"""

        def __init__(self) -> None:
            """初始化假视图。"""
            super().__init__()
            self._window = _Window()

        def window(self) -> _Window:
            """返回假窗口。"""
            return self._window

    view = _View()
    controller = HomeController.__new__(HomeController)
    controller.view = view
    controller._last_import_session = ProcessingSession(
        source_path="E:/data/a.xlsx",
        source_type="excel",
    )
    controller._show_top_warning = lambda title, content: None
    monkeypatch.setattr(
        "ui.controllers.home_controller.InfoBar.success",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "ui.controllers.home_controller.CreateSessionDialog",
        _FakeCreateSessionDialog,
    )

    HomeController.import_current_session(controller)

    assert view.window().created == [controller._last_import_session]
    assert controller._last_import_session.display_name == "a.xlsx"
    assert controller._last_import_session.remark == "测试备注"
