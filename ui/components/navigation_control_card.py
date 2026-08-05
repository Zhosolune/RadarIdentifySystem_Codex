"""导航与主操作控制组件。"""

from __future__ import annotations

from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    CheckBox,
    FluentIcon,
    HyperlinkButton,
    PrimaryPushButton,
    PushButton,
    TogglePushButton,
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
        merge_menu_button: 激活或退出合并横向浏览模式的按钮。
        reset_cur_slice_button: 重置当前切片的按钮。
        slice_navigation_layout: 第一行切片与合并菜单按钮布局。
        cluster_navigation_layout: 第二行类别与重置按钮布局。
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
        # 为主操作区和固定两行导航区保留纵向伸缩空间。
        self.setMinimumHeight(72)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        self._action_layout_mode = ""

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
        self.merge_menu_button: TogglePushButton = TogglePushButton(
            FluentIcon.LAYOUT,
            "合并菜单",
            self,
        )

        # 组件库“16px 图标 + 4 个中文字符”按钮的建议宽度当前为 106px。
        # 复用真实四字按钮的 sizeHint，确保字体或 DPI 变化时仍按组件库规则计算。
        navigation_button_width = self.start_slicing_button.sizeHint().width()
        for button in (
            self.prev_slice_button,
            self.next_slice_button,
            self.prev_cluster_button,
            self.next_cluster_button,
        ):
            button.setFixedWidth(navigation_button_width)

        self._init_layout()

    def _init_layout(self) -> None:
        """初始化卡片内部布局。

        功能描述：
            采用垂直嵌套布局排版。
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # 主操作行：切片和识别按钮
        action_container = QWidget(self)
        self._action_button_layout = QVBoxLayout(action_container)
        self._action_button_layout.setContentsMargins(0, 0, 0, 0)
        self._action_button_layout.setSpacing(8)

        self._action_primary_layout = QHBoxLayout()
        self._action_primary_layout.setContentsMargins(0, 0, 0, 0)
        self._action_primary_layout.setSpacing(8)
        self._action_primary_layout.addWidget(self.start_slicing_button)
        self._action_primary_layout.addWidget(self.start_recognition_button)
        self._action_primary_layout.addStretch(1)
        self._action_primary_layout.addWidget(self.drawer_options_button)

        self._action_checkbox_layout = QHBoxLayout()
        self._action_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self._action_checkbox_layout.setSpacing(8)

        self._action_button_layout.addLayout(self._action_primary_layout)
        self._action_button_layout.addLayout(self._action_checkbox_layout)
        self._update_action_layout_mode()
        
        # 导航区固定为两行，避免按钮随宽度重排后改变业务分组。
        nav_container = QWidget(self)
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        self.slice_navigation_layout = QHBoxLayout()
        self.slice_navigation_layout.setContentsMargins(0, 0, 0, 0)
        self.slice_navigation_layout.setSpacing(8)
        self.slice_navigation_layout.addWidget(self.prev_slice_button)
        self.slice_navigation_layout.addWidget(self.next_slice_button)
        self.slice_navigation_layout.addWidget(self.merge_menu_button)
        self.slice_navigation_layout.addStretch(1)

        self.cluster_navigation_layout = QHBoxLayout()
        self.cluster_navigation_layout.setContentsMargins(0, 0, 0, 0)
        self.cluster_navigation_layout.setSpacing(8)
        self.cluster_navigation_layout.addWidget(self.prev_cluster_button)
        self.cluster_navigation_layout.addWidget(self.next_cluster_button)
        self.cluster_navigation_layout.addWidget(self.reset_cur_slice_button)
        self.cluster_navigation_layout.addStretch(1)

        nav_layout.addLayout(self.slice_navigation_layout)
        nav_layout.addLayout(self.cluster_navigation_layout)

        main_layout.addWidget(action_container)
        main_layout.addWidget(nav_container)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """根据当前宽度刷新主操作区布局。"""
        super().resizeEvent(event)
        if not hasattr(self, "_action_button_layout"):
            return
        self._update_action_layout_mode()

    def _update_action_layout_mode(self) -> None:
        """根据可用宽度切换主操作区单行或折行布局。"""
        layout = self._action_button_layout
        margin = layout.contentsMargins()
        available_width = max(0, self.width() - margin.left() - margin.right())
        spacing = self._action_primary_layout.spacing()
        full_row_width = (
            self.start_slicing_button.sizeHint().width()
            + self.start_recognition_button.sizeHint().width()
            + self.adaptive_slicing_checkbox.sizeHint().width()
            + self.drawer_options_button.sizeHint().width()
            + spacing * 3
        )
        target_mode = "compact" if 0 < available_width < full_row_width else "wide"
        if target_mode == self._action_layout_mode:
            return

        self._action_layout_mode = target_mode
        self._remove_widget_from_layout(
            self._action_primary_layout,
            self.adaptive_slicing_checkbox,
        )
        self._clear_layout(self._action_checkbox_layout)

        if target_mode == "compact":
            # 在宽度不足时将复选框单独放到下一行。
            self._action_checkbox_layout.addWidget(self.adaptive_slicing_checkbox)
            self._action_checkbox_layout.addStretch(1)
            return

        # 宽度充足时将复选框保留在首行。
        self._action_primary_layout.insertWidget(2, self.adaptive_slicing_checkbox)

    def _remove_widget_from_layout(self, layout: QHBoxLayout, widget: QWidget) -> None:
        """从指定布局中移除控件。"""
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is not None and item.widget() is widget:
                layout.takeAt(index)
                return

    def _clear_layout(self, layout: QHBoxLayout) -> None:
        """清空布局中的条目。"""
        while layout.count():
            layout.takeAt(0)
