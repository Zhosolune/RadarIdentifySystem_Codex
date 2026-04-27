# -*- coding: utf-8 -*-
"""模型管理界面。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame

from qfluentwidgets import (
    SettingCardGroup,
    PrimaryPushSettingCard,
    FluentIcon,
    SegmentedWidget,
    TitleLabel,
    CaptionLabel,
)

from app.style_sheet import StyleSheet
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
        self.action_group = SettingCardGroup("导入模型", self.content_widget)

        # 创建导入模型设置卡
        self.import_model_card = PrimaryPushSettingCard(
            "导入",
            FluentIcon.DOWNLOAD,
            "导入模型",
            "导入 PA 或 DTOA 模型到系统目录",
            self.action_group,
        )

        # 创建模型类型切换
        self.segmentedWidget = SegmentedWidget(self.content_widget)
        self.segmentedWidget.addItem("PA", "PA 模型")
        self.segmentedWidget.addItem("DTOA", "DTOA 模型")
        self.segmentedWidget.setCurrentItem("PA")

        # 创建列表滚动容器（仅列表区域滚动）
        self.list_scroll_area = QScrollArea(self.content_widget)
        self.list_scroll_area.setWidgetResizable(True)
        self.list_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 创建列表内容容器
        self.listWidget = QWidget()
        self.listLayout = QVBoxLayout(self.listWidget)

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
        self.list_scroll_area.setObjectName("modelListScrollArea")
        self.list_scroll_area.viewport().setObjectName("modelListViewport")
        self.listWidget.setObjectName("modelListWidget")

        # 初始化样式
        StyleSheet.MODEL_MANAGER_INTERFACE.apply(self)

        # 初始化布局
        self._initLayout()
        self._connectSignalToSlot()

    def _initLayout(self):
        """初始化界面布局。"""
        # 添加导入卡片
        self.action_group.addSettingCard(self.import_model_card)

        # 设置内容边距
        self.content_layout.setContentsMargins(36, 10, 36, 0)
        self.content_layout.setSpacing(16)

        # 添加操作分组
        self.content_layout.addWidget(self.action_group)

        # 创建分段切换布局
        self.segment_layout = QHBoxLayout()
        self.segment_layout.setContentsMargins(0, 0, 0, 0)
        self.segment_layout.addWidget(self.segmentedWidget)
        self.segment_layout.addStretch(1)
        self.content_layout.addLayout(self.segment_layout)

        # 配置列表容器
        self.listLayout.setContentsMargins(0, 0, 0, 0)
        self.listLayout.setSpacing(6)
        self.list_scroll_area.setWidget(self.listWidget)

        # 组装列表区域布局
        list_area_layout = QVBoxLayout()
        list_area_layout.setContentsMargins(0, 0, 0, 0)
        list_area_layout.setSpacing(0)
        list_area_layout.addWidget(self.list_scroll_area, 1)
        self.content_layout.addLayout(list_area_layout, 1)

    def _connectSignalToSlot(self) -> None:
        """连接界面内部信号。

        说明：
            当前界面交互信号统一在控制器中绑定，
            该方法保留用于与 `SettingInterface` 结构保持一致。
        """
        # 预留信号连接入口
        return
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
