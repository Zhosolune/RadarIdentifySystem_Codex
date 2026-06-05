# -*- coding: utf-8 -*-
"""导入数据面板组件。

以 CardWidget 为卡片基底，内部依次排列
CommandBar → EdgeTabWidget 两层结构。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QTableWidgetItem,
)

from qfluentwidgets import (
    Action,
    SimpleCardWidget,
    CommandBar,
    ToolTipFilter,
    ToolTipPosition,
    FluentIcon,
    TableWidget,
)

from ui.components.edge_tab_view import EdgeTabWidget


class _FileTableWidget(TableWidget):
    """文件信息表格。"""

    _COLUMN_STRETCHES: tuple[int, int, int] = (5, 3, 2)

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件，默认为 None。
        """
        super().__init__(parent)
        self.setObjectName("fileTableWidget")
        self._init_table()

    def _init_table(self) -> None:
        """初始化表格列、表头和基础交互。"""
        self.setColumnCount(3)
        self.setRowCount(0)
        self.setHorizontalHeaderLabels(["文件名", "修改日期", "大小"])
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.setBorderVisible(False)
        self.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(TableWidget.SelectionMode.SingleSelection)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._apply_header_divider_style(header)

        # 表头文本与单元格保持左对齐，避免“大小”列默认靠右。
        for column in range(self.columnCount()):
            header_item = self.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )

    def _apply_header_divider_style(self, header: QHeaderView) -> None:
        """仅覆盖表头边框，保留组件库表格主体默认样式。"""
        header.setStyleSheet("""
            QHeaderView::section:horizontal {
                border-left: none;
                border-right: none;
                border-top: none;
                padding-left: 16px;
                padding-right: 16px;
            }
            QHeaderView::section:horizontal:last {
                border-right: none;
            }
        """)

    def set_files(self, files: list[tuple[str, str, str]]) -> None:
        """设置文件列表数据。

        Args:
            files: 文件信息列表，每项依次为文件名、修改日期、大小。

        Returns:
            None: 无返回值。
        """
        self.setRowCount(len(files))
        for row, file_info in enumerate(files):
            for column, text in enumerate(file_info):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(row, column, item)

        self._apply_column_widths()

    def resizeEvent(self, event) -> None:
        """在表格尺寸变化时按配置比例重新分配列宽。

        Args:
            event: Qt 尺寸变化事件。

        Returns:
            None: 无返回值。
        """
        super().resizeEvent(event)
        self._apply_column_widths()

    def _apply_column_widths(self) -> None:
        """按配置比例设置文件名、修改日期、大小三列宽度。"""
        total_stretch = sum(self._COLUMN_STRETCHES)
        available_width = max(0, self.viewport().width())
        if available_width <= 0:
            return

        # 最后一列吃掉四舍五入误差，保证三列总宽等于可视区宽度。
        used_width = 0
        for column, stretch in enumerate(self._COLUMN_STRETCHES):
            if column == len(self._COLUMN_STRETCHES) - 1:
                width = max(1, available_width - used_width)
            else:
                width = max(1, available_width * stretch // total_stretch)
                used_width += width
            self.setColumnWidth(column, width)


class ImportDataPanel(SimpleCardWidget):
    """导入数据面板。

    以 CardWidget 为卡片基底，内部自上而下依次排列：
      1. CommandBar  ── 提供"添加文件/目录""清除"等操作按钮。
      2. EdgeTabWidget ── 仿 Edge 风格标签页，含 Excel / Bin / MAT 三标签。

    Attributes:
        file_pages: routeKey → 文件表格映射字典。
        command_bar: 顶部命令栏。
        tab_widget: 仿 Edge 标签页容器，整合标签栏与内容堆叠区。
        refresh_action: 刷新动作。
        remove_action: 移除动作。
        sort_action: 排序动作。
    """

    # 三个标签的路由键、显示文字、图标
    _TABS: list[tuple[str, str, FluentIcon]] = [
        ("excel", "Excel", FluentIcon.DOCUMENT),
        ("bin",   "Bin",   FluentIcon.ZIP_FOLDER),
        ("mat",   "MAT",   FluentIcon.LAYOUT),
    ]
    _SAMPLE_FILES: list[tuple[str, str, str]] = [
        ("radar_echo_001.xlsx", "2026-06-05 09:12", "2.4 MB"),
        ("radar_echo_002.xlsx", "2026-06-05 09:35", "3.1 MB"),
        ("pulse_train_alpha.xlsx", "2026-06-05 10:08", "856 KB"),
        ("pulse_train_beta.xlsx", "2026-06-05 10:42", "1.7 MB"),
        ("signal_feature_set.xlsx", "2026-06-05 11:03", "4.6 MB"),
        ("target_profile_a.xlsx", "2026-06-05 11:28", "938 KB"),
        ("target_profile_b.xlsx", "2026-06-05 13:16", "1.2 MB"),
        ("frequency_scan_01.xlsx", "2026-06-05 13:44", "5.8 MB"),
        ("frequency_scan_02.xlsx", "2026-06-05 14:05", "6.3 MB"),
        ("识别样本预览.xlsx", "2026-06-05 14:37", "742 KB"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件，默认为 None。
        """
        super().__init__(parent)
        self.setObjectName("importDataPanel")
        self.file_pages: dict[str, _FileTableWidget] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        """构建 CommandBar → EdgeTabWidget 两层 UI 结构。

        Returns:
            None: 无返回值。
        """
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 1. 命令栏 ──────────────────────────────────────────────────
        self.command_bar = CommandBar(self)
        self.command_bar.setObjectName("importCommandBar")
        self.command_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.command_bar.setButtonTight(True)

        # 实例化动作
        self.refresh_action = Action(FluentIcon.ADD,         "刷新")
        self.remove_action  = Action(FluentIcon.FOLDER_ADD,  "移除")
        self.sort_action    = Action(FluentIcon.DELETE,       "排序")

        self.refresh_action.setToolTip("刷新当前文件列表")
        self.remove_action.setToolTip("移除选中的文件")
        self.sort_action.setToolTip("对文件列表进行排序")

        self.command_bar.addActions([self.refresh_action, self.remove_action])
        self.command_bar.addSeparator()
        self.command_bar.addAction(self.sort_action)

        # 禁用溢出菜单，所有按钮常驻可见
        self.command_bar.setMenuDropDown(False)
        self.command_bar.resizeToSuitableWidth()

        # 为命令栏按钮安装 Fluent 风格悬浮提示
        for btn in self.command_bar.commandButtons:
            btn.installEventFilter(ToolTipFilter(btn, 500, ToolTipPosition.BOTTOM))

        # 添加命令栏的外层布局，以实现与边框的间距
        cmd_layout = QHBoxLayout()
        cmd_layout.setContentsMargins(8, 8, 8, 8)
        cmd_layout.addWidget(self.command_bar)
        cmd_layout.addStretch()
        root_layout.addLayout(cmd_layout)
        
        self.separator = QWidget(self)
        self.separator.setObjectName("edgeTabSeparator")
        self.separator.setFixedHeight(1)
        self.separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root_layout.addWidget(self.separator, 0)

        # ── 2. 仿 Edge 标签页容器 ──────────────────────────────────────
        self.tab_widget = EdgeTabWidget(self)
        self.tab_widget.setObjectName("importEdgeTab")
        self.tab_widget.setTabMaximumWidth(200)

        for route_key, text, icon in self._TABS:
            table = _FileTableWidget(self.tab_widget)
            self.file_pages[route_key] = table
            # 临时填充示例数据，便于检查表格视觉效果。
            table.set_files(self._build_sample_files(text))
            self.tab_widget.addTab(table, text, icon, route_key)

        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(8, 0, 8, 8)
        tab_layout.addWidget(self.tab_widget, 1)
        root_layout.addLayout(tab_layout, 1)

        # 初始选中第一个标签
        self.tab_widget.setCurrentIndex(0)

    def _build_sample_files(self, tab_name: str) -> list[tuple[str, str, str]]:
        """生成当前标签页的示例文件列表。

        Args:
            tab_name: 当前标签页显示名称。

        Returns:
            示例文件信息列表，每项依次为文件名、修改日期、大小。
        """
        suffix_map = {"Excel": "xlsx", "Bin": "bin", "MAT": "mat"}
        suffix = suffix_map.get(tab_name, tab_name.lower())
        return [
            (name.replace(".xlsx", f".{suffix}"), modified_time, size)
            for name, modified_time, size in self._SAMPLE_FILES
        ]
