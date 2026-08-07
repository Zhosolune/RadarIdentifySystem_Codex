"""主页全速处理 Session 面板。"""

from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEvent,
    QObject,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QResizeEvent
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    FluentIcon,
    IconInfoBadge,
    IndeterminateProgressRing,
    InfoLevel,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    SimpleCardWidget,
    StrongBodyLabel,
    setFont,
)

from core.models.processing_session import ProcessingSession
from runtime.full_speed_session_registry import (
    FullSpeedExecutionState,
    FullSpeedStatus,
)
from ui.components.scrolling_name_label import ScrollingNameLabel


_STATUS_TEXT = {
    FullSpeedStatus.CONFIGURING: "等待启动",
    FullSpeedStatus.RUNNING: "执行中",
    FullSpeedStatus.PAUSING: "正在暂停",
    FullSpeedStatus.PAUSED: "已暂停",
    FullSpeedStatus.RESTARTING: "正在重新执行",
    FullSpeedStatus.DELETING: "正在删除",
    FullSpeedStatus.EXPORTING: "正在保存",
    FullSpeedStatus.SUCCEEDED: "已完成",
    FullSpeedStatus.FAILED: "失败",
    FullSpeedStatus.INTERRUPTED: "已中断",
}

_START_ACTION_TEXT = {
    FullSpeedStatus.CONFIGURING: "开始",
    FullSpeedStatus.RUNNING: "执行中",
    FullSpeedStatus.PAUSING: "暂停中",
    FullSpeedStatus.PAUSED: "重新执行",
    FullSpeedStatus.RESTARTING: "重新执行中",
    FullSpeedStatus.DELETING: "删除中",
    FullSpeedStatus.EXPORTING: "保存中",
    FullSpeedStatus.SUCCEEDED: "已完成",
    FullSpeedStatus.FAILED: "重试",
    FullSpeedStatus.INTERRUPTED: "重试",
}

_STARTABLE_STATUSES = {
    FullSpeedStatus.CONFIGURING,
    FullSpeedStatus.FAILED,
    FullSpeedStatus.PAUSED,
    FullSpeedStatus.INTERRUPTED,
}

_SECONDARY_TEXT_COLORS = ("#606060", "#d2d2d2")

_STATUS_VISUALS = {
    FullSpeedStatus.CONFIGURING: (
        FluentIcon.INFO,
        InfoLevel.INFOAMTION,
        "#606060",
        "#d2d2d2",
    ),
    FullSpeedStatus.RUNNING: (
        FluentIcon.SYNC,
        InfoLevel.ATTENTION,
        "#0078d4",
        "#4cc2ff",
    ),
    FullSpeedStatus.PAUSING: (
        FluentIcon.SYNC,
        InfoLevel.WARNING,
        "#9d5d00",
        "#fce100",
    ),
    FullSpeedStatus.PAUSED: (
        FluentIcon.PAUSE,
        InfoLevel.WARNING,
        "#9d5d00",
        "#fce100",
    ),
    FullSpeedStatus.RESTARTING: (
        FluentIcon.SYNC,
        InfoLevel.ATTENTION,
        "#0078d4",
        "#4cc2ff",
    ),
    FullSpeedStatus.DELETING: (
        FluentIcon.SYNC,
        InfoLevel.WARNING,
        "#9d5d00",
        "#fce100",
    ),
    FullSpeedStatus.EXPORTING: (
        FluentIcon.SAVE,
        InfoLevel.WARNING,
        "#9d5d00",
        "#fce100",
    ),
    FullSpeedStatus.SUCCEEDED: (
        FluentIcon.ACCEPT,
        InfoLevel.SUCCESS,
        "#107c10",
        "#6ccb5f",
    ),
    FullSpeedStatus.FAILED: (
        FluentIcon.CANCEL_MEDIUM,
        InfoLevel.ERROR,
        "#c42b1c",
        "#ff99a4",
    ),
    FullSpeedStatus.INTERRUPTED: (
        FluentIcon.PAUSE,
        InfoLevel.WARNING,
        "#9d5d00",
        "#fce100",
    ),
}


class FullSpeedSessionCard(CardWidget):
    """展示单个全速 Session 的参数冻结、进度和操作入口。

    Attributes:
        outputDirectoryRequested: 请求修改保存目录的信号。
        parametersRequested: 请求修改 Session 参数快照的信号。
        startRequested: 请求开始或重试的信号。
        pauseRequested: 请求暂停或继续的信号。
        deleteRequested: 请求删除 Session 的信号。
        openOutputRequested: 请求打开结果文件的信号。
    """

    outputDirectoryRequested = pyqtSignal(str)
    parametersRequested = pyqtSignal(str)
    startRequested = pyqtSignal(str)
    pauseRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)
    openOutputRequested = pyqtSignal(str)

    def __init__(
        self,
        session: ProcessingSession,
        parent: QWidget | None = None,
    ) -> None:
        """初始化全速 Session 卡片。

        Args:
            session [ProcessingSession]: 当前卡片绑定的 Session。
            parent [QWidget | None]: 父组件。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.session_id = session.session_id
        self.setObjectName("fullSpeedSessionCard")
        self.setBorderRadius(8)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(7)

        title_layout = QHBoxLayout()
        self.title_label = StrongBodyLabel(session.display_name, self)
        self.title_label.setObjectName("fullSpeedSessionTitle")
        setFont(self.title_label, 16, QFont.Weight.DemiBold)
        self.status_badge = IconInfoBadge(
            FluentIcon.INFO,
            self,
            InfoLevel.INFOAMTION,
        )
        self.status_badge.setFixedSize(20, 20)
        self.status_badge.setIconSize(QSize(11, 11))
        self.status_spinner = IndeterminateProgressRing(self, start=False)
        self.status_spinner.setFixedSize(20, 20)
        self.status_spinner.setStrokeWidth(2)
        self.status_spinner.hide()
        self.status_label = StrongBodyLabel("等待启动", self)
        self.status_label.setObjectName("fullSpeedSessionStatus")
        setFont(self.status_label, 14, QFont.Weight.DemiBold)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.status_badge)
        title_layout.addWidget(self.status_spinner)
        title_layout.addWidget(self.status_label)
        root_layout.addLayout(title_layout)

        self.source_label = CaptionLabel(
            f"数据包 {session.data_package_id or '未知'}",
            self,
        )
        self.source_label.setObjectName("fullSpeedSessionCaption")
        self.source_label.setTextColor(*_SECONDARY_TEXT_COLORS)
        root_layout.addWidget(self.source_label)

        self.stage_label = BodyLabel("等待启动", self)
        self.stage_label.setObjectName("fullSpeedSessionStage")
        root_layout.addWidget(self.stage_label)

        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setObjectName("fullSpeedProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar, 1)
        self.progress_label = StrongBodyLabel("0%", self)
        self.progress_label.setObjectName("fullSpeedSessionProgress")
        self.progress_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.progress_label.setFixedWidth(
            self.progress_label.fontMetrics().horizontalAdvance("100%")
        )
        progress_layout.addWidget(self.progress_label)
        root_layout.addLayout(progress_layout)

        self.message_label = CaptionLabel("", self)
        self.message_label.setObjectName("fullSpeedSessionCaption")
        self.message_label.setTextColor(*_SECONDARY_TEXT_COLORS)
        self.message_label.setWordWrap(True)
        root_layout.addWidget(self.message_label)

        # 保存路径保持单行显示，超出任务卡片可用宽度后循环滚动。
        self.output_label = ScrollingNameLabel(
            "保存目录：未设置",
            max_width=None,
            parent=self,
            label_class=CaptionLabel,
            label_object_name="fullSpeedSessionCaption",
        )
        self.output_label.primary_label.setTextColor(*_SECONDARY_TEXT_COLORS)
        self.output_label.secondary_label.setTextColor(*_SECONDARY_TEXT_COLORS)
        root_layout.addWidget(self.output_label)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)
        self.output_button = PushButton("保存路径", self)
        self.params_button = PushButton("修改参数", self)
        self.start_button = PrimaryPushButton("开始", self)
        # 用组件库自身的 sizeHint 按最长状态文案计算按钮完整宽度。
        start_text = self.start_button.text()
        widest_action_text = max(
            _START_ACTION_TEXT.values(),
            key=self.start_button.fontMetrics().horizontalAdvance,
        )
        self.start_button.setText(widest_action_text)
        self.start_button.setFixedWidth(self.start_button.sizeHint().width())
        self.start_button.setText(start_text)
        self.pause_button = PushButton("暂停", self)
        self.open_button = PushButton("打开结果", self)
        self.delete_button = PushButton("删除", self)
        for button in (
            self.output_button,
            self.params_button,
            self.pause_button,
            self.open_button,
            self.delete_button,
        ):
            # 次要动作通过主页 QSS 清除组件库默认实色背景。
            button.setProperty("fullSpeedSecondaryAction", True)
        action_layout.addWidget(self.output_button)
        action_layout.addWidget(self.params_button)
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.pause_button)
        action_layout.addWidget(self.open_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.delete_button)
        root_layout.addLayout(action_layout)

        self.output_button.clicked.connect(
            lambda: self.outputDirectoryRequested.emit(self.session_id)
        )
        self.params_button.clicked.connect(
            lambda: self.parametersRequested.emit(self.session_id)
        )
        self.start_button.clicked.connect(
            lambda: self.startRequested.emit(self.session_id)
        )
        self.pause_button.clicked.connect(
            lambda: self.pauseRequested.emit(self.session_id)
        )
        self.delete_button.clicked.connect(
            lambda: self.deleteRequested.emit(self.session_id)
        )
        self.open_button.clicked.connect(
            lambda: self.openOutputRequested.emit(self.session_id)
        )

    def update_state(
        self,
        session: ProcessingSession,
        state: FullSpeedExecutionState,
    ) -> None:
        """按最新 Session 和执行状态刷新卡片。

        Args:
            session [ProcessingSession]: 最新 Session 元信息。
            state [FullSpeedExecutionState]: 最新执行状态。

        Returns:
            None: 无返回值。
        """
        self.title_label.setText(session.display_name)
        self.status_label.setText(_STATUS_TEXT[state.status])
        self._apply_status_visuals(state.status)
        slice_text = (
            f" · 切片 {state.current_slice}/{state.total_slices}"
            if state.total_slices
            else ""
        )
        self.stage_label.setText(f"{state.current_stage}{slice_text}")
        self.progress_bar.setValue(state.progress)
        self.progress_label.setText(f"{state.progress}%")
        self.message_label.setText(state.message)

        output_text = state.output_file or state.output_dir
        output_kind = "结果文件" if state.output_file else "保存目录"
        self.output_label.setText(
            f"{output_kind}：{output_text or '未设置'}"
        )

        running = state.status is FullSpeedStatus.RUNNING
        pausing = state.status is FullSpeedStatus.PAUSING
        paused = state.status is FullSpeedStatus.PAUSED
        restarting = state.status is FullSpeedStatus.RESTARTING
        deleting = state.status is FullSpeedStatus.DELETING
        exporting = state.status is FullSpeedStatus.EXPORTING
        settings_editable = not session.full_speed_locked or paused
        self.output_button.setEnabled(
            settings_editable
            and not running
            and not pausing
            and not restarting
            and not deleting
            and not exporting
        )
        self.params_button.setEnabled(
            settings_editable
            and not running
            and not pausing
            and not restarting
            and not deleting
            and not exporting
        )
        # 只有尚未启动或未成功结束的任务可以进入执行流程；成功任务由运行时禁止重启。
        self.start_button.setEnabled(state.status in _STARTABLE_STATUSES)
        self.start_button.setText(_START_ACTION_TEXT[state.status])
        # 暂停后只有未修改设置时可继续原 Worker；修改后必须重新执行。
        self.pause_button.setText(
            "继续" if paused else ("暂停中" if pausing else "暂停")
        )
        self.pause_button.setEnabled(
            running or (paused and not state.restart_required)
        )
        self.open_button.setEnabled(bool(state.output_file))
        self.delete_button.setEnabled(
            paused
            or not (
                running
                or pausing
                or restarting
                or deleting
                or exporting
            )
        )

    def _apply_status_visuals(self, status: FullSpeedStatus) -> None:
        """同步状态图标、文字颜色及组件库进度条状态。"""
        icon, level, light_color, dark_color = _STATUS_VISUALS[status]
        self.status_badge.setIcon(icon)
        self.status_badge.setLevel(level)
        if status in {
            FullSpeedStatus.RUNNING,
            FullSpeedStatus.PAUSING,
            FullSpeedStatus.RESTARTING,
            FullSpeedStatus.DELETING,
        }:
            self.status_badge.hide()
            self.status_spinner.setCustomBarColor(light_color, dark_color)
            self.status_spinner.show()
            if (
                self.status_spinner.aniGroup.state()
                is not QAbstractAnimation.State.Running
            ):
                self.status_spinner.start()
        else:
            self.status_spinner.stop()
            self.status_spinner.hide()
            self.status_badge.show()
        for label in (
            self.status_label,
            self.stage_label,
            self.progress_label,
        ):
            label.setTextColor(light_color, dark_color)

        # 先恢复默认状态和主题色，避免重试时继承上一状态的暂停色或成功色。
        self.progress_bar.resume()
        self.progress_bar.setCustomBarColor(QColor(), QColor())
        if status is FullSpeedStatus.SUCCEEDED:
            self.progress_bar.setCustomBarColor("#107c10", "#6ccb5f")
        elif status is FullSpeedStatus.FAILED:
            self.progress_bar.error()
        elif status in {
            FullSpeedStatus.EXPORTING,
            FullSpeedStatus.PAUSING,
            FullSpeedStatus.PAUSED,
            FullSpeedStatus.RESTARTING,
            FullSpeedStatus.DELETING,
            FullSpeedStatus.INTERRUPTED,
        }:
            self.progress_bar.pause()


class FullSpeedSessionPanel(SimpleCardWidget):
    """展示多个可并发执行的全速 Session 卡片。

    Attributes:
        outputDirectoryRequested: 携带 Session ID 的保存目录请求。
        parametersRequested: 携带 Session ID 的参数编辑请求。
        startRequested: 携带 Session ID 的开始请求。
        pauseRequested: 携带 Session ID 的暂停或继续请求。
        deleteRequested: 携带 Session ID 的删除请求。
        openOutputRequested: 携带 Session ID 的打开结果请求。
    """

    outputDirectoryRequested = pyqtSignal(str)
    parametersRequested = pyqtSignal(str)
    startRequested = pyqtSignal(str)
    pauseRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)
    openOutputRequested = pyqtSignal(str)

    _MIN_CARD_WIDTH = 500
    _SCROLLBAR_CARD_GAP = 8
    _SCROLLBAR_GUTTER_WIDTH = 10

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化全速 Session 面板。

        Args:
            parent [QWidget | None]: 父组件。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.setObjectName("homeFullSpeedSessionPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._cards: dict[str, FullSpeedSessionCard] = {}
        self._ordered_session_ids: list[str] = []
        self._column_count = 1

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 8, 8, 7)
        title_label = BodyLabel("全速处理", self)
        title_label.setObjectName("fullSpeedPanelTitle")
        title_label.setFixedHeight(34)
        setFont(title_label, 14)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        root_layout.addLayout(header_layout)

        separator = QWidget(self)
        separator.setObjectName("fullSpeedPanelSeparator")
        separator.setFixedHeight(1)
        separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root_layout.addWidget(separator)

        self.body_widget = QWidget(self)
        self.body_widget.setObjectName("homeFullSpeedBody")
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(10, 10, 0, 10)
        body_layout.setSpacing(0)

        # 为组件库默认浮动滚动条预留独立沟槽，避免覆盖任务卡片。
        self.scroll_area = ScrollArea(self.body_widget)
        self.scroll_area.setObjectName("homeFullSpeedScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setViewportMargins(
            0,
            0,
            self._SCROLLBAR_GUTTER_WIDTH,
            0,
        )
        self.scroll_area.viewport().setObjectName("homeFullSpeedViewport")
        self.scroll_area.viewport().installEventFilter(self)

        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setObjectName("homeFullSpeedContent")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.empty_label = BodyLabel(
            "从数据池创建全速处理Session",
            self.content_widget,
        )
        self.empty_label.setObjectName("homeFullSpeedEmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.empty_label, 1)

        self.cards_widget = QWidget(self.content_widget)
        self.cards_widget.setObjectName("homeFullSpeedCards")
        self.card_layout = QGridLayout(self.cards_widget)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setHorizontalSpacing(8)
        self.card_layout.setVerticalSpacing(8)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.addWidget(self.cards_widget, 1)
        self.scroll_area.setWidget(self.content_widget)
        self.scroll_area.enableTransparentBackground()
        body_layout.addWidget(self.scroll_area)
        root_layout.addWidget(self.body_widget, 1)

    def set_sessions(
        self,
        sessions: list[ProcessingSession],
        states: dict[str, FullSpeedExecutionState],
        *,
        selected_session_id: str | None = None,
    ) -> None:
        """刷新全速 Session 卡片。

        Args:
            sessions [list[ProcessingSession]]: 全速 Session 列表。
            states [dict[str, FullSpeedExecutionState]]: Session ID 到执行状态的映射。
            selected_session_id [str | None]: 兼容主页刷新调用的优先 ID，
                卡片视图会同时展示全部 Session。

        Returns:
            None: 无返回值。
        """
        del selected_session_id
        self._ordered_session_ids = [
            session.session_id
            for session in sessions
        ]
        session_ids = {session.session_id for session in sessions}
        for session_id in list(self._cards):
            if session_id in session_ids:
                continue
            card = self._cards.pop(session_id)
            card.deleteLater()

        for session in sessions:
            card = self._cards.get(session.session_id)
            if card is None:
                card = FullSpeedSessionCard(session, self.cards_widget)
                card.outputDirectoryRequested.connect(
                    self.outputDirectoryRequested
                )
                card.parametersRequested.connect(self.parametersRequested)
                card.startRequested.connect(self.startRequested)
                card.pauseRequested.connect(self.pauseRequested)
                card.deleteRequested.connect(self.deleteRequested)
                card.openOutputRequested.connect(self.openOutputRequested)
                self._cards[session.session_id] = card
            card.update_state(
                session,
                states.get(
                    session.session_id,
                    FullSpeedExecutionState(),
                ),
            )

        self.empty_label.setVisible(not sessions)
        self.cards_widget.setVisible(bool(sessions))
        self._relayout_cards(force=True)

    def column_count(self) -> int:
        """返回当前任务网格列数。

        Returns:
            int: 按当前可用宽度和卡片最小宽度计算出的栏数。
        """
        return self._column_count

    def resizeEvent(self, event: QResizeEvent) -> None:
        """在面板宽度变化时重新计算任务网格栏数。"""
        super().resizeEvent(event)
        if hasattr(self, "card_layout"):
            self._relayout_cards(panel_width=event.size().width())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """按滚动视口实际宽度修正任务栏数。

        Args:
            watched [QObject]: 当前被监听对象。
            event [QEvent]: Qt 事件。

        Returns:
            bool: 父类事件过滤结果。
        """
        if (
            hasattr(self, "scroll_area")
            and watched is self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
            and hasattr(self, "card_layout")
        ):
            self._relayout_cards(viewport_width=event.size().width())
        return super().eventFilter(watched, event)

    def _responsive_column_count(
        self,
        panel_width: int | None = None,
        viewport_width: int | None = None,
    ) -> int:
        """根据卡片最小宽度计算当前可容纳的栏数。"""
        spacing = max(0, self.card_layout.horizontalSpacing())
        if viewport_width is not None:
            available_width = max(0, viewport_width)
        else:
            if panel_width is None:
                panel_width = self.width()
            # 视口建立前先预估，建立后由 viewport Resize 精确修正。
            available_width = max(
                0,
                panel_width
                - 12
                - self._SCROLLBAR_GUTTER_WIDTH,
            )
        return max(
            1,
            (available_width + spacing)
            // (self._MIN_CARD_WIDTH + spacing),
        )

    def _relayout_cards(
        self,
        *,
        force: bool = False,
        panel_width: int | None = None,
        viewport_width: int | None = None,
    ) -> None:
        """保持任务顺序并按当前断点重新放入网格。"""
        column_count = self._responsive_column_count(
            panel_width,
            viewport_width,
        )
        if not force and column_count == self._column_count:
            return
        previous_column_count = self._column_count
        self._column_count = column_count

        while self.card_layout.count():
            self.card_layout.takeAt(0)
        for column in range(max(previous_column_count, column_count)):
            self.card_layout.setColumnStretch(
                column,
                1 if column < column_count else 0,
            )
        for index, session_id in enumerate(self._ordered_session_ids):
            card = self._cards.get(session_id)
            if card is None:
                continue
            self.card_layout.addWidget(
                card,
                index // column_count,
                index % column_count,
            )
