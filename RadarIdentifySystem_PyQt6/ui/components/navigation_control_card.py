"""导航与主操作控制组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CheckBox,
    FluentIcon,
    HyperlinkButton,
    PrimaryPushButton,
    PushButton,
    ToolTipFilter,
    ToolTipPosition,
)
from app.custom_icon import CustomIcon


class NavigationControlCard(QWidget):
    """导航与主操作控制组件。

    Attributes:
        start_slicing_button: 触发切片工作流的按钮。
        start_recognition_button: 触发识别工作流的按钮。
        adaptive_slicing_checkbox: 是否启用自适应切片的复选框。
        drawer_options_button: 打开右侧参数抽屉的按钮。
        prev_cluster_button: 切换上一类别的文字按钮。
        next_cluster_button: 切换下一类别的文字按钮。
        prev_slice_button: 切换上一切片的文字按钮。
        next_slice_button: 切换下一切片的文字按钮。
        reset_cur_slice_button: 重置当前切片的按钮。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """创建主操作按钮和文字导航按钮。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> card = NavigationControlCard()
            >>> card.prev_slice_button.text()
            '上一片'
        """
        super().__init__(parent)
        self.setObjectName("navigationControlCard")
        self.setFixedHeight(140)

        # --- 主操作区域 ---
        self.start_slicing_button: PrimaryPushButton = PrimaryPushButton(
            FluentIcon.CUT,
            "开始切片",
            self,
        )
        self.start_recognition_button: PrimaryPushButton = PrimaryPushButton(
            FluentIcon.SEARCH,
            "开始识别",
            self,
        )
        self.adaptive_slicing_checkbox: CheckBox = CheckBox("启用自适应切片", self)
        # 借助 HyperlinkButton 的主题色透明按钮样式
        self.drawer_options_button: HyperlinkButton = HyperlinkButton(
            FluentIcon.MENU,
            "",
            "更多选项",
            self,
        )
        self.drawer_options_button.setToolTip("配置子Session的参数及模型")
        self.drawer_options_button.installEventFilter(
            ToolTipFilter(self.drawer_options_button, 1000, ToolTipPosition.TOP)
        )

        # --- 导航控制区域 ---
        self.prev_slice_button: PushButton = PushButton(
            CustomIcon.CHEVRONS_LEFT,
            "上一片",
            self,
        )
        self.prev_cluster_button: PushButton = PushButton(
            CustomIcon.CHEVRON_LEFT,
            "上一类",
            self,
        )
        self.reset_cur_slice_button: PrimaryPushButton = PrimaryPushButton(
            FluentIcon.SYNC,
            "重置当前切片",
            self,
        )
        self.next_cluster_button: PushButton = PushButton(
            CustomIcon.CHEVRON_RIGHT,
            "下一类",
            self,
        )
        self.next_slice_button: PushButton = PushButton(
            CustomIcon.CHEVRONS_RIGHT,
            "下一片",
            self,
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
        action_button_layout.addWidget(self.drawer_options_button, 0)
        # action_button_layout.addStretch(1)
        
        # 导航行：切片和类别的文字入口复用标题区图形按钮行为。
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        nav_layout.addWidget(self.prev_slice_button)
        nav_layout.addWidget(self.prev_cluster_button)
        nav_layout.addWidget(self.reset_cur_slice_button)
        nav_layout.addWidget(self.next_cluster_button)
        nav_layout.addWidget(self.next_slice_button)

        main_layout.addLayout(action_button_layout)
        main_layout.addLayout(nav_layout)
