from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFrame
)
from PyQt5.QtCore import Qt, QRectF, QPoint
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QPen, QMouseEvent

class BaseFramelessDialog(QDialog):
    """
    无边框圆角对话框基类
    
    提供统一的无边框窗口风格，包含：
    - 圆角半透明背景
    - 自定义标题栏（支持拖动）
    - 关闭按钮
    - 白色内容容器
    """
    
    def __init__(self, parent=None, title="对话框"):
        super().__init__(parent)
        self._drag_pos = None
        self._title = title
        
        # 设置窗口标志
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 初始化UI
        self._init_base_ui()
        
    def _init_base_ui(self):
        """初始化基础UI结构"""
        # 设置全局字体和颜色
        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
            QLabel, QPushButton, QLineEdit {
                font-family: "Microsoft YaHei";
                color: #4772c3;
            }
        """)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(0)
        
        # 1. 标题栏
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(30)
        title_bar_layout = QHBoxLayout(self.title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(0)
        
        # 标题标签
        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 18px; border: none;")
        
        # 关闭按钮
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #999999;
                font-size: 20px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #e81123;
                border-radius: 4px;
                color: white;
            }
            QPushButton:pressed {
                background-color: #e5e5e5;
                color: #333333;
            }
        """)
        self.close_btn.clicked.connect(self.reject)
        
        title_bar_layout.addWidget(self.title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(self.close_btn)
        
        # 2. 内容容器
        self.content_container = QFrame()
        self.content_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 5px;
            }
        """)
        # 内容容器的布局需要由子类设置，或者提供接口添加控件
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)
        
        # 组装
        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.content_container)
        
    def set_title(self, title: str):
        """设置标题"""
        self._title = title
        self.title_label.setText(title)
        self.setWindowTitle(title)
        
    def add_content_widget(self, widget: QWidget):
        """添加控件到内容区域"""
        self.content_layout.addWidget(widget)
        
    def add_content_layout(self, layout):
        """添加布局到内容区域"""
        self.content_layout.addLayout(layout)
        
    def add_content_stretch(self, stretch=0):
        """添加弹簧到内容区域"""
        self.content_layout.addStretch(stretch)

    def paintEvent(self, event):
        """绘制圆角背景和边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制圆角矩形背景
        path = QPainterPath()
        # 调整矩形以适应边框宽度
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        
        # 填充背景色
        painter.fillPath(path, QColor("#F3F3F3"))

        # 绘制边框
        painter.setPen(QPen(QColor("#cccccc"), 1))
        painter.drawPath(path)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 支持拖动窗口"""
        if event.button() == Qt.LeftButton:
            # 检查是否在标题栏区域
            if self.title_bar.geometry().contains(event.pos()):
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 支持拖动窗口"""
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        self._drag_pos = None
        super().mouseReleaseEvent(event)
