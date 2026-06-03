# -*- coding: utf-8 -*-
"""导入数据面板组件。

以 CardWidget 为卡片基底，内部依次排列
CommandBar → StyledTabBar → QStackedWidget 三层结构。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QStackedWidget

from qfluentwidgets import (
    Action,
    CardWidget,
    TabBar,
    CommandBar,
    ToolTipFilter,
    ToolTipPosition,
    FluentIcon, TabCloseButtonDisplayMode
)

# from ui.components.styled_tab_bar import StyledTabBar
from ui.components.file_list_page import FileListPage


class ImportDataPanel(CardWidget):
    """导入数据面板。

    以 CardWidget 为卡片基底，内部自上而下依次排列：
      1. CommandBar  ── 提供"添加文件/目录""清除"等操作按钮。
      2. StyledTabBar ── Excel / Bin / MAT 三格式标签（Win11 风格，不可关闭）。
      3. QStackedWidget ── 对应每个标签页的 FileListPage 内容区。

    Attributes:
        file_pages: routeKey → 文件列表页映射字典。
        command_bar: 顶部命令栏。
        tab_bar: 格式标签栏，监听 currentChanged 信号。
        stack: 内容堆叠页，与标签栏索引对应。
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

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件，默认为 None。
        """
        super().__init__(parent)
        self.setObjectName("importDataPanel")
        self.file_pages: dict[str, FileListPage] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        """构建 CommandBar → StyledTabBar → StackedWidget 三层 UI 结构。

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

        # ── 2. Win11 风格自定义标签栏 ──────────────────────────────────
        self.tab_bar = TabBar(self)
        self.tab_bar.setObjectName("importTabBar")
        self.tab_bar.setScrollable(False)
        self.tab_bar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.NEVER)
        self.tab_bar.setAddButtonVisible(False)
        self.tab_bar.setTabMaximumWidth(100)

        for route_key, text, icon in self._TABS:
            self.tab_bar.addTab(routeKey=route_key, text=text, icon=icon)

        root_layout.addWidget(self.tab_bar)

        # ── 3. 内容堆叠区 ──────────────────────────────────────────────
        self.stack = QStackedWidget(self)
        self.stack.setObjectName("importTabStack")

        for route_key, _, _ in self._TABS:
            page = FileListPage(self.stack)
            self.file_pages[route_key] = page
            self.stack.addWidget(page)

        root_layout.addWidget(self.stack, 1)

        # ── 初始选中第一个标签 ─────────────────────────────────────────
        self.tab_bar.setCurrentIndex(0)
        self.stack.setCurrentIndex(0)
        # 标签切换联动内容区
        self.tab_bar.currentChanged.connect(self.stack.setCurrentIndex)
