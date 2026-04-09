"""导航控制组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import CardWidget, FluentIcon, SwitchSettingCard, IconWidget
from .action_button_widget import ActionButtonCard
from app.app_config import appConfig
from app.custom_icon import CustomIcon

class NavigationControlCard(QWidget):
    """导航控制组件。

    功能描述：
        提供“上一类”、“下一类”、“上一片”、“下一片”导航按钮（使用 ElevatedCardWidget，位于同一行）。
        下方包含一个“点击下一片直接识别”开关设置卡（SwitchSettingCard），与全局配置联动。
        整体采用垂直布局划分区域。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        prev_cluster_button (NavButtonCard): 切换上一类的按钮。
        next_cluster_button (NavButtonCard): 切换下一类的按钮。
        prev_slice_button (NavButtonCard): 切换上一片的按钮。
        next_slice_button (NavButtonCard): 切换下一片的按钮。
        auto_recognize_card (SwitchSettingCard): 切换下一片时是否自动识别的设置卡。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化导航控制组件。

        功能描述：
            创建布局并实例化内部的所有导航按钮和复选框组件。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(parent)
        self.setObjectName("navigationControlCard")

        # 类别导航
        self.prev_cluster_button = ActionButtonCard(CustomIcon.CHEVRON_LEFT, "上一类", self)
        self.next_cluster_button = ActionButtonCard(CustomIcon.CHEVRON_RIGHT, "下一类", self)

        # 重置按钮
        self.reset_cur_slice_button  = ActionButtonCard(CustomIcon.RESET, "重置当前切片", self)

        # 切片导航
        self.prev_slice_button = ActionButtonCard(CustomIcon.CHEVRONS_LEFT, "上一片", self)
        self.next_slice_button = ActionButtonCard(CustomIcon.CHEVRONS_RIGHT, "下一片", self)
        
        # 自动选项设置卡
        self.auto_recognize_card = SwitchSettingCard(
            icon=FluentIcon.PLAY,
            title="自动识别",
            content="切换下一片时自动执行识别工作流",
            configItem=appConfig.autoRecognizeNextSlice,
            parent=self
        )

        self._init_layout()

    def _init_layout(self) -> None:
        """初始化卡片内部布局。

        功能描述：
            将导航悬浮按钮放在同一行居中，设置卡放在下方，采用垂直嵌套布局排版。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # 第一行：所有导航按钮
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        nav_layout.addWidget(self.prev_cluster_button)
        nav_layout.addWidget(self.next_cluster_button)
        nav_layout.addWidget(self.prev_slice_button)
        nav_layout.addWidget(self.next_slice_button)
        nav_layout.addWidget(self.reset_cur_slice_button)

        main_layout.addLayout(nav_layout)
        main_layout.addWidget(self.auto_recognize_card)
