"""提示通知组件

提供类似 PyQt-Fluent-Widgets InfoBar 风格的提示通知，支持 success、error 和 warning 类型。
"""

from PyQt5.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, 
    QGraphicsOpacityEffect, QToolButton, QWidget
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPen, QPixmap
from common.paths import Paths


class ToastNotification(QFrame):
    """Toast 提示通知组件
    
    类似 Fluent Design 风格的提示通知，自动消失，支持 success、error 和 warning 类型。
    
    Signals:
        closed: 通知关闭时发出
    """
    
    closed = pyqtSignal()
    
    # 图标路径
    ICON_SUCCESS = str(Paths.get_resource_path("resources/icons/success.png"))
    ICON_ERROR = str(Paths.get_resource_path("resources/icons/error.png"))
    ICON_WARNING = str(Paths.get_resource_path("resources/icons/warning.png"))
    ICON_INFO = str(Paths.get_resource_path("resources/icons/info.png"))
    
    def __init__(self, message: str, toast_type: str = "success", 
                 duration: int = 2000, isClosable: bool = False, parent=None):
        """初始化 Toast 通知
        
        Args:
            message: 提示消息
            toast_type: 类型 ("success", "error", "warning", "info")
            duration: 显示时长（毫秒），-1 表示不自动关闭
            isClosable: 是否显示关闭按钮
            parent: 父窗口
        """
        super().__init__(parent)
        self._message = message
        self._toast_type = toast_type
        self._duration = duration
        self._isClosable = isClosable
        
        self._setup_ui()
        self._setup_animation()
        
    def _get_colors(self):
        """根据类型获取颜色配置"""
        colors = {
            "success": {
                "bg": QColor(223, 246, 221),      # 浅绿背景
                "border": QColor(76, 175, 80),     # 绿色边框
                "icon_bg": QColor(76, 175, 80),    # 绿色图标背景
                "icon": QColor(255, 255, 255),     # 白色图标
                "text": QColor(30, 70, 32),        # 深绿文字
            },
            "error": {
                "bg": QColor(253, 237, 237),      # 浅红背景
                "border": QColor(244, 67, 54),     # 红色边框
                "icon_bg": QColor(244, 67, 54),    # 红色图标背景
                "icon": QColor(255, 255, 255),     # 白色图标
                "text": QColor(97, 26, 21),        # 深红文字
            },
            "warning": {
                "bg": QColor(255, 244, 229),      # 浅橙背景
                "border": QColor(255, 152, 0),     # 橙色边框
                "icon_bg": QColor(255, 152, 0),    # 橙色图标背景
                "icon": QColor(255, 255, 255),     # 白色图标
                "text": QColor(102, 60, 0),        # 深橙文字
            },
            "info": {
                "bg": QColor(229, 246, 253),      # 浅蓝背景
                "border": QColor(33, 150, 243),    # 蓝色边框
                "icon_bg": QColor(33, 150, 243),   # 蓝色图标背景
                "icon": QColor(255, 255, 255),     # 白色图标
                "text": QColor(1, 67, 97),         # 深蓝文字
            }
        }
        return colors.get(self._toast_type, colors["info"])
        
    def _setup_ui(self):
        """设置 UI"""
        colors = self._get_colors()
        
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # 储存颜色
        self._bg_color = colors["bg"]
        self._border_color = colors["border"]
        self._icon_bg_color = colors["icon_bg"]
        
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(0)
        
        # 图标容器
        icon_widget = QWidget()
        icon_widget.setFixedSize(36, 36)
        icon_layout = QVBoxLayout(icon_widget)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)
        
        # 图标路径
        icon_path = {
            "success": self.ICON_SUCCESS,
            "error": self.ICON_ERROR,
            "warning": self.ICON_WARNING,
            "info": self.ICON_INFO
        }.get(self._toast_type, self.ICON_INFO)
        
        # 使用 QPixmap 加载图标
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        self._icon_label.setAlignment(Qt.AlignCenter)
        
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._icon_label.setPixmap(scaled_pixmap)
        
        self._icon_label.setStyleSheet("background: transparent;")
        icon_layout.addWidget(self._icon_label)
        main_layout.addWidget(icon_widget)
        
        # 文本布局
        text_layout = QHBoxLayout()
        text_layout.setContentsMargins(8, 8, 8, 8)
        text_layout.setSpacing(5)
        
        # 消息标签
        self._message_label = QLabel(self._message)
        self._message_label.setStyleSheet(f"""
            QLabel {{
                color: {colors["text"].name()};
                font-size: 16px;
                font-family: "Microsoft YaHei";
                background: transparent;
            }}
        """)
        text_layout.addWidget(self._message_label)
        text_layout.addStretch()
        main_layout.addLayout(text_layout)
        
        # 关闭按钮
        if self._isClosable:
            close_btn = QToolButton()
            close_btn.setText("×")
            close_btn.setFixedSize(28, 28)
            close_btn.setCursor(Qt.PointingHandCursor)
            close_btn.setStyleSheet(f"""
                QToolButton {{
                    border: none;
                    background: transparent;
                    color: {colors["text"].name()};
                    font-size: 16px;
                    font-weight: bold;
                }}
                QToolButton:hover {{
                    background: rgba(0, 0, 0, 0.05);
                    border-radius: 4px;
                }}
            """)
            close_btn.clicked.connect(self._start_fade_out)
            main_layout.addWidget(close_btn)
        
        # 调整大小
        self.adjustSize()
        self.setMinimumWidth(200)
        
        # 透明度效果
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        
    def _setup_animation(self):
        """设置动画"""
        # 淡入动画
        self._fade_in_ani = QPropertyAnimation(self._opacity_effect, b'opacity', self)
        self._fade_in_ani.setDuration(150)
        self._fade_in_ani.setStartValue(0.0)
        self._fade_in_ani.setEndValue(1.0)
        self._fade_in_ani.setEasingCurve(QEasingCurve.OutCubic)
        
        # 淡出动画
        self._fade_out_ani = QPropertyAnimation(self._opacity_effect, b'opacity', self)
        self._fade_out_ani.setDuration(200)
        self._fade_out_ani.setStartValue(1.0)
        self._fade_out_ani.setEndValue(0.0)
        self._fade_out_ani.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out_ani.finished.connect(self._on_fade_out_finished)
        
    def paintEvent(self, event):
        """绘制背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制圆角矩形背景
        path = QPainterPath()
        rect = self.rect().adjusted(2, 2, -2, -2)
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 8, 8)
        
        # 填充背景
        painter.fillPath(path, self._bg_color)
        
        # 绘制边框
        pen = QPen(self._border_color)
        pen.setWidthF(0.5)  # 更细的线宽
        pen.setCosmetic(True)  # Cosmetic 模式确保线条粗细一致
        painter.setPen(pen)
        painter.drawPath(path)
        
    def showEvent(self, event):
        """显示事件"""
        super().showEvent(event)
        
        # 启动淡入动画
        self._fade_in_ani.start()
        
        # 定时自动关闭
        if self._duration >= 0:
            QTimer.singleShot(self._duration, self._start_fade_out)
            
    def _start_fade_out(self):
        """开始淡出"""
        self._fade_out_ani.start()
        
    def _on_fade_out_finished(self):
        """淡出完成"""
        self.closed.emit()
        self.close()
        self.deleteLater()
        
    def show_at(self, x: int, y: int):
        """在指定位置显示"""
        self.move(x, y)
        self.show()
        
    def show_at_bottom(self, parent: QWidget, margin: int = 20):
        """在父窗口底部居中显示"""
        if parent:
            parent_rect = parent.rect()
            parent_pos = parent.mapToGlobal(parent_rect.topLeft())
            x = parent_pos.x() + (parent_rect.width() - self.width()) // 2
            y = parent_pos.y() + parent_rect.height() - self.height() - margin
            self.move(x, y)
        self.show()
    
    def show_at_top(self, parent: QWidget, margin: int = 20):
        """在父窗口顶部居中显示"""
        if parent:
            parent_rect = parent.rect()
            parent_pos = parent.mapToGlobal(parent_rect.topLeft())
            x = parent_pos.x() + (parent_rect.width() - self.width()) // 2
            y = parent_pos.y() + margin
            self.move(x, y)
        self.show()

    @classmethod
    def success(cls, message: str, parent=None, duration: int = 2000):
        """显示成功提示"""
        toast = cls(message, "success", duration, False, parent)
        toast.show_at_bottom(parent)
        return toast
    
    @classmethod
    def error(cls, message: str, parent=None, duration: int = -1):
        """显示错误提示（必须手动关闭）"""
        toast = cls(message, "error", duration, True, parent)
        toast.show_at_bottom(parent)
        return toast
    
    @classmethod
    def warning(cls, message: str, parent=None, duration: int = 3000):
        """显示警告提示"""
        toast = cls(message, "warning", duration, False, parent)
        toast.show_at_bottom(parent)
        return toast
    
    @classmethod
    def info(cls, message: str, parent=None, duration: int = 2000):
        """显示信息提示"""
        toast = cls(message, "info", duration, False, parent)
        toast.show_at_bottom(parent)
        return toast
