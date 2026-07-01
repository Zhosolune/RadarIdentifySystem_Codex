"""分析结果表格卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHeaderView, QSizePolicy, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import SimpleCardWidget, TableWidget, qconfig, themeColor
from qfluentwidgets.common.font import getFont
from qfluentwidgets.common.style_sheet import isDarkTheme


class RoundedAnalysisHeaderView(QHeaderView):
    """分析结果表格圆角表头。

    只绘制表格整体表头的左上角和右上角圆角，避免在每个表头单元格上应用圆角。

    Attributes:
        corner_radius: 表头整体左右上角圆角半径，单位为像素。
    """

    def __init__(
        self,
        orientation: Qt.Orientation,
        parent: QWidget | None = None,
        corner_radius: int = 5,
    ) -> None:
        """初始化圆角表头。

        Args:
            orientation [Qt.Orientation]: 表头方向，本组件使用水平方向。
            parent [QWidget | None]: 父级控件，默认值为 None。
            corner_radius [int]: 表头整体左右上角圆角半径，默认 5px。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtCore import Qt
            >>> header = RoundedAnalysisHeaderView(Qt.Orientation.Horizontal)
            >>> header.corner_radius
            5
        """
        super().__init__(orientation, parent)
        self.corner_radius = corner_radius
        qconfig.themeChanged.connect(self.viewport().update)

    def paintSection(self, painter: QPainter, rect: QRect, logicalIndex: int) -> None:
        """绘制单个表头分区，并仅在首尾分区绘制整体圆角。"""
        if not rect.isValid():
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = self._section_path(rect, logicalIndex)
        border_color = QColor("#5f6368" if isDarkTheme() else "#c9cdd4")
        painter.fillPath(path, themeColor())
        painter.setPen(QPen(border_color, 1))
        painter.drawPath(path)
        painter.setPen(Qt.GlobalColor.black if isDarkTheme() else Qt.GlobalColor.white)
        painter.setFont(getFont(15))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._section_text(logicalIndex))
        painter.restore()

    def _section_path(self, rect: QRect, logical_index: int) -> QPainterPath:
        """返回当前表头分区的绘制路径。"""
        path = QPainterPath()
        radius = float(self.corner_radius)
        adjusted_rect = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        left = adjusted_rect.left()
        top = adjusted_rect.top()
        right = adjusted_rect.right()
        bottom = adjusted_rect.bottom()

        if logical_index == 0:
            path.moveTo(left, bottom)
            path.lineTo(left, top + radius)
            path.quadTo(left, top, left + radius, top)
            path.lineTo(right, top)
            path.lineTo(right, bottom)
            path.closeSubpath()
            return path

        if logical_index == self.count() - 1:
            path.moveTo(left, top)
            path.lineTo(right - radius, top)
            path.quadTo(right, top, right, top + radius)
            path.lineTo(right, bottom)
            path.lineTo(left, bottom)
            path.closeSubpath()
            return path

        path.addRect(adjusted_rect)
        return path

    def _section_text(self, logical_index: int) -> str:
        """返回指定表头分区的展示文本。"""
        model = self.model()
        if model is None:
            return ""
        return str(
            model.headerData(
                logical_index,
                self.orientation(),
                Qt.ItemDataRole.DisplayRole,
            )
            or ""
        )


class AnalysisResultCard(SimpleCardWidget):
    """分析结果表格卡片。

    使用 Fluent 卡片承载固定的 2 列分析结果表格。表格左列展示雷达信号指标，
    右列预留后续分析结果填充位置，当前只负责静态展示结构。

    Attributes:
        table: 组件库表格控件，包含 2 列和 9 行默认指标内容。
    """

    ROW_LABELS: tuple[str, ...] = (
        "载频/MHz",
        "脉宽/us",
        "PRI/us",
        "DOA/°",
        "PA预测结果",
        "PA预测分类",
        "DTOA预测结果",
        "DTOA预测分类",
        "联合预测概率",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化分析结果表格卡片。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> card = AnalysisResultCard()
            >>> card.table.columnCount()
            2
        """
        super().__init__(parent)
        self.setObjectName("analysisResultCard")
        self.table = TableWidget(self)
        self.table.setObjectName("analysisResultTable")
        self._init_layout()
        self._init_table()

    def _init_layout(self) -> None:
        """初始化卡片内部布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        layout.addWidget(self.table)

    def _init_table(self) -> None:
        """初始化表格列、表头和默认行数据。"""
        self.table.setColumnCount(2)
        self.table.setRowCount(len(self.ROW_LABELS))
        self.table.setHorizontalHeaderLabels(["雷达信号", "分析结果"])
        self.table.setShowGrid(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(4)
        self.table.setHorizontalHeader(
            RoundedAnalysisHeaderView(Qt.Orientation.Horizontal, self.table, 4)
        )
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(TableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 138)

        # 表头与内容均居中，保持截图所示的两列信息对齐方式。
        for column in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        for row, label in enumerate(self.ROW_LABELS):
            signal_item = self._create_centered_item(label)
            result_item = self._create_centered_item("")
            self.table.setItem(row, 0, signal_item)
            self.table.setItem(row, 1, result_item)

        table_height = 36 * (len(self.ROW_LABELS) + 1) + 2
        self.table.setFixedHeight(table_height)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _create_centered_item(self, text: str) -> QTableWidgetItem:
        """创建居中并带 14px 字体的表格内容项。"""
        item = QTableWidgetItem(text)
        item.setFont(getFont(14))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
