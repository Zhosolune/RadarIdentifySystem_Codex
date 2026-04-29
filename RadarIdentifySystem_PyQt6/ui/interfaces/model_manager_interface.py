# -*- coding: utf-8 -*-
"""模型管理界面。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget

from qfluentwidgets import (
    SettingCardGroup,
    PushSettingCard,
    FluentIcon,
    SegmentedWidget,
)

from app.style_sheet import StyleSheet
from ui.components.model_list_page import ModelListPage
from ui.controllers.model_manager_controller import ModelManagerController


class ModelManagerInterface(QWidget):
    """模型管理界面。

    负责模型管理页面的视图布局，业务逻辑由控制器承接。

    Attributes:
        MAX_CONTENT_WIDTH (int): 内容区域的最大宽度限制。
    """

    MAX_CONTENT_WIDTH = 860

    def __init__(self, parent=None):
        """初始化模型管理界面。

        Args:
            parent (QWidget | None): 父组件。
        """
        super().__init__(parent)

        # 初始化内容容器
        self.content_widget = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_widget)

        # 创建分组
        self.manage_group = SettingCardGroup("模型管理", self.content_widget)

        # 创建导入模型设置卡
        self.import_model_card = PushSettingCard(
            "选择模型",
            FluentIcon.DOWNLOAD,
            "导入模型",
            "导入 PA 或 DTOA 模型到用户模型目录",
            self.manage_group,
        )

        # 创建用户模型目录设置卡
        self.user_model_root_card = PushSettingCard(
            "选择目录",
            FluentIcon.FOLDER,
            "用户模型目录",
            "目录占位",    # 初始化结束后会自动更新为实际路径，若不占位卡片高度会异常
            self.manage_group,
        )

        # 创建模型类型切换
        self.segmentedWidget = SegmentedWidget(self.content_widget)
        # 创建堆叠页面容器
        self.stackedWidget = QStackedWidget(self.content_widget)
        # 创建 PA 列表页
        self.pa_model_page = ModelListPage("PA", self.stackedWidget)
        # 创建 DTOA 列表页
        self.dtoa_model_page = ModelListPage("DTOA", self.stackedWidget)
        # 缓存模型页面映射
        self.model_pages = {
            "PA": self.pa_model_page,
            "DTOA": self.dtoa_model_page,
        }

        # 装配界面模块
        self._initWidget()

        # 初始化控制器
        self._controller = ModelManagerController(self)

    def _initWidget(self) -> None:
        """初始化界面样式属性。"""
        # 初始化根布局
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 28, 0, 20)
        self.root_layout.setSpacing(0)
        # 添加内容容器
        self.root_layout.addWidget(self.content_widget)

        # 设置对象名
        self.setObjectName("modelManagerInterface")
        self.content_widget.setObjectName("modelContentWidget")
        self.stackedWidget.setObjectName("modelStackedWidget")

        # 初始化样式
        StyleSheet.MODEL_MANAGER_INTERFACE.apply(self)

        # 初始化布局
        self._initLayout()
        self._connectSignalToSlot()

    def _initLayout(self):
        """初始化界面布局。"""

        # 设置内容边距
        self.content_layout.setContentsMargins(36, 10, 36, 0)
        self.content_layout.setSpacing(16)

        # 添加设置卡
        self.manage_group.addSettingCard(self.import_model_card)
        self.manage_group.addSettingCard(self.user_model_root_card)

        # 添加模型管理分组
        self.content_layout.addWidget(self.manage_group)

        # 注册分段页面项
        self._add_sub_interface(self.pa_model_page, "PA", "PA 模型")
        self._add_sub_interface(self.dtoa_model_page, "DTOA", "DTOA 模型")
        # 初始化默认页面
        self.stackedWidget.setCurrentWidget(self.pa_model_page)
        self.segmentedWidget.setCurrentItem("PA")

        # 创建分段切换布局
        self.segment_layout = QHBoxLayout()
        self.segment_layout.setContentsMargins(0, 0, 0, 0)
        self.segment_layout.addWidget(self.segmentedWidget)
        self.segment_layout.addStretch(1)
        self.content_layout.addLayout(self.segment_layout)

        # 添加堆叠页面容器
        self.content_layout.addWidget(self.stackedWidget, 1)

    def _connectSignalToSlot(self) -> None:
        """连接界面内部信号。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 绑定分段切换事件
        self.segmentedWidget.currentItemChanged.connect(self._on_segmented_item_changed)
        # 绑定堆叠页切换事件
        self.stackedWidget.currentChanged.connect(self._on_stacked_widget_changed)

    def _add_sub_interface(
        self,
        widget: ModelListPage,
        route_key: str,
        text: str,
    ) -> None:
        """注册模型列表子页面。

        Args:
            widget (ModelListPage): 待注册的列表页面。
            route_key (str): 分段路由键。
            text (str): 分段展示文本。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 路由键为空时抛出异常。
        """
        if not route_key:
            raise ValueError("route_key 不能为空")

        # 绑定页面对象名
        widget.setObjectName(route_key)
        # 注册堆叠页面
        self.stackedWidget.addWidget(widget)
        # 注册分段项点击行为
        self.segmentedWidget.addItem(
            routeKey=route_key,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget),
        )

    def _on_segmented_item_changed(self, item_key: str) -> None:
        """处理分段切换事件。

        Args:
            item_key (str): 当前选中的分段路由键。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        current_page = self.model_pages.get(item_key)
        if current_page is None:
            return
        if self.stackedWidget.currentWidget() is current_page:
            return

        # 同步切换堆叠页面
        self.stackedWidget.setCurrentWidget(current_page)

    def _on_stacked_widget_changed(self, index: int) -> None:
        """处理堆叠页面切换事件。

        Args:
            index (int): 当前页面索引。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        current_page = self.stackedWidget.widget(index)
        if current_page is None:
            return

        route_key = current_page.objectName()
        if self.segmentedWidget.currentRouteKey() == route_key:
            return

        # 同步分段选中状态
        self.segmentedWidget.setCurrentItem(route_key)

    def get_model_page(self, model_type: str) -> ModelListPage:
        """获取指定模型类型对应的列表页面。

        Args:
            model_type (str): 模型类型。

        Returns:
            ModelListPage: 模型列表页面组件。

        Raises:
            KeyError: 模型类型不存在时抛出异常。
        """
        return self.model_pages[model_type]

    def current_model_type(self) -> str:
        """获取当前激活的模型类型。

        Args:
            无。

        Returns:
            str: 当前激活的模型类型。

        Raises:
            无。
        """
        current_route = self.segmentedWidget.currentRouteKey()
        return current_route if current_route else "PA"

    def set_user_model_root_path(self, path: str) -> None:
        """更新用户模型目录卡片内容。

        Args:
            path (str): 用户模型根目录路径。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 同步展示用户模型根目录
        self.user_model_root_card.setContent(path)

    def resizeEvent(self, event):
        """处理界面大小变化事件。

        Args:
            event (QResizeEvent): 尺寸变更事件对象。
        """
        super().resizeEvent(event)
        # 计算水平边距
        viewport_w = self.width()
        h_margin = max(36, (viewport_w - self.MAX_CONTENT_WIDTH) // 2)
        # 更新内容边距
        self.content_layout.setContentsMargins(h_margin, 10, h_margin, 0)
