"""合并面板的操作卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SimpleCardWidget

from .merge_action_button_bar import MergeActionButtonBar
from .merge_category_display_card import MergeCategoryDisplayCard


class MergeOperationCard(SimpleCardWidget):
    """组合合并按钮和类别显示控制的操作卡片。

    Attributes:
        button_bar [MergeActionButtonBar]: 水平排列的四按钮操作区。
        category_title_label [QLabel]: 位于骨架卡片外部上方的类别控制标签。
        category_display_card [MergeCategoryDisplayCard]: 包裹默认骨架屏的卡片。

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> app = QApplication.instance() or QApplication([])
        >>> card = MergeOperationCard()
        >>> card.button_bar.merge_button.text()
        '合并'
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化按钮区和类别显示控制区。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("mergeOperationCard")
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.button_bar = MergeActionButtonBar(self)
        self.category_title_label = BodyLabel("类别显示控制", self)
        self.category_title_label.setObjectName("mergeCategoryTitleLabel")
        self.category_title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.category_title_label.setFixedHeight(20)
        self.category_display_card = MergeCategoryDisplayCard(self)
        self.category_display_card.height_changed.connect(
            lambda _height: self._sync_height()
        )
        self._init_layout()
        self._sync_height()

    def _init_layout(self) -> None:
        """纵向排列按钮区、外部标签和类别骨架卡片。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        layout.addWidget(self.button_bar)
        layout.addSpacing(10)
        layout.addWidget(self.category_title_label)
        layout.addSpacing(5)
        layout.addWidget(self.category_display_card)

    def _sync_height(self) -> None:
        """根据动态类别控制卡片更新操作卡片高度。"""
        self.layout().activate()
        self.setFixedHeight(self.sizeHint().height())
