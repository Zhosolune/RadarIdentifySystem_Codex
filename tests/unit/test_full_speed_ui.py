"""全速 Session 创建选项与主页卡片状态测试。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QAbstractAnimation, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    FluentIcon,
    IconInfoBadge,
    IndeterminateProgressRing,
    InfoLevel,
    PrimaryPushButton,
    ScrollArea,
    TextEdit,
)
from pytest import MonkeyPatch

from core.models.processing_session import ProcessingMode, ProcessingSession
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
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
    """创建窗口应优先选择处理方式并使用 Fluent 富文本备注框。"""
    _app()
    parent = QWidget()
    dialog = CreateSessionDialog("demo.xlsx", parent)
    hint_labels = {
        label.text(): label
        for label in dialog.findChildren(BodyLabel)
    }

    assert isinstance(dialog.remark_text_edit, TextEdit)
    assert dialog.remark_text_edit.acceptRichText()
    assert (
        dialog.viewLayout.indexOf(hint_labels["请选择 Session 处理方式"])
        < dialog.viewLayout.indexOf(hint_labels["请输入 Session 名称"])
        < dialog.viewLayout.indexOf(hint_labels["请输入备注信息"])
    )
    assert dialog.get_processing_mode() is ProcessingMode.SLICE_INTERACTIVE
    dialog.full_speed_radio.setChecked(True)
    assert dialog.get_processing_mode() is ProcessingMode.FULL_SPEED


def test_full_speed_card_locks_configuration_and_shows_progress() -> None:
    """任务开始后保存路径应锁定，卡片应展示切片与总进度。"""
    app = _app()
    panel = FullSpeedSessionPanel()
    panel.resize(620, 500)
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
    panel.show()
    app.processEvents()
    card = panel._cards[session.session_id]

    assert card.progress_bar.value() == 37
    assert "切片 2/5" in card.stage_label.text()
    assert "%" not in card.stage_label.text()
    assert card.progress_label.text() == "37%"
    assert card.progress_label.x() > card.progress_bar.x()
    assert card.title_label.font().pixelSize() == 16
    assert card.status_label.font().pixelSize() == 14
    assert card.status_label.font().weight() == QFont.Weight.DemiBold
    assert card.status_badge.size().width() == 20
    assert card.status_spinner.size().width() == 20
    assert card.source_label.lightColor == QColor("#606060")
    assert card.source_label.darkColor == QColor("#d2d2d2")
    assert card.message_label.lightColor == QColor("#606060")
    assert card.output_label.primary_label.darkColor == QColor("#d2d2d2")
    assert not card.output_button.isEnabled()
    assert not card.params_button.isEnabled()
    assert card.cancel_button.isEnabled()
    assert not card.open_button.isEnabled()


def test_full_speed_card_maps_status_to_badge_text_and_progress_state() -> None:
    """卡片应通过徽标、文字色和进度条状态区分全部执行状态。"""
    _app()
    panel = FullSpeedSessionPanel()
    session = ProcessingSession(
        session_id="fullspeed-status-visual",
        processing_mode=ProcessingMode.FULL_SPEED,
        display_name="状态视觉任务",
        data_package_id="package-status-visual",
    )
    expected_visuals = {
        FullSpeedStatus.CONFIGURING: (
            FluentIcon.INFO,
            InfoLevel.INFOAMTION,
            "#606060",
            False,
            False,
        ),
        FullSpeedStatus.RUNNING: (
            FluentIcon.SYNC,
            InfoLevel.ATTENTION,
            "#0078d4",
            False,
            False,
        ),
        FullSpeedStatus.EXPORTING: (
            FluentIcon.SAVE,
            InfoLevel.WARNING,
            "#9d5d00",
            True,
            False,
        ),
        FullSpeedStatus.SUCCEEDED: (
            FluentIcon.ACCEPT,
            InfoLevel.SUCCESS,
            "#107c10",
            False,
            False,
        ),
        FullSpeedStatus.FAILED: (
            FluentIcon.CANCEL_MEDIUM,
            InfoLevel.ERROR,
            "#c42b1c",
            False,
            True,
        ),
        FullSpeedStatus.CANCELLED: (
            FluentIcon.CANCEL_MEDIUM,
            InfoLevel.WARNING,
            "#9d5d00",
            True,
            False,
        ),
        FullSpeedStatus.INTERRUPTED: (
            FluentIcon.PAUSE,
            InfoLevel.WARNING,
            "#9d5d00",
            True,
            False,
        ),
    }

    for status, (
        icon,
        level,
        light_color,
        is_paused,
        is_error,
    ) in expected_visuals.items():
        panel.set_sessions(
            [session],
            {
                session.session_id: FullSpeedExecutionState(
                    status=status,
                    progress=58,
                )
            },
        )
        card = panel._cards[session.session_id]

        assert isinstance(card.status_badge, IconInfoBadge)
        assert isinstance(card.status_spinner, IndeterminateProgressRing)
        assert card.status_badge._icon is icon
        assert card.status_badge.level is level
        assert card.status_label.lightColor == QColor(light_color)
        assert card.stage_label.lightColor == QColor(light_color)
        assert card.progress_label.lightColor == QColor(light_color)
        assert card.progress_bar.isPaused() is is_paused
        assert card.progress_bar.isError() is is_error

        if status is FullSpeedStatus.RUNNING:
            assert card.status_badge.isHidden()
            assert not card.status_spinner.isHidden()
            assert (
                card.status_spinner.aniGroup.state()
                is QAbstractAnimation.State.Running
            )
            assert card.status_spinner.lightBarColor() == QColor(light_color)
            initial_angles = (
                card.status_spinner.startAngle,
                card.status_spinner.spanAngle,
            )
            QTest.qWait(80)
            assert (
                card.status_spinner.startAngle,
                card.status_spinner.spanAngle,
            ) != initial_angles
            angles_before_refresh = (
                card.status_spinner.startAngle,
                card.status_spinner.spanAngle,
            )
            card.update_state(
                session,
                FullSpeedExecutionState(status=FullSpeedStatus.RUNNING),
            )
            assert (
                card.status_spinner.startAngle,
                card.status_spinner.spanAngle,
            ) == angles_before_refresh
        else:
            assert not card.status_badge.isHidden()
            assert card.status_spinner.isHidden()
            assert (
                card.status_spinner.aniGroup.state()
                is QAbstractAnimation.State.Stopped
            )
            assert card.status_spinner.startAngle == 0
            assert card.status_spinner.spanAngle == 0

        if status is FullSpeedStatus.SUCCEEDED:
            assert card.progress_bar.lightBarColor() == QColor("#107c10")
            assert card.progress_bar.darkBarColor() == QColor("#6ccb5f")


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


def test_full_speed_params_window_edits_isolated_two_column_draft(
    monkeypatch: MonkeyPatch,
) -> None:
    """全速参数窗口左列首位应编辑并提交独立参数与模型草稿。"""
    app = _app()
    enabled_models = {
        "PA": ["E:/models/pa-a.onnx", "E:/models/pa-b.onnx"],
        "DTOA": [
            "E:/models/dtoa-a.onnx",
            "E:/models/dtoa-b.onnx",
        ],
    }
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_enabled_model_paths",
        lambda model_type: list(enabled_models[model_type]),
    )
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_display_name",
        lambda path, model_type: Path(path).stem,
    )
    source_snapshot = SessionConfigSnapshot.default()
    source_snapshot.clustering.eps_cf = 3.25
    source_selection = SessionModelSelection(
        pa_model_path=enabled_models["PA"][0],
        dtoa_model_path=enabled_models["DTOA"][0],
    )
    window = FullSpeedParamsWindow(
        "fullspeed-params-window",
        "两栏参数任务",
        source_snapshot,
        source_selection,
    )
    submitted: list[tuple[SessionConfigSnapshot, SessionModelSelection]] = []
    window.settingsSaved.connect(
        lambda snapshot, selection: submitted.append(
            (snapshot, selection)
        )
    )

    window.show()
    app.processEvents()

    assert len(window.parameter_items) == 25
    assert window.left_column_widget.layout().itemAt(0).widget() is (
        window.model_selection_card
    )
    assert window.model_selection_card.parent() is window.left_column_widget
    assert window.cluster_group.parent() is window.left_column_widget
    assert window.extract_pri_group.parent() is window.left_column_widget
    assert window.recognition_group.parent() is window.right_column_widget
    assert window.extract_cf_group.parent() is window.right_column_widget
    assert window.extract_pw_group.parent() is window.right_column_widget
    assert window.merge_group.parent() is window.right_column_widget
    assert window.left_column_widget.width() == window.right_column_widget.width()

    eps_cf_card = window.parameter_cards["clustering.eps_cf"]
    eps_cf_card.spinBox.setValue(4.75)
    window.model_selection_card.pa_model_combo.setCurrentIndex(1)
    window.model_selection_card.dtoa_model_combo.setCurrentIndex(1)
    app.processEvents()

    assert source_snapshot.clustering.eps_cf == 3.25
    assert source_selection.pa_model_path == enabled_models["PA"][0]
    assert source_selection.dtoa_model_path == enabled_models["DTOA"][0]
    assert window.snapshot().clustering.eps_cf == 4.75
    assert window.model_selection().pa_model_path == enabled_models["PA"][1]
    assert (
        window.model_selection().dtoa_model_path
        == enabled_models["DTOA"][1]
    )

    window.save_button.click()
    assert len(submitted) == 1
    assert submitted[0][0].clustering.eps_cf == 4.75
    assert submitted[0][1].pa_model_path == enabled_models["PA"][1]
    assert submitted[0][1].dtoa_model_path == enabled_models["DTOA"][1]
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
