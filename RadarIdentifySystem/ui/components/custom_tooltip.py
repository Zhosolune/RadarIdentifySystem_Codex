"""自定义 Tooltip 组件

由于 PyQt5 标准 tooltip 样式受系统主题影响难以修改，
此组件提供一个可完全自定义样式的 tooltip 替代方案。
"""

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QPainter, QColor, QPainterPath


class CustomToolTip(QWidget):
    """自定义 Tooltip 控件
    
    用于替代系统 tooltip，支持自定义背景色、文字颜色等样式。
    """
    
    _instance = None  # 单例实例
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.ToolTip | 
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # 样式配置
        self.bg_color = QColor(255, 255, 255)  # 白色背景
        self.text_color = QColor(71, 114, 195)  # 蓝色文字 #4772c3
        self.shadow_color = QColor(0, 0, 0, 40)  # 阴影颜色
        self.border_radius = 4
        self.padding = 6
        self.shadow_offset = 3  # 阴影偏移
        
        # 创建标签
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.padding + 2, 
            self.padding, 
            self.padding + 2 + self.shadow_offset,  # 右侧预留阴影空间
            self.padding + self.shadow_offset  # 底部预留阴影空间
        )
        
        self.label = QLabel()
        self.label.setStyleSheet(f"""
            QLabel {{
                color: {self.text_color.name()};
                font-family: "Microsoft YaHei";
                font-size: 14px;
                background: transparent;
            }}
        """)
        layout.addWidget(self.label)
        
        # 隐藏定时器
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        
        # 显示延迟定时器
        self.show_timer = QTimer(self)
        self.show_timer.setSingleShot(True)
        self.show_timer.timeout.connect(self._do_show)
        
        self._pending_text = ""
        self._pending_pos = QPoint()
    
    @classmethod
    def instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = CustomToolTip()
        return cls._instance
    
    def paintEvent(self, event):
        """绘制背景和阴影"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 主体区域（减去阴影空间）
        body_width = self.width() - self.shadow_offset
        body_height = self.height() - self.shadow_offset
        
        # 绘制多层阴影实现柔和效果
        shadow_layers = [
            (self.shadow_offset, 25),      # 最外层，最淡
            (self.shadow_offset - 1, 20),  # 中间层
            (self.shadow_offset - 2, 15),  # 内层，较深
        ]
        
        for offset, alpha in shadow_layers:
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(
                offset, offset,
                body_width - 1, body_height - 1,
                self.border_radius, self.border_radius
            )
            painter.fillPath(shadow_path, QColor(0, 0, 0, alpha))
        
        # 绘制主体背景
        body_path = QPainterPath()
        body_path.addRoundedRect(
            0, 0,
            body_width - 1, body_height - 1,
            self.border_radius, self.border_radius
        )
        painter.fillPath(body_path, self.bg_color)
        
        # 绘制1px灰色边框
        painter.setPen(QColor(204, 204, 204))  # #cccccc
        painter.drawPath(body_path)
    
    def showText(self, pos: QPoint, text: str, delay: int = 500):
        """显示 tooltip
        
        Args:
            pos: 全局坐标位置
            text: 显示的文本
            delay: 显示延迟（毫秒）
        """
        self._pending_text = text
        self._pending_pos = pos
        
        self.hide_timer.stop()
        self.show_timer.start(delay)
    
    def _do_show(self):
        """实际显示 tooltip"""
        if not self._pending_text:
            return
        
        self.label.setText(self._pending_text)
        self.adjustSize()
        
        # 调整位置，确保在屏幕内
        screen = QApplication.primaryScreen().geometry()
        x = self._pending_pos.x() + 15
        y = self._pending_pos.y() + 15
        
        if x + self.width() > screen.right():
            x = screen.right() - self.width()
        if y + self.height() > screen.bottom():
            y = self._pending_pos.y() - self.height() - 5
        
        self.move(x, y)
        self.show()
        
        # 自动隐藏
        self.hide_timer.start(3000)
    
    def hideText(self):
        """隐藏 tooltip"""
        self.show_timer.stop()
        self.hide_timer.stop()
        self.hide()


def install_custom_tooltip(widget, text: str):
    """为控件安装自定义 tooltip
    
    Args:
        widget: 要安装 tooltip 的控件
        text: tooltip 文本
    """
    # 禁用系统 tooltip
    widget.setToolTip("")
    
    # 保存 tooltip 文本
    widget._custom_tooltip_text = text
    
    # 保存原始事件处理器
    original_enter = widget.enterEvent
    original_leave = widget.leaveEvent
    
    def on_enter(event):
        tooltip = CustomToolTip.instance()
        pos = widget.mapToGlobal(QPoint(widget.width() // 2, widget.height()))
        tooltip.showText(pos, text, delay=500)
        if original_enter:
            original_enter(event)
    
    def on_leave(event):
        CustomToolTip.instance().hideText()
        if original_leave:
            original_leave(event)
    
    widget.enterEvent = on_enter
    widget.leaveEvent = on_leave
