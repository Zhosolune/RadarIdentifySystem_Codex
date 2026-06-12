# -*- coding: utf-8 -*-
"""导入数据仪表盘卡片组件。

提供标题栏、动态标签页和流式指标卡布局，用于展示选中文件或数据包的摘要信息。
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FlowLayout,
    FluentIcon,
    SimpleCardWidget,
    StrongBodyLabel,
    TransparentPushButton,
    setFont,
)

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
        self.setFixedSize(96, 64)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_ui(metric)
        self._apply_shadow()

    def _init_ui(self, metric: DashboardMetric) -> None:
        """构建指标值与指标名称布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = StrongBodyLabel(metric.value, self)
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
        flow_layout = FlowLayout(self, needAni=False, isTight=True)
        flow_layout.setContentsMargins(10, 8, 10, 8)
        flow_layout.setHorizontalSpacing(10)
        flow_layout.setVerticalSpacing(10)

        for metric in metrics:
            # 指标卡尺寸固定，由 FlowLayout 自动换行排列。
            flow_layout.addWidget(DashboardCard(metric, self))


class ImportDashboardPanel(SimpleCardWidget):
    """导入数据仪表盘卡片。

    以普通水平标题栏 + Edge 风格动态标签页 + 流式指标卡组成。

    Attributes:
        export_button: 右上角导出按钮。
        tab_widget: 仿 Edge 风格动态标签页容器。
    """

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
        self.clear_dashboard_pages()

        for page in pages:
            content = _DashboardPageWidget(page.metrics, self.tab_widget)
            self.tab_widget.addTab(content, page.title, None, page.route_key)

        if pages:
            self.tab_widget.setCurrentIndex(0)

    def clear_dashboard_pages(self) -> None:
        """清空当前所有仪表盘标签页。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.tab_widget.clearTabs()

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

        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(8, 0, 8, 8)
        tab_layout.addWidget(self.tab_widget, 1)
        root_layout.addLayout(tab_layout, 1)
