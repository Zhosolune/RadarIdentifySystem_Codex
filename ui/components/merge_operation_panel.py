"""合并操作面板组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPaintEvent, QPainter, QResizeEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SimpleCardWidget, isDarkTheme

from .merge_action_button_bar import MergeActionButtonBar


class _MergeSkeletonBar(QWidget):
    """绘制一条随主题变化的灰色圆角骨架占位。"""

    CORNER_RADIUS = 5.0

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化固定高度的骨架条。"""
        super().__init__(parent)
        self.setObjectName("mergeCategorySkeletonBar")
        self.setFixedHeight(20)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制无边框灰色圆角矩形。"""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # 使用中性透明灰适配明暗主题，不依赖页面 QSS。
        painter.setBrush(
            Qt.GlobalColor.lightGray
            if not isDarkTheme()
            else Qt.GlobalColor.darkGray
        )
        painter.drawRoundedRect(
            self.rect(),
            self.CORNER_RADIUS,
            self.CORNER_RADIUS,
        )


class MergeCategorySkeleton(QWidget):
    """展示三条等长、左对齐的类别控制区骨架占位。

    每条骨架的宽度始终等于本控件宽度的一半，作为类别显示控制区尚未载入时的
    默认状态。

    Attributes:
        skeleton_bars [tuple[_MergeSkeletonBar, ...]]: 三条等长骨架占位。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化类别显示控制区骨架屏。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("mergeCategorySkeleton")
        self.skeleton_bars = tuple(_MergeSkeletonBar(self) for _ in range(3))
        self._init_layout()

    def _init_layout(self) -> None:
        """创建左对齐的三行骨架布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        for bar in self.skeleton_bars:
            layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """在控制区缩放时同步三条骨架为面板宽度的一半。"""
        super().resizeEvent(event)
        target_width = max(0, self.width() // 2)
        for bar in self.skeleton_bars:
            bar.setFixedWidth(target_width)


class MergeOperationPanel(QWidget):
    """承载合并标题栏、按钮卡片和类别控制卡片的工作区面板 D。

    标题栏下方依次排列操作按钮卡片和类别显示控制卡片。类别控制区默认显示
    三条骨架占位，后续加载实际类别控件时可替换该占位组件。

    面板宽度由外部横向工作区统一设置为视口宽度的一半。

    Attributes:
        title_label [QLabel]: 显示“合并操作”的固定高度标题。
        operate_panel_card [SimpleCardWidget]: 包裹水平按钮区的操作卡片。
        button_bar [MergeActionButtonBar]: 独立的四按钮操作区。
        category_display_card [SimpleCardWidget]: 包裹类别显示控制区的卡片。
        category_skeleton [MergeCategorySkeleton]: 类别控制区默认骨架屏。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化合并操作标题栏及上下两张内容卡片。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> panel = MergeOperationPanel()
            >>> panel.title_label.text()
            '合并操作'
        """
        super().__init__(parent)
        self.setObjectName("mergeOperationPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        self.title_label = QLabel("合并操作面板", self)
        # 与右侧操作面板标题共用 QSS 选择器和固定高度。
        self.title_label.setObjectName("sliceMiddleTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(25)

        self.operate_panel_card = SimpleCardWidget(self)
        self.operate_panel_card.setObjectName("mergeOperationCard")
        self.operate_panel_card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.operate_panel_card.setFixedHeight(56)
        self.button_bar = MergeActionButtonBar(self.operate_panel_card)

        self.category_display_card = SimpleCardWidget(self)
        self.category_display_card.setObjectName("mergeCategoryDisplayCard")
        self.category_display_card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        self.category_skeleton = MergeCategorySkeleton(
            self.category_display_card
        )

        self._init_card_layouts()
        self._init_layout()

    def _init_card_layouts(self) -> None:
        """分别把按钮区和类别骨架屏装入对应卡片。"""
        button_card_layout = QHBoxLayout(self.operate_panel_card)
        button_card_layout.setContentsMargins(12, 12, 12, 12)
        button_card_layout.addWidget(self.button_bar)

        category_card_layout = QVBoxLayout(self.category_display_card)
        category_card_layout.setContentsMargins(0, 0, 0, 0)
        category_card_layout.addWidget(self.category_skeleton)

    def _init_layout(self) -> None:
        """创建标题、按钮卡片及类别控制卡片的纵向布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.operate_panel_card)
        layout.addWidget(self.category_display_card, 1)
