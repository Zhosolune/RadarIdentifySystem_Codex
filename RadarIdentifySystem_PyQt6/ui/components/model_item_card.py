# -*- coding: utf-8 -*-
"""模型项卡片组件。"""

from pathlib import Path
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy, QWidget
from PyQt6.QtCore import Qt, pyqtSignal

from qfluentwidgets import (
    CardWidget,
    CommandBar,
    Action,
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    RadioButton,
)

class ModelItemCard(CardWidget):
    """单个模型项卡片。
    
    功能描述：
        用于在模型管理列表中展示单个模型文件，提供模型名称、路径截断显示以及重命名和删除操作。
        
    Attributes:
        model_type (str): 模型类型，如 "PA" 或 "DTOA"。
        file_path (Path): 模型文件的完整路径。
    """
    deleteRequested = pyqtSignal(str, str)
    renameRequested = pyqtSignal(str, str)
    enabledToggled = pyqtSignal(str, str, bool)
    
    def __init__(
        self,
        model_type: str,
        file_path: str,
        display_name: str = None,
        is_enabled: bool = False,
        parent=None,
    ):
        """初始化模型项卡片。

        Args:
            model_type (str): 模型类型标识，通常为 ``PA`` 或 ``DTOA``。
            file_path (str): 模型文件完整路径。
            display_name (str | None): 模型显示名称，未传入时使用文件名。
            is_enabled (bool): 当前模型是否已启用，默认值为 False。
            parent (QWidget | None): 父组件。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前构造函数不主动抛出异常。
        """
        super().__init__(parent)
        self.model_type = model_type
        self.file_path = Path(file_path)
        self.display_name = display_name or self.file_path.name
        self.is_enabled = is_enabled
        # 设置卡片对象名，供 QSS 统一管理样式
        self.setObjectName("modelItemCard")
        # 固定纵向策略，避免在列表中被拉伸均分高度
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        
        self.setFixedHeight(70)
        
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(20, 0, 20, 0)
        self.hBoxLayout.setSpacing(10)
        
        # 徽标
        self.badgeLabel = QLabel(model_type)
        # 设置徽标对象名，供 QSS 统一管理样式
        self.badgeLabel.setObjectName("modelTypeBadge")
        # 写入模型类型属性，供 QSS 按类型差异化着色
        self.badgeLabel.setProperty("modelType", model_type)
        self.badgeLabel.setFixedSize(40, 40)
        self.badgeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 启用单选按钮
        self.enableBtn = RadioButton("", self)
        self.enableBtn.setObjectName("modelEnableButton")
        self.enableBtn.setFixedWidth(16)
        self.enableBtn.setChecked(self.is_enabled)
        
        # 文本
        self.textLayout = QVBoxLayout()
        self.textLayout.setContentsMargins(0, 14, 0, 14)
        self.textLayout.setSpacing(2)
        
        self.nameLabel = BodyLabel(self.display_name)
        # 设置名称对象名，供 QSS 统一管理样式
        self.nameLabel.setObjectName("modelNameLabel")
        
        # 截断路径显示
        parent_path = str(self.file_path.parent)
        display_path = parent_path if len(parent_path) < 60 else "..." + parent_path[-57:]
        self.pathLabel = CaptionLabel(f"{display_path}/{self.file_path.name}")
        # 设置路径对象名，供 QSS 统一管理样式
        self.pathLabel.setObjectName("modelPathLabel")
        
        self.textLayout.addWidget(self.nameLabel)
        self.textLayout.addWidget(self.pathLabel)
        
        # 命令栏
        self.commandBar = CommandBar(self)
        self.commandBar.setObjectName("modelCommandBar")
        self.commandBar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        
        self.renameAction = Action(FluentIcon.EDIT, "重命名")
        self.deleteAction = Action(FluentIcon.DELETE, "删除")
        self.deleteAction.setProperty("danger", True)

        # 创建命令栏占位容器，确保隐藏命令栏时保留布局位置
        self.commandBarContainer = QWidget(self)
        self.commandBarContainer.setObjectName("modelCommandBarContainer")
        self.commandBarContainer.setFixedWidth(100)
        self.commandBarLayout = QHBoxLayout(self.commandBarContainer)
        self.commandBarLayout.setContentsMargins(0, 0, 0, 0)
        self.commandBarLayout.setSpacing(0)
        self.commandBarLayout.addWidget(self.commandBar)
        # 默认隐藏命令栏，悬浮时显示
        self.commandBar.setVisible(False)
        
        self.renameAction.triggered.connect(self._onRename)
        self.deleteAction.triggered.connect(self._onDelete)
        self.enableBtn.toggled.connect(self._onEnableToggled)
        
        self.commandBar.addAction(self.renameAction)
        self.commandBar.addAction(self.deleteAction)
        
        # 组装
        self.hBoxLayout.addWidget(self.enableBtn)
        self.hBoxLayout.addWidget(self.badgeLabel)
        self.hBoxLayout.addLayout(self.textLayout)
        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.commandBarContainer)
        # 应用启用态样式
        self._apply_enabled_style()
        
    def _onRename(self):
        """触发重命名信号。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前方法不主动抛出异常。
        """
        # 发射重命名请求信号，由控制器统一弹出对话框
        self.renameRequested.emit(str(self.file_path), self.display_name)
        
    def _onDelete(self):
        """触发删除信号。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前方法不主动抛出异常。
        """
        # 发射删除请求信号，由控制器统一弹出确认框
        self.deleteRequested.emit(str(self.file_path), self.display_name)

    def _onEnableToggled(self, checked: bool) -> None:
        """处理启用开关切换。

        Args:
            checked (bool): 目标启用状态。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 同步本地状态并更新样式
        self.is_enabled = checked
        self._apply_enabled_style()
        # 发射启用状态变更请求，由控制器统一执行业务约束
        self.enabledToggled.emit(str(self.file_path), self.model_type, checked)

    def set_enabled(self, enabled: bool) -> None:
        """设置启用状态并刷新显示。

        Args:
            enabled (bool): 目标启用状态。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 避免重复发射切换信号
        self.enableBtn.blockSignals(True)
        self.enableBtn.setChecked(enabled)
        self.enableBtn.blockSignals(False)
        self.is_enabled = enabled
        self._apply_enabled_style()

    def _apply_enabled_style(self) -> None:
        """应用启用状态样式。"""
        # 写入启用属性，供 QSS 按状态切换卡片样式
        self.setProperty("enabledModel", self.is_enabled)
        # 触发样式重绘，确保状态变化立即生效
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def enterEvent(self, event) -> None:
        """处理鼠标进入事件。"""
        # 悬浮时显示命令栏
        self.commandBar.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """处理鼠标离开事件。"""
        # 离开时隐藏命令栏
        self.commandBar.setVisible(False)
        super().leaveEvent(event)
