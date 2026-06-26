"""主页 session 管理面板。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    AdaptiveFlowLayout,
    BodyLabel,
    CaptionLabel,
    CommandBar,
    FluentIcon,
    PrimaryPushButton,
    SimpleCardWidget,
    ToolTipFilter,
    ToolTipPosition,
    TransparentPushButton,
)
from qfluentwidgets.common.font import setFont

from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from ui.components.card_navigation_list import CardNavigationList
from ui.components.import_dashboard_panel import DashboardCard, DashboardMetric, format_dashboard_duration


class SessionManagerPanel(SimpleCardWidget):
    """展示当前运行期 session 的卡片式管理面板。

    面板内部为标题栏 + 内容区结构；内容区使用左右两栏布局展示
    session 导航列表与详情区域。左侧卡片点击只负责选中和刷新详情，
    不直接触发页面跳转；详情区中的动作通过信号交给上层控制。

    Attributes:
        sessionSelected: 请求切换当前详情展示的 session 信号。
        sessionEnableRequested: 请求启用指定 session 页面的信号。
        sessionCloseRequested: 请求关闭指定 session 的信号。
        sessionRenameRequested: 请求重命名指定 session 的信号。
        sessionDeleteRequested: 请求删除指定 session 的信号。
        sessionJumpRequested: 请求跳转到指定 session 页面的信号。
        session_nav: 左侧卡片导航列表。
        session_detail_placeholder: 右侧空状态占位标签。
    """

    sessionSelected = pyqtSignal(str)
    sessionEnableRequested = pyqtSignal(str)
    sessionCloseRequested = pyqtSignal(str)
    sessionRenameRequested = pyqtSignal(str)
    sessionDeleteRequested = pyqtSignal(str)
    sessionJumpRequested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化 session 管理面板。

        Args:
            parent: 父组件，默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.session_titles()
            []
        """
        super().__init__(parent)
        self.setObjectName("sessionManagerPanel")
        self._sessions: list[ProcessingSession] = []
        self._session_map: dict[str, ProcessingSession] = {}
        self._selected_session_id: str | None = None
        self._enabled_session_ids: set[str] = set()
        self._metric_cards: list[DashboardCard] = []

        # 创建标题标签。
        self.session_title_label = BodyLabel("Session 管理", self)
        self.session_title_label.setObjectName("sessionManagerTitleLabel")
        setFont(self.session_title_label, 14)

        # 创建透明按钮。
        self.create_session_button = TransparentPushButton("新建", self, FluentIcon.ADD)
        self.create_session_button.setObjectName("createSessionButton")
        self.create_session_button.setFixedHeight(34)
        self.create_session_button.setToolTip("新建空白 Session")
        self.create_session_button.installEventFilter(
            ToolTipFilter(self.create_session_button, 500, ToolTipPosition.TOP)
        )

        # 创建标题分隔线。
        self.session_header_separator = QWidget(self)
        self.session_header_separator.setObjectName("sessionManagerSeparator")
        self.session_header_separator.setFixedHeight(1)
        self.session_header_separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        # 创建左侧 session 导航列表。
        self.session_nav = CardNavigationList(self)
        self.session_nav.setObjectName("sessionNavigationList")
        self.session_nav.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # 创建右侧详情容器。
        self._detail_widget = QWidget(self)
        self._detail_widget.setObjectName("sessionDetailPane")
        self._detail_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._detail_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # 创建右侧详情占位标签。
        self.session_detail_placeholder = BodyLabel("请选择一个 Session 查看详情", self._detail_widget)
        self.session_detail_placeholder.setObjectName("sessionDetailPlaceholder")
        self.session_detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 创建详情命令栏。
        self.session_command_bar = CommandBar(self._detail_widget)
        self.session_command_bar.setObjectName("sessionDetailCommandBar")
        self.session_command_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.session_command_bar.setButtonTight(True)
        self.enable_action = Action(FluentIcon.ACCEPT, "启用")
        self.close_action = Action(FluentIcon.CLOSE, "关闭")
        self.edit_remark_action = Action(FluentIcon.EDIT, "编辑备注")
        self.rename_action = Action(FluentIcon.EDIT, "编辑信息")
        self.delete_action = Action(FluentIcon.DELETE, "删除")
        self.delete_action.setProperty("danger", True)
        self.session_command_bar.addActions(
            [
                self.enable_action,
                self.close_action,
                self.rename_action,
                self.delete_action,
            ]
        )
        self.session_command_bar.setMenuDropDown(False)
        self.session_command_bar.resizeToSuitableWidth()

        # 创建详情内容容器。
        self._detail_content = QWidget(self._detail_widget)
        self._detail_content.setObjectName("sessionDetailContent")
        self._detail_metrics_widget = QWidget(self._detail_content)
        self._detail_metrics_widget.setObjectName("sessionDetailMetrics")
        self._detail_info_widget = QWidget(self._detail_content)
        self._detail_info_widget.setObjectName("sessionDetailInfoPanel")

        self._detail_name_label = BodyLabel("数据包信息", self._detail_content)
        self._detail_name_label.setObjectName("sessionDetailName")
        setFont(self._detail_name_label, 16)

        self._session_id_value_label = CaptionLabel("--", self._detail_info_widget)
        self._file_name_value_label = CaptionLabel("--", self._detail_info_widget)
        self._file_size_value_label = CaptionLabel("--", self._detail_info_widget)
        self._file_path_value_label = CaptionLabel("--", self._detail_info_widget)
        self._remark_value_label = CaptionLabel("无", self._detail_info_widget)
        self._file_path_value_label.setWordWrap(True)
        self._remark_value_label.setWordWrap(True)

        # 创建右下角跳转按钮。
        self.jump_button = PrimaryPushButton(FluentIcon.PLAY, "跳转到 Session", self._detail_content)
        self.jump_button.setObjectName("sessionJumpButton")
        self.jump_button.setFixedHeight(34)

        self._root_layout = QVBoxLayout(self)
        self._header_layout = QHBoxLayout()
        self._content_layout = QHBoxLayout()
        self._detail_layout = QVBoxLayout(self._detail_widget)

        # 组装面板布局。
        self._init_widget()
        # 连接卡片选择与详情动作信号。
        self._connect_signals()
        # 初始化空状态详情。
        self._update_action_states(None)
        self._show_placeholder(True)

    def _init_widget(self) -> None:
        """初始化面板布局。"""
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # 标题栏布局。
        self._header_layout.setContentsMargins(20, 8, 8, 7)
        self._header_layout.setSpacing(8)
        self._header_layout.addWidget(self.session_title_label)
        self._header_layout.addStretch(1)
        self._header_layout.addWidget(self.create_session_button)

        # 内容区双栏布局。
        self._content_layout.setContentsMargins(8, 7, 8, 8)
        self._content_layout.setSpacing(8)

        # 详情区布局。
        self._detail_layout.setContentsMargins(8, 8, 8, 8)
        self._detail_layout.setSpacing(8)
        self._detail_layout.addWidget(self.session_command_bar, 0, Qt.AlignmentFlag.AlignLeft)
        self._detail_layout.addWidget(self.session_detail_placeholder, 1)
        self._detail_layout.addWidget(self._detail_content, 1)

        # 组装指标卡区域，使用自适应流式布局按行均分卡片宽度。
        self._metrics_layout = AdaptiveFlowLayout(
            self._detail_metrics_widget, needAni=True, isTight=True
        )
        self._metrics_layout.setContentsMargins(3, 8, 3, 8)
        self._metrics_layout.setHorizontalSpacing(10)
        self._metrics_layout.setVerticalSpacing(10)
        self._metrics_layout.setWidgetMinimumWidth(110)

        # 文件详情区域。
        info_layout = QVBoxLayout(self._detail_info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(5)
        info_layout.addWidget(self._create_info_row("Session ID", self._session_id_value_label))
        info_layout.addWidget(self._create_info_row("文件名", self._file_name_value_label))
        info_layout.addWidget(self._create_info_row("文件大小", self._file_size_value_label))
        info_layout.addWidget(self._create_info_row("文件路径", self._file_path_value_label))
        info_layout.addWidget(self._create_info_row("备注信息", self._remark_value_label))

        # 跳转按钮布局。
        jump_layout = QHBoxLayout()
        jump_layout.setContentsMargins(0, 0, 0, 0)
        jump_layout.addStretch(1)
        jump_layout.addWidget(self.jump_button, 0, Qt.AlignmentFlag.AlignRight)

        # 详情内容布局。
        detail_content_layout = QVBoxLayout(self._detail_content)
        detail_content_layout.setContentsMargins(10, 0, 10, 0)
        detail_content_layout.setSpacing(8)
        detail_content_layout.addWidget(self._detail_name_label)
        detail_content_layout.addWidget(self._detail_metrics_widget)
        detail_content_layout.addWidget(self._detail_info_widget)
        detail_content_layout.addStretch(1)
        detail_content_layout.addLayout(jump_layout)

        # 按“标题栏 + 分隔线 + 内容区”顺序挂接布局。
        self._root_layout.addLayout(self._header_layout)
        self._root_layout.addWidget(self.session_header_separator)
        self._content_layout.addWidget(self.session_nav, 2)
        self._content_layout.addWidget(self._detail_widget, 5)
        self._root_layout.addLayout(self._content_layout, 1)

    def _connect_signals(self) -> None:
        """连接卡片选择和详情动作信号。"""
        # 响应卡片选中切换详情，不直接触发页面跳转。
        self.session_nav.itemSelected.connect(self._on_session_selected)
        # 发射启用动作信号。
        self.enable_action.triggered.connect(
            lambda _checked=False: self._emit_action_for_selected(self.sessionEnableRequested)
        )
        # 发射关闭动作信号。
        self.close_action.triggered.connect(
            lambda _checked=False: self._emit_action_for_selected(self.sessionCloseRequested)
        )
        # 发射备注编辑动作信号。
        self.edit_remark_action.triggered.connect(
            lambda _checked=False: self._emit_action_for_selected(self.sessionRemarkEditRequested)
        )
        # 发射重命名动作信号。
        self.rename_action.triggered.connect(
            lambda _checked=False: self._emit_action_for_selected(self.sessionRenameRequested)
        )
        # 发射删除动作信号。
        self.delete_action.triggered.connect(
            lambda _checked=False: self._emit_action_for_selected(self.sessionDeleteRequested)
        )
        # 发射跳转动作信号。
        self.jump_button.clicked.connect(
            lambda _checked=False: self._emit_action_for_selected(self.sessionJumpRequested)
        )

    def _create_info_row(self, title: str, value_label: BodyLabel) -> QWidget:
        """创建一个“标题：值”同排显示的详情行。"""
        row = QWidget(self._detail_info_widget)
        row.setObjectName("sessionDetailInfoRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 创建字段标题。
        title_label = CaptionLabel(f"{title}：", row)
        title_label.setObjectName("sessionDetailInfoTitle")
        title_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        title_label.setFixedWidth(72)
        # 组装字段标题和值。
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(value_label, 1, Qt.AlignmentFlag.AlignTop)
        return row

    def set_sessions(
        self,
        sessions: list[ProcessingSession],
        selected_session_id: str | None = None,
        enabled_session_ids: set[str] | None = None,
    ) -> None:
        """刷新 session 卡片列表并同步右侧详情。

        Args:
            sessions: 需要显示的 session 列表。
            selected_session_id: 刷新后优先选中的 session id，默认保留当前选中项。
            enabled_session_ids: 当前已启用切片页面的 session id 集合。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.set_sessions([])
            >>> panel.session_titles()
            []
        """
        # 缓存当前 session 列表和索引映射。
        self._sessions = list(sessions)
        self._session_map = {session.session_id: session for session in self._sessions}
        self._enabled_session_ids = set(enabled_session_ids or set())

        # 清空旧导航项。
        self.session_nav.clear_items()

        for session in self._sessions:
            # 追加新的 session 导航项。
            self.session_nav.add_item(
                session.session_id,
                session.display_name,
                self._format_created_at(session.created_at),
            )

        if not self._sessions:
            # 切回空状态详情。
            self._selected_session_id = None
            self._update_detail(None)
            return

        # 优先恢复指定选中项，其次保留旧选中项，最后退回到第一个 session。
        target_session_id = selected_session_id or self._selected_session_id
        if target_session_id not in self._session_map:
            target_session_id = self._sessions[0].session_id

        self.session_nav.set_current_key(target_session_id)

    def set_selected_session(self, session_id: str | None) -> None:
        """设置当前详情展示的 session。

        Args:
            session_id: 需要展示详情的 session id；为 None 时清空详情。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: 当传入的 session_id 不在当前列表中时抛出。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.set_sessions([])
            >>> panel.set_selected_session(None)
        """
        if session_id is None:
            # 切回空状态详情。
            self._selected_session_id = None
            self._update_detail(None)
            return

        if session_id not in self._session_map:
            raise KeyError(session_id)

        self.session_nav.set_current_key(session_id)

    def current_session_id(self) -> str | None:
        """返回当前详情展示的 session id。

        Args:
            无。

        Returns:
            str | None: 当前详情选中的 session id；未选中时返回 None。

        Raises:
            无显式抛出异常。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.current_session_id() is None
            True
        """
        return self._selected_session_id

    def session_titles(self) -> list[str]:
        """返回当前显示的 session 标题。

        Args:
            无。

        Returns:
            list[str]: 当前面板持有的 session 展示标题。

        Raises:
            无显式抛出异常。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.session_titles()
            []
        """
        return [session.display_name for session in self._sessions]

    def _on_session_selected(self, session_id: str) -> None:
        """响应卡片选中并刷新详情。"""
        self._selected_session_id = session_id
        # 刷新当前选中 session 的详情数据。
        self._update_detail(self._session_map.get(session_id))
        # 发射详情选中变化信号。
        self.sessionSelected.emit(session_id)

    def _emit_action_for_selected(self, signal) -> None:
        """对当前选中 session 发射动作信号。"""
        if self._selected_session_id is None:
            return
        signal.emit(self._selected_session_id)

    def _update_detail(self, session: ProcessingSession | None) -> None:
        """按当前选中 session 刷新详情显示。"""
        has_session = session is not None
        # 切换空状态占位和详情内容显隐。
        self._show_placeholder(not has_session)
        # 同步动作控件启用状态。
        self._update_action_states(session)

        if not has_session:
            # 清空详情内容。
            self._detail_name_label.setText("数据包信息")
            self._session_id_value_label.setText("--")
            self._file_name_value_label.setText("--")
            self._file_size_value_label.setText("--")
            self._file_path_value_label.setText("--")
            self._remark_value_label.setText("无")
            self._refresh_metric_cards(self._build_empty_metrics())
            return

        file_path = Path(session.source_path) if session.source_path else None
        # 保持固定标题，仅刷新基础文件信息。
        self._detail_name_label.setText("数据包信息")
        # 刷新 session_id。
        self._session_id_value_label.setText(session.session_id)
        # 刷新基础文件信息。
        self._file_name_value_label.setText(file_path.name if file_path else "--")
        self._file_size_value_label.setText(self._format_source_file_size(file_path))
        self._file_path_value_label.setText(session.source_path or "--")
        self._remark_value_label.setText(self._session_remark_text(session))
        # 重建导入仪表盘指标卡。
        self._refresh_metric_cards(self._build_metrics(session))

    def _show_placeholder(self, visible: bool) -> None:
        """切换详情区空状态显示。"""
        self.session_detail_placeholder.setVisible(visible)
        self._detail_content.setVisible(not visible)

    def _update_action_states(self, session: ProcessingSession | None) -> None:
        """按选中 session 的启用状态刷新动作文案与禁用态。"""
        if session is None:
            self.enable_action.setText("启用")
            self.close_action.setText("关闭")
            self.enable_action.setEnabled(False)
            self.close_action.setEnabled(False)
            self.rename_action.setEnabled(False)
            self.delete_action.setEnabled(False)
            self.jump_button.setEnabled(False)
            return

        is_enabled = session.session_id in self._enabled_session_ids
        # 已启用的 session 不再重复启用，未启用的 session 不允许重复关闭。
        self.enable_action.setText("已启用" if is_enabled else "启用")
        self.close_action.setText("关闭" if is_enabled else "已关闭")
        self.enable_action.setEnabled(not is_enabled)
        self.close_action.setEnabled(is_enabled)
        self.rename_action.setEnabled(True)
        self.delete_action.setEnabled(True)
        self.jump_button.setEnabled(is_enabled)

    def _build_metrics(self, session: ProcessingSession) -> list[DashboardMetric]:
        """构建当前 session 的导入仪表盘指标。"""
        dashboard_info = session.dashboard_info
        if not isinstance(dashboard_info, ExcelDashboardInfo):
            return self._build_empty_metrics()

        return [
            DashboardMetric("总脉冲", str(dashboard_info.total_pulses)),
            DashboardMetric("剔除脉冲", str(dashboard_info.removed_pulses)),
            DashboardMetric("幅度丢弃", str(dashboard_info.amplitude_dropped_pulses)),
            DashboardMetric("持续时间", format_dashboard_duration(dashboard_info.duration)),
            DashboardMetric("波段", dashboard_info.band or "--"),
            DashboardMetric("预计切片数", str(dashboard_info.estimated_slice_count)),
        ]

    def _build_empty_metrics(self) -> list[DashboardMetric]:
        """构建空状态仪表盘指标。"""
        return [
            DashboardMetric("总脉冲", "--"),
            DashboardMetric("剔除脉冲", "--"),
            DashboardMetric("幅度丢弃", "--"),
            DashboardMetric("持续时间", "--"),
            DashboardMetric("波段", "--"),
            DashboardMetric("预计切片数", "--"),
        ]

    def _refresh_metric_cards(self, metrics: list[DashboardMetric]) -> None:
        """重建详情区中的仪表盘卡片，宽度交给 AdaptiveFlowLayout 按行均分。"""
        # 清空旧卡片。
        for card in self._metric_cards:
            self._metrics_layout.removeWidget(card)
            card.deleteLater()
        self._metric_cards.clear()

        # 创建卡片并加入流式布局，宽度由布局按行均分。
        for metric in metrics:
            card = DashboardCard(metric, self._detail_metrics_widget)
            self._metric_cards.append(card)
            self._metrics_layout.addWidget(card)

    def _format_source_file_size(self, file_path: Path | None) -> str:
        """格式化源文件大小文本。"""
        if file_path is None or not file_path.exists():
            return "未知"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(max(file_path.stat().st_size, 0))
        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _session_remark_text(self, session: ProcessingSession) -> str:
        """返回 session 备注文本。"""
        remark = getattr(session, "remark", "")
        if isinstance(remark, str) and remark.strip():
            return remark.strip()
        return "无"

    def _format_created_at(self, created_at: datetime) -> str:
        """格式化 session 创建时间。"""
        return created_at.strftime("%Y-%m-%d %H:%M")
