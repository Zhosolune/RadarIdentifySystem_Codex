"""主窗口动态 session 切片页面管理测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore
from qfluentwidgets.common.router import qrouter
from runtime.session_registry import SessionRegistry
from ui.main_window import MainWindow


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _dispose_window(window: MainWindow) -> None:
    """释放主窗口并清理 qfluentwidgets 全局路由引用。

    Args:
        window [MainWindow]: 需要释放的主窗口实例。

    Returns:
        None: 无返回值。

    Raises:
        无显式抛出异常。
    """
    # 测试进程复用 QApplication，先移除本窗口在全局路由中的堆栈历史。
    qrouter.history = [
        item
        for item in qrouter.history
        if item.stacked is not window.stackedWidget
    ]
    qrouter.stackHistories.pop(window.stackedWidget, None)
    window.close()
    sip.delete(window)


def _routes_for_window(window: MainWindow) -> list[str]:
    """返回指定主窗口在 qrouter 全局历史中的 route key。"""
    return [
        item.routeKey
        for item in qrouter.history
        if item.stacked is window.stackedWidget
    ]


def test_main_window_creates_independent_session_interfaces(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """主窗口应为不同 session 创建独立切片页面并可按 id 查回。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    try:
        first_session = ProcessingSession(session_id="session_a", display_name="A.xlsx")
        second_session = ProcessingSession(session_id="session_b", display_name="B.xlsx")

        first_interface = window.create_session_interface(first_session)
        second_interface = window.create_session_interface(second_session)

        assert first_interface is not second_interface
        assert window.session_interface("session_a") is first_interface
        assert window.session_interface("session_b") is second_interface
        assert first_interface.objectName() == "sessionSliceInterface_session_a"
        assert second_interface.objectName() == "sessionSliceInterface_session_b"
    finally:
        _dispose_window(window)


def test_main_window_reuses_existing_session_interface(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """同一 session_id 重复创建时应复用并返回已有页面。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    try:
        session = ProcessingSession(session_id="session_reused", display_name="复用.xlsx")

        first_interface = window.create_session_interface(session)
        reused_interface = window.create_session_interface(session)

        assert reused_interface is first_interface
        assert window.session_interface("session_reused") is first_interface
    finally:
        _dispose_window(window)


def test_main_window_closes_session_interface(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """关闭动态 session 页面后应移除索引并回到主页。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    try:
        session = ProcessingSession(session_id="session_closed", display_name="关闭.xlsx")

        window.create_session_interface(session)
        window.close_session_interface("session_closed")

        assert window.session_interface("session_closed") is None
        assert window.stackedWidget.currentWidget() is window.homeInterface
        route_history = _routes_for_window(window)
        assert "sessionSliceInterface_session_closed" not in route_history
        assert "settingInterface" not in route_history
        assert route_history[-1] == window.homeInterface.objectName()
    finally:
        _dispose_window(window)


def test_main_window_closes_background_session_without_switching_current_page(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """关闭非当前动态 session 页面时应保留用户当前所在页面。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    try:
        background_session = ProcessingSession(
            session_id="session_background",
            display_name="后台.xlsx",
        )
        current_session = ProcessingSession(
            session_id="session_current",
            display_name="当前.xlsx",
        )

        background_interface = window.create_session_interface(background_session)
        current_interface = window.create_session_interface(current_session)

        assert window.stackedWidget.currentWidget() is current_interface

        window.close_session_interface("session_background")

        assert window.session_interface("session_background") is None
        assert window.stackedWidget.currentWidget() is current_interface
        route_history = _routes_for_window(window)
        assert background_interface.objectName() not in route_history
        assert route_history[-1] == current_interface.objectName()
    finally:
        _dispose_window(window)


def test_main_window_registers_parsed_session_and_emits_lifecycle_signals(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """主窗口应注册解析结果、创建动态页并发出 session 生命周期信号。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    received_registered: list[str] = []
    received_activated: list[str] = []
    try:
        session = ProcessingSession(
            session_id="session_imported",
            source_path="E:/data/imported.xlsx",
            source_type="excel",
        )
        signal_bus.session_registered.connect(received_registered.append)
        signal_bus.session_activated.connect(received_activated.append)

        interface = window.create_session_from_parsed(session)

        assert window.session_registry.get("session_imported") is session
        assert window.session_registry.active_session_id == "session_imported"
        assert window.session_interface("session_imported") is interface
        assert window.stackedWidget.currentWidget() is interface
        assert received_registered == ["session_imported"]
        assert received_activated == ["session_imported"]
        assert (tmp_path / "session_imported" / "session.json").exists()
        assert (tmp_path / "session_imported" / "config.json").exists()
    finally:
        try:
            signal_bus.session_registered.disconnect(received_registered.append)
        except TypeError:
            pass
        try:
            signal_bus.session_activated.disconnect(received_activated.append)
        except TypeError:
            pass
        _dispose_window(window)


def test_main_window_rolls_back_registration_when_session_page_creation_fails(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """动态页面创建失败时主窗口应回滚 session 注册和持久化。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    registry = SessionRegistry(SessionStore(tmp_path))
    first_session = ProcessingSession(
        session_id="session_first",
        display_name="first.xlsx",
    )
    second_session = ProcessingSession(
        session_id="session_second",
        display_name="second.xlsx",
    )
    registry.register(first_session)
    registry.register(second_session)
    registry.activate("session_first")
    window = MainWindow(session_registry=registry)
    received_registered: list[str] = []
    received_activated: list[str] = []

    def _raise_page_error(_session: ProcessingSession) -> None:
        """模拟动态页面创建失败。"""
        raise RuntimeError("page creation failed")

    try:
        session = ProcessingSession(
            session_id="session_failed_page",
            source_path="E:/data/failed.xlsx",
            source_type="excel",
        )
        signal_bus.session_registered.connect(received_registered.append)
        signal_bus.session_activated.connect(received_activated.append)
        monkeypatch.setattr(window, "create_session_interface", _raise_page_error)

        try:
            window.create_session_from_parsed(session)
        except RuntimeError as exc:
            assert str(exc) == "page creation failed"
        else:
            raise AssertionError("页面创建失败应继续抛出原始异常")

        assert window.session_registry.get("session_failed_page") is None
        assert window.session_registry.get("session_first") is first_session
        assert window.session_registry.get("session_second") is second_session
        assert window.session_registry.active_session_id == "session_first"
        assert not (tmp_path / "session_failed_page").exists()
        assert (tmp_path / "session_first").exists()
        assert (tmp_path / "session_second").exists()
        assert registry.store.load_index().active_session_id == "session_first"
        assert received_registered == []
        assert received_activated == []
    finally:
        try:
            signal_bus.session_registered.disconnect(received_registered.append)
        except TypeError:
            pass
        try:
            signal_bus.session_activated.disconnect(received_activated.append)
        except TypeError:
            pass
        _dispose_window(window)
