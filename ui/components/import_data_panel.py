# -*- coding: utf-8 -*-
"""导入数据面板组件。

以 CardWidget 为卡片基底，内部依次排列
CommandBar → EdgeTabWidget 两层结构。
"""

from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import (QHeaderView, QHBoxLayout, QVBoxLayout, QWidget, QTableWidgetItem)

from qfluentwidgets import (Action, SimpleCardWidget, CommandBar, ToolTipFilter, ToolTipPosition,
                            FluentIcon, TableWidget, TransparentDropDownPushButton, CheckableMenu, 
                            MenuIndicatorType, TransparentPushButton, setFont,
                            InfoBar, InfoBarPosition)

from ui.components.edge_tab_view import EdgeTabWidget
from app.custom_icon import CustomIcon


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
        self.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)

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

        # 让覆盖式滚动条仅贴合项目视口区域，避免覆盖到表头。
        self._adjust_overlay_scroll_bars()

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
        # 数据量变化后同步刷新覆盖式滚动条区域。
        self._adjust_overlay_scroll_bars()

    def resizeEvent(self, event) -> None:
        """在表格尺寸变化时按配置比例重新分配列宽。

        Args:
            event: Qt 尺寸变化事件。

        Returns:
            None: 无返回值。
        """
        super().resizeEvent(event)
        self._apply_column_widths()
        # 跟随视口区域重设滚动条，避免表头被覆盖。
        self._adjust_overlay_scroll_bars()

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

    def _adjust_overlay_scroll_bars(self) -> None:
        """让 Fluent 覆盖式滚动条仅覆盖表格项目视口区域。"""
        scroll_delegate = getattr(self, "scrollDelagate", None)
        if scroll_delegate is None:
            return

        viewport_rect = self.viewport().geometry()
        if not viewport_rect.isValid():
            return

        vertical_bar = getattr(scroll_delegate, "vScrollBar", None)
        if vertical_bar is not None:
            vertical_bar.setGeometry(
                viewport_rect.right() - 11,
                viewport_rect.top(),
                12,
                viewport_rect.height(),
            )

        horizontal_bar = getattr(scroll_delegate, "hScrollBar", None)
        if horizontal_bar is not None:
            horizontal_bar.setGeometry(
                viewport_rect.left(),
                viewport_rect.bottom() - 11,
                viewport_rect.width(),
                12,
            )


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
        ("excel", "Excel", CustomIcon.EXCELFILE),
        ("bin",   "Bin",   CustomIcon.BINARYFILE),
        ("mat",   "MAT",   CustomIcon.MATRIXFILE),
    ]
    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件，默认为 None。
        """
        super().__init__(parent)
        self.setObjectName("importDataPanel")
        self.file_pages: dict[str, _FileTableWidget] = {}

        # 实例化动作
        self.refresh_action = Action(FluentIcon.SYNC, "刷新")
        self.remove_action = Action(FluentIcon.DELETE, "移除")

        self.nameAction = Action(FluentIcon.FONT, "名称", checkable=True)
        self.sizeAction = Action(FluentIcon.FOLDER, "文件大小", checkable=True)
        self.dateAction = Action(FluentIcon.EDIT, "修改日期", checkable=True)
        self.actionGroup1 = QActionGroup(self)
        self.actionGroup1.addAction(self.nameAction)
        self.actionGroup1.addAction(self.sizeAction)
        self.actionGroup1.addAction(self.dateAction)

        self.ascendAction = Action(FluentIcon.UP, "升序", checkable=True)
        self.descendAction = Action(FluentIcon.DOWN, "降序", checkable=True)
        self.actionGroup2 = QActionGroup(self)
        self.actionGroup2.addAction(self.ascendAction)
        self.actionGroup2.addAction(self.descendAction)

        self.oldFormatAction = Action(FluentIcon.EDIT, "使用旧格式", checkable=True)
        self.newFormatAction = Action(FluentIcon.EDIT, "使用新格式", checkable=True)
        self.actionGroup3 = QActionGroup(self)
        self.actionGroup3.addAction(self.oldFormatAction)
        self.actionGroup3.addAction(self.newFormatAction)

        self.nameAction.setChecked(True)
        self.ascendAction.setChecked(True)
        self.oldFormatAction.setChecked(True)

        self.parseButton = TransparentPushButton("解析",self, FluentIcon.LABEL)
        self.parseButton.setFixedHeight(34)

        self._init_ui()
        self._connect_menu_feedback()

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

        # 自定义动作
        self.sort_button = TransparentDropDownPushButton("排序",self, FluentIcon.SCROLL)
        self.option_button = TransparentDropDownPushButton("选项",self, FluentIcon.MORE)
        self.sort_button.setMenu(self.createSortCheckableMenu())
        self.option_button.setMenu(self.createOptionCheckableMenu())
        self.sort_button.setFixedHeight(34)
        self.option_button.setFixedHeight(34)
        setFont(self.sort_button, 12)
        setFont(self.option_button, 12)

        # 添加命令栏按钮
        self.command_bar.addActions([self.refresh_action, self.remove_action])
        self.command_bar.addWidget(self.sort_button)
        self.command_bar.addSeparator()
        self.command_bar.addWidget(self.option_button)

        # 禁用溢出菜单，所有按钮常驻可见
        self.command_bar.setMenuDropDown(False)
        self.command_bar.resizeToSuitableWidth()

        # 添加命令栏的外层布局，以实现与边框的间距
        cmd_layout = QHBoxLayout()
        cmd_layout.setContentsMargins(8, 8, 8, 7)
        cmd_layout.addWidget(self.command_bar)
        cmd_layout.addStretch()
        cmd_layout.addWidget(self.parseButton)
        root_layout.addLayout(cmd_layout)

        self.separator = QWidget(self)
        self.separator.setObjectName("edgeTabSeparator")
        self.separator.setFixedHeight(1)
        self.separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root_layout.addWidget(self.separator, 0)

        # ── 2. 仿 Edge 标签页容器 ──────────────────────────────────────
        self.tab_widget = EdgeTabWidget(self)
        self.tab_widget.setObjectName("importEdgeTab")
        self.tab_widget.setTabMaximumWidth(100)

        for route_key, text, icon in self._TABS:
            table = _FileTableWidget(self.tab_widget)
            self.file_pages[route_key] = table
            table.set_files([])
            self.tab_widget.addTab(table, text, icon, route_key)

        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(8, 0, 8, 8)
        tab_layout.addWidget(self.tab_widget, 1)
        root_layout.addLayout(tab_layout, 1)

        # 初始选中第一个标签
        self.tab_widget.setCurrentIndex(0)

    def set_files_by_type(self, files_by_type: dict[str, list[tuple[str, str, str]]]) -> None:
        """按文件格式刷新各标签页表格。

        Args:
            files_by_type: 文件格式到表格行的映射，键为 ``excel``、``bin``、``mat``；
                每行依次为文件名、修改日期、大小。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常；未知格式键会被忽略。

        """
        for route_key, table in self.file_pages.items():
            # 未提供的格式按空列表处理，避免保留旧扫描结果。
            table.set_files(files_by_type.get(route_key, []))

    def current_format_key(self) -> str:
        """返回当前激活标签页对应的格式键。

        Args:
            无。

        Returns:
            当前格式键，可能为 ``excel``、``bin``、``mat``；索引异常时返回空字符串。

        Raises:
            无显式抛出异常。
        """
        current_index = self.tab_widget.currentIndex()
        if not (0 <= current_index < len(self._TABS)):
            return ""
        return self._TABS[current_index][0]

    def current_selected_row(self) -> int:
        """返回当前标签页选中的表格行索引。

        Args:
            无。

        Returns:
            选中行索引；没有选中行时返回 -1。

        Raises:
            无显式抛出异常。
        """
        format_key = self.current_format_key()
        table = self.file_pages.get(format_key)
        if table is None:
            return -1

        selected_ranges = table.selectedRanges()
        if not selected_ranges:
            return -1
        return selected_ranges[0].topRow()

    def current_sort_key(self) -> str:
        """返回当前选择的排序字段。

        Args:
            无。

        Returns:
            排序字段，取值为 ``name``、``size``、``date``。

        Raises:
            无显式抛出异常。
        """
        if self.sizeAction.isChecked():
            return "size"
        if self.dateAction.isChecked():
            return "date"
        return "name"

    def is_sort_ascending(self) -> bool:
        """返回当前是否为升序排序。

        Args:
            无。

        Returns:
            True 表示升序，False 表示降序。

        Raises:
            无显式抛出异常。
        """
        return not self.descendAction.isChecked()

    def current_excel_data_format(self) -> Literal["old", "new"]:
        """返回当前选择的 Excel 原始列格式。

        Args:
            无。

        Returns:
            Literal["old", "new"]: ``new`` 表示新格式，``old`` 表示旧格式。

        Raises:
            无显式抛出异常。

        Example:
            >>> from typing import get_args
            >>> get_args(Literal["old", "new"])
            ('old', 'new')
        """
        return "new" if self.newFormatAction.isChecked() else "old"

    def _connect_menu_feedback(self) -> None:
        """连接可选中菜单项的状态提示信号。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        action_messages = (
            (self.nameAction, "排序字段", "名称"),
            (self.sizeAction, "排序字段", "文件大小"),
            (self.dateAction, "排序字段", "修改日期"),
            (self.ascendAction, "排序方向", "升序"),
            (self.descendAction, "排序方向", "降序"),
            (self.oldFormatAction, "格式选项", "使用旧格式"),
            (self.newFormatAction, "格式选项", "使用新格式"),
        )
        for action, title, value in action_messages:
            action.triggered.connect(
                lambda checked=False, current_action=action, current_title=title, current_value=value:
                self._show_menu_selection_info(current_action, current_title, current_value)
            )

    def _show_menu_selection_info(self, action: Action, title: str, value: str) -> None:
        """显示菜单选中状态提示。

        Args:
            action: 被触发的可选中菜单动作。
            title: 提示标题。
            value: 当前选中的值。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        if action.isCheckable() and not action.isChecked():
            return

        InfoBar.info(
            title=title,
            content=f"已选择：{value}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1800,
            parent=self.window() or self,
        )

    def createSortCheckableMenu(self, pos=None) -> QMenu:
        """创建可选菜单。

        Returns:
            QMenu: 可选菜单实例。
        """
        menu = CheckableMenu(parent=self, indicatorType=MenuIndicatorType.RADIO)

        menu.addActions([self.nameAction, self.sizeAction, self.dateAction])
        menu.addSeparator()
        menu.addActions([self.ascendAction, self.descendAction])

        if pos is not None:
            menu.exec(pos, ani=True)

        return menu

    def createOptionCheckableMenu(self, pos=None) -> QMenu:
        """创建可选菜单。

        Returns:
            QMenu: 可选菜单实例。
        """
        menu = CheckableMenu(parent=self, indicatorType=MenuIndicatorType.RADIO)

        menu.addActions([self.oldFormatAction, self.newFormatAction])

        if pos is not None:
            menu.exec(pos, ani=True)

        return menu
