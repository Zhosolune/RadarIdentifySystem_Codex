# -*- coding: utf-8 -*-
"""仿 Edge 浏览器风格的标签页组件。

提供 EdgeTabItem、EdgeTabBar、EdgeTabWidget 三层结构，
标签带上圆角和底部反向圆角（concave corners），激活标签与内容区轮廓一体式绘制。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QRect, QSize, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QIcon,
    QMouseEvent, QFontMetrics
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QSizePolicy
)

from qfluentwidgets import isDarkTheme, FluentIconBase, drawIcon


class EdgeTabContentStack(QStackedWidget):
    """仿 Edge 标签页内容堆叠区。

    仅承载标签页内容，背景和外轮廓由 `EdgeTabWidget` 一体式绘制。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件。
        """
        super().__init__(parent)

    def paintEvent(self, event) -> None:
        """保留默认内容绘制，不再绘制背景和边框。

        Args:
            event: Qt 绘制事件。

        Returns:
            None。

        Raises:
            无。
        """
        super().paintEvent(event)


class EdgeTabItem(QWidget):
    """仿 Edge 单个标签内容项。

    仅负责标签的点击区域、悬浮状态以及图标文字绘制，
    激活标签轮廓由 `EdgeTabWidget.paintEvent()` 与内容区一体式绘制。

    Attributes:
        text: 标签文字。
        isSelected: 是否为当前激活标签。
    """

    clicked = pyqtSignal()

    # 绘制参数
    _TOP_RADIUS = 8         # 上圆角半径
    _CONCAVE_RADIUS = 6     # 底部反向圆角半径
    _OVERLAP = 10           # 反向圆角的水平延伸宽度
    _TOP_MARGIN = 4         # 标签顶部留白
    _HEIGHT = 36            # 标签固定高度
    _PADDING_H = 12         # 文字水平内边距

    def __init__(
        self, text: str = "", parent: QWidget | None = None,
        icon: QIcon | str | FluentIconBase | None = None
    ) -> None:
        """
        Args:
            text: 标签显示文字。
            parent: 父级控件。
            icon: 标签图标，可选。
        """
        super().__init__(parent)
        self._text = text
        self._icon = icon
        self.isSelected = False
        self.isHover = False
        self.isPressed = False
        self._routeKey: str = ""

        self.setFixedHeight(self._HEIGHT)
        self.setMinimumWidth(64)
        self.setMaximumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    # ── 公共接口 ──────────────────────────────────────────────────────

    def text(self) -> str:
        """返回标签文字。"""
        return self._text

    def setText(self, text: str) -> None:
        """设置标签文字。"""
        self._text = text
        self.update()

    def icon(self) -> QIcon | str | FluentIconBase | None:
        """返回标签图标。"""
        return self._icon

    def setIcon(self, icon: QIcon | str | FluentIconBase | None) -> None:
        """设置标签图标。"""
        self._icon = icon
        self.update()

    def routeKey(self) -> str:
        """返回路由键。"""
        return self._routeKey

    def setRouteKey(self, key: str) -> None:
        """设置路由键。"""
        self._routeKey = key

    def setSelected(self, selected: bool) -> None:
        """设置选中状态。"""
        self.isSelected = selected
        self.update()
        self._updateBar()

    # ── 事件处理 ──────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self.isHover = True
        self.update()
        self._updateBar()

    def leaveEvent(self, event) -> None:
        self.isHover = False
        self.isPressed = False
        self.update()
        self._updateBar()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.isPressed = True
            self.update()
            self._updateBar()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.isPressed = False
            self.clicked.emit()
            self.update()
            self._updateBar()

    # ── 尺寸提示 ──────────────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        """计算理想宽度（仅内容宽度，不含外扩圆角区域）。

        Args:
            无。

        Returns:
            QSize: 受当前最小宽度和最大宽度约束后的标签尺寸。

        Raises:
            无。
        """
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self._text)
        icon_w = 22 if self._icon else 0
        # 仅为内容区预留空间，外扩圆角在父级容器统一绘制
        w = self._PADDING_H * 2 + icon_w + text_w
        min_w = self.minimumWidth()
        max_w = max(min_w, self.maximumWidth())
        return QSize(max(min(w, max_w), min_w), self._HEIGHT)

    # ── 绘制 ──────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        """绘制标签图标与文字。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制图标
        if self._icon:
            icon_x = self._PADDING_H
            icon_rect = QRectF(icon_x, (self._HEIGHT - 16) / 2, 16, 16)
            if not self.isSelected:
                painter.setOpacity(0.7)
            drawIcon(self._icon, painter, icon_rect)
            painter.setOpacity(1.0)

        # 绘制文字
        self._drawText(painter)
        painter.end()

    def _drawText(self, painter: QPainter) -> None:
        """绘制标签文字。"""
        dark = isDarkTheme()
        pad = self._PADDING_H

        # 文字绘制区域
        text_x = pad + (22 if self._icon else 0)
        text_rect = QRectF(text_x, 0, self.width() - text_x - pad, self._HEIGHT)

        color = QColor(Qt.GlobalColor.white) if dark else QColor(Qt.GlobalColor.black)
        if not self.isSelected:
            color.setAlphaF(0.7)

        painter.setPen(QPen(color))
        font = self.font()
        font.setBold(self.isSelected)
        painter.setFont(font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text
        )

    def _updateBar(self) -> None:
        """触发父级标签栏重绘。"""
        parent = self.parentWidget()
        if parent is not None:
            parent.update()


class EdgeTabBar(QWidget):
    """仿 Edge 标签条。

    水平排列 EdgeTabItem，管理标签切换与当前索引。
    仅负责标签排列、切换和未选中标签悬浮态，激活标签轮廓由父级容器绘制。

    Attributes:
        items: 所有标签项列表。
        currentIndex: 当前激活标签索引。
    """

    currentChanged = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件。
        """
        super().__init__(parent)
        self.items: list[EdgeTabItem] = []
        self._currentIndex: int = -1
        self._tabMinimumWidth: int = 64
        self._tabMaximumWidth: int = 200

        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(EdgeTabItem._HEIGHT + 4)  # 标签高度 + 上下留白
        self._hLayout = QHBoxLayout(self)
        self._hLayout.setContentsMargins(12, 0, 0, 0)  # 左移半圆角，对齐内容区圆角
        # 标签的逻辑宽度彼此贴紧，外扩圆角由父级容器统一绘制
        self._hLayout.setSpacing(0)
        self._hLayout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        # 右侧弹性留白
        self._hLayout.addStretch(1)

    # ── 公共接口 ──────────────────────────────────────────────────────

    def addTab(
        self, routeKey: str, text: str,
        icon: QIcon | str | FluentIconBase | None = None
    ) -> int:
        """添加一个标签。

        Args:
            routeKey: 标签唯一路由键。
            text: 标签显示文字。
            icon: 标签图标，可选。

        Returns:
            新标签的索引位置。
        """
        item = EdgeTabItem(text, self, icon)
        item.setRouteKey(routeKey)
        item.setMinimumWidth(self._tabMinimumWidth)
        item.setMaximumWidth(max(self._tabMinimumWidth, self._tabMaximumWidth))
        item.clicked.connect(lambda: self._onItemClicked(item))

        index = len(self.items)
        self.items.append(item)
        # 插入到 stretch 之前
        self._hLayout.insertWidget(index, item)

        # 首个标签自动选中
        if self._currentIndex == -1:
            self.setCurrentIndex(0)

        return index

    def setCurrentIndex(self, index: int) -> None:
        """设置当前激活标签索引。

        Args:
            index: 目标标签索引。
        """
        if index == self._currentIndex:
            return
        if not (0 <= index < len(self.items)):
            return

        # 取消旧选中
        if 0 <= self._currentIndex < len(self.items):
            self.items[self._currentIndex].setSelected(False)

        self._currentIndex = index
        self.items[index].setSelected(True)
        # 触发父级重绘，统一刷新激活标签和内容区轮廓
        self.update()
        self.currentChanged.emit(index)

    def currentIndex(self) -> int:
        """返回当前激活标签索引。"""
        return self._currentIndex

    def setTabMaximumWidth(self, width: int) -> None:
        """设置标签最大宽度，并应用到当前和后续新增标签。

        Args:
            width: 标签最大宽度，单位为像素。

        Returns:
            None。

        Raises:
            无。
        """
        self._tabMaximumWidth = max(1, width)
        for item in self.items:
            item.setMaximumWidth(max(item.minimumWidth(), self._tabMaximumWidth))
            item.updateGeometry()
        self._refreshTabGeometry()

    def setTabMinimumWidth(self, width: int) -> None:
        """设置标签最小宽度，并应用到当前和后续新增标签。

        Args:
            width: 标签最小宽度，单位为像素。

        Returns:
            None。

        Raises:
            无。
        """
        self._tabMinimumWidth = max(1, width)
        for item in self.items:
            item.setMinimumWidth(self._tabMinimumWidth)
            item.setMaximumWidth(max(self._tabMinimumWidth, self._tabMaximumWidth))
            item.updateGeometry()
        self._refreshTabGeometry()

    def _refreshTabGeometry(self) -> None:
        """刷新标签栏布局和父级一体化轮廓。

        Args:
            无。

        Returns:
            None。

        Raises:
            无。
        """
        self._hLayout.invalidate()
        self._hLayout.activate()
        self.updateGeometry()
        self.update()
        parent = self.parentWidget()
        if parent is not None:
            parent.update()

    def count(self) -> int:
        """返回标签数量。"""
        return len(self.items)

    def tabRect(self, index: int) -> QRect:
        """返回指定索引标签在 EdgeTabBar 坐标系内的矩形。

        Args:
            index: 标签索引。

        Returns:
            标签矩形，索引越界时返回空矩形。
        """
        if 0 <= index < len(self.items):
            return self.items[index].geometry()
        return QRect()

    # ── 绘制 ──────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        """绘制未选中标签的悬浮态。

        Args:
            event: Qt 绘制事件。

        Returns:
            None。

        Raises:
            无。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for item in self.items:
            if item.isSelected:
                continue
            if item.isHover or item.isPressed:
                self._drawHoverTabBackground(painter, item)

        painter.end()

    def _drawHoverTabBackground(self, painter: QPainter, item: EdgeTabItem) -> None:
        """绘制悬浮标签背景。"""
        dark = isDarkTheme()
        rect = QRectF(item.geometry())
        radius_top = float(EdgeTabItem._TOP_RADIUS)
        radius_concave = float(EdgeTabItem._CONCAVE_RADIUS)
        if item.isPressed:
            color = QColor(255, 255, 255, 12) if dark else QColor(0, 0, 0, 7)
        else:
            color = QColor(255, 255, 255, 18) if dark else QColor(0, 0, 0, 10)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(rect.adjusted(0, 0, 0, 0), radius_top, radius_concave)

    # ── 内部方法 ──────────────────────────────────────────────────────

    def _onItemClicked(self, item: EdgeTabItem) -> None:
        """标签点击槽函数。"""
        index = self.items.index(item)
        self.setCurrentIndex(index)


class EdgeTabWidget(QWidget):
    """仿 Edge 标签页容器。

    垂直排列 EdgeTabBar + QStackedWidget，标签条底部与内容区顶部
    重叠 1px，激活标签的形状覆盖内容区上边框，形成视觉相通效果。

    Attributes:
        tabBar: 标签条。
        stackedWidget: 内容堆叠区。
    """

    currentChanged = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件。
        """
        super().__init__(parent)
        self.tabBar = EdgeTabBar(self)
        self.stackedWidget = EdgeTabContentStack(self)
        self.stackedWidget.setObjectName("edgeTabContent")

        self._initLayout()
        self._connectSignals()

    def _initLayout(self) -> None:
        """构建垂直布局，标签条与内容区重叠 1px。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # 标签向下多画 1px 覆盖内容区上边框，消除缝隙
        layout.setSpacing(0)
        layout.addWidget(self.tabBar, 0)
        layout.addWidget(self.stackedWidget, 1)
        # 提升标签条 z 序，使其绘制在内容区之上
        self.tabBar.raise_()

        # 内容区只承载页面，背景和外轮廓由父容器一体式绘制
        self._applyContentStyle()

    def _applyContentStyle(self) -> None:
        """将内容承载区设为透明，避免遮挡父级一体化轮廓。

        Args:
            无。

        Returns:
            None。

        Raises:
            无。
        """
        self.stackedWidget.setAutoFillBackground(False)
        self.stackedWidget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.stackedWidget.setStyleSheet(
            "QStackedWidget#edgeTabContent { background: transparent; border: none; }"
        )

    def _connectSignals(self) -> None:
        """连接标签栏信号到内容区切换。"""
        self.tabBar.currentChanged.connect(self._onCurrentTabChanged)

    # ── 绘制 ──────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        """一体式绘制当前标签与内容区的背景和轮廓。

        Args:
            event: Qt 绘制事件。

        Returns:
            None。

        Raises:
            无。
        """
        super().paintEvent(event)
        self._drawUnifiedPanel()

    def _drawUnifiedPanel(self) -> None:
        """绘制标签和内容区共用的一条连续轮廓。

        Args:
            无。

        Returns:
            None。

        Raises:
            无。
        """
        path = self._buildUnifiedPanelPath()
        if path.isEmpty():
            return

        dark = isDarkTheme()
        fill_color = QColor(45, 45, 45) if dark else QColor(255, 255, 255)
        border_color = QColor(255, 255, 255, 25) if dark else QColor(0, 0, 0, 20)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_color)
        painter.drawPath(path)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()

    def _buildUnifiedPanelPath(self) -> QPainterPath:
        """构建包含激活标签凸起和内容区外框的一体化路径。

        Args:
            无。

        Returns:
            QPainterPath: 一条连续闭合的外轮廓路径；控件尺寸无效时返回空路径。

        Raises:
            无。
        """
        content_rect = QRectF(self.stackedWidget.geometry()).adjusted(
            0.5, 0.5, -0.5, -0.5
        )
        if content_rect.width() <= 0 or content_rect.height() <= 0:
            return QPainterPath()

        active_idx = self.tabBar.currentIndex()
        if not (0 <= active_idx < self.tabBar.count()):
            return self._buildRoundedContentPath(content_rect)

        active_item = self.tabBar.items[active_idx]
        tab_rect = QRectF(
            self.tabBar.geometry().x() + active_item.geometry().x(),
            self.tabBar.geometry().y() + active_item.geometry().y(),
            active_item.geometry().width(),
            active_item.geometry().height(),
        )
        return self._buildTabbedContentPath(content_rect, tab_rect)

    def _buildRoundedContentPath(self, rect: QRectF) -> QPainterPath:
        """构建无激活标签时的内容区圆角路径。

        Args:
            rect: 内容区在当前控件坐标系内的矩形。

        Returns:
            QPainterPath: 内容区圆角外轮廓路径。

        Raises:
            无。
        """
        radius = 8.0
        path = QPainterPath()
        path.moveTo(rect.left() + radius, rect.top())
        path.lineTo(rect.right() - radius, rect.top())
        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
        path.lineTo(rect.right(), rect.bottom() - radius)
        path.quadTo(rect.right(), rect.bottom(), rect.right() - radius, rect.bottom())
        path.lineTo(rect.left() + radius, rect.bottom())
        path.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - radius)
        path.lineTo(rect.left(), rect.top() + radius)
        path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
        path.closeSubpath()
        return path

    def _buildTabbedContentPath(
        self,
        content_rect: QRectF,
        tab_rect: QRectF,
    ) -> QPainterPath:
        """构建带激活标签凸起的内容区一体化路径。

        Args:
            content_rect: 内容区在当前控件坐标系内的矩形。
            tab_rect: 激活标签在当前控件坐标系内的矩形。

        Returns:
            QPainterPath: 标签与内容区共用的一条闭合路径。

        Raises:
            无。
        """
        radius = 8.0
        tab_radius = float(EdgeTabItem._TOP_RADIUS)
        concave_radius = float(EdgeTabItem._CONCAVE_RADIUS)
        overlap = float(EdgeTabItem._OVERLAP)

        left = content_rect.left()
        top = content_rect.top()
        right = content_rect.right()
        bottom = content_rect.bottom()
        inner_left = tab_rect.left()
        inner_right = tab_rect.right()
        tab_top = self.tabBar.geometry().y() + EdgeTabItem._TOP_MARGIN + 0.5

        # 首尾标签靠近内容区圆角时，避免反向圆角压到内容区自身圆角描边。
        outer_left = max(left + radius, inner_left - overlap)
        outer_right = min(right - radius, inner_right + overlap)
        if outer_left >= outer_right:
            return self._buildRoundedContentPath(content_rect)

        path = QPainterPath()
        path.moveTo(outer_left, top)
        path.lineTo(left + radius, top)
        path.quadTo(left, top, left, top + radius)
        path.lineTo(left, bottom - radius)
        path.quadTo(left, bottom, left + radius, bottom)
        path.lineTo(right - radius, bottom)
        path.quadTo(right, bottom, right, bottom - radius)
        path.lineTo(right, top + radius)
        path.quadTo(right, top, right - radius, top)
        path.lineTo(outer_right, top)
        path.cubicTo(
            inner_right + overlap / 2,
            top,
            inner_right,
            top,
            inner_right,
            top - concave_radius,
        )
        path.lineTo(inner_right, tab_top + tab_radius)
        path.quadTo(inner_right, tab_top, inner_right - tab_radius, tab_top)
        path.lineTo(inner_left + tab_radius, tab_top)
        path.quadTo(inner_left, tab_top, inner_left, tab_top + tab_radius)
        path.lineTo(inner_left, top - concave_radius)
        path.cubicTo(
            inner_left,
            top,
            inner_left - overlap / 2,
            top,
            outer_left,
            top,
        )
        path.closeSubpath()
        return path

    # ── 公共接口 ──────────────────────────────────────────────────────

    def addTab(
        self, widget: QWidget, text: str,
        icon: QIcon | str | FluentIconBase | None = None,
        routeKey: str | None = None
    ) -> int:
        """添加标签页。

        Args:
            widget: 标签对应的内容控件。
            text: 标签显示文字。
            icon: 标签图标，可选。
            routeKey: 路由键，默认使用 text。

        Returns:
            新标签页的索引位置。
        """
        key = routeKey or text
        self.stackedWidget.addWidget(widget)
        self.tabBar.addTab(key, text, icon)
        self.update()
        return self.stackedWidget.count() - 1

    def setCurrentIndex(self, index: int) -> None:
        """设置当前显示的标签页索引。

        Args:
            index: 目标索引。
        """
        self.tabBar.setCurrentIndex(index)
        self.stackedWidget.setCurrentIndex(index)

    def currentIndex(self) -> int:
        """返回当前标签页索引。"""
        return self.stackedWidget.currentIndex()

    def currentWidget(self) -> QWidget:
        """返回当前显示的内容控件。"""
        return self.stackedWidget.currentWidget()

    def widget(self, index: int) -> QWidget:
        """返回指定索引的内容控件。

        Args:
            index: 标签页索引。

        Returns:
            对应的内容控件。
        """
        return self.stackedWidget.widget(index)

    def count(self) -> int:
        """返回标签页数量。"""
        return self.stackedWidget.count()

    def setTabMaximumWidth(self, width: int) -> None:
        """设置标签最大宽度。"""
        self.tabBar.setTabMaximumWidth(width)

    def setTabMinimumWidth(self, width: int) -> None:
        """设置标签最小宽度。"""
        self.tabBar.setTabMinimumWidth(width)

    # ── 内部槽函数 ────────────────────────────────────────────────────

    def _onCurrentTabChanged(self, index: int) -> None:
        """标签切换联动内容区。"""
        if not (0 <= index < self.stackedWidget.count()):
            return
        self.stackedWidget.setCurrentIndex(index)
        self.update()
        self.currentChanged.emit(index)

    def resizeEvent(self, event) -> None:
        """在尺寸变化后刷新父级一体化轮廓。

        Args:
            event: Qt 尺寸变化事件。

        Returns:
            None。

        Raises:
            无。
        """
        super().resizeEvent(event)
        self.update()
