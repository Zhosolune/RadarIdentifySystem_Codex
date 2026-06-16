# -*- coding: utf-8 -*-
"""导入数据仪表盘卡片组件。

提供标题栏、动态标签页和流式指标卡布局，用于展示选中文件或数据包的摘要信息。
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    SimpleCardWidget,
    TransparentPushButton,
    setFont,
)
from qfluentwidgets.components.layout import AdaptiveFlowLayout

from ui.components.edge_tab_view import EdgeTabWidget


def format_dashboard_duration(duration: float) -> str:
    """格式化仪表盘持续时间。

    Args:
        duration: 持续时间，单位为 0.1us，必须大于或等于 0。

    Returns:
        适合仪表盘展示的持续时间文本；不超过 1000ms 时使用 ms，超过
        1000ms 时使用 s，超过 60s 时使用 min。

    Raises:
        无显式抛出异常。

    Example:
        >>> format_dashboard_duration(10_000)
        '1.00 ms'
        >>> format_dashboard_duration(10_010_000)
        '1.00 s'
    """
    milliseconds = max(float(duration), 0.0) / 10_000
    if milliseconds > 60_000:
        return f"{milliseconds / 60_000:.2f} min"
    if milliseconds > 1_000:
        return f"{milliseconds / 1_000:.2f} s"
    return f"{milliseconds:.2f} ms"


@dataclass(frozen=True)
class DashboardMetric:
    """仪表盘指标项。

    Attributes:
        label: 指标名称。
        value: 指标显示值。
    """

    label: str
    value: str


@dataclass(frozen=True)
class DashboardPage:
    """仪表盘标签页数据。

    Attributes:
        route_key: 标签页唯一键。
        title: 标签页显示标题。
        metrics: 标签页中的指标项列表。
    """

    route_key: str
    title: str
    metrics: list[DashboardMetric]


class DashboardCard(QFrame):
    """仪表盘指标卡片。

    使用 QFrame 承载指标内容，避免组件库卡片自带边框干扰视觉效果。
    """

    def __init__(self, metric: DashboardMetric, parent: QWidget | None = None) -> None:
        """初始化仪表盘指标卡片。

        Args:
            metric: 指标数据。
            parent: 父级控件，默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("dashboardCard")
        self.setFixedHeight(60)
        self.setMinimumWidth(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_ui(metric)
        self._apply_shadow()

    def _init_ui(self, metric: DashboardMetric) -> None:
        """构建指标值与指标名称布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(metric.value, self)
        value_label.setObjectName("dashboardMetricValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_label = CaptionLabel(metric.label, self)
        name_label.setObjectName("dashboardMetricName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(False)

        layout.addWidget(value_label)
        layout.addWidget(name_label)

    def _apply_shadow(self) -> None:
        """应用右下方向投影效果。"""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)


class DashboardSkeletonWidget(QWidget):
    """仪表盘懒加载骨架占位。

    在解析数据完成前展示浅灰色圆角块，避免用户误认为默认指标是真实解析结果。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化仪表盘骨架占位。

        Args:
            parent: 父级控件，默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("dashboardSkeleton")
        self._blocks: list[tuple[QFrame, int]] = []
        self._init_ui()

    def _init_ui(self) -> None:
        """构建顶部矩形和三条递增长条。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 顶部块模拟数据图形区域，下面三条模拟加载中的指标文本。
        top_block = self._create_block("dashboardSkeletonHero", QSize(90, 60))
        short_bar = self._create_block("dashboardSkeletonBar", QSize(90, 20))
        middle_bar = self._create_block("dashboardSkeletonBar", QSize(182, 20))
        long_bar = self._create_block("dashboardSkeletonBar", QSize(265, 20))

        layout.addWidget(top_block)
        layout.addWidget(short_bar)
        layout.addWidget(middle_bar)
        layout.addWidget(long_bar)
        layout.addStretch(1)

    def _create_block(self, object_name: str, size: QSize) -> QFrame:
        """创建固定尺寸的骨架圆角块。"""
        block = QFrame(self)
        block.setObjectName(object_name)
        block.setFixedSize(size)
        block.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._blocks.append((block, size.width()))
        return block

    def resizeEvent(self, event) -> None:
        """在容器变窄时收缩骨架块宽度，避免挤出父布局。"""
        super().resizeEvent(event)
        self._apply_block_widths()

    def _apply_block_widths(self) -> None:
        """按当前可用宽度限制骨架块宽度。"""
        available_width = max(48, self.width() - 56)
        for block, target_width in self._blocks:
            # 高度保持设计尺寸，宽度不超过当前内容区。
            block.setFixedWidth(min(target_width, available_width))


class DashboardFlowLayout(AdaptiveFlowLayout):
    """仪表盘指标卡自适应流式布局。

    在组件库 AdaptiveFlowLayout 的均分逻辑基础上限制每行最多 5 张卡片。
    """

    _MAX_CARDS_PER_ROW = 6

    def _doLayout(self, rect: QRect, move: bool) -> int:
        """根据容器宽度均分卡片宽度，并限制每行最多 5 张。"""
        ani_restart = False
        margin = self.contentsMargins()
        space_x = self.horizontalSpacing()
        space_y = self.verticalSpacing()
        available_width = max(0, rect.width() - margin.left() - margin.right())

        if self.widgetMinimumWidth() + space_x > 0:
            cards_per_row = max(
                1,
                (available_width + space_x) // (self.widgetMinimumWidth() + space_x),
            )
        else:
            cards_per_row = 1
        cards_per_row = min(cards_per_row, self._MAX_CARDS_PER_ROW)

        if cards_per_row > 1:
            card_width = (
                available_width - (cards_per_row - 1) * space_x
            ) // cards_per_row
        else:
            card_width = available_width

        maximum_width = self.widgetMaximumWidth()
        if maximum_width is not None and card_width > maximum_width:
            card_width = maximum_width

        x = rect.x() + margin.left()
        y = rect.y() + margin.top()
        row_height = 0
        column_index = 0

        for index, item in enumerate(self._items):
            if item.widget() and not item.widget().isVisible() and self.isTight:
                continue

            if column_index >= cards_per_row:
                x = rect.x() + margin.left()
                y = y + row_height + space_y
                row_height = 0
                column_index = 0

            if move:
                # 只调整宽度，高度仍由卡片自身 sizeHint 决定。
                target_size = QSize(card_width, item.sizeHint().height())
                target = QRect(QPoint(x, y), target_size)

                if not self.needAni:
                    item.setGeometry(target)
                elif index < len(self._anis) and target != self._anis[index].endValue():
                    self._anis[index].stop()
                    self._anis[index].setEndValue(target)
                    ani_restart = True

            x = x + card_width + space_x
            row_height = max(row_height, item.sizeHint().height())
            column_index += 1

        if self.needAni and ani_restart:
            self._aniGroup.stop()
            self._aniGroup.start()

        return y + row_height + margin.bottom() - rect.y()


class _DashboardPageWidget(QWidget):
    """仪表盘单个标签页内容。"""

    def __init__(self, metrics: list[DashboardMetric], parent: QWidget | None = None) -> None:
        """初始化仪表盘标签页内容。

        Args:
            metrics: 当前标签页要展示的指标项列表。
            parent: 父级控件，默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("dashboardPage")
        self._init_ui(metrics)

    def _init_ui(self, metrics: list[DashboardMetric]) -> None:
        """构建流式指标卡布局。"""
        flow_layout = DashboardFlowLayout(self, needAni=False, isTight=True)
        flow_layout.setContentsMargins(10, 8, 10, 8)
        flow_layout.setHorizontalSpacing(10)
        flow_layout.setVerticalSpacing(10)
        flow_layout.setWidgetMinimumWidth(90)

        for metric in metrics:
            # 指标卡宽度交给 DashboardFlowLayout 按行均分。
            flow_layout.addWidget(DashboardCard(metric, self))


class ImportDashboardPanel(SimpleCardWidget):
    """导入数据仪表盘卡片。

    以普通水平标题栏 + Edge 风格动态标签页 + 流式指标卡组成。

    Attributes:
        export_button: 右上角导出按钮。
        tab_widget: 仿 Edge 风格动态标签页容器。
        skeleton_widget: 空标题占位标签页中的懒加载骨架。
    """

    _SKELETON_ROUTE_KEY = "__dashboard_skeleton__"

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化导入数据仪表盘卡片。

        Args:
            parent: 父级控件，默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("importDashboardPanel")
        self._init_ui()

    def set_dashboard_pages(self, pages: list[DashboardPage]) -> None:
        """按实际数据重建仪表盘标签页。

        Args:
            pages: 需要展示的标签页数据列表；列表长度决定实际创建的标签页数量。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.tab_widget.clearTabs()
        self.skeleton_widget = None

        for page in pages:
            content = _DashboardPageWidget(page.metrics, self.tab_widget)
            self.tab_widget.addTab(content, page.title, None, page.route_key)

        if pages:
            self.tab_widget.setCurrentIndex(0)
        else:
            self._show_skeleton_page()

    def clear_dashboard_pages(self) -> None:
        """清空当前所有仪表盘标签页。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self._show_skeleton_page()

    def _show_skeleton_page(self) -> None:
        """创建空标题占位标签页并在内容区显示骨架屏。"""
        self.tab_widget.clearTabs()
        self.skeleton_widget = DashboardSkeletonWidget(self.tab_widget)
        self.tab_widget.addTab(
            self.skeleton_widget,
            "",
            None,
            self._SKELETON_ROUTE_KEY,
        )
        self.tab_widget.setCurrentIndex(0)

    def _init_ui(self) -> None:
        """构建标题栏与动态标签页布局。"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 8, 8, 7)
        header_layout.setSpacing(8)

        title_label = BodyLabel("文件信息", self)
        title_label.setObjectName("dashboardTitleLabel")
        setFont(title_label, 14)

        self.export_button = TransparentPushButton("导出", self, FluentIcon.DOWNLOAD)
        self.export_button.setObjectName("dashboardExportButton")
        self.export_button.setFixedHeight(34)
        # setFont(self.export_button, 12)

        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.export_button)
        root_layout.addLayout(header_layout)

        self.separator = QWidget(self)
        self.separator.setObjectName("dashboardSeparator")
        self.separator.setFixedHeight(1)
        self.separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root_layout.addWidget(self.separator)

        self.tab_widget = EdgeTabWidget(self)
        self.tab_widget.setObjectName("dashboardEdgeTab")
        self.tab_widget.setTabMaximumWidth(120)
        self.skeleton_widget: DashboardSkeletonWidget | None = None
        self._show_skeleton_page()

        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(8, 0, 8, 8)
        tab_layout.addWidget(self.tab_widget, 1)
        root_layout.addLayout(tab_layout, 1)
