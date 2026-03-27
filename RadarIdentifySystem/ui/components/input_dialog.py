"""自定义输入对话框组件

提供与 QInputDialog.getText 类似功能但具备自定义样式的输入对话框。
继承自 BaseFramelessDialog，保持 UI 风格一致。
"""

from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QDialog
)
from PyQt5.QtCore import Qt
from .custom_dialog import BaseFramelessDialog

class CustomInputDialog(BaseFramelessDialog):
    """自定义输入对话框
    
    用于替代 QInputDialog，提供一致的 UI 风格。
    包含标题、提示文本、输入框和确认/取消按钮。
    """
    
    def __init__(self, parent=None, title="输入", label="请输入:", text="", placeholder=""):
        """初始化输入对话框
        
        Args:
            parent: 父窗口
            title: 标题
            label: 提示标签文本
            text: 输入框默认文本
            placeholder: 输入框占位符
        """
        super().__init__(parent, title=title)
        
        self.text_value = text
        self.ok = False
        
        # 设置固定宽度
        self.setFixedWidth(400)
        
        self._setup_ui(label, text, placeholder)
        
    def _setup_ui(self, label_text, default_text, placeholder):
        """设置内部 UI"""
        # 提示标签
        self.label = QLabel(label_text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 14px; color: #333333; border: none; background: transparent;")
        self.add_content_widget(self.label)
        
        # 输入框
        self.line_edit = QLineEdit(default_text)
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #4772c3;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 14px;
                color: #333333;
                background-color: white;
                font-family: "Microsoft YaHei";
            }
            QLineEdit:focus {
                border: 2px solid #4772c3;
            }
        """)
        # 选中所有文本，方便直接修改
        self.line_edit.selectAll()
        # 连接回车信号
        self.line_edit.returnPressed.connect(self.accept_input)
        self.add_content_widget(self.line_edit)
        
        self.add_content_stretch(1)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch(1)
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setFixedSize(80, 32)
        self.cancel_btn.setStyleSheet("""
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
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        # 确认按钮
        self.ok_btn = QPushButton("确定")
        self.ok_btn.setDefault(True)
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.setFixedSize(80, 32)
        self.ok_btn.setStyleSheet("""
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
        self.ok_btn.clicked.connect(self.accept_input)
        button_layout.addWidget(self.ok_btn)
        
        self.add_content_layout(button_layout)
        
    def accept_input(self):
        """确认输入处理"""
        self.text_value = self.line_edit.text()
        self.ok = True
        self.accept()
        
    @classmethod
    def get_text(cls, parent, title, label, text="", placeholder=""):
        """获取文本输入静态方法
        
        Args:
            parent: 父窗口
            title: 标题
            label: 提示标签
            text: 默认文本
            placeholder: 占位符
            
        Returns:
            tuple: (输入文本, 是否点击确定)
        """
        dialog = cls(parent, title, label, text, placeholder)
        result = dialog.exec_()
        return dialog.text_value, result == QDialog.Accepted
