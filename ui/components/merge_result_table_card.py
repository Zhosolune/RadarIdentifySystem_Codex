"""合并面板的结果表格卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics
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
    AnalysisResultCard,
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
    ROW_HEIGHT = AnalysisResultCard.DEFAULT_ROW_HEIGHT
    HEADER_HEIGHT = 36
    PRI_MAX_VALUES_PER_LINE = AnalysisResultCard.PRI_VALUES_PER_LINE
    ROW_VERTICAL_PADDING = AnalysisResultCard.ROW_VERTICAL_PADDING
    CELL_HORIZONTAL_PADDING = 16
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
        self._raw_rows: tuple[tuple[str, str], ...] = ()
        self._is_adjusting_layout = False
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
        header.sectionResized.connect(self._on_header_section_resized)

        for column in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        for row in range(self.ROW_COUNT):
            for column in range(self.table.columnCount()):
                self.table.setItem(row, column, self._create_empty_item())
            self.table.setRowHeight(row, self.ROW_HEIGHT)

        self._adjust_table_height_to_contents()

    def update_rows(self, rows: tuple[tuple[str, str], ...]) -> None:
        """显示当前合并结果的参数行。

        Args:
            rows [tuple[tuple[str, str], ...]]: ``(类别, 合并结果)``文本行。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 数据行数量超过固定表格容量时抛出。
        """
        if len(rows) > self.ROW_COUNT:
            raise ValueError("合并结果表格数据行超过容量")
        self._raw_rows = tuple(rows)
        # 先清空固定四行，防止较短的新结果保留上一结果尾部文本。
        self._clear_cell_texts()
        for row_index, (label, value) in enumerate(rows):
            self.table.item(row_index, 0).setText(label)
            display_value = (
                self._wrap_pri_text(value)
                if label == "PRI"
                else value
            )
            self.table.item(row_index, 1).setText(display_value)
        self._adjust_table_height_to_contents()

    def clear_rows(self) -> None:
        """清空全部参数文本并保留表格结构。

        Returns:
            None: 无返回值。
        """
        self._raw_rows = ()
        self._clear_cell_texts()
        self._adjust_table_height_to_contents()

    def _clear_cell_texts(self) -> None:
        """清除单元格文本并保留字体、对齐和表格结构。"""
        for row in range(self.ROW_COUNT):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item is not None:
                    item.setText("")

    def _wrap_pri_text(
        self,
        text: str,
        *,
        result_column_width: int | None = None,
    ) -> str:
        """按结果列实际宽度和最多六项规则重新组织PRI文本。"""
        tokens = [
            token
            for source_line in text.splitlines() or [text]
            for token in source_line.split("、")
            if token
        ]
        if not tokens:
            return ""

        item = self.table.item(0, 1)
        font = item.font() if item is not None else self.table.font()
        metrics = QFontMetrics(font)
        available_width = max(
            1,
            (
                result_column_width
                if result_column_width is not None
                else self.table.columnWidth(1)
            )
            - self.CELL_HORIZONTAL_PADDING,
        )
        lines: list[str] = []
        current_tokens: list[str] = []
        for token in tokens:
            candidate_tokens = [*current_tokens, token]
            candidate = "、".join(candidate_tokens)
            if (
                current_tokens
                and (
                    len(candidate_tokens) > self.PRI_MAX_VALUES_PER_LINE
                    or metrics.horizontalAdvance(candidate) > available_width
                )
            ):
                lines.append("、".join(current_tokens))
                current_tokens = [token]
            else:
                current_tokens = candidate_tokens
        if current_tokens:
            lines.append("、".join(current_tokens))
        return "\n".join(lines)

    def _on_header_section_resized(
        self,
        logical_index: int,
        _old_size: int,
        new_size: int,
    ) -> None:
        """结果列宽变化时按新宽度重新分行并计算PRI行高。"""
        if (
            logical_index != 1
            or not self._raw_rows
            or self._is_adjusting_layout
        ):
            return
        self._is_adjusting_layout = True
        try:
            pri_row = next(
                (
                    row_index
                    for row_index, (label, _value) in enumerate(self._raw_rows)
                    if label == "PRI"
                ),
                None,
            )
            if pri_row is None:
                return
            raw_value = self._raw_rows[pri_row][1]
            self.table.item(pri_row, 1).setText(
                self._wrap_pri_text(
                    raw_value,
                    result_column_width=new_size,
                )
            )
            self._adjust_table_height_to_contents()
        finally:
            self._is_adjusting_layout = False

    def _adjust_table_height_to_contents(self) -> None:
        """按实际多行文本调整行高，并同步表格与卡片总高度。"""
        self.table.resizeRowsToContents()
        for row in range(self.ROW_COUNT):
            self.table.setRowHeight(
                row,
                max(self.ROW_HEIGHT, self.table.rowHeight(row)),
            )

        pri_row = self._find_row("PRI")
        if pri_row is not None:
            pri_item = self.table.item(pri_row, 1)
            if pri_item is not None:
                line_count = max(1, pri_item.text().count("\n") + 1)
                line_height = QFontMetrics(pri_item.font()).lineSpacing()
                target_height = max(
                    self.ROW_HEIGHT,
                    line_count * line_height + self.ROW_VERTICAL_PADDING,
                )
                self.table.setRowHeight(
                    pri_row,
                    max(target_height, self.table.rowHeight(pri_row)),
                )
        self._resize_card_to_table()

    def _resize_card_to_table(self) -> None:
        """根据当前全部行高同步表格和外层卡片高度。"""
        table_height = self.HEADER_HEIGHT + 2 + sum(
            self.table.rowHeight(row) for row in range(self.ROW_COUNT)
        )
        self.table.setFixedHeight(table_height)
        margins = self.layout().contentsMargins()
        self.setFixedHeight(table_height + margins.top() + margins.bottom())
        self.table._sync_vertical_scrollbar_geometry()

    def _find_row(self, label: str) -> int | None:
        """返回指定左列表签所在行；不存在时返回 ``None``。"""
        for row in range(self.ROW_COUNT):
            item = self.table.item(row, 0)
            if item is not None and item.text() == label:
                return row
        return None

    @staticmethod
    def _create_empty_item() -> QTableWidgetItem:
        """创建与右侧分析结果表格一致的空白居中单元格。"""
        item = QTableWidgetItem("")
        font = getFont(14)
        font.setFamilies(ANALYSIS_FONT_FAMILIES)
        item.setFont(font)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
