"""主页界面。"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    FluentIcon,
    BodyLabel,
    ScrollArea,
    SimpleCardWidget,
    FolderListSettingCard,
    setFont
)
from app.app_config import appConfig
from app.style_sheet import StyleSheet
from ui.components import (
    ImportDashboardPanel,
    ImportDataPanel,
    JitterFreeCardGroup,
    SessionManagerPanel,
)
from ui.controllers.home_controller import HomeController


class HomeInterface(QFrame):
    """主页界面（非滚动、两栏布局）。

    左侧列使用固定三区结构：顶部数据目录卡固定高度，中部导入列表卡片
    撑满剩余高度，底部仪表盘卡固定高度。右侧列使用上下双卡片结构，
    上方放置 session 管理卡，下方保留同风格占位卡。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化主页界面。

        Args:
            parent: 父级控件，默认值为 None。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """

        super().__init__(parent)
        self.setObjectName("homeInterface")
        self._init_layout()
        StyleSheet.HOME_INTERFACE.apply(self)
        self._home_controller = HomeController(self)

    def _init_layout(self) -> None:
        """初始化两栏布局。

        构建左侧固定三区列和右侧上下双卡片列。
        """

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # 创建左侧固定三区布局。
        self.left_column = self._create_left_column()
        # 创建右侧上下双卡片布局。
        self.right_column = self._create_right_column()

        root_layout.addWidget(self.left_column, 4)
        root_layout.addWidget(self.right_column, 6)

    def _create_left_column(self) -> QWidget:
        """创建左侧固定三区布局面板。

        左侧列由三个卡片区组成：顶部目录选项卡固定高度，中部文件列表卡片
        撑满剩余空间，底部仪表盘卡片固定高度。
        """

        column = QWidget(self)
        column.setObjectName("homeLeftColumn")

        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(0)

        # ---------- ScrollArea ----------
        # 使用 qfluentwidgets 的 ScrollArea，自带主题感知滚动条样式
        scroll_area = ScrollArea(column)
        scroll_area.setObjectName("homeLeftScrollArea")
        scroll_area.setWidgetResizable(True)
        # 关闭水平滚动条，保持面板整洁
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # ---------- 滚动内容容器 ----------
        scroll_content = QWidget()
        scroll_content.setObjectName("homeLeftScrollContent")

        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # ---------- JitterFreeCardGroup ----------
        data_dir_group = JitterFreeCardGroup(scroll_content)
        data_dir_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        # FolderListSettingCard：自动从 appConfig.importDataDirs 读写
        # directory 参数指定"添加文件夹"对话框的初始目录
        import os
        default_dir = os.path.expanduser("~")
        self.import_dir_card = FolderListSettingCard(
            configItem=appConfig.importDataDirs,
            title="数据目录",
            content="管理雷达数据文件的导入目录列表",
            directory=default_dir,
            parent=data_dir_group,
        )
        data_dir_group.addSettingCard(self.import_dir_card)
        content_layout.addWidget(data_dir_group)

        # ---------- 导入数据面板（标签栏 + 文件列表） ----------
        # 放置在导入目录卡片下方，提供 Excel/Bin/MAT 三种格式的文件管理界面
        self.import_panel = ImportDataPanel(scroll_content)
        # 文件列表承担右侧栏剩余高度，空间不足时交给外层 ScrollArea 滚动。
        self.import_panel.setMinimumHeight(320)
        self.import_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        content_layout.addWidget(self.import_panel, 1)

        # ---------- 仪表盘面板（动态标签页 + 流式指标卡） ----------
        self.dashboard_panel = ImportDashboardPanel(scroll_content)
        self.dashboard_panel.setFixedHeight(300)
        content_layout.addWidget(self.dashboard_panel, 0)

        # 将内容容器注入 ScrollArea
        scroll_area.setWidget(scroll_content)

        column_layout.addWidget(scroll_area)
        return column

    def _create_right_column(self) -> QWidget:
        """创建右侧上下双卡片面板。

        右侧列包含上下两个卡片：上方为 session 管理卡，下方为后续扩展预留卡。
        两张卡片按相同拉伸因子分配高度。
        """

        column = QWidget(self)
        column.setObjectName("homeSessionColumn")

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # session管理面板
        self.session_manager_panel = SessionManagerPanel(column)
        self.session_manager_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.session_manager_panel, 1)
        self.session_placeholder_card = self._create_placeholder_card(column)
        layout.addWidget(self.session_placeholder_card, 1)
        return column

    def _create_placeholder_card(self, parent: QWidget) -> SimpleCardWidget:
        """创建右侧下半区预留卡片。"""
        card = SimpleCardWidget(parent)
        card.setObjectName("homeRightPlaceholderCard")

        root_layout = QVBoxLayout(card)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 8, 8, 7)
        header_layout.setSpacing(8)

        title_label = BodyLabel("预留面板", card)
        title_label.setObjectName("homeRightPlaceholderTitle")
        setFont(title_label, 14)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        root_layout.addLayout(header_layout)

        separator = QWidget(card)
        separator.setObjectName("homePanelSeparator")
        separator.setFixedHeight(1)
        separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root_layout.addWidget(separator)

        body_widget = QWidget(card)
        body_widget.setObjectName("homeRightPlaceholderBody")
        body_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(0)

        placeholder_label = BodyLabel("右侧下半区占位", body_widget)
        placeholder_label.setObjectName("homeRightPlaceholderText")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_layout.addWidget(placeholder_label, 1)
        root_layout.addWidget(body_widget, 1)
        return card
