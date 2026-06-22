"""主页界面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    FluentIcon,
    ScrollArea,
    SettingCardGroup,
    FolderListSettingCard,
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

    功能描述：
        提供一个固定两栏的主页骨架区域。
        - 左侧栏：保留空白占位，供后续业务填充。
        - 右侧栏：包含一个 ScrollArea，其内放置 FolderListSettingCard，
          用于展示并持久化管理"导入数据目录"列表。

    参数说明：
        parent (QWidget | None): 父级控件，默认值为 None。

    返回值说明：
        无。

    异常说明：
        无。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化主页界面。

        功能描述：
            创建左右两栏容器，右侧栏包含带滚动的目录列表设置卡。

        参数说明：
            parent (QWidget | None): 父级控件，默认值为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        super().__init__(parent)
        self.setObjectName("homeInterface")
        self._init_layout()
        StyleSheet.HOME_INTERFACE.apply(self)
        self._home_controller = HomeController(self)

    def _init_layout(self) -> None:
        """初始化两栏布局。

        功能描述：
            构建左侧空白占位栏与右侧带滚动目录管理卡片的两栏布局。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # 左侧空白占位栏
        self.left_column = self._create_left_column()
        # 右侧目录管理面板
        self.right_column = self._create_right_column()

        root_layout.addWidget(self.left_column, 1)
        root_layout.addWidget(self.right_column, 1)

    def _create_left_column(self) -> QWidget:
        """创建左侧带滚动的目录管理面板。

        功能描述：
            构建一个包含 ScrollArea 的右侧面板，ScrollArea 内放置
            SettingCardGroup + FolderListSettingCard，供用户管理
            "导入数据目录"列表，目录变动实时写入 appConfig 持久化配置。

        参数说明：
            无。

        返回值说明：
            QWidget: 右侧列容器对象。

        异常说明：
            无。
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
        """创建右侧空白占位栏。

        功能描述：
            构建一个带圆角边框的占位栏位，内部保留空白区，供后续业务填充。

        参数说明：
            无。

        返回值说明：
            QFrame: 左侧栏容器对象。

        异常说明：
            无。
        """

        column = QWidget(self)
        column.setObjectName("homeSessionColumn")

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.session_manager_panel = SessionManagerPanel(column)
        self.session_manager_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.session_manager_panel, 1)
        return column
