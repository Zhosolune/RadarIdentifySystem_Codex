"""主页全速处理 Session 面板。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    SimpleCardWidget,
    StrongBodyLabel,
    TransparentPushButton,
    setFont,
)

from core.models.processing_session import ProcessingSession
from runtime.full_speed_session_registry import (
    FullSpeedExecutionState,
    FullSpeedStatus,
)


_STATUS_TEXT = {
    FullSpeedStatus.CONFIGURING: "等待启动",
    FullSpeedStatus.RUNNING: "执行中",
    FullSpeedStatus.EXPORTING: "正在保存",
    FullSpeedStatus.SUCCEEDED: "已完成",
    FullSpeedStatus.FAILED: "失败",
    FullSpeedStatus.CANCELLED: "已取消",
    FullSpeedStatus.INTERRUPTED: "已中断",
}


class FullSpeedSessionCard(QFrame):
    """展示单个全速 Session 的参数冻结、进度和操作入口。

    Attributes:
        outputDirectoryRequested: 请求修改保存目录的信号。
        startRequested: 请求开始或重试的信号。
        cancelRequested: 请求取消的信号。
        deleteRequested: 请求删除 Session 的信号。
        openOutputRequested: 请求打开结果文件的信号。
    """

    outputDirectoryRequested = pyqtSignal(str)
    startRequested = pyqtSignal(str)
    cancelRequested = pyqtSignal(str)
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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        self.status_label = CaptionLabel("等待启动", self)
        self.status_label.setObjectName("fullSpeedSessionStatus")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(self.status_label)
        root_layout.addLayout(title_layout)

        self.source_label = CaptionLabel(
            f"数据包 {session.data_package_id or '未知'}",
            self,
        )
        self.source_label.setObjectName("fullSpeedSessionCaption")
        root_layout.addWidget(self.source_label)

        self.stage_label = BodyLabel("等待启动", self)
        self.stage_label.setObjectName("fullSpeedSessionStage")
        root_layout.addWidget(self.stage_label)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setObjectName("fullSpeedProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        root_layout.addWidget(self.progress_bar)

        self.message_label = CaptionLabel("", self)
        self.message_label.setObjectName("fullSpeedSessionCaption")
        self.message_label.setWordWrap(True)
        root_layout.addWidget(self.message_label)

        self.output_label = CaptionLabel("保存目录：未设置", self)
        self.output_label.setObjectName("fullSpeedSessionCaption")
        self.output_label.setWordWrap(True)
        root_layout.addWidget(self.output_label)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        self.output_button = PushButton("保存路径", self)
        self.start_button = PrimaryPushButton("开始", self)
        self.cancel_button = PushButton("取消", self)
        self.open_button = PushButton("打开结果", self)
        self.delete_button = PushButton("删除", self)
        for button in (
            self.output_button,
            self.cancel_button,
            self.open_button,
            self.delete_button,
        ):
            # 次要动作通过主页 QSS 清除组件库默认实色背景。
            button.setProperty("fullSpeedSecondaryAction", True)
        action_layout.addWidget(self.output_button)
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.open_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.delete_button)
        root_layout.addLayout(action_layout)

        self.output_button.clicked.connect(
            lambda: self.outputDirectoryRequested.emit(self.session_id)
        )
        self.start_button.clicked.connect(
            lambda: self.startRequested.emit(self.session_id)
        )
        self.cancel_button.clicked.connect(
            lambda: self.cancelRequested.emit(self.session_id)
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
        slice_text = (
            f" · 切片 {state.current_slice}/{state.total_slices}"
            if state.total_slices
            else ""
        )
        self.stage_label.setText(
            f"{state.current_stage}{slice_text} · {state.progress}%"
        )
        self.progress_bar.setValue(state.progress)
        self.message_label.setText(state.message)

        output_text = state.output_file or state.output_dir
        output_kind = "结果文件" if state.output_file else "保存目录"
        self.output_label.setText(
            f"{output_kind}：{output_text or '未设置'}"
        )

        running = state.status is FullSpeedStatus.RUNNING
        exporting = state.status is FullSpeedStatus.EXPORTING
        succeeded = state.status is FullSpeedStatus.SUCCEEDED
        self.output_button.setEnabled(
            not session.full_speed_locked and not running and not exporting
        )
        self.start_button.setEnabled(not running and not exporting and not succeeded)
        self.start_button.setText(
            "开始"
            if state.status is FullSpeedStatus.CONFIGURING
            else "重试"
        )
        # Excel 写入阶段不接受取消，避免原子替换完成后产生“已取消但文件存在”的歧义。
        self.cancel_button.setEnabled(running)
        self.open_button.setEnabled(bool(state.output_file))
        self.delete_button.setEnabled(not running and not exporting)


class FullSpeedSessionPanel(SimpleCardWidget):
    """展示多个可并发执行的全速 Session 卡片。

    Attributes:
        outputDirectoryRequested: 携带 Session ID 的保存目录请求。
        startRequested: 携带 Session ID 的开始请求。
        cancelRequested: 携带 Session ID 的取消请求。
        deleteRequested: 携带 Session ID 的删除请求。
        openOutputRequested: 携带 Session ID 的打开结果请求。
    """

    outputDirectoryRequested = pyqtSignal(str)
    startRequested = pyqtSignal(str)
    cancelRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)
    openOutputRequested = pyqtSignal(str)

    _MIN_CARD_WIDTH = 440

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
        title_label = BodyLabel("全速处理 Session", self)
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
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(0)

        self.session_pane = QWidget(self.body_widget)
        self.session_pane.setObjectName("homeFullSpeedSessionPane")
        self.session_pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        pane_layout = QVBoxLayout(self.session_pane)
        pane_layout.setContentsMargins(0, 0, 0, 0)
        pane_layout.setSpacing(0)

        self.scroll_area = ScrollArea(self.session_pane)
        self.scroll_area.setObjectName("homeFullSpeedScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.viewport().setObjectName("homeFullSpeedViewport")
        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setObjectName("homeFullSpeedContent")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(0)
        self.empty_label = BodyLabel(
            "从数据池创建“全速处理（自动）”Session",
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
        pane_layout.addWidget(self.scroll_area)
        body_layout.addWidget(self.session_pane)
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
                card.startRequested.connect(self.startRequested)
                card.cancelRequested.connect(self.cancelRequested)
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

    def _responsive_column_count(
        self,
        panel_width: int | None = None,
    ) -> int:
        """根据卡片最小宽度计算当前可容纳的栏数。"""
        spacing = max(0, self.card_layout.horizontalSpacing())
        if panel_width is None:
            panel_width = self.width()
        # 扣除面板主体、内容区边距和滚动条预留空间。
        available_width = max(0, panel_width - 48)
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
    ) -> None:
        """保持任务顺序并按当前断点重新放入网格。"""
        column_count = self._responsive_column_count(panel_width)
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
