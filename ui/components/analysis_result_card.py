"""分析结果表格卡片组件。"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHeaderView, QSizePolicy, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import SimpleCardWidget, TableWidget, qconfig, themeColor
from qfluentwidgets.common.font import getFont
from qfluentwidgets.common.style_sheet import isDarkTheme

from core.models.extraction_result import ExtractedClusterParams
from core.models.recognition_result import ClusterRecognition


PA_LABEL_NAMES: dict[int, str] = {
    0: "完整包络",
    1: "残缺包络",
    2: "部分包络",
    3: "相扫",
    4: "旁瓣",
    5: "非雷达信号",
}

DTOA_LABEL_NAMES: dict[int, str] = {
    0: "常规",
    1: "脉间参差",
    2: "脉组参差",
    3: "脉间脉组参差",
    4: "组变脉间",
    5: "非雷达信号",
}

ANALYSIS_FONT_FAMILIES: list[str] = ["Microsoft YaHei", "Microsoft YaHei UI"]


def _analysis_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """创建分析结果表格专用微软雅黑字体。"""
    font = getFont(pixel_size, weight)
    # 统一使用微软雅黑字体族，避免中英数字混排时风格漂移。
    font.setFamilies(ANALYSIS_FONT_FAMILIES)
    return font


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
        painter.setFont(_analysis_font(15))
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
    右列展示当前浏览类别的缓存参数、实际预测类别名和分类概率汇总。

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
    DEFAULT_ROW_HEIGHT = 36
    PRI_VALUES_PER_LINE = 6
    ROW_VERTICAL_PADDING = 16

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
        self._result_column = 1
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
            RoundedAnalysisHeaderView(Qt.Orientation.Horizontal, self.table)
        )
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(self.DEFAULT_ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.setWordWrap(True)
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

        self._adjust_table_height_to_contents()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _create_centered_item(self, text: str) -> QTableWidgetItem:
        """创建居中并带 14px 微软雅黑字体的表格内容项。"""
        item = QTableWidgetItem(text)
        item.setFont(_analysis_font(14))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def clear_results(self) -> None:
        """清空表格分析结果列。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> card = AnalysisResultCard()
            >>> card.clear_results()
            >>> card.table.item(0, 1).text()
            ''
        """
        # 清空结果列，保留左侧指标名称。
        for row in range(self.table.rowCount()):
            self._set_result_text(row, "")
        self._adjust_table_height_to_contents()

    def update_from_recognition(self, recognition: ClusterRecognition | None) -> None:
        """根据当前类别识别缓存刷新分析结果表格。

        Args:
            recognition: 当前类别识别结果；为 None 时清空表格。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> from core.models.recognition_result import ClusterRecognition
            >>> app = QApplication.instance() or QApplication([])
            >>> card = AnalysisResultCard()
            >>> rec = ClusterRecognition(0, "CF", 1, 0, 0, 0.9, 0, 0.8, True)
            >>> card.update_from_recognition(rec)
            >>> card.table.item(4, 1).text()
            '完整包络'
        """
        if recognition is None:
            self.clear_results()
            return

        # 读取识别阶段已缓存的参数，禁止在 UI 切换时重新提取。
        params = recognition.extracted_params or ExtractedClusterParams()
        row_values = self._build_result_values(recognition, params)
        for row, value in enumerate(row_values):
            self._set_result_text(row, value)
        self._adjust_table_height_to_contents()

    def _adjust_table_height_to_contents(self) -> None:
        """按当前单元格内容自动调整表格高度。"""
        # 先交给 Qt 根据普通内容计算基础行高。
        self.table.resizeRowsToContents()
        # 再按多行文本行数补足关键单元格高度，避免多行概率或 PRI 被裁剪。
        for label in ("PRI/us", "PA预测分类", "DTOA预测分类"):
            self._adjust_row_height_by_text(label)

        table_height = self.table.horizontalHeader().height() + 2
        for row in range(self.table.rowCount()):
            table_height += self.table.rowHeight(row)
        self.table.setFixedHeight(table_height)

    def _adjust_row_height_by_text(self, label: str) -> None:
        """根据指定指标行的实际文本行数设置当前行高度。"""
        row = self.ROW_LABELS.index(label)
        line_count = self._row_text_line_count(row)
        item = self.table.item(row, self._result_column) or self.table.item(row, 0)
        if item is None:
            return

        # 使用当前单元格字体行距计算高度，保持字号变化时仍能自适应。
        line_height = QFontMetrics(item.font()).lineSpacing()
        target_height = max(
            self.DEFAULT_ROW_HEIGHT,
            line_count * line_height + self.ROW_VERTICAL_PADDING,
        )
        if target_height > self.table.rowHeight(row):
            self.table.setRowHeight(row, target_height)

    def _row_text_line_count(self, row: int) -> int:
        """返回指定行左右单元格中的最大文本行数。"""
        line_counts: list[int] = []
        for column in range(self.table.columnCount()):
            item = self.table.item(row, column)
            text = item.text() if item is not None else ""
            # 空文本仍按一行计算，确保清空后行高回落到默认高度。
            line_counts.append(max(1, text.count("\n") + 1))
        return max(line_counts, default=1)

    def _build_result_values(
        self,
        recognition: ClusterRecognition,
        params: ExtractedClusterParams,
    ) -> list[str]:
        """构建当前识别记录对应的表格结果列文本。"""
        return [
            self._format_numeric_values(params.cf_values, decimal_places=0),
            self._format_numeric_values(params.pw_values, decimal_places=1),
            self._format_numeric_values(
                params.pri_values,
                decimal_places=1,
                values_per_line=self.PRI_VALUES_PER_LINE,
            ),
            self._format_numeric_values(params.doa_values, decimal_places=1),
            PA_LABEL_NAMES.get(recognition.pa_label, f"未知类别{recognition.pa_label}"),
            self._format_probability_lines(recognition.pa_conf_dict, PA_LABEL_NAMES),
            DTOA_LABEL_NAMES.get(recognition.dtoa_label, f"未知类别{recognition.dtoa_label}"),
            self._format_probability_lines(recognition.dtoa_conf_dict, DTOA_LABEL_NAMES),
            self._format_probability(recognition.joint_prob),
        ]

    def _set_result_text(self, row: int, text: str) -> None:
        """设置指定行的结果列文本。"""
        item = self.table.item(row, self._result_column)
        if item is None:
            # 补建结果项，避免外部测试或异常状态下空指针。
            item = self._create_centered_item("")
            self.table.setItem(row, self._result_column, item)
        item.setText(text)

    @staticmethod
    def _format_numeric_values(
        values: list[float],
        decimal_places: int,
        values_per_line: int | None = None,
    ) -> str:
        """按指定小数位格式化参数列表。"""
        if not values:
            return ""

        # 逐值四舍五入，兼容同一类别存在多个典型值的情况。
        formatted_values = [
            AnalysisResultCard._format_decimal(value, decimal_places)
            for value in values
        ]
        if values_per_line is None or values_per_line <= 0:
            return "、".join(formatted_values)

        # 按指定数量分行，便于 PRI 按实际值数量动态撑开行高。
        lines = [
            "、".join(formatted_values[index : index + values_per_line])
            for index in range(0, len(formatted_values), values_per_line)
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_probability(value: float) -> str:
        """格式化概率值，零概率直接显示 0。"""
        rounded = AnalysisResultCard._rounded_decimal(value, decimal_places=4)
        if rounded == Decimal("0"):
            return "0"
        return f"{rounded:.4f}"

    @staticmethod
    def _format_probability_lines(
        probabilities: dict[int, float],
        label_names: dict[int, str],
    ) -> str:
        """把同一模型的类别名称和概率合并为单元格多行文本。"""
        # 同一种类别体系写入同一个单元格，保持表格行数不变。
        return "\n".join(
            f"{name}: {AnalysisResultCard._format_probability(probabilities.get(label, 0.0))}"
            for label, name in label_names.items()
        )

    @staticmethod
    def _format_decimal(value: float, decimal_places: int) -> str:
        """按四舍五入规则格式化普通数值。"""
        rounded = AnalysisResultCard._rounded_decimal(value, decimal_places)
        if rounded == Decimal("0"):
            rounded = Decimal("0")
        return f"{rounded:.{decimal_places}f}"

    @staticmethod
    def _rounded_decimal(value: float, decimal_places: int) -> Decimal:
        """使用 ROUND_HALF_UP 规则返回 Decimal 结果。"""
        quantizer = Decimal("1") if decimal_places == 0 else Decimal(f"1e-{decimal_places}")
        return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)
