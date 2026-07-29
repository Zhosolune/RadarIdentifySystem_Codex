# -*- coding: utf-8 -*-
"""模型名称滚动标签组件。"""

from __future__ import annotations

from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtWidgets import QSizePolicy, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ToolTipFilter,
    ToolTipPosition,
)


ScrollingLabelClass = type[BodyLabel] | type[CaptionLabel]


class ScrollingNameLabel(QWidget):
    """可滚动显示长文本的名称标签。

    功能描述：
        当文本宽度超过控件可用宽度时，自动以水平滚动方式展示完整内容；
        未超出时保持静态显示。

    Attributes:
        full_text: 当前完整文本。
        max_width: 标签最大宽度；None 表示交给父布局决定。
        scroll_gap: 主副标签之间的间隔宽度。
        scroll_step: 每次滚动的像素步长。
        scroll_timer: 文本滚动定时器。
        primary_label: 主显示标签。
        secondary_label: 补位显示标签。
    """

    def __init__(
        self,
        text: str,
        max_width: int | None = 240,
        parent: QWidget | None = None,
        *,
        label_class: ScrollingLabelClass = BodyLabel,
        label_object_name: str = "modelNameLabel",
    ) -> None:
        """初始化滚动名称标签。

        Args:
            text [str]: 初始显示文本。
            max_width [int | None]: 标签最大宽度；None 表示由父布局决定。
            parent [QWidget | None]: 父组件。
            label_class [ScrollingLabelClass]: 内部文本标签类，默认使用
                ``BodyLabel``，紧凑信息可传入 ``CaptionLabel``。
            label_object_name [str]: 主副标签共用的 QSS 对象名。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: max_width 不为 None 且小于 1 时抛出。
        """
        super().__init__(parent)
        if max_width is not None and max_width < 1:
            raise ValueError("max_width 必须大于 0 或为 None")
        self.full_text = ""
        self.max_width = max_width
        self.scroll_gap = 24
        self.scroll_step = 1
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(40)
        self.scroll_timer.timeout.connect(self._on_scroll_timeout)

        # 创建主文本标签
        self.primary_label = label_class(self)
        self.primary_label.setObjectName(label_object_name)
        # 创建补位文本标签
        self.secondary_label = label_class(self)
        self.secondary_label.setObjectName(label_object_name)
        self.secondary_label.hide()

        # 可选最大宽度；None 时让父布局分配全部可用宽度。
        if max_width is not None:
            self.setMaximumWidth(max_width)
        self.setMinimumWidth(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.installEventFilter(
            ToolTipFilter(self, 500, ToolTipPosition.BOTTOM)
        )
        self.setText(text)

    def setText(self, text: str) -> None:
        """设置标签文本。

        Args:
            text (str): 目标显示文本。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if text == self.full_text:
            return
        self.full_text = text
        self._scroll_offset = 0
        # 同步主副标签文本
        self.primary_label.setText(text)
        self.secondary_label.setText(text)
        self.setToolTip(text)
        self._update_scroll_state()

    def text(self) -> str:
        """返回当前完整文本。

        Returns:
            str: 未裁剪的完整标签文本。
        """
        return self.full_text

    def resizeEvent(self, event) -> None:
        """处理尺寸变化事件。

        Args:
            event (QResizeEvent): 尺寸变化事件。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        super().resizeEvent(event)
        # 刷新滚动布局
        self._update_scroll_state()

    def showEvent(self, event) -> None:
        """处理显示事件。

        Args:
            event (QShowEvent): 显示事件。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        super().showEvent(event)
        # 首次显示时刷新滚动布局
        self._update_scroll_state()

    def sizeHint(self) -> QSize:
        """返回建议尺寸。

        Args:
            无。

        Returns:
            QSize: 建议尺寸。

        Raises:
            无。
        """
        text_width = self.primary_label.fontMetrics().horizontalAdvance(self.full_text)
        label_height = self.primary_label.sizeHint().height()
        # 提供稳定建议宽度
        width_limit = self.max_width if self.max_width is not None else text_width
        return QSize(min(width_limit, max(96, text_width)), label_height)

    def minimumSizeHint(self) -> QSize:
        """返回最小建议尺寸。

        Args:
            无。

        Returns:
            QSize: 最小建议尺寸。

        Raises:
            无。
        """
        label_height = self.primary_label.sizeHint().height()
        return QSize(96, label_height)

    def _update_scroll_state(self) -> None:
        """刷新滚动状态。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        available_width = max(1, self.width())
        text_width = self.primary_label.fontMetrics().horizontalAdvance(self.full_text)
        label_height = self.primary_label.sizeHint().height()
        # 固定标签高度
        self.setFixedHeight(label_height)

        if text_width <= available_width:
            # 停止滚动并恢复静态显示
            self.scroll_timer.stop()
            self.primary_label.move(0, 0)
            self.primary_label.resize(available_width, label_height)
            self.secondary_label.hide()
            return

        # 启用双标签循环滚动
        self.primary_label.resize(text_width, label_height)
        self.secondary_label.resize(text_width, label_height)
        self.secondary_label.show()
        if not self.scroll_timer.isActive():
            self.scroll_timer.start()
        self._layout_scrolling_labels()

    def _layout_scrolling_labels(self) -> None:
        """布局滚动中的双标签。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        text_width = self.primary_label.width()
        cycle_width = text_width + self.scroll_gap
        current_offset = getattr(self, "_scroll_offset", 0) % cycle_width
        # 移动主标签
        self.primary_label.move(-current_offset, 0)
        # 移动补位标签
        self.secondary_label.move(text_width + self.scroll_gap - current_offset, 0)

    def _on_scroll_timeout(self) -> None:
        """处理滚动定时事件。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        text_width = self.primary_label.width()
        cycle_width = max(1, text_width + self.scroll_gap)
        # 更新滚动偏移
        self._scroll_offset = (
            getattr(self, "_scroll_offset", 0) + self.scroll_step
        ) % cycle_width
        self._layout_scrolling_labels()
