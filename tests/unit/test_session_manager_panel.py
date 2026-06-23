"""主页 session 管理器面板测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.models.dashboard_info import ExcelDashboardInfo
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


def test_session_manager_panel_uses_card_navigation_list_and_detail_view(
    tmp_path: Path,
) -> None:
    """session 管理器应使用卡片导航列表并同步刷新详情区域。"""
    _app()
    source_file = tmp_path / "A.xlsx"
    source_file.write_bytes(b"session-a")
    panel = SessionManagerPanel()
    session = ProcessingSession(
        session_id="session_a",
        source_path=str(source_file),
        display_name="A.xlsx",
        created_at=datetime(2026, 6, 22, 12, 30),
    )
    session.dashboard_info = ExcelDashboardInfo(
        total_pulses=12,
        removed_pulses=2,
        amplitude_dropped_pulses=1,
        duration=25_000,
        band="C波段",
        estimated_slice_count=3,
    )

    panel.set_sessions([session], enabled_session_ids={"session_a"})

    item = panel.session_nav.item("session_a")
    assert item.title_label.text().startswith("\u4e2d\u6587\u6d4b\u8bd5\u770b\u770b\u5b57\u4f53")
    assert item.title_label.text().endswith("A.xlsx")
    assert item.subtitle_label is not None
    assert item.subtitle_label.text() == "2026-06-22 12:30"
    assert item.title_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert item.subtitle_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert panel.session_title_label.text() == "Session 管理"
    assert panel.session_header_separator.height() == 1
    assert panel.current_session_id() == "session_a"
    assert panel.session_detail_placeholder.text() == "请选择一个 Session 查看详情"
    assert panel._detail_name_label.text() == "数据包信息"
    assert panel._file_name_value_label.text() == "A.xlsx"
    assert panel._file_size_value_label.text() == "9 B"
    assert panel._file_path_value_label.text() == str(source_file)
    assert panel._remark_value_label.text() == "无"
    assert len(panel._metric_cards) == 6
    assert len(panel.session_command_bar.actions()) == 4
    assert panel.jump_button.text() == "跳转到 Session"
    assert panel.jump_button.isEnabled() is True
    assert panel.enable_action.text() == "已启用"
    assert panel.enable_action.isEnabled() is False
    assert panel.close_action.text() == "关闭"
    assert panel.close_action.isEnabled() is True
    title_labels = panel._detail_info_widget.findChildren(type(panel._file_name_value_label))
    info_titles = [
        label.text()
        for label in title_labels
        if label.objectName() == "sessionDetailInfoTitle"
    ]
    assert info_titles == ["文件名：", "文件大小：", "文件路径：", "备注信息："]
    assert panel.session_titles() == ["A.xlsx"]


def test_session_manager_panel_card_click_only_switches_detail_selection() -> None:
    """点击 session 卡片时应只刷新详情，不直接触发启用信号。"""
    _app()
    panel = SessionManagerPanel()
    first_session = ProcessingSession(
        session_id="session_a",
        display_name="A.xlsx",
        created_at=datetime(2026, 6, 22, 12, 30),
    )
    second_session = ProcessingSession(
        session_id="session_b",
        display_name="B.xlsx",
        created_at=datetime(2026, 6, 22, 12, 31),
    )
    selected_session_ids: list[str] = []
    activated_session_ids: list[str] = []

    panel.set_sessions([first_session, second_session], selected_session_id="session_a")
    panel.sessionSelected.connect(selected_session_ids.append)
    panel.sessionEnableRequested.connect(activated_session_ids.append)

    panel.session_nav.set_current_key("session_b")

    assert selected_session_ids == ["session_b"]
    assert activated_session_ids == []
    assert panel.current_session_id() == "session_b"
    assert panel._detail_name_label.text() == "数据包信息"


def test_session_manager_panel_updates_action_states_by_enabled_sessions() -> None:
    """详情动作应按当前 session 是否已启用切换文案和禁用态。"""
    _app()
    panel = SessionManagerPanel()
    session = ProcessingSession(
        session_id="session_a",
        display_name="A.xlsx",
        created_at=datetime(2026, 6, 22, 12, 30),
    )

    panel.set_sessions([session], enabled_session_ids=set())

    assert panel.enable_action.text() == "启用"
    assert panel.enable_action.isEnabled() is True
    assert panel.close_action.text() == "已关闭"
    assert panel.close_action.isEnabled() is False
    assert panel.jump_button.isEnabled() is False

    panel.set_sessions([session], enabled_session_ids={"session_a"})

    assert panel.enable_action.text() == "已启用"
    assert panel.enable_action.isEnabled() is False
    assert panel.close_action.text() == "关闭"
    assert panel.close_action.isEnabled() is True
    assert panel.jump_button.isEnabled() is True


def test_session_manager_panel_metric_layout_tracks_detail_width() -> None:
    """详情区指标卡列数应按截断取整公式随宽度变化。"""
    _app()
    panel = SessionManagerPanel()

    three_columns, three_width = panel._metric_layout_spec(320, 6)
    four_columns, four_width = panel._metric_layout_spec(420, 6)
    six_columns, six_width = panel._metric_layout_spec(620, 6)

    assert three_columns == 3
    assert three_width == 100
    assert four_columns == 4
    assert four_width == 97
    assert six_columns == 5
    assert six_width == 116
