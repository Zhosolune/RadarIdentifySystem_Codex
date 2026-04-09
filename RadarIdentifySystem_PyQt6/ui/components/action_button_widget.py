"""操作按钮组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt
from qfluentwidgets import CardWidget, FluentIcon, IconWidget, isDarkTheme

class ActionButtonCard(CardWidget):
    """自定义的可点击悬浮卡片按钮。"""
    
    def __init__(self, icon: FluentIcon, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("actionButtonCard")
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.icon_widget = IconWidget(icon, self)
        self.icon_widget.setFixedSize(20, 20)
        self.icon_widget.setObjectName("actionButtonIcon")
        
        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("actionButtonLabel")
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 10, 0, 10)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vBoxLayout.addWidget(self.icon_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignHCenter)

    def enterEvent(self, e):
        super().enterEvent(e)
        self.setProperty('isHover', True)
        self.style().polish(self)

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.setProperty('isHover', False)
        self.style().polish(self)
        
    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        if e.button() == Qt.MouseButton.LeftButton:
            self.setProperty('isPressed', True)
            self.style().polish(self)
            
    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() == Qt.MouseButton.LeftButton:
            self.setProperty('isPressed', False)
            self.style().polish(self)
            
    def paintEvent(self, e):
        """覆盖父类的 paintEvent。
        
        功能描述：
            屏蔽父类的默认边框绘制，使普通按钮也受 QSS 控制，从而与 SettingCard 等保持一致外观。
        """
        from PyQt6.QtWidgets import QStyleOption, QStyle
        from PyQt6.QtGui import QPainter
        
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

        if isDarkTheme():
            # painter.setBrush(QColor(255, 255, 255, 13))
            painter.setPen(QColor(0, 0, 0, 50))
        else:
            # painter.setBrush(QColor(255, 255, 255, 170))
            painter.setPen(QColor(0, 0, 0, 19))

        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

class PrimaryActionButtonCard(ActionButtonCard):
    """主题色的自定义可点击悬浮卡片按钮。"""
    
    def __init__(self, icon: FluentIcon, text: str, parent=None):
        super().__init__(icon, text, parent)
        self.setObjectName("primaryActionButtonCard")
        self.label.setObjectName("primaryActionButtonLabel")
        self._icon = icon
        
        # 监听主题变化以更新图标颜色
        from qfluentwidgets import qconfig
        qconfig.themeChanged.connect(self._update_icon_theme)
        self._update_icon_theme()

    def _update_icon_theme(self):
        """根据当前主题设置图标颜色（与主色背景反色以保证对比度）"""
        from qfluentwidgets import Theme, isDarkTheme
        if isDarkTheme():
            # 深色模式下，主色（如浅蓝）背景需搭配黑色图标
            self.icon_widget.setIcon(self._icon.icon(theme=Theme.LIGHT))
        else:
            # 浅色模式下，主色（如深蓝）背景需搭配白色图标
            self.icon_widget.setIcon(self._icon.icon(theme=Theme.DARK))

    # paintEvent 已经由父类 ActionButtonCard 提供，子类无需重复编写
