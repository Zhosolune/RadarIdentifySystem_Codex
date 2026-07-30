"""主窗口动态 session 切片页面管理测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.signal_bus import signal_bus
from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from core.models.processing_session import ProcessingStage
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
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
    QApplication.processEvents()
    sip.delete(window)
    QApplication.processEvents()


def _routes_for_window(window: MainWindow) -> list[str]:
    """返回指定主窗口在 qrouter 全局历史中的 route key。"""
    return [
        item.routeKey
        for item in qrouter.history
        if item.stacked is window.stackedWidget
    ]


class _FakeDialogButton:
    """测试用弹窗按钮桩对象。"""

    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        """记录按钮文本。"""
        self.text = text


class _FakeMessageBox:
    """测试用 MessageBox 桩对象。"""

    accepted = False
    created_count = 0

    def __init__(self, title: str, content: str, parent=None) -> None:
        type(self).created_count += 1
        self.title = title
        self.content = content
        self.parent = parent
        self.yesButton = _FakeDialogButton()
        self.cancelButton = _FakeDialogButton()

    def exec(self) -> bool:
        """返回预设的弹窗结果。"""
        return self.accepted


@pytest.fixture(autouse=True)
def _stub_restore_message_box(monkeypatch: MonkeyPatch) -> None:
    """默认使用弹窗桩，避免删除确认弹窗阻塞测试进程。"""
    _FakeMessageBox.accepted = False
    _FakeMessageBox.created_count = 0
    monkeypatch.setattr("ui.controllers.session_manager_controller.MessageBox", _FakeMessageBox)


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
        dashboard_info = ExcelDashboardInfo(
            total_pulses=1,
            removed_pulses=0,
            amplitude_dropped_pulses=0,
            duration=0.0,
            band="C波段",
            estimated_slice_count=0,
        )
        session.raw_batch = PulseBatch(
            np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]]),
            session.source_path,
            "excel",
            1,
        )
        session.preprocess_result = PreprocessResult(
            np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]]),
            total_pulses=1,
            filtered_pulses=0,
            toa_flip_count=0,
            time_range=0.0,
            estimated_slice_count=0,
            band="C波段",
            dashboard_info=dashboard_info,
        )
        session.dashboard_info = dashboard_info
        signal_bus.session_registered.connect(received_registered.append)
        signal_bus.session_activated.connect(received_activated.append)

        interface = window.session_manager_controller.add_session_from_import(
            session,
            activate=True,
        )

        assert window.session_registry.get("session_imported") is session
        assert window.session_registry.active_session_id == "session_imported"
        assert window.session_interface("session_imported") is interface
        assert window.stackedWidget.currentWidget() is interface
        assert received_registered == ["session_imported"]
        assert received_activated == ["session_imported"]
        assert (tmp_path / "session_imported" / "session.json").exists()
        assert (tmp_path / "session_imported" / "config.json").exists()
        assert (tmp_path / "session_imported" / "import_cache.npz").exists()
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


def test_main_window_add_session_from_import_stays_on_home_and_persists_remark(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """导入面板创建 session 时应停留主页并持久化备注。"""
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
            session_id="session_from_import_panel",
            source_path="E:/data/imported.xlsx",
            source_type="excel",
            display_name="imported.xlsx",
            remark="导入备注",
        )
        dashboard_info = ExcelDashboardInfo(
            total_pulses=1,
            removed_pulses=0,
            amplitude_dropped_pulses=0,
            duration=0.0,
            band="C波段",
            estimated_slice_count=0,
        )
        session.raw_batch = PulseBatch(
            np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]]),
            session.source_path,
            "excel",
            1,
        )
        session.preprocess_result = PreprocessResult(
            np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]]),
            total_pulses=1,
            filtered_pulses=0,
            toa_flip_count=0,
            time_range=0.0,
            estimated_slice_count=0,
            band="C波段",
            dashboard_info=dashboard_info,
        )
        session.dashboard_info = dashboard_info
        signal_bus.session_registered.connect(received_registered.append)
        signal_bus.session_activated.connect(received_activated.append)

        interface = window.session_manager_controller.add_session_from_import(
            session
        )
        persisted_session = window.session_registry.store.load_session(session.session_id)

        assert window.session_registry.get(session.session_id) is session
        assert window.session_registry.active_session_id is None
        assert window.session_interface(session.session_id) is interface
        assert window.stackedWidget.currentWidget() is window.homeInterface
        assert window.homeInterface.session_manager_panel.current_session_id() == session.session_id
        assert received_registered == [session.session_id]
        assert received_activated == []
        assert persisted_session.display_name == "imported.xlsx"
        assert persisted_session.remark == "导入备注"
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


def test_session_drawer_config_change_is_persisted(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """动态 session 抽屉配置变更后应同步写入持久化子配置。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    store = SessionStore(tmp_path)
    window = MainWindow(session_registry=SessionRegistry(store))
    try:
        session = ProcessingSession(
            session_id="session_config_saved",
            source_path="E:/data/config.xlsx",
            source_type="excel",
        )
        interface = window.session_manager_controller.add_session_from_import(
            session,
            activate=True,
        )
        target_value = not bool(interface.slice_param_panel.auto_recognize_item.value)

        interface.slice_param_panel.auto_recognize_card.setChecked(target_value)

        assert (
            store.load_session("session_config_saved")
            .config_snapshot
            .business
            .auto_recognize_next_slice
            is target_value
        )
    finally:
        _dispose_window(window)


def test_main_window_restores_session_interfaces_from_registry_and_stays_on_home_by_default(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """主窗口启动恢复已有 session 时应默认停留主页且不恢复历史 active 状态。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    store = SessionStore(tmp_path)
    first_session = ProcessingSession(
        session_id="session_restore_a",
        source_path="E:/data/a.xlsx",
        source_type="excel",
    )
    second_session = ProcessingSession(
        session_id="session_restore_b",
        source_path="E:/data/b.xlsx",
        source_type="excel",
    )
    store.upsert_session(first_session)
    store.upsert_session(second_session)
    index_payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    index_payload["active_session_id"] = "session_restore_a"
    index_payload["last_exit_view"] = "home"
    (tmp_path / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    window = MainWindow(session_registry=SessionRegistry(store))
    try:
        QApplication.processEvents()
        first_interface = window.session_interface("session_restore_a")
        second_interface = window.session_interface("session_restore_b")

        assert first_interface is not None
        assert second_interface is not None
        assert window.stackedWidget.currentWidget() is window.homeInterface
        assert window.session_registry.active_session_id is None
        assert _FakeMessageBox.created_count == 0
    finally:
        _dispose_window(window)


def test_main_window_ignores_legacy_restore_state_and_stays_on_home(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """主窗口应忽略旧索引中的恢复状态并直接进入主页。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    _FakeMessageBox.accepted = True
    store = SessionStore(tmp_path)
    first_session = ProcessingSession(
        session_id="session_restore_a",
        source_path="E:/data/a.xlsx",
        source_type="excel",
    )
    second_session = ProcessingSession(
        session_id="session_restore_b",
        source_path="E:/data/b.xlsx",
        source_type="excel",
    )
    store.upsert_session(first_session)
    store.upsert_session(second_session)
    index_payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    index_payload["active_session_id"] = "session_restore_a"
    index_payload["last_exit_view"] = "session"
    (tmp_path / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    window = MainWindow(session_registry=SessionRegistry(store))
    try:
        QApplication.processEvents()
        first_interface = window.session_interface("session_restore_a")

        assert first_interface is not None
        assert window.stackedWidget.currentWidget() is window.homeInterface
        assert window.session_registry.active_session_id is None
        assert _FakeMessageBox.created_count == 0
    finally:
        _dispose_window(window)


def test_main_window_close_does_not_persist_home_exit_view(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """在主页退出时不应保存用于下次启动恢复的界面状态。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    store = SessionStore(tmp_path)
    session = ProcessingSession(
        session_id="session_exit_from_home",
        source_path="E:/data/home.xlsx",
        source_type="excel",
    )

    first_window = MainWindow(session_registry=SessionRegistry(store))
    try:
        first_window.session_manager_controller.add_session_from_import(
            session,
            activate=True,
        )
        first_window.switchTo(first_window.homeInterface)
        first_window.close()
        QApplication.processEvents()
        payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))

        assert "active_session_id" not in payload
        assert "last_exit_view" not in payload
    finally:
        qrouter.history = [
            item
            for item in qrouter.history
            if item.stacked is not first_window.stackedWidget
        ]
        qrouter.stackHistories.pop(first_window.stackedWidget, None)
        sip.delete(first_window)
        QApplication.processEvents()

    second_window = MainWindow(session_registry=SessionRegistry(store))
    try:
        QApplication.processEvents()

        assert second_window.stackedWidget.currentWidget() is second_window.homeInterface
        assert second_window.session_registry.active_session_id is None
        assert _FakeMessageBox.created_count == 0
    finally:
        _dispose_window(second_window)


def test_main_window_close_does_not_persist_session_exit_view(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """在 session 页面退出时不应保存恢复提示所需的界面状态。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    store = SessionStore(tmp_path)
    session = ProcessingSession(
        session_id="session_exit_from_page",
        source_path="E:/data/page.xlsx",
        source_type="excel",
    )

    first_window = MainWindow(session_registry=SessionRegistry(store))
    try:
        first_window.session_manager_controller.add_session_from_import(
            session,
            activate=True,
        )
        first_window.close()
        QApplication.processEvents()
        payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))

        assert "active_session_id" not in payload
        assert "last_exit_view" not in payload
    finally:
        qrouter.history = [
            item
            for item in qrouter.history
            if item.stacked is not first_window.stackedWidget
        ]
        qrouter.stackHistories.pop(first_window.stackedWidget, None)
        sip.delete(first_window)
        QApplication.processEvents()

    _FakeMessageBox.accepted = False
    _FakeMessageBox.created_count = 0
    second_window = MainWindow(session_registry=SessionRegistry(store))
    try:
        QApplication.processEvents()

        assert second_window.stackedWidget.currentWidget() is second_window.homeInterface
        assert second_window.session_registry.active_session_id is None
        assert _FakeMessageBox.created_count == 0
    finally:
        _dispose_window(second_window)


def test_main_window_restores_import_cache_for_sessions(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """主窗口恢复 session 页面时应同步恢复导入缓存运行态。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    store = SessionStore(tmp_path)
    session = ProcessingSession(
        session_id="session_restore_cache",
        source_path="E:/data/cache.xlsx",
        source_type="excel",
    )
    raw_data = np.array([[1200.0, 3.0, 50.0, 40.0, 40.0, 10.0]])
    preprocess_data = np.array([[1200.0, 3.0, 50.0, 40.0, 40.0, 10.0]])
    dashboard_info = ExcelDashboardInfo(
        total_pulses=1,
        removed_pulses=0,
        amplitude_dropped_pulses=0,
        duration=0.0,
        band="C波段",
        estimated_slice_count=0,
    )
    session.raw_batch = PulseBatch(raw_data, session.source_path, "excel", 1)
    session.preprocess_result = PreprocessResult(
        preprocess_data,
        total_pulses=1,
        filtered_pulses=0,
        toa_flip_count=0,
        time_range=0.0,
        estimated_slice_count=0,
        band="C波段",
        dashboard_info=dashboard_info,
    )
    session.dashboard_info = dashboard_info
    store.upsert_session(session)
    store.save_import_cache(session)

    window = MainWindow(session_registry=SessionRegistry(store))
    try:
        restored = window.session_registry.get("session_restore_cache")

        assert restored is not None
        assert restored.raw_batch is not None
        assert restored.preprocess_result is not None
        assert restored.dashboard_info == dashboard_info
        assert restored.stage is ProcessingStage.PREPROCESSED
        np.testing.assert_array_equal(restored.raw_batch.data, raw_data)
        np.testing.assert_array_equal(restored.preprocess_result.data, preprocess_data)
    finally:
        _dispose_window(window)


def test_home_session_manager_lists_created_session(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """创建 session 后主页 session 管理器应显示该 session。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    try:
        session = ProcessingSession(
            session_id="session_manager_created",
            source_path="E:/data/a.xlsx",
            source_type="excel",
        )

        window.session_manager_controller.add_session_from_import(
            session,
            activate=True,
        )

        titles = window.homeInterface.session_manager_panel.session_titles()
        assert session.display_name in titles
    finally:
        _dispose_window(window)


def test_main_window_close_session_keeps_card_and_registry_entry(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """关闭 session 时应仅关闭动态页面，保留卡片与注册表数据。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    try:
        session = ProcessingSession(
            session_id="session_close_only",
            source_path="E:/data/close.xlsx",
            source_type="excel",
            display_name="close.xlsx",
        )

        window.session_manager_controller.add_session_from_import(
            session,
            activate=True,
        )
        window.homeInterface.session_manager_panel.sessionCloseRequested.emit(session.session_id)

        panel = window.homeInterface.session_manager_panel
        assert window.session_interface(session.session_id) is None
        assert window.session_registry.get(session.session_id) is not None
        assert session.display_name in panel.session_titles()
        assert panel.current_session_id() == session.session_id
        assert panel.enable_action.text() == "启用"
        assert panel.enable_action.isEnabled() is True
        assert panel.close_action.text() == "已关闭"
        assert panel.close_action.isEnabled() is False
        assert window.session_registry.active_session_id is None
    finally:
        _dispose_window(window)


def test_main_window_delete_session_removes_card_and_persisted_data(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """删除 session 时应移除卡片、动态页面和持久化数据。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    _FakeMessageBox.accepted = True
    window = MainWindow(session_registry=SessionRegistry(SessionStore(tmp_path)))
    try:
        session = ProcessingSession(
            session_id="session_delete_all",
            source_path="E:/data/delete.xlsx",
            source_type="excel",
            display_name="delete.xlsx",
        )

        window.session_manager_controller.add_session_from_import(
            session,
            activate=True,
        )
        window.homeInterface.session_manager_panel.sessionDeleteRequested.emit(session.session_id)

        panel = window.homeInterface.session_manager_panel
        assert window.session_interface(session.session_id) is None
        assert window.session_registry.get(session.session_id) is None
        assert session.display_name not in panel.session_titles()
        with pytest.raises(FileNotFoundError):
            window.session_registry.store.load_session(session.session_id)
    finally:
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

    def _raise_page_error(
        _session: ProcessingSession,
        activate: bool = True,
    ) -> None:
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
            window.session_manager_controller.add_session_from_import(
                session,
                activate=True,
            )
        except RuntimeError as exc:
            assert str(exc) == "page creation failed"
        else:
            raise AssertionError("页面创建失败应继续抛出原始异常")

        assert window.session_registry.get("session_failed_page") is None
        assert window.session_registry.get("session_first") is not None
        assert window.session_registry.get("session_second") is not None
        assert window.session_registry.get("session_first").display_name == "first.xlsx"
        assert window.session_registry.get("session_second").display_name == "second.xlsx"
        # 主窗口启动恢复不再继承历史 active 状态；失败回滚不得凭空激活页面。
        assert window.session_registry.active_session_id is None
        assert not (tmp_path / "session_failed_page").exists()
        assert (tmp_path / "session_first").exists()
        assert (tmp_path / "session_second").exists()
        index_payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
        assert "active_session_id" not in index_payload
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
