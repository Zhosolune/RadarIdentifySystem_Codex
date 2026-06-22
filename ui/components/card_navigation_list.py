"""卡片式页面导航列表组件。

本模块提供一个独立的布局式卡片导航列表，不绑定任何具体页面路由。
调用方可以按 key 添加导航项，并通过 `itemSelected` 信号完成外部页面切换。

Example:
    >>> from PyQt6.QtWidgets import QApplication
    >>> app = QApplication.instance() or QApplication([])
    >>> nav = CardNavigationList()
    >>> nav.add_item("home", "首页")
    <ui.components.card_navigation_list.CardNavigationItem object at ...>
    >>> nav.set_current_key("home")
    >>> nav.current_key()
    'home'
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, CardWidget, IconWidget, themeColor
from qfluentwidgets.common.icon import FluentIconBase


NavigationIcon = str | QIcon | FluentIconBase


class CardNavigationItem(CardWidget):
    """单个卡片导航项。

    该组件复用 `CardWidget` 的明暗主题背景、悬浮态和按压态，仅在选中时
    额外绘制左侧主题色竖条。

    Attributes:
        key: 导航项的唯一键。
        title_label: 主标题标签。
        subtitle_label: 副标题标签，未传入副标题时为 None。
        icon_widget: 图标组件，未传入图标时为 None。
    """

    def __init__(
        self,
        key: str,
        title: str,
        subtitle: str = "",
        icon: NavigationIcon | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """初始化卡片导航项。

        Args:
            key: 导航项唯一键，不能为空。
            title: 导航项主标题，不能为空。
            subtitle: 导航项副标题，默认空字符串表示不显示。
            icon: 可选图标，支持组件库图标、QIcon 或图标路径。
            parent: 父组件。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: key 或 title 为空时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> item = CardNavigationItem("home", "首页")
            >>> item.key
            'home'
        """
        super().__init__(parent)
        if not key:
            raise ValueError("导航项 key 不能为空")
        if not title:
            raise ValueError("导航项标题不能为空")

        self.key = key
        self.title_label = BodyLabel(title, self)
        self.subtitle_label: CaptionLabel | None = None
        self.icon_widget: IconWidget | None = None
        self._is_selected = False

        self.setObjectName("cardNavigationItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(56 if not subtitle else 68)

        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(16, 8, 16, 8)
        self._main_layout.setSpacing(12)

        if icon is not None:
            # 图标可选，避免纯文本导航项承担额外视觉负担。
            self.icon_widget = IconWidget(icon, self)
            self.icon_widget.setFixedSize(18, 18)
            self._main_layout.addWidget(self.icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self.title_label)

        if subtitle:
            self.subtitle_label = CaptionLabel(subtitle, self)
            text_layout.addWidget(self.subtitle_label)

        self._main_layout.addLayout(text_layout, 1)

    def set_selected(self, selected: bool) -> None:
        """设置选中状态并刷新绘制。

        Args:
            selected: True 表示选中，False 表示取消选中。

        Returns:
            None: 无返回值。

        Raises:
            无。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> item = CardNavigationItem("home", "首页")
            >>> item.set_selected(True)
            >>> item.is_selected()
            True
        """
        self._is_selected = selected
        self.setProperty("selected", selected)
        self.update()

    def is_selected(self) -> bool:
        """返回当前选中状态。

        Args:
            无。

        Returns:
            bool: True 表示当前卡片被选中。

        Raises:
            无。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> item = CardNavigationItem("home", "首页")
            >>> item.is_selected()
            False
        """
        return self._is_selected

    def paintEvent(self, event) -> None:
        """绘制卡片背景和选中竖条。

        Args:
            event: Qt 绘制事件。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        super().paintEvent(event)
        if not self._is_selected:
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(themeColor()))

        # 与组件库列表项一致，选中标记为居中的窄竖条。
        height = self.height()
        padding_y = round(0.257 * height)
        painter.drawRoundedRect(0, padding_y, 3, height - 2 * padding_y, 1.5, 1.5)


class CardNavigationList(QWidget):
    """布局式卡片导航列表。

    该组件只负责卡片项的增删和单选状态管理，不绑定页面栈或业务路由。

    Attributes:
        itemSelected: 当前项变化后发出的导航 key 信号。
        scroll_area: 外层滚动区域。
        content_widget: 卡片容器组件。
        content_layout: 卡片容器布局。
    """

    itemSelected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化卡片导航列表。

        Args:
            parent: 父组件。

        Returns:
            None: 无返回值。

        Raises:
            无。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> nav = CardNavigationList()
            >>> nav.item_count()
            0
        """
        super().__init__(parent)
        self._items: dict[str, CardNavigationItem] = {}
        self._current_key: str | None = None

        self.scroll_area = QScrollArea(self)
        self.content_widget = QWidget(self.scroll_area)
        self.content_layout = QVBoxLayout(self.content_widget)
        self._main_layout = QVBoxLayout(self)

        self.setObjectName("cardNavigationList")
        self.scroll_area.setObjectName("cardNavigationScrollArea")
        self.content_widget.setObjectName("cardNavigationContent")

        self._init_widget()

    def _init_widget(self) -> None:
        """初始化滚动容器和列表布局。"""
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        self.content_layout.addStretch(1)

        self.scroll_area.setWidget(self.content_widget)
        self._main_layout.addWidget(self.scroll_area)

    def add_item(
        self,
        key: str,
        title: str,
        subtitle: str = "",
        icon: NavigationIcon | None = None,
    ) -> CardNavigationItem:
        """添加一个卡片导航项。

        Args:
            key: 导航项唯一键，不能为空且不能重复。
            title: 导航项主标题，不能为空。
            subtitle: 导航项副标题，默认空字符串表示不显示。
            icon: 可选图标，支持组件库图标、QIcon 或图标路径。

        Returns:
            CardNavigationItem: 新创建的卡片导航项。

        Raises:
            ValueError: key 重复、key 为空或 title 为空时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> nav = CardNavigationList()
            >>> item = nav.add_item("home", "首页")
            >>> item.key
            'home'
        """
        if key in self._items:
            raise ValueError(f"导航项 key 已存在: {key}")

        item = CardNavigationItem(key, title, subtitle, icon, self.content_widget)
        item.clicked.connect(lambda current_key=key: self.set_current_key(current_key))

        # 伸缩项始终保留在底部，新卡片插入到伸缩项之前。
        self.content_layout.insertWidget(self.content_layout.count() - 1, item)
        self._items[key] = item
        return item

    def clear_items(self) -> None:
        """清空所有导航项。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> nav = CardNavigationList()
            >>> nav.add_item("home", "首页")
            <ui.components.card_navigation_list.CardNavigationItem object at ...>
            >>> nav.clear_items()
            >>> nav.item_count()
            0
        """
        for item in self._items.values():
            self.content_layout.removeWidget(item)
            item.deleteLater()

        self._items.clear()
        self._current_key = None

    def set_current_key(self, key: str) -> None:
        """切换当前选中的导航项。

        Args:
            key: 要选中的导航项 key。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: key 不存在时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> nav = CardNavigationList()
            >>> nav.add_item("home", "首页")
            <ui.components.card_navigation_list.CardNavigationItem object at ...>
            >>> nav.set_current_key("home")
            >>> nav.current_key()
            'home'
        """
        if key not in self._items:
            raise KeyError(f"导航项 key 不存在: {key}")
        if key == self._current_key:
            return

        if self._current_key is not None:
            self._items[self._current_key].set_selected(False)

        self._items[key].set_selected(True)
        self._current_key = key
        self.itemSelected.emit(key)

    def current_key(self) -> str | None:
        """返回当前选中的导航项 key。

        Args:
            无。

        Returns:
            str | None: 当前选中的导航项 key，未选中时返回 None。

        Raises:
            无。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> CardNavigationList().current_key() is None
            True
        """
        return self._current_key

    def item(self, key: str) -> CardNavigationItem:
        """按 key 返回导航项。

        Args:
            key: 导航项唯一键。

        Returns:
            CardNavigationItem: 对应的卡片导航项。

        Raises:
            KeyError: key 不存在时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> nav = CardNavigationList()
            >>> nav.add_item("home", "首页")
            <ui.components.card_navigation_list.CardNavigationItem object at ...>
            >>> nav.item("home").key
            'home'
        """
        return self._items[key]

    def item_count(self) -> int:
        """返回导航项数量。

        Args:
            无。

        Returns:
            int: 当前导航项数量。

        Raises:
            无。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> nav = CardNavigationList()
            >>> nav.item_count()
            0
        """
        return len(self._items)
