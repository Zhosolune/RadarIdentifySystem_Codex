"""滚动区域悬停显隐适配。"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QAbstractScrollArea


class HoverScrollBarAdapter(QObject):
    """统一 Qt 原生与 Fluent 覆盖式滚动条的悬停按需显示策略。

    Attributes:
        scroll_area [QAbstractScrollArea]: 当前适配的滚动区域。
    """

    def __init__(self, scroll_area: QAbstractScrollArea) -> None:
        """记录原始方向策略并立即隐藏滚动条。

        Args:
            scroll_area [QAbstractScrollArea]: 需要应用悬停策略的滚动区域。

        Returns:
            None: 无返回值。
        """
        super().__init__(scroll_area)
        self.scroll_area = scroll_area
        self._viewport = scroll_area.viewport()
        self._fluent_bars: list[tuple[Any, bool]] = []
        self._native_policies: (
            tuple[Qt.ScrollBarPolicy, Qt.ScrollBarPolicy] | None
        ) = None
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.timeout.connect(self._hide_if_pointer_outside)

        scroll_delegate = getattr(scroll_area, "scrollDelagate", None)
        if scroll_delegate is None:
            scroll_delegate = getattr(scroll_area, "delegate", None)

        vertical_bar = getattr(scroll_delegate, "vScrollBar", None)
        horizontal_bar = getattr(scroll_delegate, "hScrollBar", None)
        if vertical_bar is not None and horizontal_bar is not None:
            # Fluent 的 Qt 原生策略始终为 AlwaysOff，允许方向只能从代理读取。
            self._fluent_bars = [
                (vertical_bar, not vertical_bar._isForceHidden),
                (horizontal_bar, not horizontal_bar._isForceHidden),
            ]
        else:
            self._native_policies = (
                scroll_area.verticalScrollBarPolicy(),
                scroll_area.horizontalScrollBarPolicy(),
            )

        scroll_area.installEventFilter(self)
        self._viewport.installEventFilter(self)
        self._hide_scroll_bars()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """按鼠标是否位于滚动区域内切换滚动条策略。

        Args:
            watched [QObject]: 当前接收事件的滚动区域或其视口。
            event [QEvent]: Qt 事件。

        Returns:
            bool: 父类事件过滤结果。
        """
        if watched is self.scroll_area or watched is self._viewport:
            if event.type() == QEvent.Type.Enter:
                self._leave_timer.stop()
                self._show_scroll_bars_if_needed()
            elif (
                watched is self.scroll_area
                and event.type() == QEvent.Type.Leave
            ):
                self._leave_timer.stop()
                self._hide_scroll_bars()
            elif event.type() == QEvent.Type.Leave:
                # 从视口移到覆盖式滚动条时仍位于滚动区域内，延后核验位置。
                self._leave_timer.start(0)
        return super().eventFilter(watched, event)

    def _hide_if_pointer_outside(self) -> None:
        """指针确已离开整个滚动区域时再隐藏滚动条。"""
        local_position = self.scroll_area.mapFromGlobal(QCursor.pos())
        if not self.scroll_area.rect().contains(local_position):
            self._hide_scroll_bars()

    def _show_scroll_bars_if_needed(self) -> None:
        """恢复允许方向，具体显隐继续由实际滚动范围决定。"""
        if self._native_policies is not None:
            vertical_policy, horizontal_policy = self._native_policies
            self.scroll_area.setVerticalScrollBarPolicy(vertical_policy)
            self.scroll_area.setHorizontalScrollBarPolicy(horizontal_policy)
            return

        for bar, was_allowed in self._fluent_bars:
            bar.setForceHidden(not was_allowed)

    def _hide_scroll_bars(self) -> None:
        """隐藏滚动区域的全部原生或 Fluent 滚动条。"""
        if self._native_policies is not None:
            self.scroll_area.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            return

        for bar, _ in self._fluent_bars:
            bar.setForceHidden(True)
