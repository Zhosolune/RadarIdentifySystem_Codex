"""响应式内容宽度适配。"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QLayout, QWidget


class ResponsiveContentWidthAdapter(QObject):
    """让目标布局在宽视口中保持最大内容宽度并水平居中。

    Attributes:
        width_source [QWidget]: 提供当前可用宽度的控件。
        target_layout [QLayout]: 接收动态边距的布局。
    """

    def __init__(
        self,
        width_source: QWidget,
        target_layout: QLayout,
        *,
        max_content_width: int,
        minimum_horizontal_margin: int = 36,
        top_margin: int = 10,
        bottom_margin: int = 0,
        parent: QObject | None = None,
    ) -> None:
        """初始化响应式边距适配器。

        Args:
            width_source [QWidget]: 提供可用宽度并接收 Resize 事件的控件。
            target_layout [QLayout]: 需要更新内容边距的目标布局。
            max_content_width [int]: 内容区允许占用的最大宽度。
            minimum_horizontal_margin [int]: 最小左右边距，默认 36px。
            top_margin [int]: 顶部边距，默认 10px。
            bottom_margin [int]: 底部边距，默认 0px。
            parent [QObject | None]: 生命周期父对象，默认跟随宽度来源控件。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 最大内容宽度非正数或边距为负数时抛出。
        """
        if max_content_width <= 0:
            raise ValueError("max_content_width 必须大于 0")
        if min(
            minimum_horizontal_margin,
            top_margin,
            bottom_margin,
        ) < 0:
            raise ValueError("布局边距不能为负数")

        super().__init__(parent or width_source)
        self.width_source = width_source
        self.target_layout = target_layout
        self.max_content_width = max_content_width
        self.minimum_horizontal_margin = minimum_horizontal_margin
        self.top_margin = top_margin
        self.bottom_margin = bottom_margin

        width_source.installEventFilter(self)
        self.update_margins()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """在宽度来源控件变化时刷新布局边距。

        Args:
            watched [QObject]: 当前被监听对象。
            event [QEvent]: Qt 事件。

        Returns:
            bool: 父类事件过滤结果。
        """
        if (
            watched is self.width_source
            and event.type() == QEvent.Type.Resize
        ):
            self.update_margins()
        return super().eventFilter(watched, event)

    def update_margins(self) -> None:
        """根据当前宽度更新目标布局左右边距。

        Returns:
            None: 无返回值。
        """
        horizontal_margin = max(
            self.minimum_horizontal_margin,
            (self.width_source.width() - self.max_content_width) // 2,
        )
        self.target_layout.setContentsMargins(
            horizontal_margin,
            self.top_margin,
            horizontal_margin,
            self.bottom_margin,
        )
