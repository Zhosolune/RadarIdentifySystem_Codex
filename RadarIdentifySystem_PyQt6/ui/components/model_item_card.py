# -*- coding: utf-8 -*-
"""模型项卡片组件。"""

from pathlib import Path
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal

from qfluentwidgets import (
    CardWidget,
    CommandBar,
    Action,
    BodyLabel,
    CaptionLabel,
    FluentIcon,
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
    
    def __init__(self, model_type: str, file_path: str, display_name: str = None, parent=None):
        """初始化模型项卡片。

        Args:
            model_type (str): 模型类型标识，通常为 ``PA`` 或 ``DTOA``。
            file_path (str): 模型文件完整路径。
            display_name (str | None): 模型显示名称，未传入时使用文件名。
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
        # 设置卡片对象名，供 QSS 统一管理样式
        self.setObjectName("modelItemCard")
        # 固定纵向策略，避免在列表中被拉伸均分高度
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        
        self.setFixedHeight(70)
        
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(16, 0, 16, 0)
        self.hBoxLayout.setSpacing(16)
        
        # 徽标
        self.badgeLabel = QLabel(model_type)
        # 设置徽标对象名，供 QSS 统一管理样式
        self.badgeLabel.setObjectName("modelTypeBadge")
        # 写入模型类型属性，供 QSS 按类型差异化着色
        self.badgeLabel.setProperty("modelType", model_type)
        self.badgeLabel.setFixedSize(40, 40)
        self.badgeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 文本
        self.textLayout = QVBoxLayout()
        self.textLayout.setContentsMargins(0, 14, 0, 14)
        self.textLayout.setSpacing(2)
        
        self.nameLabel = BodyLabel(self.display_name)
        # 设置名称对象名，供 QSS 统一管理样式
        self.nameLabel.setObjectName("modelNameLabel")
        
        # 截断路径显示
        parent_path = str(self.file_path.parent)
        display_path = parent_path if len(parent_path) < 40 else "..." + parent_path[-37:]
        self.pathLabel = CaptionLabel(f"{display_path}/{self.file_path.name}")
        # 设置路径对象名，供 QSS 统一管理样式
        self.pathLabel.setObjectName("modelPathLabel")
        
        self.textLayout.addWidget(self.nameLabel)
        self.textLayout.addWidget(self.pathLabel)
        
        # 命令栏
        self.commandBar = CommandBar(self)
        self.commandBar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        
        self.renameAction = Action(FluentIcon.EDIT, "重命名")
        self.deleteAction = Action(FluentIcon.DELETE, "删除")
        
        self.renameAction.triggered.connect(self._onRename)
        self.deleteAction.triggered.connect(self._onDelete)
        
        self.commandBar.addAction(self.renameAction)
        self.commandBar.addAction(self.deleteAction)
        
        # 组装
        self.hBoxLayout.addWidget(self.badgeLabel)
        self.hBoxLayout.addLayout(self.textLayout)
        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.commandBar)
        
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
