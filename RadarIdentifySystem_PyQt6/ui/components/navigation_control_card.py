"""导航与主操作控制组件。"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    CheckBox,
    FluentIcon,
    HyperlinkButton,
    PrimaryPushButton,
    PushButton,
    ToolTipFilter,
    ToolTipPosition,
)
from qfluentwidgets.components.layout import FlowLayout
from app.custom_icon import CustomIcon


class _NavigationFlowLayout(FlowLayout):
    """在单行场景下让末尾按钮贴右的流式布局。"""

    def _doLayout(self, rect: QRect, move: bool) -> int:
        """在单行可容纳时吸附末尾按钮，否则退回默认换行布局。"""
        visible_items = [
            (index, item)
            for index, item in enumerate(self._items)
            if not (item.widget() and not item.widget().isVisible() and self.isTight)
        ]
        if not visible_items:
            margin = self.contentsMargins()
            return margin.top() + margin.bottom()

        margin = self.contentsMargins()
        available_width = rect.width() - margin.left() - margin.right()
        space_x = self.horizontalSpacing()
        total_width = sum(item.sizeHint().width() for _, item in visible_items)
        total_width += max(0, len(visible_items) - 1) * space_x

        # 单行可容纳时让最后一个按钮贴靠右侧。
        if total_width > available_width:
            return super()._doLayout(rect, move)

        x = rect.x() + margin.left()
        y = rect.y() + margin.top()
        row_height = 0
        ani_restart = False
        last_visible_index = len(visible_items) - 1

        for visible_index, (item_index, item) in enumerate(visible_items):
            target_x = x
            if visible_index == last_visible_index:
                # 吸附重置按钮到单行最右侧。
                target_x = rect.x() + rect.width() - margin.right() - item.sizeHint().width()

            if move:
                target = QRect(QPoint(target_x, y), item.sizeHint())
                if not self.needAni:
                    item.setGeometry(target)
                elif target != self._anis[item_index].endValue():
                    self._anis[item_index].stop()
                    self._anis[item_index].setEndValue(target)
                    ani_restart = True

            if visible_index != last_visible_index:
                x += item.sizeHint().width() + space_x
            row_height = max(row_height, item.sizeHint().height())

        if self.needAni and ani_restart:
            self._aniGroup.stop()
            self._aniGroup.start()

        return y + row_height + margin.bottom() - rect.y()


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
        # 允许导航区在窄宽度下自动增高换行。
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
        
        # 导航行：单行时让重置按钮贴右，窄宽度下自动换行。
        nav_container = QWidget(self)
        nav_layout = _NavigationFlowLayout(nav_container, needAni=False, isTight=True)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setHorizontalSpacing(8)
        nav_layout.setVerticalSpacing(8)
        nav_layout.addWidget(self.prev_slice_button)
        nav_layout.addWidget(self.prev_cluster_button)
        nav_layout.addWidget(self.next_cluster_button)
        nav_layout.addWidget(self.next_slice_button)
        nav_layout.addWidget(self.reset_cur_slice_button)

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
