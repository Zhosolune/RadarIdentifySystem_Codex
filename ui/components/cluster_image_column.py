"""聚类图像列组件。"""

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


class ClusterImageColumn(QWidget):
    """管理聚类标题、类别导航按钮和五维图像卡片。

    Attributes:
        prev_button [TransparentToolButton]: 切换上一类别的标题栏按钮。
        next_button [TransparentToolButton]: 切换下一类别的标题栏按钮。
        title_label [QLabel]: 聚类图像列标题。
        dimension_cards [tuple[SliceDimensionCard, ...]]: 五维图像卡片集合。
        cards_by_dimension [dict[str, SliceDimensionCard]]: 维度名到图像卡片的映射。
    """

    EMPTY_TITLE = "暂无聚类结果"

    def __init__(
        self,
        parent: QWidget | None = None,
        scale_mode_getter: Callable[[], str] | None = None,
    ) -> None:
        """初始化聚类图像列。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。
            scale_mode_getter [Callable[[], str] | None]: 当前图像缩放模式读取回调。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("sliceMiddleColumn")

        self.prev_button = self._create_navigation_button(
            CustomIcon.CHEVRON_LEFT,
            "上一类",
        )
        self.next_button = self._create_navigation_button(
            CustomIcon.CHEVRON_RIGHT,
            "下一类",
        )
        self.title_label = QLabel(self.EMPTY_TITLE, self)
        self.title_label.setObjectName("sliceMiddleTitle")
        self._configure_title_label()

        self.cf_card = self._create_dimension_card(
            "载频", "clusterCfCard", "聚类结果 - 载频", scale_mode_getter
        )
        self.pw_card = self._create_dimension_card(
            "脉宽", "clusterPwCard", "聚类结果 - 脉宽", scale_mode_getter
        )
        self.pa_card = self._create_dimension_card(
            "幅度", "clusterPaCard", "聚类结果 - 幅度", scale_mode_getter
        )
        self.dtoa_card = self._create_dimension_card(
            "一级差", "clusterDtoaCard", "聚类结果 - 一级差", scale_mode_getter
        )
        self.doa_card = self._create_dimension_card(
            "方位角", "clusterDoaCard", "聚类结果 - 方位角", scale_mode_getter
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
        """设置聚类图像列标题。

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

    def set_snapshot_context(self, slice_number: int, cluster_title: str) -> None:
        """同步设置五维聚类快照窗口的上下文标题。

        Args:
            slice_number [int]: 当前显示的 1-based 切片编号，必须大于等于 1。
            cluster_title [str]: 当前显示的非空聚类标题。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片编号无效或聚类标题为空时抛出。
        """
        if slice_number < 1:
            raise ValueError("slice_number 必须大于等于 1")
        if not cluster_title.strip():
            raise ValueError("cluster_title 不能为空")

        dimension_names = ("载频", "脉宽", "幅度", "一级差", "方位角")
        for card, dimension_name in zip(
            self.dimension_cards,
            dimension_names,
            strict=True,
        ):
            card.set_snapshot_window_title(
                f"切片 {slice_number}  - {cluster_title} - {dimension_name}"
            )

    def clear_images(self) -> None:
        """清空五维聚类图像并恢复空态标题。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.title_label.setText(self.EMPTY_TITLE)
        for card in self.dimension_cards:
            card.clear_image()

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
            CustomIcon.CHEVRON_LEFT.colored(light_color, dark_color)
        )
        self.next_button.setIcon(
            CustomIcon.CHEVRON_RIGHT.colored(light_color, dark_color)
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
