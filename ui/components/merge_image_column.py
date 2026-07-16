"""合并图像列组件。

该组件只负责合并工作区中的五维空白图像卡片，
不读取合并结果，也不包含任何合并业务逻辑。
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .slice_dimension_card import SliceDimensionCard


class MergeImageColumn(QWidget):
    """承载五维合并图像的等宽内容列。

    Attributes:
        title_label [QLabel]: 合并图像列标题。
        merge_cf_card [SliceDimensionCard]: 载频合并图像卡片。
        merge_pw_card [SliceDimensionCard]: 脉宽合并图像卡片。
        merge_pa_card [SliceDimensionCard]: 幅度合并图像卡片。
        merge_dtoa_card [SliceDimensionCard]: 一级差合并图像卡片。
        merge_doa_card [SliceDimensionCard]: 方位角合并图像卡片。
        dimension_cards [tuple[SliceDimensionCard, ...]]: 按五维显示顺序排列的卡片集合。
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scale_mode_getter: Callable[[], str] | None = None,
    ) -> None:
        """初始化合并图像列。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。
            scale_mode_getter [Callable[[], str] | None]: 当前图像缩放模式读取回调。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> column = MergeImageColumn()
            >>> len(column.dimension_cards)
            5
        """
        super().__init__(parent)
        self.setObjectName("sliceMergeColumn")

        self.title_label = QLabel("合并结果", self)
        # 复用切片页现有标题样式，避免为同类标题新增平行样式规则。
        self.title_label.setObjectName("sliceMiddleTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(25)
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        self.merge_cf_card = SliceDimensionCard(
            "载频",
            "mergeCfCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 载频",
        )
        self.merge_pw_card = SliceDimensionCard(
            "脉宽",
            "mergePwCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 脉宽",
        )
        self.merge_pa_card = SliceDimensionCard(
            "幅度",
            "mergePaCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 幅度",
        )
        self.merge_dtoa_card = SliceDimensionCard(
            "一级差",
            "mergeDtoaCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 一级差",
        )
        self.merge_doa_card = SliceDimensionCard(
            "方位角",
            "mergeDoaCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 方位角",
        )
        self.dimension_cards = (
            self.merge_cf_card,
            self.merge_pw_card,
            self.merge_pa_card,
            self.merge_dtoa_card,
            self.merge_doa_card,
        )

        self._init_layout()

    def _init_layout(self) -> None:
        """创建标题栏和五维图像卡片布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self.title_label)
        for card in self.dimension_cards:
            layout.addWidget(card, 1)
