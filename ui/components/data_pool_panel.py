"""主页数据池标签页、数据卡片与详情弹层组件。"""

from __future__ import annotations

from math import ceil
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    AdaptiveFlowLayout,
    BodyLabel,
    CaptionLabel,
    Flyout,
    FlyoutAnimationType,
    FlyoutViewBase,
    FluentIcon,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SimpleCardWidget,
    TransparentPushButton,
    TransparentToolButton,
    setFont,
)

from app.custom_icon import CustomIcon
from app.style_sheet import StyleSheet
from core.models.dashboard_info import ExcelDashboardInfo
from core.models.data_package import DataPackage
from ui.components.card_navigation_list import CardNavigationItem
from ui.components.edge_tab_view import EdgeTabWidget
from ui.components.import_dashboard_panel import (
    DashboardCard,
    DashboardMetric,
    format_dashboard_duration,
)


class DataPackageCard(CardNavigationItem):
    """展示数据池中单个数据包的摘要和详情入口。

    Attributes:
        packageSelected: 用户点击卡片时发出的数据包选择信号。
        detailsRequested: 用户点击详情按钮时发出的详情请求信号。
        package_id: 当前卡片绑定的数据包唯一 ID。
        details_button: 卡片右下角透明详情按钮。
    """

    packageSelected = pyqtSignal(str)
    detailsRequested = pyqtSignal(str)

    def __init__(
        self,
        package: DataPackage,
        parent: QWidget | None = None,
    ) -> None:
        """初始化数据包卡片。

        Args:
            package [DataPackage]: 卡片绑定的只读数据包。
            parent [QWidget | None]: 父组件，默认为 None。

        Returns:
            None: 无返回值。
        """
        super().__init__(
            package.package_id,
            package.display_name,
            package.band or "未知波段",
            parent=parent,
        )
        self.package_id = package.package_id
        self.setObjectName("dataPoolCard")
        self.setMinimumWidth(0)
        self.title_label.setToolTip(package.display_name)
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        if self.subtitle_label is not None:
            self.subtitle_label.setMinimumWidth(0)
            self.subtitle_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
        self._main_layout.setSpacing(8)
        self.details_button = TransparentPushButton("详情", self)
        self.details_button.setObjectName("dataPoolDetailsButton")
        # self.details_button.setFixedSize(52, 26)
        self._main_layout.addWidget(
            self.details_button,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )

        self.clicked.connect(
            lambda: self.packageSelected.emit(self.package_id)
        )
        self.details_button.clicked.connect(
            lambda _checked=False: self.detailsRequested.emit(self.package_id)
        )


class DataPackageDetailFlyoutView(FlyoutViewBase):
    """使用 Session 详情同款流式指标卡展示数据包详情。

    Attributes:
        closeRequested: 请求关闭当前详情 Flyout 的信号。
        close_button: 弹层右上角关闭按钮。
        metrics_layout: 六项解析指标的自适应流式布局。
        metric_cards: 当前展示的仪表盘指标卡片。
    """

    closeRequested = pyqtSignal()

    def __init__(
        self,
        package: DataPackage,
        width: int,
        parent: QWidget | None = None,
    ) -> None:
        """初始化数据包详情弹层内容。

        Args:
            package [DataPackage]: 需要展示的只读数据包。
            width [int]: 弹层内容宽度，不含 Flyout 外层阴影边距。
            parent [QWidget | None]: 父组件，默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: width 小于 1 时抛出。
        """
        if width < 1:
            raise ValueError("详情弹层宽度必须大于 0")
        super().__init__(parent)
        self.setObjectName("dataPoolDetailFlyout")
        self.setFixedWidth(width)
        self.metric_cards: list[DashboardCard] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(8)
        self._root_layout = root_layout

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title_label = BodyLabel("数据包详情", self)
        title_label.setObjectName("dataPoolDetailTitle")
        setFont(title_label, 16)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.close_button.setObjectName("dataPoolDetailCloseButton")
        self.close_button.setFixedSize(32, 32)
        self.close_button.setIconSize(QSize(12, 12))
        header_layout.addWidget(self.close_button)
        root_layout.addLayout(header_layout)

        metrics_widget = QWidget(self)
        metrics_widget.setObjectName("dataPoolDetailMetrics")
        # 根据弹层实际宽度计算行数，窄窗口下也不会裁切流式指标卡。
        metrics_available_width = max(1, width - 34)
        cards_per_row = max(1, (metrics_available_width + 10) // 120)
        metric_rows = ceil(6 / cards_per_row)
        metrics_widget.setFixedHeight(
            metric_rows * 60 + max(0, metric_rows - 1) * 10 + 6
        )
        self.metrics_layout = AdaptiveFlowLayout(
            metrics_widget,
            needAni=False,
            isTight=True,
        )
        self.metrics_layout.setContentsMargins(3, 3, 3, 3)
        self.metrics_layout.setHorizontalSpacing(10)
        self.metrics_layout.setVerticalSpacing(10)
        self.metrics_layout.setWidgetMinimumWidth(110)
        root_layout.addWidget(metrics_widget)

        for metric in self._build_metrics(package):
            card = DashboardCard(metric, metrics_widget)
            self.metric_cards.append(card)
            self.metrics_layout.addWidget(card)

        info_widget = QWidget(self)
        info_widget.setObjectName("dataPoolDetailInfoPanel")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(2, 0, 2, 2)
        info_layout.setSpacing(5)
        file_path = Path(package.source_path) if package.source_path else None
        info_layout.addWidget(
            self._create_info_row("数据包 ID", package.package_id, info_widget)
        )
        info_layout.addWidget(
            self._create_info_row(
                "文件名",
                file_path.name if file_path else "--",
                info_widget,
            )
        )
        info_layout.addWidget(
            self._create_info_row(
                "文件大小",
                self._format_source_file_size(file_path),
                info_widget,
            )
        )
        info_layout.addWidget(
            self._create_info_row(
                "数据格式",
                package.data_format or package.source_type.upper() or "--",
                info_widget,
            )
        )
        info_layout.addWidget(
            self._create_info_row(
                "加入时间",
                package.created_at.strftime("%Y-%m-%d %H:%M"),
                info_widget,
            )
        )
        info_layout.addWidget(
            self._create_info_row(
                "文件路径",
                package.source_path or "--",
                info_widget,
            )
        )
        root_layout.addWidget(info_widget)

        self.close_button.clicked.connect(self.closeRequested)
        # Flyout 不属于 HomeInterface 的子树，需要主动应用同一套主页主题 QSS。
        StyleSheet.HOME_INTERFACE.apply(self)

    def addWidget(
        self,
        widget: QWidget,
        stretch: int = 0,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> None:
        """向详情弹层追加自定义组件。

        Args:
            widget [QWidget]: 需要追加的组件。
            stretch [int]: 垂直拉伸因子，默认为 0。
            align [Qt.AlignmentFlag]: 组件对齐方式，默认为左对齐。

        Returns:
            None: 无返回值。
        """
        self._root_layout.addWidget(widget, stretch, align)

    def _build_metrics(self, package: DataPackage) -> list[DashboardMetric]:
        """构建与 Session 详情一致的六项解析指标。"""
        info = package.dashboard_info
        if not isinstance(info, ExcelDashboardInfo):
            return [
                DashboardMetric("总脉冲", "--"),
                DashboardMetric("剔除脉冲", "--"),
                DashboardMetric("幅度丢弃", "--"),
                DashboardMetric("持续时间", "--"),
                DashboardMetric("波段", package.band or "--"),
                DashboardMetric("预计切片数", "--"),
            ]
        return [
            DashboardMetric("总脉冲", str(info.total_pulses)),
            DashboardMetric("剔除脉冲", str(info.removed_pulses)),
            DashboardMetric("幅度丢弃", str(info.amplitude_dropped_pulses)),
            DashboardMetric("持续时间", format_dashboard_duration(info.duration)),
            DashboardMetric("波段", info.band or "--"),
            DashboardMetric("预计切片数", str(info.estimated_slice_count)),
        ]

    def _create_info_row(
        self,
        title: str,
        value: str,
        parent: QWidget,
    ) -> QWidget:
        """创建与 Session 详情一致的标题和值信息行。"""
        row = QWidget(parent)
        row.setObjectName("dataPoolDetailInfoRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_label = CaptionLabel(f"{title}：", row)
        title_label.setObjectName("dataPoolDetailInfoTitle")
        title_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        title_label.setFixedWidth(72)
        value_label = CaptionLabel(value, row)
        value_label.setObjectName("dataPoolDetailInfoValue")
        value_label.setWordWrap(True)
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(value_label, 1, Qt.AlignmentFlag.AlignTop)
        return row

    def _format_source_file_size(self, file_path: Path | None) -> str:
        """格式化源文件大小。"""
        if file_path is None or not file_path.exists():
            return "未知"

        units = ("B", "KB", "MB", "GB", "TB")
        size = float(max(file_path.stat().st_size, 0))
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return (
                    f"{int(size)} {unit}"
                    if unit == "B"
                    else f"{size:.1f} {unit}"
                )
            size /= 1024
        return f"{size:.1f} TB"


class _DataPoolTabPage(QWidget):
    """按可用宽度承载两列至四列等宽数据卡片。"""

    packageSelected = pyqtSignal(str)
    detailsRequested = pyqtSignal(str)

    _MIN_COLUMNS = 2
    _MAX_COLUMNS = 4
    _MIN_CARD_WIDTH = 240

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化标签页滚动区和响应式网格。"""
        super().__init__(parent)
        self.setObjectName("dataPoolTabPage")
        self.cards: dict[str, DataPackageCard] = {}
        self._empty_label: BodyLabel | None = None
        self._column_count = self._MIN_COLUMNS

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setObjectName("dataPoolTabScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.viewport().setObjectName("dataPoolTabViewport")

        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setObjectName("dataPoolTabContent")
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setHorizontalSpacing(8)
        self.grid_layout.setVerticalSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.content_widget)
        self.scroll_area.viewport().installEventFilter(self)
        root_layout.addWidget(self.scroll_area)

    def set_packages(self, packages: list[DataPackage]) -> None:
        """刷新当前数据类型的响应式卡片。

        Args:
            packages [list[DataPackage]]: 当前标签页需要展示的数据包。

        Returns:
            None: 无返回值。
        """
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.cards.clear()
        self._empty_label = None

        if not packages:
            self._empty_label = BodyLabel(
                "暂无该类型数据",
                self.content_widget,
            )
            self._empty_label.setObjectName("dataPoolEmptyLabel")
            self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_label.setMinimumHeight(120)
            self._relayout_cards(force=True)
            return

        for package in packages:
            card = DataPackageCard(package, self.content_widget)
            card.packageSelected.connect(self.packageSelected)
            card.detailsRequested.connect(self.detailsRequested)
            self.cards[package.package_id] = card
        self._relayout_cards(force=True)

    def column_count(self) -> int:
        """返回当前响应式网格列数。

        Returns:
            int: 当前列数，取值范围为 2 至 4。
        """
        return self._column_count

    def first_package_id(self) -> str | None:
        """返回当前标签页首个数据包 ID。"""
        return next(iter(self.cards), None)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """在滚动视口宽度变化时重新计算卡片列数。"""
        if (
            watched is self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            resize_size = getattr(event, "size", None)
            viewport_width = (
                resize_size().width()
                if callable(resize_size)
                else None
            )
            self._relayout_cards(viewport_width=viewport_width)
        return super().eventFilter(watched, event)

    def _responsive_column_count(
        self,
        viewport_width: int | None = None,
    ) -> int:
        """根据视口可用宽度返回两列、三列或四列。"""
        margins = self.grid_layout.contentsMargins()
        spacing = max(0, self.grid_layout.horizontalSpacing())
        if viewport_width is None:
            viewport_width = self.scroll_area.viewport().width()
        available_width = max(
            0,
            viewport_width
            - margins.left()
            - margins.right(),
        )
        for columns in range(self._MAX_COLUMNS, self._MIN_COLUMNS, -1):
            required_width = (
                columns * self._MIN_CARD_WIDTH
                + (columns - 1) * spacing
            )
            if available_width >= required_width:
                return columns
        return self._MIN_COLUMNS

    def _relayout_cards(
        self,
        *,
        force: bool = False,
        viewport_width: int | None = None,
    ) -> None:
        """保持卡片顺序并按当前断点重新放入网格。"""
        column_count = self._responsive_column_count(viewport_width)
        if not force and column_count == self._column_count:
            return
        self._column_count = column_count

        while self.grid_layout.count():
            self.grid_layout.takeAt(0)
        for column in range(self._MAX_COLUMNS):
            self.grid_layout.setColumnStretch(
                column,
                1 if column < column_count else 0,
            )

        if self._empty_label is not None:
            self.grid_layout.addWidget(
                self._empty_label,
                0,
                0,
                1,
                column_count,
            )
            return

        for index, card in enumerate(self.cards.values()):
            self.grid_layout.addWidget(
                card,
                index // column_count,
                index % column_count,
            )


class DataPoolPanel(SimpleCardWidget):
    """按数据类型标签页展示数据包并提供 Session 创建入口。

    Attributes:
        createSessionRequested: 携带选中 ``package_id`` 的创建请求信号。
        deletePackageRequested: 携带选中 ``package_id`` 的删除请求信号。
        tab_widget: Excel、Bin、MAT 和其他数据类型标签页。
        package_pages: 数据类型路由键到标签页的映射。
    """

    createSessionRequested = pyqtSignal(str)
    deletePackageRequested = pyqtSignal(str)

    _TABS = (
        ("excel", "Excel", CustomIcon.EXCELFILE),
        ("bin", "Bin", CustomIcon.BINARYFILE),
        ("mat", "MAT", CustomIcon.MATRIXFILE),
        ("other", "其他", FluentIcon.DOCUMENT),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化数据池面板。

        Args:
            parent [QWidget | None]: 父组件，默认为 None。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.setObjectName("homeDataPoolPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._package_map: dict[str, DataPackage] = {}
        self._selected_package_id: str | None = None
        self._cards_by_id: dict[str, DataPackageCard] = {}
        self._detail_flyout: Flyout | None = None
        self._updating_tabs = False

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 8, 8, 7)
        title_label = BodyLabel("数据池", self)
        title_label.setFixedHeight(34)
        setFont(title_label, 14)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        root_layout.addLayout(header_layout)

        separator = QWidget(self)
        separator.setObjectName("homePanelSeparator")
        separator.setFixedHeight(1)
        separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root_layout.addWidget(separator)

        body = QWidget(self)
        body.setObjectName("dataPoolBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 0, 8, 8)
        body_layout.setSpacing(7)

        self.tab_widget = EdgeTabWidget(body)
        self.tab_widget.setObjectName("dataPoolEdgeTab")
        self.tab_widget.setTabMaximumWidth(100)
        self.package_pages: dict[str, _DataPoolTabPage] = {}
        for route_key, text, icon in self._TABS:
            page = _DataPoolTabPage(self.tab_widget)
            page.packageSelected.connect(self._on_package_selected)
            page.detailsRequested.connect(self._show_package_details)
            self.package_pages[route_key] = page
            self.tab_widget.addTab(page, text, icon, route_key)
        self.tab_widget.setCurrentIndex(0)
        body_layout.addWidget(self.tab_widget, 1)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        self.create_button = PrimaryPushButton(FluentIcon.ADD, "创建 Session", body)
        self.delete_button = PushButton(FluentIcon.DELETE, "删除数据包", body)
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        action_layout.addWidget(self.create_button)
        action_layout.addWidget(self.delete_button)
        body_layout.addLayout(action_layout)
        root_layout.addWidget(body, 1)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.create_button.clicked.connect(self._emit_create_request)
        self.delete_button.clicked.connect(self._emit_delete_request)

    def set_packages(
        self,
        packages: list[DataPackage],
        *,
        selected_package_id: str | None = None,
    ) -> None:
        """按数据类型刷新标签页并恢复优先选中的数据包。

        Args:
            packages [list[DataPackage]]: 按展示顺序排列的数据包。
            selected_package_id [str | None]: 刷新后优先选中的数据包 ID。

        Returns:
            None: 无返回值。
        """
        self._updating_tabs = True
        self._package_map = {
            package.package_id: package
            for package in packages
        }
        grouped_packages = {route_key: [] for route_key, _text, _icon in self._TABS}
        package_routes: dict[str, str] = {}
        for package in packages:
            route_key = self._route_key_for_package(package)
            grouped_packages[route_key].append(package)
            package_routes[package.package_id] = route_key

        self._cards_by_id.clear()
        for route_key, page in self.package_pages.items():
            page.set_packages(grouped_packages[route_key])
            self._cards_by_id.update(page.cards)

        target_id = selected_package_id
        if target_id not in self._package_map:
            target_id = self._selected_package_id
        if target_id not in self._package_map:
            target_id = packages[0].package_id if packages else None

        if target_id is not None:
            target_route = package_routes[target_id]
            target_index = next(
                index
                for index, (route_key, _text, _icon) in enumerate(self._TABS)
                if route_key == target_route
            )
            self.tab_widget.setCurrentIndex(target_index)
        self._updating_tabs = False
        self._select_package(target_id)

    def current_package_id(self) -> str | None:
        """返回当前选中的数据包 ID。

        Returns:
            str | None: 当前数据包 ID；没有选择时返回 None。
        """
        return self._selected_package_id

    def resizeEvent(self, event: QResizeEvent) -> None:
        """在数据池宽度变化时同步刷新全部标签页栏数。"""
        super().resizeEvent(event)
        if not hasattr(self, "package_pages"):
            return
        # 扣除数据池主体左右边距和标签内容边框。
        viewport_width = max(0, event.size().width() - 18)
        for page in self.package_pages.values():
            page._relayout_cards(viewport_width=viewport_width)

    def _route_key_for_package(self, package: DataPackage) -> str:
        """将数据包来源类型归一化为稳定标签页路由键。"""
        source_type = package.source_type.strip().lower()
        aliases = {
            "xls": "excel",
            "xlsx": "excel",
            "binary": "bin",
            "matlab": "mat",
        }
        source_type = aliases.get(source_type, source_type)
        if source_type in self.package_pages:
            return source_type

        suffix = Path(package.source_path).suffix.lower()
        if suffix in {".xls", ".xlsx"}:
            return "excel"
        if suffix == ".bin":
            return "bin"
        if suffix == ".mat":
            return "mat"
        return "other"

    def _on_package_selected(self, package_id: str) -> None:
        """响应卡片点击并同步全局选择状态。"""
        self._select_package(package_id)

    def _on_tab_changed(self, index: int) -> None:
        """切换数据类型时选中当前页首个数据包。"""
        if self._updating_tabs or not (0 <= index < len(self._TABS)):
            return
        route_key = self._TABS[index][0]
        page = self.package_pages[route_key]
        if self._selected_package_id in page.cards:
            return
        self._select_package(page.first_package_id())

    def _select_package(self, package_id: str | None) -> None:
        """设置唯一选中的数据包并同步操作按钮。"""
        if package_id not in self._package_map:
            package_id = None
        self._selected_package_id = package_id
        for current_id, card in self._cards_by_id.items():
            card.set_selected(current_id == package_id)
        enabled = package_id is not None
        self.create_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def _show_package_details(self, package_id: str) -> None:
        """在详情按钮上方向上弹出与数据池等宽的详情视图。"""
        package = self._package_map.get(package_id)
        card = self._cards_by_id.get(package_id)
        if package is None or card is None:
            return

        if self._detail_flyout is not None:
            self._detail_flyout.close()
        # Flyout 固定包含左右各 15px 的阴影边距，扣除后外层总宽与面板一致。
        view_width = max(1, self.width() - 30)
        view = DataPackageDetailFlyoutView(package, view_width)
        flyout = Flyout.make(
            view,
            card.details_button,
            self.window() or self,
            aniType=FlyoutAnimationType.PULL_UP,
        )
        self._detail_flyout = flyout
        view.closeRequested.connect(flyout.close)
        flyout.closed.connect(self._clear_detail_flyout)

    def _clear_detail_flyout(self) -> None:
        """清除已经关闭的详情弹层引用。"""
        self._detail_flyout = None

    def _emit_create_request(self) -> None:
        """发出当前数据包的创建 Session 请求。"""
        package_id = self.current_package_id()
        if package_id:
            self.createSessionRequested.emit(package_id)

    def _emit_delete_request(self) -> None:
        """发出当前数据包的删除请求。"""
        package_id = self.current_package_id()
        if package_id:
            self.deletePackageRequested.emit(package_id)
