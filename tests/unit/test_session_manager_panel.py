"""主页 session 管理器面板测试。"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import QApplication

from core.models.processing_session import ProcessingSession
from ui.components.card_navigation_list import UNIFIED_NAVIGATION_FONT_FAMILIES
from ui.components.session_manager_panel import SessionManagerPanel


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_session_manager_panel_uses_card_navigation_list() -> None:
    """session 管理器应使用卡片导航列表展示名称和创建时间。"""
    _app()
    panel = SessionManagerPanel()
    session = ProcessingSession(
        session_id="session_a",
        display_name="A.xlsx",
        created_at=datetime(2026, 6, 22, 12, 30),
    )

    panel.set_sessions([session])

    item = panel.session_nav.item("session_a")
    assert item.title_label.text().startswith("\u4e2d\u6587\u6d4b\u8bd5\u770b\u770b\u5b57\u4f53")
    assert item.title_label.text().endswith("A.xlsx")
    assert item.subtitle_label is not None
    assert item.subtitle_label.text() == "2026-06-22 12:30"
    assert item.title_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert item.subtitle_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert panel.session_title_label.text() == "Session 管理"
    assert panel.session_header_separator.height() == 1
    assert panel._content_divider.width() == 1
    assert panel.session_detail_placeholder.text() == "Session 详情占位"
    assert panel.session_titles() == ["A.xlsx"]
