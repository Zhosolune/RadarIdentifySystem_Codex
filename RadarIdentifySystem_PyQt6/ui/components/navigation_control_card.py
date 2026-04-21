"""导航与主操作控制组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import CardWidget, FluentIcon, SwitchSettingCard, IconWidget, PushButton, PrimaryPushButton, CheckBox
from app.app_config import appConfig
from app.custom_icon import CustomIcon

class NavigationControlCard(QWidget):
    """导航与主操作控制组件。

    功能描述：
        提供“开始切片”与“开始识别”按钮，以及自适应切片的复选框。
        提供“上一类”、“下一类”、“上一片”、“下一片”导航按钮及重置当前切片按钮。
        下方包含一个“点击下一片直接识别”开关设置卡，与全局配置联动。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        start_slicing_button (PushButton): 触发切片工作流的按钮。
        start_recognition_button (PrimaryPushButton): 触发识别的按钮。
        adaptive_slicing_checkbox (CheckBox): 是否启用自适应切片的复选框。
        prev_cluster_button (PushButton): 切换上一类的按钮。
        next_cluster_button (PushButton): 切换下一类的按钮。
        prev_slice_button (PushButton): 切换上一片的按钮。
        next_slice_button (PushButton): 切换下一片的按钮。
        reset_cur_slice_button (PushButton): 重置当前切片的按钮。
        auto_recognize_card (SwitchSettingCard): 切换下一片时是否自动识别的设置卡。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化导航控制组件。

        功能描述：
            创建布局并实例化内部的所有按钮、复选框和设置卡组件。

        参数说明：
            parent (QWidget | None): 父级控件。
        """
        super().__init__(parent)
        self.setObjectName("navigationControlCard")
        self.setFixedHeight(140)

        # --- 主操作区域 ---
        self.start_slicing_button = PrimaryPushButton(FluentIcon.CUT, "开始切片", self)
        self.start_recognition_button = PrimaryPushButton(FluentIcon.SEARCH, "开始识别", self)
        self.adaptive_slicing_checkbox = CheckBox("启用自适应切片", self)

        # --- 导航控制区域 ---
        # self.prev_cluster_button = PushButton(CustomIcon.CHEVRON_LEFT, "上一类", self)
        # self.next_cluster_button = PushButton(CustomIcon.CHEVRON_RIGHT, "下一类", self)
        self.reset_cur_slice_button  = PrimaryPushButton(CustomIcon.RESET, "重置当前切片", self)
        # self.prev_slice_button = PushButton(CustomIcon.CHEVRONS_LEFT, "上一片", self)
        # self.next_slice_button = PushButton(CustomIcon.CHEVRONS_RIGHT, "下一片", self)
        
        # --- 自动选项设置卡 ---
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
            采用垂直嵌套布局排版。
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(3)

        # 主操作行：切片和识别按钮
        action_button_layout = QHBoxLayout()
        action_button_layout.setSpacing(8)
        action_button_layout.addWidget(self.start_slicing_button, 1)
        action_button_layout.addWidget(self.start_recognition_button, 1)
        action_button_layout.addWidget(self.adaptive_slicing_checkbox, 2)
        action_button_layout.addStretch(1)
        
        # 导航行：重置当前切片按钮
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        nav_layout.addWidget(self.reset_cur_slice_button)
        nav_layout.addStretch(1)

        main_layout.addLayout(action_button_layout)
        main_layout.addLayout(nav_layout)
        main_layout.addWidget(self.auto_recognize_card)
