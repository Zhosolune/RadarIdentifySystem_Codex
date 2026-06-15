# -*- coding: utf-8 -*-
"""通用覆盖层滑动抽屉组件。"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QCloseEvent, QLinearGradient, QMouseEvent, QPaintEvent, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, Theme, TransparentToolButton, isDarkTheme, qconfig


class DrawerPosition(Enum):
    """抽屉展开方向。"""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class SlidingDrawer(QWidget):
    """基于组件库弹层模型的通用抽屉。

    抽屉本体是父组件上的覆盖层，展开时覆盖父组件完整区域并将面板贴边显示。
    面板之外由遮罩承载点击关闭交互，面板内部可自由放置业务控件。

    Attributes:
        expandedChanged: 展开状态变化时发出的信号。
        opened: 抽屉展开后发出的信号。
        closed: 抽屉关闭后发出的信号。
    """

    expandedChanged = pyqtSignal(bool)
    opened = pyqtSignal()
    closed = pyqtSignal()

    _TOGGLE_BUTTON_SIZE = 32
    _DEFAULT_ANIMATION_DURATION = 360
    _PANEL_SHADOW_BLUR = 35
    _PANEL_SHADOW_LIGHT_ALPHA = 30
    _PANEL_SHADOW_DARK_ALPHA = 80
    _PANEL_SHADOW_OFFSET = (0, 8)
    _MASK_ALPHA = 0
    _EDGE_SHADOW_ALPHA = 0
    _EDGE_SHADOW_WIDTH = 36
    _SHADOW_SOURCE = "qfluentwidgets/components/widgets/flyout.py: Flyout.setShadowEffect"
    _PANEL_BG_SOURCE = "qfluentwidgets/_rc/qss/{theme}/navigation_interface.qss: NavigationPanel[menu=true]"
    # _LIGHT_PANEL_BG = "rgb(243, 243, 243)"
    _LIGHT_PANEL_BG = "rgb(255, 255, 255)"
    _DARK_PANEL_BG = "rgb(32, 32, 32)"
    _LIGHT_PANEL_BORDER = "rgb(229, 229, 229)"
    _DARK_PANEL_BORDER = "rgb(57, 57, 57)"

    def __init__(
        self,
        position: DrawerPosition = DrawerPosition.RIGHT,
        drawer_size: int = 320,
        parent: QWidget | None = None,
        title: str = "标题",
    ) -> None:
        """初始化覆盖层抽屉。

        Args:
            position (DrawerPosition): 抽屉展开方向。
            drawer_size (int): 面板展开尺寸，左右抽屉表示宽度，上下抽屉表示高度。
            parent (QWidget | None): 抽屉覆盖的父组件。
            title (str): 面板标题文本。

        Raises:
            ValueError: 当 drawer_size 小于 0 时抛出。

        Example:
            >>> drawer = SlidingDrawer(DrawerPosition.RIGHT, 320)
            >>> drawer.isExpanded()
            False
        """
        super().__init__(parent)
        if drawer_size < 0:
            raise ValueError("drawer_size 不能小于 0")

        self._position = position
        self._drawer_size = drawer_size
        self._expanded = False
        self._toggle_button_visible = False
        self._trigger_widget: QWidget | None = None
        self._is_applying_theme = False
        self._animation_duration = self._DEFAULT_ANIMATION_DURATION
        self._closing_after_animation = False

        self.setObjectName("slidingDrawerOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.hide()

        self._panel = QFrame(self)
        self._panel.setObjectName("slidingDrawerPanel")
        self._panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._title_label = QLabel(title, self._panel)
        self._title_label.setObjectName("slidingDrawerTitleLabel")
        self._close_button = TransparentToolButton(FluentIcon.CLOSE, self._panel)
        self._close_button.setObjectName("slidingDrawerCloseButton")
        self._close_button.setFixedSize(32, 32)
        self._close_button.clicked.connect(self.close)

        self._content_widget = QWidget(self._panel)
        self._content_widget.setObjectName("slidingDrawerContent")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(16, 8, 16, 16)
        self._content_layout.setSpacing(8)

        self._toggle_button = TransparentToolButton(self)
        self._toggle_button.setObjectName("slidingDrawerToggleButton")
        self._toggle_button.setFixedSize(self._TOGGLE_BUTTON_SIZE, self._TOGGLE_BUTTON_SIZE)
        self._toggle_button.clicked.connect(self.toggle)
        self._toggle_button.hide()

        self._panel_animation = QPropertyAnimation(self._panel, b"pos", self)
        self._panel_animation.setDuration(self._animation_duration)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.finished.connect(self._on_panel_animation_finished)

        self._init_panel_layout()
        self._set_shadow_effect()
        self._apply_theme()
        self._sync_overlay_geometry()
        qconfig.themeChanged.connect(self._on_theme_changed)

        if parent is not None:
            parent.installEventFilter(self)

    def panel(self) -> QFrame:
        """返回抽屉面板。

        Args:
            无。

        Returns:
            QFrame: 承载标题、关闭按钮与内容区的面板。

        Raises:
            无显式抛出异常。
        """
        return self._panel

    def closeButton(self) -> TransparentToolButton:
        """返回面板右上角关闭按钮。

        Args:
            无。

        Returns:
            TransparentToolButton: 点击后关闭抽屉的透明工具按钮。

        Raises:
            无显式抛出异常。
        """
        return self._close_button

    def toggleButton(self) -> TransparentToolButton:
        """返回可选的内置唤起按钮。

        Args:
            无。

        Returns:
            TransparentToolButton: 内置唤起按钮，默认隐藏。

        Raises:
            无显式抛出异常。
        """
        return self._toggle_button

    def setTriggerWidget(self, widget: QWidget | None) -> None:
        """设置外部唤起控件。

        点击外部唤起控件所在区域时，覆盖层会关闭抽屉而不吞掉为其他行为。

        Args:
            widget (QWidget | None): 外部唤起控件；传入 None 时清空。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self._trigger_widget = widget

    def triggerWidget(self) -> QWidget | None:
        """返回外部唤起控件。

        Args:
            无。

        Returns:
            QWidget | None: 当前注册的外部唤起控件。

        Raises:
            无显式抛出异常。
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
        """
        return self._content_widget

    def contentLayout(self) -> QVBoxLayout | None:
        """返回默认内容布局。

        Args:
            无。

        Returns:
            QVBoxLayout | None: 默认内容布局；替换内容组件后返回 None。

        Raises:
            无显式抛出异常。
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
            panel_layout.addWidget(self._content_widget, 1)
        self._apply_theme()

    def setTitle(self, title: str) -> None:
        """设置抽屉标题。

        Args:
            title (str): 新标题文本。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self._title_label.setText(title)

    def title(self) -> str:
        """返回抽屉标题。

        Args:
            无。

        Returns:
            str: 当前标题文本。

        Raises:
            无显式抛出异常。
        """
        return self._title_label.text()

    def setDrawerSize(self, size: int) -> None:
        """设置抽屉面板展开尺寸。

        Args:
            size (int): 面板尺寸，必须大于或等于 0。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当 size 小于 0 时抛出。
        """
        if size < 0:
            raise ValueError("size 不能小于 0")
        self._drawer_size = size
        self._sync_overlay_geometry()

    def drawerSize(self) -> int:
        """返回抽屉面板展开尺寸。

        Args:
            无。

        Returns:
            int: 当前面板尺寸。

        Raises:
            无显式抛出异常。
        """
        return self._drawer_size

    def setAnimationDuration(self, duration: int) -> None:
        """设置展开关闭动画时长。

        Args:
            duration (int): 动画时长，单位为毫秒，必须大于或等于 0。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当 duration 小于 0 时抛出。
        """
        if duration < 0:
            raise ValueError("duration 不能小于 0")
        self._animation_duration = duration
        self._panel_animation.setDuration(duration)

    def animationDuration(self) -> int:
        """返回展开关闭动画时长。

        Args:
            无。

        Returns:
            int: 当前动画时长，单位为毫秒。

        Raises:
            无显式抛出异常。
        """
        return self._animation_duration

    def maskAlpha(self) -> int:
        """返回遮罩透明度。

        Args:
            无。

        Returns:
            int: 遮罩颜色的 alpha 值。

        Raises:
            无显式抛出异常。
        """
        return self._MASK_ALPHA

    def edgeShadowAlpha(self) -> int:
        """返回边缘渐变阴影透明度。

        Args:
            无。

        Returns:
            int: 边缘渐变阴影起始 alpha 值。

        Raises:
            无显式抛出异常。
        """
        return self._EDGE_SHADOW_ALPHA

    def lightPanelBackgroundColor(self) -> str:
        """返回浅色主题下面板背景色。

        Args:
            无。

        Returns:
            str: 浅色主题下使用的 QSS 背景色字符串。

        Raises:
            无显式抛出异常。
        """
        return self._LIGHT_PANEL_BG

    def darkPanelBackgroundColor(self) -> str:
        """返回暗色主题下面板背景色。

        Args:
            无。

        Returns:
            str: 暗色主题下使用的 QSS 背景色字符串。

        Raises:
            无显式抛出异常。
        """
        return self._DARK_PANEL_BG

    def lightPanelBorderColor(self) -> str:
        """返回浅色主题下面板边框色。

        Args:
            无。

        Returns:
            str: 浅色主题下使用的 QSS 边框色字符串。

        Raises:
            无显式抛出异常。
        """
        return self._LIGHT_PANEL_BORDER

    def darkPanelBorderColor(self) -> str:
        """返回暗色主题下面板边框色。

        Args:
            无。

        Returns:
            str: 暗色主题下使用的 QSS 边框色字符串。

        Raises:
            无显式抛出异常。
        """
        return self._DARK_PANEL_BORDER

    def panelBackgroundColorSource(self) -> str:
        """返回浅色面板背景色来源。

        Args:
            无。

        Returns:
            str: 背景色在本地组件库中的来源说明。

        Raises:
            无显式抛出异常。
        """
        return self._PANEL_BG_SOURCE

    def shadowEffectSource(self) -> str:
        """返回面板阴影参数来源。

        Args:
            无。

        Returns:
            str: 阴影参数在本地组件库中的来源说明。

        Raises:
            无显式抛出异常。
        """
        return self._SHADOW_SOURCE

    def setPosition(self, position: DrawerPosition) -> None:
        """设置抽屉展开方向。

        Args:
            position (DrawerPosition): 新的展开方向。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当 position 不是 DrawerPosition 时抛出。
        """
        if not isinstance(position, DrawerPosition):
            raise ValueError("position 必须是 DrawerPosition")
        if self._position == position:
            return
        self._position = position
        self._set_shadow_effect()
        self._sync_toggle_icon()
        self._sync_overlay_geometry()
        self.update()

    def position(self) -> DrawerPosition:
        """返回抽屉展开方向。

        Args:
            无。

        Returns:
            DrawerPosition: 当前展开方向。

        Raises:
            无显式抛出异常。
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
        """
        if self._expanded == expanded:
            return

        self._expanded = expanded
        if self._expanded:
            self._sync_overlay_geometry()
            self.show()
            self.raise_()
            self._animate_panel(self._hidden_panel_rect(), self._panel_rect())
        else:
            self._animate_panel(self._panel.geometry(), self._hidden_panel_rect())

        self.expandedChanged.emit(self._expanded)
        if self._expanded:
            self.opened.emit()
        else:
            self.closed.emit()
        self.update()

    def setToggleButtonVisible(self, visible: bool) -> None:
        """设置内置唤起按钮是否可见。

        Args:
            visible (bool): True 表示显示按钮，False 表示隐藏按钮。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self._toggle_button_visible = visible
        self._toggle_button.setVisible(visible)
        self._sync_overlay_geometry()

    def isToggleButtonVisible(self) -> bool:
        """返回内置唤起按钮是否可见。

        Args:
            无。

        Returns:
            bool: 内置唤起按钮配置为显示时返回 True，否则返回 False。

        Raises:
            无显式抛出异常。
        """
        return self._toggle_button_visible

    def event(self, event: QEvent) -> bool:
        """处理组件事件。

        Args:
            event (QEvent): Qt 事件对象。

        Returns:
            bool: 事件处理结果。

        Raises:
            无显式抛出异常。
        """
        if event.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            self._apply_theme()
            self.update()
        return super().event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """过滤父组件尺寸变化事件。

        Args:
            watched (QObject): 被过滤事件的对象。
            event (QEvent): Qt 事件对象。

        Returns:
            bool: 始终返回 False，不截断父组件事件。

        Raises:
            无显式抛出异常。
        """
        if watched is self.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._sync_overlay_geometry()
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """处理遮罩点击关闭。

        Args:
            event (QMouseEvent): Qt 鼠标事件。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        pos = event.position().toPoint()
        if self._panel.geometry().contains(pos):
            super().mousePressEvent(event)
            return
        self.close()
        event.accept()

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制覆盖层遮罩和面板边缘阴影。

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
        if self.maskAlpha() > 0:
            painter.fillRect(self.rect(), self._mask_color())
        if self.edgeShadowAlpha() > 0:
            painter.fillRect(self._shadow_rect(), self._shadow_gradient())

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭时同步展开状态。

        Args:
            event (QCloseEvent): Qt 关闭事件。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self._expanded = False
        super().closeEvent(event)

    def _init_panel_layout(self) -> None:
        """初始化面板内部布局。"""
        root_layout = QVBoxLayout(self._panel)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(16, 12, 12, 6)
        header_layout.setSpacing(8)
        header_layout.addWidget(self._title_label, 1, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self._close_button, 0, Qt.AlignmentFlag.AlignRight)

        root_layout.addLayout(header_layout)
        root_layout.addWidget(self._content_widget, 1)

    def _sync_overlay_geometry(self) -> None:
        """同步覆盖层、面板和可选内置按钮几何。"""
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

        self._panel.setGeometry(self._panel_rect())
        self._sync_toggle_icon()
        self._sync_toggle_button_geometry()

    def _panel_rect(self) -> QRect:
        """计算抽屉面板几何。"""
        width = self.width()
        height = self.height()
        size = min(self._drawer_size, width if self._is_horizontal() else height)

        if self._position == DrawerPosition.LEFT:
            return QRect(0, 0, size, height)
        if self._position == DrawerPosition.RIGHT:
            return QRect(width - size, 0, size, height)
        if self._position == DrawerPosition.TOP:
            return QRect(0, 0, width, size)
        return QRect(0, height - size, width, size)

    def _hidden_panel_rect(self) -> QRect:
        """计算抽屉面板收起时的隐藏几何。"""
        rect = self._panel_rect()
        if self._position == DrawerPosition.LEFT:
            return QRect(-rect.width(), 0, rect.width(), rect.height())
        if self._position == DrawerPosition.RIGHT:
            return QRect(self.width(), 0, rect.width(), rect.height())
        if self._position == DrawerPosition.TOP:
            return QRect(0, -rect.height(), rect.width(), rect.height())
        return QRect(0, self.height(), rect.width(), rect.height())

    def _animate_panel(self, start_rect: QRect, end_rect: QRect) -> None:
        """按指定起止几何播放面板位移动画。"""
        self._panel_animation.stop()
        self._panel.resize(end_rect.size())
        self._closing_after_animation = not self._expanded
        if self._animation_duration == 0:
            self._panel.setGeometry(end_rect)
            self._on_panel_animation_finished()
            return

        self._panel.move(start_rect.topLeft())
        self._panel_animation.setStartValue(start_rect.topLeft())
        self._panel_animation.setEndValue(end_rect.topLeft())
        self._panel_animation.start()

    def _on_panel_animation_finished(self) -> None:
        """在关闭动画结束后隐藏覆盖层。"""
        if self._closing_after_animation and not self._expanded:
            self.hide()
        self._closing_after_animation = False

    def _sync_toggle_icon(self) -> None:
        """同步内置唤起按钮图标。"""
        icon_map = {
            DrawerPosition.LEFT: FluentIcon.RIGHT_ARROW,
            DrawerPosition.RIGHT: FluentIcon.LEFT_ARROW,
            DrawerPosition.TOP: FluentIcon.DOWN,
            DrawerPosition.BOTTOM: FluentIcon.UP,
        }
        self._toggle_button.setIcon(icon_map[self._position])

    def _sync_toggle_button_geometry(self) -> None:
        """同步内置唤起按钮位置。"""
        if not self._toggle_button_visible:
            self._toggle_button.hide()
            return

        panel_rect = self._panel.geometry()
        size = self._TOGGLE_BUTTON_SIZE
        if self._position == DrawerPosition.LEFT:
            x = panel_rect.right() + 8
            y = max(8, (self.height() - size) // 2)
        elif self._position == DrawerPosition.RIGHT:
            x = panel_rect.left() - size - 8
            y = max(8, (self.height() - size) // 2)
        elif self._position == DrawerPosition.TOP:
            x = max(8, (self.width() - size) // 2)
            y = panel_rect.bottom() + 8
        else:
            x = max(8, (self.width() - size) // 2)
            y = panel_rect.top() - size - 8

        self._toggle_button.setGeometry(x, y, size, size)
        self._toggle_button.show()

    def _apply_theme(self) -> None:
        """应用深浅两色主题样式。"""
        if self._is_applying_theme:
            return

        self._is_applying_theme = True
        if isDarkTheme():
            panel_bg = self._DARK_PANEL_BG
            text_color = "rgb(255, 255, 255)"
            hover = "rgba(255, 255, 255, 14)"
            pressed = "rgba(255, 255, 255, 22)"
        else:
            panel_bg = self._LIGHT_PANEL_BG
            text_color = "rgb(0, 0, 0)"
            hover = "rgba(0, 0, 0, 8)"
            pressed = "rgba(0, 0, 0, 12)"

        style_sheet = f"""
            QFrame#slidingDrawerPanel {{
                background: {panel_bg};
                border: none;
            }}
            QLabel#slidingDrawerTitleLabel {{
                color: {text_color};
                font: 18px "Microsoft YaHei";
                font-weight: 600;
                background: transparent;
            }}
            QWidget#slidingDrawerContent {{
                background: transparent;
                border: none;
            }}
            TransparentToolButton#slidingDrawerCloseButton,
            TransparentToolButton#slidingDrawerToggleButton {{
                border: none;
                border-radius: 6px;
                background: transparent;
            }}
            TransparentToolButton#slidingDrawerCloseButton:hover,
            TransparentToolButton#slidingDrawerToggleButton:hover {{
                background: {hover};
            }}
            TransparentToolButton#slidingDrawerCloseButton:pressed,
            TransparentToolButton#slidingDrawerToggleButton:pressed {{
                background: {pressed};
            }}
        """
        try:
            if self.styleSheet() != style_sheet:
                self.setStyleSheet(style_sheet)
        finally:
            self._is_applying_theme = False

    def _on_theme_changed(self, theme: Theme) -> None:
        """按组件库主题信号刷新样式。"""
        self._apply_theme()
        self._set_shadow_effect()
        self.update()

    def _set_shadow_effect(self) -> None:
        """设置面板阴影效果。"""
        shadow = QGraphicsDropShadowEffect(self._panel)
        shadow.setBlurRadius(self._PANEL_SHADOW_BLUR)
        shadow_alpha = self._PANEL_SHADOW_DARK_ALPHA if isDarkTheme() else self._PANEL_SHADOW_LIGHT_ALPHA
        shadow.setColor(QColor(0, 0, 0, shadow_alpha))
        shadow.setOffset(*self._PANEL_SHADOW_OFFSET)
        self._panel.setGraphicsEffect(shadow)

    def _mask_color(self) -> QColor:
        """返回遮罩颜色。"""
        return QColor(0, 0, 0, self.maskAlpha())

    def _shadow_rect(self) -> QRect:
        """返回面板边缘阴影渐变区域。"""
        panel_rect = self._panel.geometry()
        shadow_width = self._EDGE_SHADOW_WIDTH
        if self._position == DrawerPosition.LEFT:
            return QRect(panel_rect.right(), 0, shadow_width, self.height())
        if self._position == DrawerPosition.RIGHT:
            return QRect(panel_rect.left() - shadow_width, 0, shadow_width, self.height())
        if self._position == DrawerPosition.TOP:
            return QRect(0, panel_rect.bottom(), self.width(), shadow_width)
        return QRect(0, panel_rect.top() - shadow_width, self.width(), shadow_width)

    def _shadow_gradient(self) -> QLinearGradient:
        """返回面板边缘阴影渐变。"""
        rect = self._shadow_rect()
        if self._position == DrawerPosition.LEFT:
            gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        elif self._position == DrawerPosition.RIGHT:
            gradient = QLinearGradient(rect.right(), 0, rect.left(), 0)
        elif self._position == DrawerPosition.TOP:
            gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        else:
            gradient = QLinearGradient(0, rect.bottom(), 0, rect.top())

        alpha = self.edgeShadowAlpha()
        gradient.setColorAt(0, QColor(0, 0, 0, alpha))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        return gradient

    def _is_horizontal(self) -> bool:
        """返回当前方向是否为左右抽屉。"""
        return self._position in (DrawerPosition.LEFT, DrawerPosition.RIGHT)
