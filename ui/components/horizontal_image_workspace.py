"""A/B/C/D 等宽横向滑动工作区。"""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt
from PyQt6.QtGui import QResizeEvent, QWheelEvent
from PyQt6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import SmoothScrollArea


class HorizontalImageWorkspace(SmoothScrollArea):
    """承载四个等宽面板并提供双列视口的横向滑动交互。

    普通状态锁定在 A+B；合并状态解除锁定并自动定位到 C+D。
    解锁后支持横向滚动及纵向滚轮转横向滚动，停止滚动时吸附到
    A+B、B+C 或 C+D 三个完整双列位置。

    Attributes:
        panels [tuple[QWidget, ...]]: 按 A、B、C、D 顺序排列的四个面板。
        content_widget [QWidget]: 承载四个面板的横向内容容器。
        content_layout [QHBoxLayout]: 四列等宽布局。
    """

    PANEL_COUNT = 4
    VISIBLE_PANEL_COUNT = 2
    COLUMN_SPACING = 12
    SNAP_DELAY_MS = 180
    SCROLL_ANIMATION_MS = 420

    def __init__(
        self,
        panels: Sequence[QWidget],
        parent: QWidget | None = None,
    ) -> None:
        """初始化四列横向滑动工作区。

        Args:
            panels [Sequence[QWidget]]: 严格按 A、B、C、D 顺序提供的四个面板。
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当面板数量不是四个时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication, QWidget
            >>> app = QApplication.instance() or QApplication([])
            >>> workspace = HorizontalImageWorkspace([QWidget() for _ in range(4)])
            >>> workspace.is_locked()
            True
        """
        if len(panels) != self.PANEL_COUNT:
            raise ValueError("横向图像工作区必须按 A/B/C/D 提供四个面板")

        super().__init__(parent)
        self.setObjectName("horizontalImageWorkspace")
        self.panels = tuple(panels)
        self._locked = True
        self._merge_active = False
        self._current_pair_index = 0
        self._panel_width = 1

        # 使用从属定时器延后恢复滚动位置，组件销毁时可自动取消回调。
        self._resize_sync_timer = QTimer(self)
        self._resize_sync_timer.setSingleShot(True)
        self._resize_sync_timer.timeout.connect(self._restore_pair_after_resize)

        self.content_widget = QWidget(self)
        self.content_widget.setObjectName("horizontalImageWorkspaceContent")
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(self.COLUMN_SPACING)
        for panel in self.panels:
            self.content_layout.addWidget(panel)

        self.setWidget(self.content_widget)
        self.setWidgetResizable(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.enableTransparentBackground()
        self.setScrollAnimation(
            Qt.Orientation.Horizontal,
            self.SCROLL_ANIMATION_MS,
        )

        # 自身事件过滤器后安装，优先处理锁定状态和纵向滚轮转横向滚动。
        self.viewport().installEventFilter(self)
        self._snap_timer = QTimer(self)
        self._snap_timer.setSingleShot(True)
        self._snap_timer.setInterval(self.SNAP_DELAY_MS)
        self._snap_timer.timeout.connect(self._snap_to_nearest_pair)

        horizontal_bar = self.delegate.hScrollBar
        horizontal_bar.valueChanged.connect(self._schedule_snap)
        horizontal_bar.sliderPressed.connect(self._snap_timer.stop)
        horizontal_bar.sliderReleased.connect(self._schedule_snap)

    def is_locked(self) -> bool:
        """返回当前是否锁定横向浏览。

        Returns:
            bool: ``True`` 表示普通状态下锁定在 A+B。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication, QWidget
            >>> app = QApplication.instance() or QApplication([])
            >>> workspace = HorizontalImageWorkspace([QWidget() for _ in range(4)])
            >>> workspace.is_locked()
            True
        """
        return self._locked

    def is_merge_active(self) -> bool:
        """返回合并滑动模式是否已激活。

        Returns:
            bool: ``True`` 表示当前允许用户横向浏览 A/B/C/D。

        Raises:
            无显式抛出异常。
        """
        return self._merge_active

    def panel_width(self) -> int:
        """返回当前单列面板宽度。

        Returns:
            int: 根据视口宽度计算的单列像素宽度。

        Raises:
            无显式抛出异常。
        """
        return self._panel_width

    def current_pair_index(self) -> int:
        """返回当前吸附位置的左侧面板索引。

        Returns:
            int: ``0``、``1``、``2``，分别对应 A+B、B+C、C+D。

        Raises:
            无显式抛出异常。
        """
        return self._current_pair_index

    def set_merge_active(self, active: bool) -> None:
        """切换普通锁定模式与合并横向浏览模式。

        Args:
            active [bool]: ``True`` 时解锁并滑动到 C+D；否则返回 A+B 并锁定。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self._merge_active = active
        self._locked = not active
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if active
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_to_pair(2 if active else 0, animated=True)

    def scroll_to_pair(self, pair_index: int, *, animated: bool = True) -> None:
        """将视口滚动到指定的完整双列位置。

        Args:
            pair_index [int]: 左侧面板索引，允许范围为 0 到 2。
            animated [bool]: 是否使用组件库平滑动画，默认值为 ``True``。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当双列位置索引不在 0 到 2 范围内时抛出。
        """
        maximum_pair_index = self.PANEL_COUNT - self.VISIBLE_PANEL_COUNT
        if not 0 <= pair_index <= maximum_pair_index:
            raise ValueError("pair_index 必须位于 0 到 2 之间")

        self._snap_timer.stop()
        self._current_pair_index = pair_index
        target = self._target_value(pair_index)
        self.delegate.hScrollBar.scrollTo(target, useAni=animated)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """拦截视口滚轮事件以落实锁定和横向浏览规则。"""
        if watched is self.viewport() and event.type() == QEvent.Type.Wheel:
            wheel_event = event
            if not isinstance(wheel_event, QWheelEvent):
                return super().eventFilter(watched, event)

            if self._locked:
                wheel_event.accept()
                return True

            delta = wheel_event.angleDelta()
            horizontal_delta = delta.x() if delta.x() != 0 else delta.y()
            if horizontal_delta != 0:
                self.delegate.hScrollBar.scrollValue(-horizontal_delta)
                wheel_event.accept()
                return True

        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """在视口尺寸变化时维持四列等宽和当前逻辑位置。"""
        previous_pair_index = self._current_pair_index
        super().resizeEvent(event)
        self._update_panel_sizes()
        self._current_pair_index = previous_pair_index
        self._resize_sync_timer.start(0)

    def _update_panel_sizes(self) -> None:
        """根据视口宽度计算单列宽度和内容容器尺寸。"""
        viewport_width = max(1, self.viewport().width())
        viewport_height = max(1, self.viewport().height())
        visible_spacing = self.COLUMN_SPACING * (self.VISIBLE_PANEL_COUNT - 1)
        self._panel_width = max(
            1,
            (viewport_width - visible_spacing) // self.VISIBLE_PANEL_COUNT,
        )

        for panel in self.panels:
            panel.setFixedWidth(self._panel_width)

        content_width = (
            self._panel_width * self.PANEL_COUNT
            + self.COLUMN_SPACING * (self.PANEL_COUNT - 1)
        )
        self.content_widget.setFixedSize(content_width, viewport_height)

    def _target_value(self, pair_index: int) -> int:
        """计算指定双列位置对应的水平滚动值。"""
        if pair_index == self.PANEL_COUNT - self.VISIBLE_PANEL_COUNT:
            return self.delegate.hScrollBar.maximum()
        return pair_index * (self._panel_width + self.COLUMN_SPACING)

    def _restore_pair_after_resize(self) -> None:
        """在滚动范围完成刷新后恢复当前双列位置。"""
        self.scroll_to_pair(self._current_pair_index, animated=False)

    def _schedule_snap(self, _value: int | None = None) -> None:
        """在用户停止滚动后安排按列吸附。"""
        if self._locked or self.delegate.hScrollBar.isSliderDown():
            return
        self._snap_timer.start()

    def _snap_to_nearest_pair(self) -> None:
        """将当前滚动值吸附到最近的完整双列位置。"""
        if self._locked:
            return

        step = max(1, self._panel_width + self.COLUMN_SPACING)
        pair_index = round(self.delegate.hScrollBar.value() / step)
        maximum_pair_index = self.PANEL_COUNT - self.VISIBLE_PANEL_COUNT
        pair_index = max(0, min(pair_index, maximum_pair_index))
        self.scroll_to_pair(pair_index, animated=True)
