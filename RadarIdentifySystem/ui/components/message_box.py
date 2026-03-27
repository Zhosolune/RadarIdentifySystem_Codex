"""自定义消息提示框组件

提供与 QMessageBox 类似功能但具备自定义样式的消息提示框。
继承自 BaseFramelessDialog，保持 UI 风格一致。
"""

from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QDialog, QStyle, QWidget
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
from .custom_dialog import BaseFramelessDialog

class CustomMessageBox(BaseFramelessDialog):
    """自定义消息提示框
    
    用于替代 QMessageBox，提供一致的 UI 风格。
    支持 Information, Warning, Critical, Question 等类型。
    """
    
    # 按钮类型定义
    Yes = 1
    No = 0
    Ok = 1
    Cancel = 0
    
    def __init__(self, parent=None, title="提示", text="", icon=None, buttons=None):
        """初始化消息提示框
        
        Args:
            parent: 父窗口
            title: 标题
            text: 消息内容
            icon: QIcon 对象或标准图标枚举
            buttons: 按钮列表，如 ["确定"] 或 ["是", "否"]
        """
        super().__init__(parent, title=title)
        
        self.clicked_button = None
        self.setFixedWidth(400)
        
        self._setup_ui(text, icon, buttons)
        
    def _setup_ui(self, text, icon, buttons):
        """设置内部 UI"""
        # 内容布局
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)
        
        # 图标
        if icon:
            icon_label = QLabel()
            if isinstance(icon, QIcon):
                pixmap = icon.pixmap(48, 48)
            elif isinstance(icon, QStyle.StandardPixmap):
                pixmap = self.style().standardIcon(icon).pixmap(48, 48)
            else:
                # 默认 Info 图标
                pixmap = self.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(48, 48)
                
            icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(48, 48)
            icon_label.setStyleSheet("background: transparent; border: none;")
            content_layout.addWidget(icon_label, 0, Qt.AlignTop)
            
        # 消息文本
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #333333;
                background: transparent;
                border: none;
                font-family: "Microsoft YaHei";
            }
        """)
        content_layout.addWidget(text_label, 1)
        
        self.add_content_layout(content_layout)
        self.add_content_stretch(1)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch(1)
        
        if not buttons:
            buttons = [("确定", self.Ok)]
            
        for btn_text, btn_role in buttons:
            btn = QPushButton(btn_text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(80, 32)
            
            # 根据按钮文本设置不同样式
            if btn_text in ["确定", "是", "完成", "Yes", "Ok"]:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4772c3;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-size: 14px;
                        font-family: "Microsoft YaHei";
                    }
                    QPushButton:hover {
                        background-color: #3d61a8;
                    }
                    QPushButton:pressed {
                        background-color: #33518c;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: white;
                        color: #666666;
                        border: 1px solid #cccccc;
                        border-radius: 4px;
                        font-size: 14px;
                        font-family: "Microsoft YaHei";
                    }
                    QPushButton:hover {
                        background-color: #f5f5f5;
                        color: #333333;
                    }
                """)
                
            # 使用 lambda 捕获变量，注意默认参数陷阱
            btn.clicked.connect(lambda checked, role=btn_role: self._on_btn_clicked(role))
            btn_layout.addWidget(btn)
            
        self.add_content_layout(btn_layout)
        
    def _on_btn_clicked(self, role):
        """按钮点击处理"""
        self.clicked_button = role
        if role == self.Ok or role == self.Yes:
            self.accept()
        else:
            self.reject()
            
    @classmethod
    def information(cls, parent, title, text):
        """显示信息框"""
        dialog = cls(
            parent, 
            title, 
            text, 
            icon=QStyle.SP_MessageBoxInformation,
            buttons=[("确定", cls.Ok)]
        )
        return dialog.exec_()
        
    @classmethod
    def warning(cls, parent, title, text):
        """显示警告框"""
        dialog = cls(
            parent, 
            title, 
            text, 
            icon=QStyle.SP_MessageBoxWarning,
            buttons=[("确定", cls.Ok)]
        )
        return dialog.exec_()
        
    @classmethod
    def critical(cls, parent, title, text):
        """显示错误框"""
        dialog = cls(
            parent, 
            title, 
            text, 
            icon=QStyle.SP_MessageBoxCritical,
            buttons=[("确定", cls.Ok)]
        )
        return dialog.exec_()
        
    @classmethod
    def question(cls, parent, title, text):
        """显示询问框"""
        dialog = cls(
            parent, 
            title, 
            text, 
            icon=QStyle.SP_MessageBoxQuestion,
            buttons=[("是", cls.Yes), ("否", cls.No)]
        )
        if dialog.exec_() == QDialog.Accepted:
            return cls.Yes
        return cls.No
