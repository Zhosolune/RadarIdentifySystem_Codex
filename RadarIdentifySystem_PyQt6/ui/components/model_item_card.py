# -*- coding: utf-8 -*-
"""模型项卡片组件。"""

from pathlib import Path
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel
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
    deleteClicked = pyqtSignal(str)
    renameClicked = pyqtSignal(str, str)
    
    def __init__(self, model_type: str, file_path: str, parent=None):
        super().__init__(parent)
        self.model_type = model_type
        self.file_path = Path(file_path)
        
        self.setFixedHeight(70)
        
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(16, 0, 16, 0)
        self.hBoxLayout.setSpacing(16)
        
        # 徽标
        self.badgeLabel = QLabel(model_type)
        self.badgeLabel.setFixedSize(40, 40)
        self.badgeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg_color = "#e6f0ff" if model_type == "PA" else "#ffe6e6"
        fg_color = "#0055ff" if model_type == "PA" else "#ff0000"
        self.badgeLabel.setStyleSheet(f"background-color: {bg_color}; color: {fg_color}; border-radius: 4px; font-weight: bold;")
        
        # 文本
        self.textLayout = QVBoxLayout()
        self.textLayout.setContentsMargins(0, 14, 0, 14)
        self.textLayout.setSpacing(2)
        
        self.nameLabel = BodyLabel(self.file_path.name)
        self.nameLabel.setStyleSheet("font-weight: bold;")
        
        # 截断路径显示
        parent_path = str(self.file_path.parent)
        display_path = parent_path if len(parent_path) < 40 else "..." + parent_path[-37:]
        self.pathLabel = CaptionLabel(f"{display_path}/{self.file_path.name}")
        self.pathLabel.setStyleSheet("color: gray;")
        
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
        """触发重命名信号"""
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入新的模型名称:", text=self.file_path.name)
        if ok and new_name and new_name != self.file_path.name:
            self.renameClicked.emit(str(self.file_path), new_name)
        
    def _onDelete(self):
        """触发删除信号"""
        self.deleteClicked.emit(str(self.file_path))
