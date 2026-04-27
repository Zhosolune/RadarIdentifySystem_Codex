# -*- coding: utf-8 -*-
"""模型管理界面。"""

import os
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from qfluentwidgets import (
    ScrollArea,
    ExpandLayout,
    SettingCardGroup,
    FluentIcon,
    SegmentedWidget,
    CardWidget,
    CommandBar,
    Action,
    TitleLabel,
    CaptionLabel,
    BodyLabel,
    PrimaryPushButton,
    qconfig,
    InfoBar,
    InfoBarPosition,
    IconWidget,
    Theme,
    FolderListSettingCard,
)

from app.app_config import appConfig
from app.style_sheet import StyleSheet
from ui.components.model_item_card import ModelItemCard

LOGGER = logging.getLogger(__name__)


class ModelManagerInterface(ScrollArea):
    """模型管理界面。
    
    负责 PA 和 DTOA 模型的导入、重命名、删除及多目录配置。

    Attributes:
        MAX_CONTENT_WIDTH (int): 内容区域的最大宽度限制。
    """

    MAX_CONTENT_WIDTH = 860

    def __init__(self, parent=None):
        """初始化模型管理界面。

        Args:
            parent (QWidget, optional): 父组件。默认为 None。
        """
        super().__init__(parent)
        
        # 初始化滚动容器
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        # 装配各个UI模块
        self._initHeader()
        self._initFolderCards()
        self._initSegmentedWidget()
        self._initModelList()

        # 配置容器属性并加载数据
        self._initWidget()
        self._loadModels()

    def _initHeader(self):
        """初始化头部区域。

        创建页面标题、描述文本及顶部的导入模型按钮。
        """
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setContentsMargins(0, 0, 0, 20)

        # 标题区域
        titleLayout = QHBoxLayout()
        iconWidget = IconWidget(FluentIcon.SETTING)
        iconWidget.setFixedSize(24, 24)
        titleLabel = TitleLabel("模型管理")

        titleVLayout = QVBoxLayout()
        titleVLayout.setSpacing(4)

        topHLayout = QHBoxLayout()
        topHLayout.addWidget(iconWidget)
        topHLayout.addWidget(titleLabel)
        topHLayout.addStretch(1)

        descLabel = CaptionLabel("导入和管理 PA / DTOA 模型文件")
        descLabel.setStyleSheet("color: gray;")

        titleVLayout.addLayout(topHLayout)
        titleVLayout.addWidget(descLabel)

        # 导入按钮
        self.importBtn = PrimaryPushButton(FluentIcon.DOWNLOAD, "导入模型")
        self.importBtn.clicked.connect(self._onImportModel)

        self.headerLayout.addLayout(titleVLayout)
        self.headerLayout.addStretch(1)
        self.headerLayout.addWidget(self.importBtn, 0, Qt.AlignmentFlag.AlignTop)

        self.vBoxLayout.addLayout(self.headerLayout)

    def _initFolderCards(self):
        """初始化模型目录配置卡片。

        实例化 PA 和 DTOA 的 FolderListSettingCard，并绑定配置变更信号。
        """
        self.foldersLayout = QVBoxLayout()
        self.foldersLayout.setSpacing(16)

        # FolderListSettingCard
        self.paFolderCard = FolderListSettingCard(
            appConfig.modelPaDirs,
            "PA 模型目录",
            directory=str(Path.home()),
            parent=self,
        )
        self.dtoaFolderCard = FolderListSettingCard(
            appConfig.modelDtoaDirs,
            "DTOA 模型目录",
            directory=str(Path.home()),
            parent=self,
        )

        # Listen to config changes
        appConfig.modelPaDirs.valueChanged.connect(self._loadModels)
        appConfig.modelDtoaDirs.valueChanged.connect(self._loadModels)

        self.foldersLayout.addWidget(self.paFolderCard)
        self.foldersLayout.addWidget(self.dtoaFolderCard)

        self.vBoxLayout.addLayout(self.foldersLayout)
        self.vBoxLayout.addSpacing(24)

    def _initSegmentedWidget(self):
        """初始化分段切换组件。

        创建 PA 和 DTOA 的切换标签，以及操作栏的刷新按钮。
        """
        self.segmentLayout = QHBoxLayout()

        self.segmentedWidget = SegmentedWidget(self)
        self.segmentedWidget.addItem("PA", "PA 模型")
        self.segmentedWidget.addItem("DTOA", "DTOA 模型")
        self.segmentedWidget.setCurrentItem("PA")
        self.segmentedWidget.currentItemChanged.connect(self._onSegmentChanged)

        self.refreshBtn = Action(FluentIcon.UPDATE, "刷新")
        self.refreshBtn.triggered.connect(self._loadModels)

        cmdBar = CommandBar()
        cmdBar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        cmdBar.addAction(self.refreshBtn)

        self.segmentLayout.addWidget(self.segmentedWidget)
        self.segmentLayout.addStretch(1)
        self.segmentLayout.addWidget(cmdBar)

        self.vBoxLayout.addLayout(self.segmentLayout)
        self.vBoxLayout.addSpacing(16)

    def _initModelList(self):
        """初始化模型列表区域。

        创建列表头及列表项的垂直布局容器。
        """
        # 表头
        headerLayout = QHBoxLayout()
        headerLayout.setContentsMargins(16, 0, 16, 8)

        nameHeader = CaptionLabel("模型名称")
        nameHeader.setStyleSheet("color: gray;")

        typeHeader = CaptionLabel("类型")
        typeHeader.setStyleSheet("color: gray;")

        actionHeader = CaptionLabel("操作")
        actionHeader.setStyleSheet("color: gray;")

        headerLayout.addWidget(nameHeader)
        headerLayout.addStretch(1)
        headerLayout.addWidget(typeHeader)
        headerLayout.addSpacing(32)
        headerLayout.addWidget(actionHeader)
        headerLayout.addSpacing(16)

        self.vBoxLayout.addLayout(headerLayout)

        # 列表容器
        self.listWidget = QWidget()
        self.listLayout = QVBoxLayout(self.listWidget)
        self.listLayout.setContentsMargins(0, 0, 0, 0)
        self.listLayout.setSpacing(8)

        self.vBoxLayout.addWidget(self.listWidget)
        self.vBoxLayout.addStretch(1)

    def _initWidget(self):
        """初始化界面基础属性。

        设置滚动条策略、边距、背景颜色及样式表。
        """
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 28, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setObjectName("modelManagerInterface")
        self.scrollWidget.setObjectName("settingScrollWidget")

        # 应用样式
        StyleSheet.SETTING_INTERFACE.apply(self)

    def _onSegmentChanged(self, item_key: str):
        """处理分段组件切换事件。

        根据选中的分段标签显示对应的目录配置卡片，并重新加载模型列表。

        Args:
            item_key (str): 切换的目标项路由标识（如 "PA" 或 "DTOA"）。
        """
        # 切换显示的文件夹卡片
        if item_key == "PA":
            self.paFolderCard.show()
            self.dtoaFolderCard.hide()
        else:
            self.paFolderCard.hide()
            self.dtoaFolderCard.show()

        self._loadModels()

    def _loadModels(self):
        """加载并渲染模型列表。

        清空当前列表容器，扫描目标目录下的模型文件，并生成卡片项添加到布局中。
        """
        # 清空当前列表
        while self.listLayout.count():
            item = self.listLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_route = self.segmentedWidget.currentRouteKey()
        if not current_route:
            current_type = "PA"
        else:
            current_type = current_route

        # 初始卡片显示状态
        if current_type == "PA":
            self.paFolderCard.show()
            self.dtoaFolderCard.hide()
        else:
            self.paFolderCard.hide()
            self.dtoaFolderCard.show()

        dir_paths = (
            qconfig.get(appConfig.modelPaDirs)
            if current_type == "PA"
            else qconfig.get(appConfig.modelDtoaDirs)
        )

        # 确保目录存在
        for dir_path in dir_paths:
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as e:
                    LOGGER.warning(f"无法创建模型目录 {dir_path}: {e}")

        try:
            files_found = False
            for dir_path in dir_paths:
                if not os.path.exists(dir_path):
                    continue

                files = [
                    f
                    for f in os.listdir(dir_path)
                    if f.endswith((".onnx", ".pkl", ".pt", ".pth"))
                ]

                for file_name in files:
                    files_found = True
                    file_path = os.path.join(dir_path, file_name)
                    card = ModelItemCard(current_type, file_path, self)
                    card.deleteClicked.connect(self._onDeleteModel)
                    card.renameClicked.connect(self._onRenameModel)
                    self.listLayout.addWidget(card)

            if not files_found:
                emptyLabel = BodyLabel(
                    "配置的模型目录为空，请先导入模型文件或添加模型目录。"
                )
                emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
                emptyLabel.setStyleSheet("color: gray; margin-top: 40px;")
                self.listLayout.addWidget(emptyLabel)

        except Exception as e:
            LOGGER.error(f"加载模型列表失败: {e}")

    def _onImportModel(self):
        """处理导入模型事件。

        打开文件选择对话框，将选中的模型文件复制到当前配置的首个模型目录中。
        """
        current_route = self.segmentedWidget.currentRouteKey()
        if not current_route:
            current_type = "PA"
        else:
            current_type = current_route

        dir_paths = (
            qconfig.get(appConfig.modelPaDirs)
            if current_type == "PA"
            else qconfig.get(appConfig.modelDtoaDirs)
        )

        if not dir_paths:
            InfoBar.warning(
                title="导入失败",
                content="请先在下方添加模型目录",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        dir_path = dir_paths[0]  # 默认导入到第一个目录

        files, _ = QFileDialog.getOpenFileNames(
            self,
            f"选择要导入的 {current_type} 模型文件",
            "",
            "Model Files (*.onnx *.pkl *.pt *.pth);;All Files (*)",
        )

        if files:
            import shutil

            success_count = 0
            for file in files:
                try:
                    file_name = os.path.basename(file)
                    dest_path = os.path.join(dir_path, file_name)
                    shutil.copy2(file, dest_path)
                    success_count += 1
                except Exception as e:
                    LOGGER.error(f"导入模型失败 {file}: {e}")

            if success_count > 0:
                InfoBar.success(
                    title="导入成功",
                    content=f"成功导入 {success_count} 个模型至 {dir_path}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self,
                )
                self._loadModels()

    def _onDeleteModel(self, file_path: str):
        """处理删除模型事件。

        从磁盘中删除指定的模型文件，并刷新列表展示。

        Args:
            file_path (str): 待删除模型文件的绝对路径。
        """
        try:
            os.remove(file_path)
            InfoBar.success(
                title="删除成功",
                content=f"已删除模型: {os.path.basename(file_path)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )
            self._loadModels()
        except Exception as e:
            LOGGER.error(f"删除模型失败: {e}")
            InfoBar.error(
                title="删除失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def _onRenameModel(self, file_path: str, new_name: str):
        """处理重命名模型事件。

        修改指定模型文件在磁盘上的名称，并刷新列表展示。

        Args:
            file_path (str): 原模型文件的绝对路径。
            new_name (str): 新的模型名称。

        Raises:
            FileExistsError: 当目标名称文件已存在时抛出。
        """
        try:
            dir_path = os.path.dirname(file_path)
            new_path = os.path.join(dir_path, new_name)
            if os.path.exists(new_path):
                raise FileExistsError("同名文件已存在")

            os.rename(file_path, new_path)
            InfoBar.success(
                title="重命名成功",
                content=f"模型已重命名为: {new_name}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )
            self._loadModels()
        except Exception as e:
            LOGGER.error(f"重命名模型失败: {e}")
            InfoBar.error(
                title="重命名失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def resizeEvent(self, event):
        """处理界面大小调整事件。

        动态计算并设置水平边距，使内容区域保持水平居中。

        Args:
            event (QResizeEvent): 大小调整事件对象。
        """
        super().resizeEvent(event)
        viewport_w = self.viewport().width()
        h_margin = max(36, (viewport_w - self.MAX_CONTENT_WIDTH) // 2)
        self.vBoxLayout.setContentsMargins(h_margin, 10, h_margin, 0)
