"""合并操作面板组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .merge_operation_card import MergeOperationCard
from .merge_result_table_card import MergeResultTableCard


class MergeOperationPanel(QWidget):
    """承载合并标题栏、操作卡片和结果表格卡片的工作区面板 D。

    面板自身保持透明，仅纵向组合独立模块卡片。操作卡片内部包含四按钮区和
    默认类别骨架屏，表格卡片位于其下方。

    面板宽度由外部横向工作区统一设置为视口宽度的一半。

    Attributes:
        title_label [QLabel]: 显示“合并操作”的固定高度标题。
        operation_card [MergeOperationCard]: 组合按钮和类别显示控制的操作卡片。
        result_table_card [MergeResultTableCard]: 两列四数据行的结果表格卡片。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化标题、操作卡片和结果表格卡片。

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

        self.operation_card = MergeOperationCard(self)
        self.result_table_card = MergeResultTableCard(self)
        self._init_layout()

    def _init_layout(self) -> None:
        """创建标题、操作卡片及结果表格卡片的纵向布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.operation_card)
        layout.addWidget(self.result_table_card)
        layout.addStretch()
