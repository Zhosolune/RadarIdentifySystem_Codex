# -*- coding: utf-8 -*-
"""通用滑动抽屉组件。"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QLinearGradient, QMouseEvent, QPaintEvent, QPainter
from PyQt6.QtWidgets import QApplication, QBoxLayout, QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, TransparentToolButton, isDarkTheme


class DrawerPosition(Enum):
    """抽屉展开方向。"""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class SlidingDrawer(QWidget):
    """基于组件库风格的通用滑动抽屉。

    抽屉支持从上下左右四个方向展开，内容区可放入任意 QWidget。
    组件自身根据深浅主题切换面板、按钮和展开遮罩样式。

    Attributes:
        expandedChanged: 展开状态变化时发出的信号。
        opened: 抽屉展开后发出的信号。
        closed: 抽屉关闭后发出的信号。
    """

    expandedChanged = pyqtSignal(bool)
    opened = pyqtSignal()
    closed = pyqtSignal()

    _BUTTON_SIZE = 32

    def __init__(
        self,
        position: DrawerPosition = DrawerPosition.LEFT,
        drawer_size: int = 240,
        parent: QWidget | None = None,
    ) -> None:
        """初始化滑动抽屉。

        Args:
            position (DrawerPosition): 抽屉展开方向。
            drawer_size (int): 抽屉展开后的面板尺寸，水平方向为宽度，垂直方向为高度。
            parent (QWidget | None): Qt 父组件。

        Raises:
            ValueError: 当 drawer_size 小于 0 时抛出。

        Example:
            >>> drawer = SlidingDrawer(DrawerPosition.LEFT, 220)
            >>> drawer.isExpanded()
            False
        """
        super().__init__(parent)
        if drawer_size < 0:
            raise ValueError("drawer_size 不能小于 0")

        self._position = position
        self._drawer_size = drawer_size
        self._expanded = False
        self._toggle_button_visible = True
        self._root_layout: QBoxLayout | None = None
        self._trigger_widget: QWidget | None = None

        self._panel = QFrame(self)
        self._panel.setObjectName("slidingDrawerPanel")
        self._panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._close_button = TransparentToolButton(FluentIcon.CLOSE, self._panel)
        self._close_button.setObjectName("slidingDrawerCloseButton")
        self._close_button.setFixedSize(28, 28)
        self._close_button.clicked.connect(self.close)

        self._content_widget = QWidget(self._panel)
        self._content_widget.setObjectName("slidingDrawerContent")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(8)

        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(4)
        close_layout = QHBoxLayout()
        close_layout.setContentsMargins(0, 0, 0, 0)
        close_layout.setSpacing(0)
        close_layout.addStretch(1)
        close_layout.addWidget(self._close_button)
        panel_layout.addLayout(close_layout)
        panel_layout.addWidget(self._content_widget)

        self._toggle_button = TransparentToolButton(self)
        self._toggle_button.setObjectName("slidingDrawerToggleButton")
        self._toggle_button.setFixedSize(self._BUTTON_SIZE, self._BUTTON_SIZE)
        self._toggle_button.clicked.connect(self.toggle)
        self._close_button.setVisible(False)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._rebuild_layout()
        self._apply_theme()
        self._sync_panel_constraints()
        self._sync_toggle_icon()

    def panel(self) -> QFrame:
        """返回抽屉面板。

        Args:
            无。

        Returns:
            QFrame: 承载内容区的抽屉面板。

        Raises:
            无显式抛出异常。

        Example:
            >>> isinstance(SlidingDrawer().panel(), QFrame)
            True
        """
        return self._panel

    def toggleButton(self) -> TransparentToolButton:
        """返回展开按钮。

        Args:
            无。

        Returns:
            TransparentToolButton: 组件库透明工具按钮。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer().toggleButton() is not None
            True
        """
        return self._toggle_button

    def closeButton(self) -> TransparentToolButton:
        """返回面板右上角关闭按钮。

        Args:
            无。

        Returns:
            TransparentToolButton: 组件库透明工具按钮，点击后关闭抽屉。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer().closeButton() is not None
            True
        """
        return self._close_button

    def setTriggerWidget(self, widget: QWidget | None) -> None:
        """设置外部唤起按钮。

        全局点击关闭启用后，点击该控件不会被当作抽屉外部点击处理，
        适合外部按钮连接到 drawer.toggle 的场景。

        Args:
            widget (QWidget | None): 外部唤起控件；传入 None 时清空外部唤起控件。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.setTriggerWidget(None)
        """
        self._trigger_widget = widget

    def triggerWidget(self) -> QWidget | None:
        """返回外部唤起按钮。

        Args:
            无。

        Returns:
            QWidget | None: 当前注册的外部唤起控件。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer().triggerWidget() is None
            True
        """
        return self._trigger_widget

    def contentWidget(self) -> QWidget:
        """返回当前内容组件。

        Args:
            无。

        Returns:
            QWidget: 当前抽屉内容组件。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer().contentWidget() is not None
            True
        """
        return self._content_widget

    def contentLayout(self) -> QVBoxLayout | None:
        """返回默认内容布局。

        当调用 setContentWidget() 替换为自定义组件后，默认布局不再可用。

        Args:
            无。

        Returns:
            QVBoxLayout | None: 默认内容布局；内容组件被替换后返回 None。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer().contentLayout() is not None
            True
        """
        return self._content_layout

    def setContentWidget(self, widget: QWidget) -> None:
        """设置抽屉内容组件。

        Args:
            widget (QWidget): 新的内容组件，不能为 None。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当 widget 为 None 时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QLabel
            >>> drawer = SlidingDrawer()
            >>> label = QLabel("content")
            >>> drawer.setContentWidget(label)
            >>> drawer.contentWidget() is label
            True
        """
        if widget is None:
            raise ValueError("widget 不能为 None")

        panel_layout = self._panel.layout()
        if panel_layout is not None:
            panel_layout.removeWidget(self._content_widget)
        self._content_widget.setParent(None)
        self._content_widget = widget
        self._content_widget.setParent(self._panel)
        self._content_widget.setObjectName("slidingDrawerContent")
        self._content_layout = None
        if panel_layout is not None:
            panel_layout.addWidget(self._content_widget)
        self._apply_theme()

    def setDrawerSize(self, size: int) -> None:
        """设置抽屉展开尺寸。

        Args:
            size (int): 展开后的面板尺寸，必须大于或等于 0。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当 size 小于 0 时抛出。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.setDrawerSize(180)
            >>> drawer.drawerSize()
            180
        """
        if size < 0:
            raise ValueError("size 不能小于 0")
        self._drawer_size = size
        self._sync_panel_constraints()

    def drawerSize(self) -> int:
        """返回抽屉展开尺寸。

        Args:
            无。

        Returns:
            int: 当前展开尺寸。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer(drawer_size=120).drawerSize()
            120
        """
        return self._drawer_size

    def setPosition(self, position: DrawerPosition) -> None:
        """设置抽屉展开方向。

        Args:
            position (DrawerPosition): 新的展开方向。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当 position 不是 DrawerPosition 时抛出。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.setPosition(DrawerPosition.TOP)
            >>> drawer.position() is DrawerPosition.TOP
            True
        """
        if not isinstance(position, DrawerPosition):
            raise ValueError("position 必须是 DrawerPosition")
        if self._position == position:
            return
        self._position = position
        self._rebuild_layout()
        self._sync_panel_constraints()
        self._sync_toggle_icon()
        self.update()

    def position(self) -> DrawerPosition:
        """返回抽屉展开方向。

        Args:
            无。

        Returns:
            DrawerPosition: 当前展开方向。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer(DrawerPosition.RIGHT).position() is DrawerPosition.RIGHT
            True
        """
        return self._position

    def isExpanded(self) -> bool:
        """返回抽屉是否展开。

        Args:
            无。

        Returns:
            bool: 抽屉展开时返回 True，否则返回 False。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer().isExpanded()
            False
        """
        return self._expanded

    @pyqtSlot()
    def open(self) -> None:
        """展开抽屉。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.open()
            >>> drawer.isExpanded()
            True
        """
        self.setExpanded(True)

    @pyqtSlot()
    def close(self) -> None:
        """关闭抽屉。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.open()
            >>> drawer.close()
            >>> drawer.isExpanded()
            False
        """
        self.setExpanded(False)

    @pyqtSlot()
    def toggle(self) -> None:
        """切换抽屉展开状态。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.toggle()
            >>> drawer.isExpanded()
            True
        """
        self.setExpanded(not self._expanded)

    @pyqtSlot(bool)
    def setExpanded(self, expanded: bool) -> None:
        """设置抽屉展开状态。

        Args:
            expanded (bool): True 表示展开，False 表示关闭。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.setExpanded(True)
            >>> drawer.isExpanded()
            True
        """
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._sync_global_event_filter()
        self._sync_panel_constraints()
        self._sync_toggle_icon()
        self.expandedChanged.emit(self._expanded)
        if self._expanded:
            self.opened.emit()
        else:
            self.closed.emit()
        self._close_button.setVisible(self._expanded)
        self.update()

    def setToggleButtonVisible(self, visible: bool) -> None:
        """设置展开按钮是否可见。

        Args:
            visible (bool): True 表示显示按钮，False 表示隐藏按钮。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> drawer = SlidingDrawer()
            >>> drawer.setToggleButtonVisible(False)
            >>> drawer.isToggleButtonVisible()
            False
        """
        self._toggle_button_visible = visible
        self._toggle_button.setVisible(visible)

    def isToggleButtonVisible(self) -> bool:
        """返回展开按钮是否可见。

        Args:
            无。

        Returns:
            bool: 展开按钮可见时返回 True，否则返回 False。

        Raises:
            无显式抛出异常。

        Example:
            >>> SlidingDrawer().isToggleButtonVisible()
            True
        """
        return self._toggle_button_visible

    def event(self, event: QEvent) -> bool:
        """处理组件事件。

        Args:
            event (QEvent): Qt 事件对象。

        Returns:
            bool: 事件已处理时返回 True，否则返回父类处理结果。

        Raises:
            无显式抛出异常。
        """
        if event.type() in (
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
        ):
            self._apply_theme()
        return super().event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """过滤全局鼠标点击事件。

        Args:
            watched (QObject): 被过滤事件的对象。
            event (QEvent): Qt 事件对象。

        Returns:
            bool: 本组件不截断事件，始终返回 False。

        Raises:
            无显式抛出异常。
        """
        if (
            self._expanded
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
            and self._is_global_outside_click(event.globalPosition().toPoint())
        ):
            self.close()
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """处理鼠标点击关闭行为。

        展开状态下点击抽屉面板外区域时关闭抽屉；点击面板或展开按钮时保留原行为。

        Args:
            event (QMouseEvent): Qt 鼠标事件。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        if self._expanded and self._is_overlay_click(event.position().toPoint()):
            self.close()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制展开状态下的主题遮罩。

        Args:
            event (QPaintEvent): Qt 绘制事件。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().paintEvent(event)
        if not self._expanded:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self._shadow_rect(), self._shadow_gradient())

    def _rebuild_layout(self) -> None:
        """按当前方向重建外层布局。"""
        if self._root_layout is None:
            self._root_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
            self._root_layout.setContentsMargins(0, 0, 0, 0)
            self._root_layout.setSpacing(0)
        while self._root_layout.count():
            item = self._root_layout.takeAt(0)
            if item.widget() is not None:
                self._root_layout.removeWidget(item.widget())

        direction_map = {
            DrawerPosition.LEFT: QBoxLayout.Direction.LeftToRight,
            DrawerPosition.RIGHT: QBoxLayout.Direction.LeftToRight,
            DrawerPosition.TOP: QBoxLayout.Direction.TopToBottom,
            DrawerPosition.BOTTOM: QBoxLayout.Direction.TopToBottom,
        }
        self._root_layout.setDirection(direction_map[self._position])

        if self._position in (DrawerPosition.LEFT, DrawerPosition.TOP):
            self._root_layout.addWidget(self._panel)
            self._root_layout.addWidget(self._toggle_button, 0, Qt.AlignmentFlag.AlignCenter)
        else:
            self._root_layout.addWidget(self._toggle_button, 0, Qt.AlignmentFlag.AlignCenter)
            self._root_layout.addWidget(self._panel)

    def _sync_panel_constraints(self) -> None:
        """根据方向和展开状态同步面板尺寸约束。"""
        size = self._drawer_size if self._expanded else 0
        if self._position in (DrawerPosition.LEFT, DrawerPosition.RIGHT):
            self._panel.setFixedWidth(size)
            self._panel.setMinimumHeight(0)
            self._panel.setMaximumHeight(16777215)
            self._panel.setMinimumWidth(size)
            self._panel.setMaximumWidth(size)
        else:
            self._panel.setFixedHeight(size)
            self._panel.setMinimumWidth(0)
            self._panel.setMaximumWidth(16777215)
            self._panel.setMinimumHeight(size)
            self._panel.setMaximumHeight(size)

    def _sync_toggle_icon(self) -> None:
        """根据方向和状态同步展开按钮图标。"""
        icon_map = {
            DrawerPosition.LEFT: FluentIcon.LEFT_ARROW if self._expanded else FluentIcon.RIGHT_ARROW,
            DrawerPosition.RIGHT: FluentIcon.RIGHT_ARROW if self._expanded else FluentIcon.LEFT_ARROW,
            DrawerPosition.TOP: FluentIcon.UP if self._expanded else FluentIcon.DOWN,
            DrawerPosition.BOTTOM: FluentIcon.DOWN if self._expanded else FluentIcon.UP,
        }
        self._toggle_button.setIcon(icon_map[self._position])

    def _apply_theme(self) -> None:
        """应用深浅两色主题样式。"""
        if isDarkTheme():
            panel_bg = "rgb(39, 39, 39)"
            content_bg = "rgb(39, 39, 39)"
            border = "rgba(255, 255, 255, 28)"
            hover = "rgba(255, 255, 255, 12)"
            pressed = "rgba(255, 255, 255, 18)"
        else:
            panel_bg = "rgb(255, 255, 255)"
            content_bg = "rgb(255, 255, 255)"
            border = "rgba(0, 0, 0, 22)"
            hover = "rgba(0, 0, 0, 8)"
            pressed = "rgba(0, 0, 0, 12)"

        self.setStyleSheet(f"""
            SlidingDrawer {{
                background: transparent;
            }}
            QFrame#slidingDrawerPanel {{
                background: {panel_bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QWidget#slidingDrawerContent {{
                background: {content_bg};
                border: none;
            }}
            TransparentToolButton#slidingDrawerCloseButton {{
                border: none;
                border-radius: 6px;
                background: transparent;
            }}
            TransparentToolButton#slidingDrawerCloseButton:hover {{
                background: {hover};
            }}
            TransparentToolButton#slidingDrawerCloseButton:pressed {{
                background: {pressed};
            }}
            TransparentToolButton#slidingDrawerToggleButton {{
                border: none;
                border-radius: 6px;
                background: transparent;
            }}
            TransparentToolButton#slidingDrawerToggleButton:hover {{
                background: {hover};
            }}
            TransparentToolButton#slidingDrawerToggleButton:pressed {{
                background: {pressed};
            }}
        """)

    def _is_overlay_click(self, position: QPoint) -> bool:
        """判断鼠标位置是否位于抽屉遮罩区域。"""
        if self._panel.geometry().contains(position):
            return False
        if self._toggle_button.isVisible() and self._toggle_button.geometry().contains(position):
            return False
        return True

    def _is_global_outside_click(self, global_position: QPoint) -> bool:
        """判断全局鼠标位置是否位于抽屉和触发控件外。"""
        for widget in (self._panel, self._toggle_button, self._close_button, self._trigger_widget):
            if widget is None:
                continue
            if widget is not self._trigger_widget and not widget.isVisible():
                continue
            local_pos = widget.mapFromGlobal(global_position)
            if widget.rect().contains(local_pos):
                return False
        return True

    def _sync_global_event_filter(self) -> None:
        """根据展开状态同步全局鼠标事件过滤器。"""
        app = QApplication.instance()
        if app is None:
            return
        app.removeEventFilter(self)
        if self._expanded:
            app.installEventFilter(self)

    def _shadow_rect(self) -> QRect:
        """返回当前方向的遮罩矩形。"""
        if self._position == DrawerPosition.LEFT:
            return self.rect().adjusted(self._panel.width(), 0, -self._BUTTON_SIZE, 0)
        if self._position == DrawerPosition.RIGHT:
            return self.rect().adjusted(self._BUTTON_SIZE, 0, -self._panel.width(), 0)
        if self._position == DrawerPosition.TOP:
            return self.rect().adjusted(0, self._panel.height(), 0, -self._BUTTON_SIZE)
        if self._position == DrawerPosition.BOTTOM:
            return self.rect().adjusted(0, self._BUTTON_SIZE, 0, -self._panel.height())
        return self.rect()

    def _shadow_gradient(self) -> QLinearGradient:
        """返回当前方向的遮罩渐变。"""
        rect = self._shadow_rect()
        if self._position == DrawerPosition.LEFT:
            gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        elif self._position == DrawerPosition.RIGHT:
            gradient = QLinearGradient(rect.right(), 0, rect.left(), 0)
        elif self._position == DrawerPosition.TOP:
            gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        else:
            gradient = QLinearGradient(0, rect.bottom(), 0, rect.top())

        if isDarkTheme():
            start = QColor(0, 0, 0, 95)
            end = QColor(0, 0, 0, 0)
        else:
            start = QColor(0, 0, 0, 45)
            end = QColor(0, 0, 0, 0)
        gradient.setColorAt(0, start)
        gradient.setColorAt(1, end)
        return gradient
