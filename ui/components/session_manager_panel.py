"""主页 session 管理面板。"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SimpleCardWidget, TransparentPushButton, FluentIcon, ToolTipFilter, ToolTipPosition
from qfluentwidgets.common.font import setFont

from core.models.processing_session import ProcessingSession
from ui.components.card_navigation_list import CardNavigationList


class SessionManagerPanel(SimpleCardWidget):
    """展示当前运行期 session 的卡片式管理面板。

    面板内部为标题栏 + 内容区结构；内容区使用左右两栏布局展示
    session 导航列表与详情占位区域。

    Attributes:
        sessionActivated: 请求激活指定 session 的信号。
        sessionCloseRequested: 请求关闭指定 session 的信号，当前最小实现暂不暴露按钮。
        session_nav: 左侧卡片导航列表。
        session_detail_placeholder: 右侧详情占位标签。
    """

    sessionActivated = pyqtSignal(str)
    sessionCloseRequested = pyqtSignal(str)

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

        # 创建标题标签。
        self.session_title_label = BodyLabel("Session 管理", self)
        self.session_title_label.setObjectName("sessionManagerTitleLabel")
        setFont(self.session_title_label, 14)

        # 创建透明按钮。
        self.create_session_button = TransparentPushButton("新建", self, FluentIcon.ADD)
        self.create_session_button.setObjectName("createSessionButton")
        self.create_session_button.setFixedHeight(34)
        self.create_session_button.setToolTip("新建空白 Session")
        self.create_session_button.installEventFilter(ToolTipFilter(self.create_session_button, 500, ToolTipPosition.TOP))

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

        # 创建右侧详情占位标签。
        self.session_detail_placeholder = BodyLabel("Session 详情占位", self)
        self.session_detail_placeholder.setObjectName("sessionDetailPlaceholder")
        self.session_detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 创建右侧详情容器。
        self._detail_widget = QWidget(self)
        self._detail_widget.setObjectName("sessionDetailPane")
        self._detail_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._detail_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._root_layout = QVBoxLayout(self)
        self._header_layout = QHBoxLayout()
        self._content_layout = QHBoxLayout()
        self._detail_layout = QVBoxLayout(self._detail_widget)

        # 组装面板布局。
        self._init_widget()
        # 转发导航激活信号。
        self.session_nav.itemSelected.connect(self.sessionActivated.emit)

    def _init_widget(self) -> None:
        """初始化面板布局。"""
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # 组装标题栏布局。
        self._header_layout.setContentsMargins(20, 8, 8, 7)
        self._header_layout.setSpacing(8)
        self._header_layout.addWidget(self.session_title_label)
        self._header_layout.addStretch(1)
        self._header_layout.addWidget(self.create_session_button)

        # 组装内容区双栏布局。
        self._content_layout.setContentsMargins(8, 7, 8, 8)
        self._content_layout.setSpacing(8)

        # 居中放置详情占位内容。
        self._detail_layout.setContentsMargins(12, 12, 12, 12)
        self._detail_layout.setSpacing(0)
        self._detail_layout.addStretch(1)
        self._detail_layout.addWidget(self.session_detail_placeholder)
        self._detail_layout.addStretch(1)

        # 按“标题栏 + 分隔线 + 内容区”顺序挂接布局。
        self._root_layout.addLayout(self._header_layout)
        self._root_layout.addWidget(self.session_header_separator)
        self._content_layout.addWidget(self.session_nav, 1)
        self._content_layout.addWidget(self._detail_widget, 2)
        self._root_layout.addLayout(self._content_layout, 1)

    def set_sessions(self, sessions: list[ProcessingSession]) -> None:
        """刷新 session 卡片列表。

        Args:
            sessions: 需要显示的 session 列表。

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
        # 缓存当前 session 列表。
        self._sessions = list(sessions)
        # 清空旧导航项。
        self.session_nav.clear_items()

        for session in self._sessions:
            # 追加新的 session 导航项。
            self.session_nav.add_item(
                session.session_id,
                session.display_name,
                self._format_created_at(session.created_at),
            )

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

    def _format_created_at(self, created_at: datetime) -> str:
        """格式化 session 创建时间。"""
        return created_at.strftime("%Y-%m-%d %H:%M")
