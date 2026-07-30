"""Session 管理器控制器元数据编辑测试。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from app.application import create_application_services
from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore
from runtime.session_registry import SessionRegistry
from ui.components.session_manager_panel import SessionManagerPanel
from ui.controllers import session_manager_controller
from ui.controllers.session_manager_controller import SessionManagerController

_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


class _FakeMainWindow(QObject):
    """提供控制器测试所需的最小主窗口接口。"""

    def __init__(self) -> None:
        """初始化假主窗口并记录刷新与导航更新调用。"""
        super().__init__()
        self.refreshed_session_ids: list[str | None] = []
        self.navigation_text_updates: list[tuple[str, str]] = []

    def set_session_navigation_text(self, session_id: str, display_name: str) -> None:
        """记录 Session 导航文案更新请求。"""
        self.navigation_text_updates.append((session_id, display_name))

    def session_interface(self, session_id: str):
        """满足控制器启用或关闭逻辑所需的占位接口。"""
        return None

    def enabled_session_ids(self) -> set[str]:
        """返回空的已启用页面集合。"""
        return set()


class _AcceptedMetadataDialog:
    """测试用自动确认元数据对话框。"""

    def __init__(self, current_name: str, current_remark: str, parent=None) -> None:
        """记录当前名称和备注并准备返回新值。"""
        self.current_name = current_name
        self.current_remark = current_remark

    def exec(self) -> bool:
        """模拟用户确认对话框。"""
        return True

    def get_session_name(self) -> str:
        """返回测试输入的新名称。"""
        return "新名称"

    def get_remark(self) -> str:
        """返回测试输入的新备注。"""
        return "新备注"


def test_controller_updates_session_name_and_remark_from_one_dialog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """编辑信息确认后应同时更新名称、备注并刷新当前详情。"""
    _app()
    registry = SessionRegistry(SessionStore(tmp_path))
    session = registry.register(
        ProcessingSession(session_id="session-a", source_path="E:/data/a.xlsx"),
    )
    view = SessionManagerPanel()
    services = create_application_services(session_registry=registry)
    main_window = _FakeMainWindow()
    controller = SessionManagerController(
        view,
        main_window,
        services.session_coordinator,
    )
    monkeypatch.setattr(
        session_manager_controller,
        "RenameSessionDialog",
        _AcceptedMetadataDialog,
    )
    monkeypatch.setattr(controller, "_show_top_success", lambda title, content: None)
    monkeypatch.setattr(
        controller,
        "refresh_panel",
        lambda selected_session_id=None: (
            main_window.refreshed_session_ids.append(selected_session_id)
        ),
    )

    view.sessionRenameRequested.emit(session.session_id)

    assert session.display_name == "新名称"
    assert session.remark == "新备注"
    restored = registry.store.load_session(session.session_id)
    assert restored.display_name == "新名称"
    assert restored.remark == "新备注"
    assert main_window.navigation_text_updates == [(session.session_id, "新名称")]
    assert main_window.refreshed_session_ids == [session.session_id]
