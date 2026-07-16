"""原始切片图像列组件。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    ToolTipFilter,
    ToolTipPosition,
    TransparentToolButton,
    themeColor,
)

from app.custom_icon import CustomIcon

from .slice_dimension_card import SliceDimensionCard


class OriginalImageColumn(QWidget):
    """管理原始切片标题、导航按钮和五维图像卡片。

    Attributes:
        prev_button [TransparentToolButton]: 切换上一切片的标题栏按钮。
        next_button [TransparentToolButton]: 切换下一切片的标题栏按钮。
        title_label [QLabel]: 原始切片图像列标题。
        dimension_cards [tuple[SliceDimensionCard, ...]]: 五维图像卡片集合。
        cards_by_dimension [dict[str, SliceDimensionCard]]: 维度名到图像卡片的映射。
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scale_mode_getter: Callable[[], str] | None = None,
    ) -> None:
        """初始化原始切片图像列。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。
            scale_mode_getter [Callable[[], str] | None]: 当前图像缩放模式读取回调。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("sliceLeftColumn")

        self.prev_button = self._create_navigation_button(
            CustomIcon.CHEVRONS_LEFT,
            "上一片",
        )
        self.next_button = self._create_navigation_button(
            CustomIcon.CHEVRONS_RIGHT,
            "下一片",
        )
        self.title_label = QLabel("第0个切片数据  原始图像", self)
        self.title_label.setObjectName("sliceLeftTitle")
        self._configure_title_label()

        self.cf_card = self._create_dimension_card(
            "载频", "originalCfCard", "原始图像 - 载频", scale_mode_getter
        )
        self.pw_card = self._create_dimension_card(
            "脉宽", "originalPwCard", "原始图像 - 脉宽", scale_mode_getter
        )
        self.pa_card = self._create_dimension_card(
            "幅度", "originalPaCard", "原始图像 - 幅度", scale_mode_getter
        )
        self.dtoa_card = self._create_dimension_card(
            "一级差", "originalDtoaCard", "原始图像 - 一级差", scale_mode_getter
        )
        self.doa_card = self._create_dimension_card(
            "方位角", "originalDoaCard", "原始图像 - 方位角", scale_mode_getter
        )
        self.cards_by_dimension = {
            "CF": self.cf_card,
            "PW": self.pw_card,
            "PA": self.pa_card,
            "DTOA": self.dtoa_card,
            "DOA": self.doa_card,
        }
        self.dimension_cards = tuple(self.cards_by_dimension.values())
        self._init_layout()

    def set_title(self, title: str) -> None:
        """设置原始切片图像列标题。

        Args:
            title [str]: 需要显示的非空标题。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当标题为空时抛出。
        """
        if not title.strip():
            raise ValueError("title 不能为空")
        self.title_label.setText(title)

    def set_snapshot_slice_number(self, slice_number: int) -> None:
        """同步设置五维图像快照窗口的切片编号。

        Args:
            slice_number [int]: 当前显示的 1-based 切片编号，必须大于等于 1。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片编号小于 1 时由维度卡片抛出。
        """
        for card in self.dimension_cards:
            card.set_snapshot_slice_number(slice_number)

    def update_icon_colors(self) -> None:
        """根据当前主题刷新标题栏导航图标颜色。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        light_color = themeColor()
        dark_color = QColor("white")
        self.prev_button.setIcon(
            CustomIcon.CHEVRONS_LEFT.colored(light_color, dark_color)
        )
        self.next_button.setIcon(
            CustomIcon.CHEVRONS_RIGHT.colored(light_color, dark_color)
        )

    def _create_navigation_button(
        self,
        icon: CustomIcon,
        tooltip: str,
    ) -> TransparentToolButton:
        """创建标题栏导航按钮。"""
        button = TransparentToolButton(
            icon.colored(themeColor(), QColor("white")),
            self,
        )
        button.setFixedSize(25, 25)
        button.setIconSize(QSize(20, 20))
        button.setToolTip(tooltip)
        button.installEventFilter(
            ToolTipFilter(button, 1000, ToolTipPosition.TOP)
        )
        return button

    def _create_dimension_card(
        self,
        title: str,
        object_name: str,
        snapshot_title: str,
        scale_mode_getter: Callable[[], str] | None,
    ) -> SliceDimensionCard:
        """创建一个归属于当前图像列的维度卡片。"""
        return SliceDimensionCard(
            title,
            object_name,
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title=snapshot_title,
        )

    def _configure_title_label(self) -> None:
        """配置标题标签的稳定宽度策略。"""
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(25)
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

    def _init_layout(self) -> None:
        """创建标题栏和五维图像卡片布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.addSpacing(33)
        title_layout.addWidget(self.prev_button)
        title_layout.addWidget(self.title_label, 1)
        title_layout.addWidget(self.next_button)

        layout.addLayout(title_layout)
        for card in self.dimension_cards:
            layout.addWidget(card, 1)
