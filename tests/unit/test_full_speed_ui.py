"""全速 Session 创建选项与主页卡片状态测试。"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QWidget

from core.models.processing_session import ProcessingMode, ProcessingSession
from runtime.full_speed_session_registry import (
    FullSpeedExecutionState,
    FullSpeedStatus,
)
from ui.components.full_speed_session_panel import FullSpeedSessionPanel
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
