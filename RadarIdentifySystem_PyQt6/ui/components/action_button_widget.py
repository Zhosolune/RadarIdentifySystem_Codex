"""操作按钮组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from qfluentwidgets import CardWidget, FluentIcon, IconWidget

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

    def paintEvent(self, e):
        """覆盖父类（CardWidget）的 paintEvent。
        
        功能描述：
            CardWidget 在其原生的 paintEvent 中会绘制一套默认的浅色/深色半透明背景和边框，
            导致哪怕在 QSS 中设置了 background-color，也会因为这层额外的原生绘制叠加出“蒙版”效果。
            这里利用 QStyleOption 结合样式表配置重新进行纯净渲染。
        """
        from PyQt6.QtWidgets import QStyleOption, QStyle
        from PyQt6.QtGui import QPainter
        
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)
