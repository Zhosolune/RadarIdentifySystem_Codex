"""切片处理子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import SimpleCardWidget, BodyLabel

from app.style_sheet import StyleSheet


class SliceInterface(QFrame):
    """切片处理子页面（非滚动、三栏布局）。

    功能描述：
        提供切片处理阶段的三栏骨架布局，左中列按垂直方向预留 5 组“文字标签 + 图片卡片”区域，
        右列预留空白业务区，不启用滚动。

    参数说明：
        parent (QWidget | None): 父级控件，默认值为 None。

    返回值说明：
        无。

    异常说明：
        无。
    """

    _DIMENSION_LABELS: tuple[str, ...] = ("载频", "脉宽", "幅度", "一级差", "方位角")

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化切片处理子页面。

        功能描述：
            创建三栏布局并应用页面样式资源。

        参数说明：
            parent (QWidget | None): 父级控件，默认值为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        super().__init__(parent)
        self.setObjectName("sliceInterface")
        self.left_cards: list[SimpleCardWidget] = []
        self.middle_cards: list[SimpleCardWidget] = []
        self._init_layout()
        StyleSheet.SLICE_INTERFACE.apply(self)

    def _init_layout(self) -> None:
        """初始化三栏主布局。

        功能描述：
            创建左栏、中栏、右栏容器并按 1:1:1 比例加入主布局。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        left_column = self._create_dimension_column("sliceLeftColumn", self.left_cards)
        middle_column = self._create_dimension_column("sliceMiddleColumn", self.middle_cards)
        right_column = self._create_right_column()

        root_layout.addWidget(left_column, 1)
        root_layout.addWidget(middle_column, 1)
        root_layout.addWidget(right_column, 1)

    def _create_dimension_column(self, object_name: str, card_store: list[SimpleCardWidget]) -> QWidget:
        """创建维度列容器。

        功能描述：
            生成左/中列的 5 行显示区域，每行包含左侧文字标签与右侧 `SimpleCardWidget` 占位卡片。

        参数说明：
            object_name (str): 列容器对象名。
            card_store (list[SimpleCardWidget]): 用于保存创建后的卡片引用列表。

        返回值说明：
            QWidget: 维度列容器。

        异常说明：
            无。
        """

        column = QWidget(self)
        column.setObjectName(object_name)

        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(10)

        # 逐行创建“竖排标签 + 图片卡片”结构，保持与旧版视觉语义一致。
        for index, label_text in enumerate[str](self._DIMENSION_LABELS):
            row = QWidget(column)
            row.setObjectName(f"{object_name}Row{index}")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            label = BodyLabel("\n".join(label_text), row)
            label.setObjectName("sliceDimensionLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(25)

            card = SimpleCardWidget(row)
            card.setObjectName("sliceImageCard")
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            card_store.append(card)

            row_layout.addWidget(label)
            row_layout.addWidget(card, 1)
            column_layout.addWidget(row, 1)

        return column

    def _create_right_column(self) -> QWidget:
        """创建右侧空白业务列。

        功能描述：
            构建右侧占位区域，作为后续操作面板与结果视图承载容器。

        参数说明：
            无。

        返回值说明：
            QWidget: 右侧列容器。

        异常说明：
            无。
        """

        right_column = QWidget(self)
        right_column.setObjectName("sliceRightColumn")
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addStretch(1)
        return right_column
