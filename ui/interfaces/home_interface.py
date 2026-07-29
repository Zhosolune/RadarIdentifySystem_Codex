"""主页界面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    FluentIcon,
    BodyLabel,
    ScrollArea,
    FolderListSettingCard,
)
from app.app_config import appConfig
from app.style_sheet import StyleSheet
from ui.components import (
    ImportDataPanel,
    DataPoolPanel,
    FullSpeedSessionPanel,
    JitterFreeCardGroup,
    SessionManagerPanel,
)
from ui.controllers.home_controller import HomeController
from runtime.data_pool_registry import DataPoolRegistry


class HomeInterface(QFrame):
    """主页两栏界面。

    左侧滚动列依次展示数据目录、导入文件和数据池；右侧上下两个同级面板
    分别管理交互式切片 Session 与全速处理 Session。
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        data_pool_registry: DataPoolRegistry | None = None,
    ) -> None:
        """初始化主页界面。

        Args:
            parent: 父级控件，默认值为 None。
            data_pool_registry: 主窗口持有的数据池注册器。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """

        super().__init__(parent)
        self.setObjectName("homeInterface")
        self._init_layout()
        StyleSheet.HOME_INTERFACE.apply(self)
        self._home_controller = HomeController(
            self,
            data_pool_registry or DataPoolRegistry(),
        )

    def _init_layout(self) -> None:
        """初始化两栏布局。

        构建左侧数据导入/数据池列和右侧双 Session 列。
        """

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # 创建左侧数据导入与数据池布局。
        self.left_column = self._create_left_column()
        # 创建右侧上下双卡片布局。
        self.right_column = self._create_right_column()

        root_layout.addWidget(self.left_column, 4)
        root_layout.addWidget(self.right_column, 6)

    def _create_left_column(self) -> QWidget:
        """创建左侧数据导入与数据池面板。

        内容较高时由列内滚动区承载，避免压缩数据池操作按钮。
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

        # ---------- 数据池面板 ----------
        # 解析完成的数据包在此统一注册，再从数据包创建不同处理模式的 Session。
        self.data_pool_panel = DataPoolPanel(scroll_content)
        self.data_pool_panel.setFixedHeight(300)
        content_layout.addWidget(self.data_pool_panel, 0)

        # 将内容容器注入 ScrollArea
        scroll_area.setWidget(scroll_content)

        column_layout.addWidget(scroll_area)
        return column

    def _create_right_column(self) -> QWidget:
        """创建右侧两类同级 Session 面板。

        上方为交互式切片 Session，下方为全速处理 Session，两者按相同
        拉伸因子分配高度。
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
        self.full_speed_session_panel = FullSpeedSessionPanel(column)
        layout.addWidget(self.full_speed_session_panel, 1)
        return column
