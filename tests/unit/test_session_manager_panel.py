"""主页 session 管理器面板测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget
from qfluentwidgets import ScrollArea, TextEdit

from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from ui.components.card_navigation_list import UNIFIED_NAVIGATION_FONT_FAMILIES
from ui.components.session_manager_panel import SessionManagerPanel
from ui.dialogs.rename_session_dialog import RenameSessionDialog


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
    assert item.title_label.text() == "A.xlsx"
    assert item.subtitle_label is not None
    assert item.subtitle_label.text() == "2026-06-22 12:30"
    assert item.title_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert item.subtitle_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert panel.session_title_label.text() == "Session 管理"
    assert panel.session_header_separator.height() == 1
    assert panel.current_session_id() == "session_a"
    assert panel.session_detail_placeholder.text() == "请选择一个 Session 查看详情"
    assert panel._detail_name_label.text() == "数据包信息"
    assert panel._session_id_value_label.text() == "session_a"
    assert panel._file_name_value_label.text() == "A.xlsx"
    assert panel._file_size_value_label.text() == "9 B"
    assert panel._file_path_value_label.text() == str(source_file)
    assert panel._remark_value_label.text() == "无"
    assert len(panel._metric_cards) == 6
    assert len(panel.session_command_bar.actions()) == 4
    assert panel._header_layout.indexOf(panel.session_command_bar) >= 0
    assert panel._detail_layout.indexOf(panel.session_command_bar) == -1
    assert not hasattr(panel, "create_session_button")
    assert isinstance(panel._detail_info_scroll_area, ScrollArea)
    assert panel._detail_info_scroll_area.widget() is panel._detail_info_widget
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
    assert info_titles == ["Session ID：", "文件名：", "文件大小：", "文件路径：", "备注信息："]
    assert panel.session_titles() == ["A.xlsx"]


def test_session_manager_detail_info_scroll_area_uses_remaining_space() -> None:
    """详情滚动区应自然伸缩，长内容不得改变管理面板最小高度。"""
    app = _app()
    panel = SessionManagerPanel()
    panel.resize(900, 420)
    long_session = ProcessingSession(
        session_id="session-long-remark",
        source_path=(
            "E:/radar/session/with/a/very/long/source/path/"
            "that/needs/to/wrap/source.xlsx"
        ),
        display_name="长备注.xlsx",
        remark="\n".join(f"第 {index + 1} 行备注" for index in range(40)),
    )

    panel.set_sessions([long_session])
    panel.show()
    app.processEvents()

    scroll_area = panel._detail_info_scroll_area
    initial_scroll_height = scroll_area.height()
    assert scroll_area.verticalScrollBar().maximum() > 0
    assert scroll_area.scrollDelagate.hScrollBar._isForceHidden
    assert not scroll_area.scrollDelagate.vScrollBar._isForceHidden

    short_panel = SessionManagerPanel()
    short_panel.resize(900, 420)
    short_session = ProcessingSession(
        session_id="session-short-remark",
        display_name="短备注.xlsx",
        remark="短备注",
    )
    short_panel.set_sessions([short_session])
    short_panel.show()
    app.processEvents()
    assert (
        panel.minimumSizeHint().height()
        == short_panel.minimumSizeHint().height()
    )
    assert short_panel._detail_info_scroll_area.verticalScrollBar().maximum() == 0

    panel.resize(900, 600)
    app.processEvents()
    assert scroll_area.height() > initial_scroll_height
    assert scroll_area.verticalScrollBar().maximum() > 0
    short_panel.close()
    panel.close()


def test_session_manager_detail_rows_keep_spacing_when_window_grows() -> None:
    """窗口增高时详情行位置不变，新增高度应由滚动区底部空白吸收。"""
    app = _app()
    panel = SessionManagerPanel()
    panel.resize(900, 420)
    session = ProcessingSession(
        session_id="session-fixed-detail-spacing",
        display_name="固定间距.xlsx",
        remark="短备注",
    )
    panel.set_sessions([session])
    panel.show()
    app.processEvents()

    rows = [
        panel._detail_info_layout.itemAt(index).widget()
        for index in range(5)
    ]
    assert all(row is not None for row in rows)
    initial_geometries = [
        (row.y(), row.height())
        for row in rows
        if row is not None
    ]
    initial_scroll_height = panel._detail_info_scroll_area.height()
    assert panel._detail_info_layout.stretch(5) == 1

    panel.resize(900, 700)
    app.processEvents()

    grown_geometries = [
        (row.y(), row.height())
        for row in rows
        if row is not None
    ]
    assert grown_geometries == initial_geometries
    assert panel._detail_info_scroll_area.height() > initial_scroll_height
    assert panel._detail_info_scroll_area.verticalScrollBar().maximum() == 0
    panel.close()


def test_session_metadata_dialog_uses_fluent_rich_text_remark_editor() -> None:
    """编辑 Session 信息时应使用组件库 TextEdit 并返回纯文本备注。"""
    _app()
    parent = QWidget()
    dialog = RenameSessionDialog("A.xlsx", "原备注", parent)

    assert isinstance(dialog.remark_text_edit, TextEdit)
    assert dialog.remark_text_edit.acceptRichText()
    assert dialog.remark_text_edit.toPlainText() == "原备注"
    dialog.remark_text_edit.setPlainText("新备注")
    assert dialog.get_remark() == "新备注"


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


def test_session_manager_panel_metric_layout_uses_adaptive_flow() -> None:
    """详情区指标卡应使用 AdaptiveFlowLayout 按行均分宽度。"""
    from qfluentwidgets.components.layout import AdaptiveFlowLayout

    _app()
    panel = SessionManagerPanel()

    # 布局应为 AdaptiveFlowLayout，最小宽度设为 110。
    assert isinstance(panel._metrics_layout, AdaptiveFlowLayout)
    assert panel._metrics_layout.widgetMinimumWidth() == 110
    assert panel._metrics_layout.needAni is True
    assert panel._metrics_layout.isTight is True


def test_session_manager_panel_uses_single_metadata_edit_action() -> None:
    """点击编辑信息动作时应复用重命名信号发出当前 session id。"""
    _app()
    panel = SessionManagerPanel()
    session = ProcessingSession(
        session_id="session_a",
        display_name="A.xlsx",
        created_at=datetime(2026, 6, 22, 12, 30),
    )
    requested_session_ids: list[str] = []

    panel.set_sessions([session])
    panel.sessionRenameRequested.connect(requested_session_ids.append)
    panel.rename_action.trigger()

    assert requested_session_ids == ["session_a"]
    assert len(panel.session_command_bar.actions()) == 4
    assert panel.rename_action.text() == "编辑信息"
    assert panel.rename_action.isEnabled() is True
