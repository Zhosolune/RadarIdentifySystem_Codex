# -*- coding: utf-8 -*-
"""导入数据仪表盘卡片组件。

提供标题栏、动态标签页和流式指标卡布局，用于展示选中文件或数据包的摘要信息。
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
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
    AdaptiveFlowLayout,
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    PrimaryPushButton,
    SimpleCardWidget,
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


def format_dashboard_band(band: str | None) -> str:
    """格式化仪表盘波段卡片中的波段名称。

    Args:
        band [str | None]: Core 层波段名称，例如 ``"S波段"``；为空时表示未知。

    Returns:
        str: 去掉末尾“波段”的短名称；未知波段返回 ``"--"``。

    Raises:
        无显式抛出异常。

    Example:
        >>> format_dashboard_band("S波段")
        'S'
        >>> format_dashboard_band(None)
        '--'
    """
    if not band:
        return "--"
    return band.removesuffix("波段") or "--"


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

class _DashboardPageWidget(QWidget):
    """仪表盘单个标签页内容。"""

    importRequested = pyqtSignal()

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
        """构建流式指标卡和右下角操作按钮布局。"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        metrics_container = QWidget(self)
        metrics_container.setObjectName("dashboardMetricsContainer")
        flow_layout = AdaptiveFlowLayout(metrics_container, needAni=True, isTight=True)
        flow_layout.setContentsMargins(10, 8, 10, 8)
        flow_layout.setHorizontalSpacing(10)
        flow_layout.setVerticalSpacing(10)
        flow_layout.setWidgetMinimumWidth(110)

        for metric in metrics:
            # 指标卡宽度交给 AdaptiveFlowLayout 按行均分。
            flow_layout.addWidget(DashboardCard(metric, metrics_container))

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(10, 0, 10, 10)
        action_layout.addStretch(1)

        self.import_button = PrimaryPushButton(
            FluentIcon.ADD_TO,
            "新建Session并导入",
            self,
        )
        self.import_button.setObjectName("dashboardImportSessionButton")
        self.import_button.setFixedHeight(32)
        self.import_button.clicked.connect(
            lambda _checked=False: self.importRequested.emit()
        )
        action_layout.addWidget(self.import_button, 0, Qt.AlignmentFlag.AlignRight)

        root_layout.addWidget(metrics_container, 1)
        root_layout.addLayout(action_layout, 0)


class ImportDashboardPanel(SimpleCardWidget):
    """导入数据仪表盘卡片。

    以普通水平标题栏 + Edge 风格动态标签页 + 流式指标卡组成。

    Attributes:
        export_button: 右上角导出按钮。
        tab_widget: 仿 Edge 风格动态标签页容器。
        skeleton_widget: 空标题占位标签页中的懒加载骨架。
    """

    importSessionRequested = pyqtSignal()

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
            content.importRequested.connect(self.importSessionRequested.emit)
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
