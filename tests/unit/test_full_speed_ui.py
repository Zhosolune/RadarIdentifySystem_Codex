"""全速 Session 创建选项与主页卡片状态测试。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QWidget,
)
from qfluentwidgets import CardWidget, PrimaryPushButton, ScrollArea

from core.models.processing_session import ProcessingMode, ProcessingSession
from core.models.session_config import SessionConfigSnapshot
from runtime.full_speed_session_registry import (
    FullSpeedExecutionState,
    FullSpeedStatus,
)
from ui.components.full_speed_params_window import FullSpeedParamsWindow
from ui.components.full_speed_session_panel import FullSpeedSessionPanel
from ui.components.scrolling_name_label import ScrollingNameLabel
from ui.dialogs.create_session_dialog import CreateSessionDialog


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_create_session_dialog_selects_peer_processing_mode() -> None:
    """创建窗口应默认交互式，并可切换到全速处理体系。"""
    _app()
    parent = QWidget()
    dialog = CreateSessionDialog("demo.xlsx", parent)

    assert dialog.get_processing_mode() is ProcessingMode.SLICE_INTERACTIVE
    dialog.full_speed_radio.setChecked(True)
    assert dialog.get_processing_mode() is ProcessingMode.FULL_SPEED


def test_full_speed_card_locks_configuration_and_shows_progress() -> None:
    """任务开始后保存路径应锁定，卡片应展示切片与总进度。"""
    _app()
    panel = FullSpeedSessionPanel()
    session = ProcessingSession(
        session_id="fullspeed1",
        processing_mode=ProcessingMode.FULL_SPEED,
        display_name="并发任务一",
        data_package_id="package1",
        full_speed_locked=True,
    )
    state = FullSpeedExecutionState(
        status=FullSpeedStatus.RUNNING,
        current_stage="聚类与识别",
        current_slice=2,
        total_slices=5,
        progress=37,
        message="正在处理第 2/5 个切片",
        output_dir="E:/output",
    )

    panel.set_sessions([session], {session.session_id: state})
    card = panel._cards[session.session_id]

    assert card.progress_bar.value() == 37
    assert "切片 2/5" in card.stage_label.text()
    assert not card.output_button.isEnabled()
    assert not card.params_button.isEnabled()
    assert card.cancel_button.isEnabled()
    assert not card.open_button.isEnabled()


def test_full_speed_card_maps_start_action_to_execution_status() -> None:
    """全速任务仅在初始或未成功结束状态提供开始与重试操作。"""
    _app()
    panel = FullSpeedSessionPanel()
    reference_button = PrimaryPushButton("已完成")
    expected_width = reference_button.sizeHint().width()
    session = ProcessingSession(
        session_id="fullspeed-action-state",
        processing_mode=ProcessingMode.FULL_SPEED,
        display_name="按钮状态任务",
        data_package_id="package-action-state",
    )
    expected_actions = {
        FullSpeedStatus.CONFIGURING: ("开始", True),
        FullSpeedStatus.RUNNING: ("执行中", False),
        FullSpeedStatus.EXPORTING: ("保存中", False),
        FullSpeedStatus.SUCCEEDED: ("已完成", False),
        FullSpeedStatus.FAILED: ("重试", True),
        FullSpeedStatus.CANCELLED: ("重试", True),
        FullSpeedStatus.INTERRUPTED: ("重试", True),
    }

    for status, (text, enabled) in expected_actions.items():
        panel.set_sessions(
            [session],
            {
                session.session_id: FullSpeedExecutionState(
                    status=status,
                )
            },
        )
        card = panel._cards[session.session_id]
        assert card.start_button.text() == text
        assert card.start_button.isEnabled() is enabled
        assert card.start_button.width() == expected_width


def test_full_speed_card_scrolls_long_output_path_without_truncation() -> None:
    """全速任务结果路径超宽时应滚动，变为短路径后应恢复静态显示。"""
    app = _app()
    panel = FullSpeedSessionPanel()
    panel.resize(520, 500)
    session = ProcessingSession(
        session_id="fullspeed-output-path",
        processing_mode=ProcessingMode.FULL_SPEED,
        display_name="长路径任务",
        data_package_id="package-output-path",
    )
    long_output_file = (
        "E:/radar-results/2026-07-29/"
        "full-speed-session-with-a-very-long-result-file-name/"
        "识别与参数提取结果_完整数据包_最终结果.xlsx"
    )
    long_state = FullSpeedExecutionState(
        status=FullSpeedStatus.SUCCEEDED,
        current_stage="处理完成",
        progress=100,
        output_file=long_output_file,
    )

    panel.set_sessions([session], {session.session_id: long_state})
    panel.show()
    app.processEvents()
    card = panel._cards[session.session_id]

    assert isinstance(card.output_label, ScrollingNameLabel)
    assert card.output_label.text() == f"结果文件：{long_output_file}"
    assert card.output_label.scroll_timer.isActive()
    assert card.output_label.secondary_label.isVisible()

    short_state = FullSpeedExecutionState(output_dir="E:/out")
    card.update_state(session, short_state)
    app.processEvents()

    assert card.output_label.text() == "保存目录：E:/out"
    assert not card.output_label.scroll_timer.isActive()
    assert card.output_label.secondary_label.isHidden()


def test_full_speed_card_places_parameter_button_between_path_and_start() -> None:
    """全速任务卡片应在保存路径与开始之间提供参数入口并转发 Session ID。"""
    app = _app()
    panel = FullSpeedSessionPanel()
    panel.resize(520, 500)
    session = ProcessingSession(
        session_id="fullspeed-params-entry",
        processing_mode=ProcessingMode.FULL_SPEED,
        display_name="参数入口任务",
        data_package_id="package-params-entry",
    )
    requested: list[str] = []
    panel.parametersRequested.connect(requested.append)

    panel.set_sessions(
        [session],
        {session.session_id: FullSpeedExecutionState()},
    )
    panel.show()
    app.processEvents()
    card = panel._cards[session.session_id]

    assert card.output_button.x() < card.params_button.x() < card.start_button.x()
    assert card.params_button.isEnabled()
    assert card.layout().minimumSize().width() <= panel._MIN_CARD_WIDTH

    card.params_button.click()
    assert requested == [session.session_id]


def test_full_speed_params_window_edits_isolated_two_column_draft() -> None:
    """全速参数窗口应照搬全部参数组，并只在保存时提交独立草稿。"""
    app = _app()
    source_snapshot = SessionConfigSnapshot.default()
    source_snapshot.clustering.eps_cf = 3.25
    window = FullSpeedParamsWindow(
        "fullspeed-params-window",
        "两栏参数任务",
        source_snapshot,
    )
    submitted: list[SessionConfigSnapshot] = []
    window.configSaved.connect(submitted.append)

    window.show()
    app.processEvents()

    assert len(window.parameter_items) == 25
    assert window.cluster_group.parent() is window.left_column_widget
    assert window.extract_pri_group.parent() is window.left_column_widget
    assert window.recognition_group.parent() is window.right_column_widget
    assert window.extract_cf_group.parent() is window.right_column_widget
    assert window.extract_pw_group.parent() is window.right_column_widget
    assert window.merge_group.parent() is window.right_column_widget
    assert window.left_column_widget.width() == window.right_column_widget.width()

    eps_cf_card = window.parameter_cards["clustering.eps_cf"]
    eps_cf_card.spinBox.setValue(4.75)
    app.processEvents()

    assert source_snapshot.clustering.eps_cf == 3.25
    assert window.snapshot().clustering.eps_cf == 4.75

    window.save_button.click()
    assert len(submitted) == 1
    assert submitted[0].clustering.eps_cf == 4.75
    window.close()


def test_full_speed_panel_uses_transparent_scroll_content_and_native_card_border() -> None:
    """全速任务应落在透明滚动内容区并使用组件库原生卡片边框。"""
    _app()
    panel = FullSpeedSessionPanel()
    session = ProcessingSession(
        session_id="fullspeed-style",
        processing_mode=ProcessingMode.FULL_SPEED,
        display_name="样式任务",
        data_package_id="package-style",
    )
    panel.set_sessions(
        [session],
        {session.session_id: FullSpeedExecutionState()},
    )
    card = panel._cards[session.session_id]

    assert panel.body_widget.objectName() == "homeFullSpeedBody"
    assert type(panel.scroll_area) is ScrollArea
    assert panel.scroll_area.parent() is panel.body_widget
    assert panel.scroll_area.widget() is panel.content_widget
    assert panel.cards_widget.parent() is panel.content_widget
    assert panel.findChildren(QAbstractScrollArea) == [panel.scroll_area]
    assert (
        panel.scroll_area.horizontalScrollBarPolicy()
        is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert panel.scroll_area.scrollDelagate.hScrollBar._isForceHidden
    assert not panel.scroll_area.scrollDelagate.vScrollBar._isForceHidden
    assert panel.scroll_area.viewportMargins().right() == 20
    assert panel.findChild(QWidget, "homeFullSpeedSessionPane") is None
    assert card.objectName() == "fullSpeedSessionCard"
    assert isinstance(card, CardWidget)
    assert type(card).paintEvent is CardWidget.paintEvent
    assert card.getBorderRadius() == 8
    assert card.output_button.property("fullSpeedSecondaryAction") is True
    assert card.params_button.property("fullSpeedSecondaryAction") is True
    assert card.delete_button.property("fullSpeedSecondaryAction") is True

    project_root = Path(__file__).resolve().parents[2]
    for theme in ("light", "dark"):
        qss = (
            project_root
            / "resources"
            / "qss"
            / theme
            / "home_interface.qss"
        ).read_text(encoding="utf-8")
        assert "QScrollArea#homeFullSpeedScrollArea" in qss
        assert "QWidget#homeFullSpeedBody" in qss
        assert "QWidget#homeFullSpeedContent" in qss
        assert "QWidget#homeFullSpeedCards" in qss
        assert "homeFullSpeedSessionPane" not in qss
        assert "QFrame#fullSpeedSessionCard" not in qss
        assert 'QPushButton[fullSpeedSecondaryAction="true"]' in qss


def test_full_speed_panel_places_visible_scrollbar_outside_cards() -> None:
    """任务溢出时纵向滚动条应位于卡片外侧并保留固定间距。"""
    app = _app()
    panel = FullSpeedSessionPanel()
    panel.resize(620, 260)
    sessions = [
        ProcessingSession(
            session_id=f"fullspeed-overflow-{index}",
            processing_mode=ProcessingMode.FULL_SPEED,
            display_name=f"溢出任务 {index + 1}",
            data_package_id=f"package-overflow-{index}",
        )
        for index in range(6)
    ]
    panel.set_sessions(
        sessions,
        {
            session.session_id: FullSpeedExecutionState()
            for session in sessions
        },
    )
    panel.show()
    app.processEvents()

    vertical_bar = panel.scroll_area.verticalScrollBar()
    assert vertical_bar.maximum() > 0
    fluent_vertical_bar = panel.scroll_area.scrollDelagate.vScrollBar
    assert not vertical_bar.isVisible()
    assert fluent_vertical_bar.isVisible()
    first_card = panel._cards[sessions[0].session_id]
    card_right = first_card.mapTo(
        panel.scroll_area,
        first_card.rect().topRight(),
    ).x()
    scrollbar_left = fluent_vertical_bar.geometry().left()
    assert (
        scrollbar_left - card_right
        >= panel._SCROLLBAR_CARD_GAP
    )
    vertical_bar.setValue(vertical_bar.maximum())
    app.processEvents()

    assert vertical_bar.value() == vertical_bar.maximum()
    assert not panel.scroll_area.scrollDelagate.hScrollBar.isVisible()


def test_full_speed_tasks_calculate_columns_from_minimum_card_width() -> None:
    """全速任务应按最小卡片宽度扩展栏数，并保持 Session 顺序。"""
    app = _app()
    panel = FullSpeedSessionPanel()
    sessions = [
        ProcessingSession(
            session_id=f"fullspeed-responsive-{index}",
            processing_mode=ProcessingMode.FULL_SPEED,
            display_name=f"响应任务 {index + 1}",
            data_package_id=f"package-{index}",
        )
        for index in range(3)
    ]
    states = {
        session.session_id: FullSpeedExecutionState()
        for session in sessions
    }

    panel.resize(800, 500)
    panel.set_sessions(sessions, states)
    panel.show()
    app.processEvents()
    assert panel.column_count() == 1
    assert [
        panel.card_layout.getItemPosition(
            panel.card_layout.indexOf(panel._cards[session.session_id])
        )[:2]
        for session in sessions
    ] == [(0, 0), (1, 0), (2, 0)]

    panel.resize(1100, 500)
    app.processEvents()
    assert panel.column_count() == 2
    assert [
        panel.card_layout.getItemPosition(
            panel.card_layout.indexOf(panel._cards[session.session_id])
        )[:2]
        for session in sessions
    ] == [(0, 0), (0, 1), (1, 0)]

    panel.resize(1550, 500)
    app.processEvents()
    assert panel.column_count() == 3
    assert [
        panel.card_layout.getItemPosition(
            panel.card_layout.indexOf(panel._cards[session.session_id])
        )[:2]
        for session in sessions
    ] == [(0, 0), (0, 1), (0, 2)]
    assert all(
        panel._cards[session.session_id].width()
        >= panel._MIN_CARD_WIDTH
        for session in sessions
    )
