"""操作按钮组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from qfluentwidgets import CardWidget, FluentIcon, IconWidget

class ActionButtonCard(CardWidget):
    """自定义的可点击悬浮卡片按钮。"""
    
    def __init__(self, icon: FluentIcon, text: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.icon_widget = IconWidget(icon, self)
        self.icon_widget.setFixedSize(20, 20)
        
        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 14px;")
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 10, 0, 10)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vBoxLayout.addWidget(self.icon_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignHCenter)