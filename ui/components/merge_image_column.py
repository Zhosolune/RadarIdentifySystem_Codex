"""合并工作区五维多颜色图像列组件。"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .slice_dimension_card import SliceDimensionCard


_DIMENSION_DISPLAY_NAMES: dict[str, str] = {
    "CF": "载频",
    "PW": "脉宽",
    "PA": "幅度",
    "DTOA": "一级差",
    "DOA": "方位角",
}


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
        cards_by_dimension [dict[str, SliceDimensionCard]]: 维度名到图像卡片的映射。
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
        self.cards_by_dimension = dict(
            zip(
                ("CF", "PW", "PA", "DTOA", "DOA"),
                self.dimension_cards,
                strict=True,
            )
        )

        self._init_layout()

    def update_images(
        self,
        images: Mapping[str, np.ndarray],
        title: str,
    ) -> None:
        """显示runtime提供的当前合并结果五维图像。

        Args:
            images [Mapping[str, np.ndarray]]: 维度名到RGB图像的映射。
            title [str]: 当前结果标题。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 图像不是 ``H×W×3`` 的 uint8 RGB 数组时抛出。
        """
        self.title_label.setText(title)
        for dimension, card in self.cards_by_dimension.items():
            image_data = images.get(dimension)
            # runtime可能只返回部分维度；缺失项必须清空，不能保留上一结果旧图。
            if image_data is None:
                card.clear_image()
                continue
            if (
                image_data.ndim != 3
                or image_data.shape[2] != 3
                or image_data.dtype.name != "uint8"
            ):
                raise ValueError(f"{dimension} 合并图像必须为 H×W×3 的 uint8 RGB 数组")
            # NumPy数组采用连续RGB三通道布局，每行字节数固定为width * 3。
            height, width, _channels = image_data.shape
            q_image = QImage(
                image_data.data,
                width,
                height,
                width * 3,
                QImage.Format.Format_RGB888,
            )
            # 卡片负责持有QImage并刷新独立窗口标题，UI层不参与再次绘图。
            card.set_image(q_image)
            card.set_snapshot_window_title(
                f"{title} - {_DIMENSION_DISPLAY_NAMES[dimension]}"
            )

    def clear_images(self) -> None:
        """清空全部合并图像并恢复默认标题。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.title_label.setText("合并结果")
        for card in self.dimension_cards:
            card.clear_image()

    def _init_layout(self) -> None:
        """创建标题栏和五维图像卡片布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self.title_label)
        for card in self.dimension_cards:
            layout.addWidget(card, 1)
