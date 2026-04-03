"""切片维度卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget
from qfluentwidgets import SimpleCardWidget


class SliceDimensionCard(QWidget):
    """切片维度卡片组件。

    功能描述：
        提供“左侧竖排维度标签 + 右侧图片占位卡片”的组合组件，用于切片页面维度图像展示位。

    参数说明：
        label_text (str): 维度标签文本。
        object_name (str): 组件对象名。
        parent (QWidget | None): 父级控件，默认值为 None。

    返回值说明：
        无。

    异常说明：
        ValueError: 当 `label_text` 或 `object_name` 为空字符串时抛出。
    """

    def __init__(self, label_text: str, object_name: str, parent: QWidget | None = None) -> None:
        """初始化切片维度卡片组件。

        功能描述：
            构建标签与卡片的水平布局并完成对象命名。

        参数说明：
            label_text (str): 维度标签文本。
            object_name (str): 组件对象名。
            parent (QWidget | None): 父级控件，默认值为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            ValueError: 当 `label_text` 或 `object_name` 为空字符串时抛出。
        """

        super().__init__(parent)
        if label_text.strip() == "":
            raise ValueError("label_text 不能为空")
        if object_name.strip() == "":
            raise ValueError("object_name 不能为空")

        self.setObjectName(object_name)
        self.dimension_label = QLabel("\n".join(label_text), self)
        self.dimension_label.setObjectName("sliceDimensionLabel")
        self.dimension_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dimension_label.setFixedWidth(25)

        self.image_card = SimpleCardWidget(self)
        self.image_card.setObjectName("sliceImageCard")
        self.image_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 添加用于显示图像的 QLabel
        self.image_label = QLabel(self.image_card)
        self.image_label.setObjectName("sliceImageLabel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        # 为 image_card 设置布局
        card_layout = QHBoxLayout(self.image_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.addWidget(self.image_label)

        self._init_layout()

    def set_image(self, pixmap: QPixmap) -> None:
        """设置卡片内的图像。

        功能描述：
            将 QPixmap 图像设置到图片标签中。

        参数说明：
            pixmap (QPixmap): 要显示的图像对象。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        self.image_label.setPixmap(pixmap)

    def _init_layout(self) -> None:
        """初始化组件布局。

        功能描述：
            将标签与图片卡片按固定间距加入水平布局。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self.dimension_label)
        row_layout.addWidget(self.image_card, 1)
