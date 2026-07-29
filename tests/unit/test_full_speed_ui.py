"""全速 Session 创建选项与主页卡片状态测试。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget

from core.models.processing_session import ProcessingMode, ProcessingSession
from runtime.full_speed_session_registry import (
    FullSpeedExecutionState,
    FullSpeedStatus,
)
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
    assert card.cancel_button.isEnabled()
    assert not card.open_button.isEnabled()


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


def test_full_speed_panel_exposes_qss_scopes_for_transparent_layers() -> None:
    """全速面板应为滚动层、卡片和次要按钮提供独立 QSS 作用域。"""
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

    assert panel.scroll_area.objectName() == "homeFullSpeedScrollArea"
    assert panel.scroll_area.viewport().objectName() == "homeFullSpeedViewport"
    assert panel.body_widget.objectName() == "homeFullSpeedBody"
    assert panel.session_pane.objectName() == "homeFullSpeedSessionPane"
    assert panel.content_widget.objectName() == "homeFullSpeedContent"
    assert card.objectName() == "fullSpeedSessionCard"
    assert card.output_button.property("fullSpeedSecondaryAction") is True
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
        assert "QWidget#homeFullSpeedContent" in qss
        assert "QWidget#homeFullSpeedSessionPane" in qss
        assert "QFrame#fullSpeedSessionCard" in qss
        assert 'QPushButton[fullSpeedSecondaryAction="true"]' in qss


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
