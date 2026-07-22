"""合并面板的结果表格卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHeaderView,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SimpleCardWidget, TableWidget
from qfluentwidgets.common.font import getFont

from .analysis_result_card import (
    ANALYSIS_FONT_FAMILIES,
    AnalysisResultTableWidget,
    RoundedAnalysisHeaderView,
)


class MergeResultTableCard(SimpleCardWidget):
    """显示两列四数据行的合并结果表格卡片。

    表格复用右侧分析结果表格的控件、圆角表头、字体、边框和交互约束，默认
    单元格保持为空，等待后续合并业务写入。

    Attributes:
        table [AnalysisResultTableWidget]: 两列表头加四数据行的结果表格。

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> app = QApplication.instance() or QApplication([])
        >>> card = MergeResultTableCard()
        >>> card.table.rowCount() + 1
        5
    """

    ROW_COUNT = 4
    ROW_HEIGHT = 36
    HEADER_HEIGHT = 36
    TABLE_BORDER_RADIUS = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化合并结果表格卡片。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("mergeResultTableCard")
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.table = AnalysisResultTableWidget(self)
        self.table.setObjectName("mergeResultTable")
        self._init_layout()
        self._init_table()
        self.setFixedHeight(self.sizeHint().height())

    def _init_layout(self) -> None:
        """将结果表格装入卡片。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        layout.addWidget(self.table)

    def _init_table(self) -> None:
        """应用与右侧分析结果表格一致的结构和交互样式。"""
        self.table.setColumnCount(2)
        self.table.setRowCount(self.ROW_COUNT)
        self.table.setHorizontalHeaderLabels(["类别", "合并结果"])
        self.table.setShowGrid(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(self.TABLE_BORDER_RADIUS)
        self.table.setHorizontalHeader(
            RoundedAnalysisHeaderView(
                Qt.Orientation.Horizontal,
                self.table,
                corner_radius=self.TABLE_BORDER_RADIUS,
            )
        )
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(self.HEADER_HEIGHT)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(TableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 138)

        for column in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        for row in range(self.ROW_COUNT):
            for column in range(self.table.columnCount()):
                self.table.setItem(row, column, self._create_empty_item())
            self.table.setRowHeight(row, self.ROW_HEIGHT)

        table_height = self.HEADER_HEIGHT + self.ROW_COUNT * self.ROW_HEIGHT + 2
        self.table.setFixedHeight(table_height)
        self.table._sync_vertical_scrollbar_geometry()

    @staticmethod
    def _create_empty_item() -> QTableWidgetItem:
        """创建与右侧分析结果表格一致的空白居中单元格。"""
        item = QTableWidgetItem("")
        font = getFont(14)
        font.setFamilies(ANALYSIS_FONT_FAMILIES)
        item.setFont(font)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
