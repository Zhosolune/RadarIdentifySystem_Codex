"""标签栏组件

提供类似Windows 11浏览器风格的标签页切换组件。
选中的标签有白色背景和向外的圆角效果。
"""

from PyQt5.QtWidgets import QTabBar
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QSize
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QIcon


class TabBar(QTabBar):
    """标签栏组件

    类似Windows 11浏览器风格的标签页切换组件。
    选中标签有白色背景和向外圆角效果。

    Signals:
        tab_changed: 标签页切换信号，参数为标签索引
    """

    tab_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 允许标签扩展
        self.setExpanding(False)
        # 设置标签的最小尺寸
        self.setMinimumWidth(90)
        self.setFixedHeight(40)
        # 开启鼠标追踪
        self.setMouseTracking(True)

        # 移除原生边框和背景
        self.setStyleSheet("""
            QTabBar {
                border: none;
                background: transparent;
                font-family: "Microsoft YaHei";
                font-size: 14px;
            }
            QTabBar::tab {
                border: none;
                background: transparent;
            }
            QTabBar::tab:first {
                margin-left: 10px;
            }
        """)

        # 连接标签切换信号
        self.currentChanged.connect(self.tab_changed.emit)

    def tabSizeHint(self, index):
        """自定义每个标签的大小"""
        size = super().tabSizeHint(index)
        return QSize(max(size.width() + 30, 90), self.height())

    def paintEvent(self, event):
        """自定义绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        count = self.count()
        current_index = self.currentIndex()

        # 检测禁用状态
        is_disabled = not self.isEnabled()

        # 获取鼠标位置检测hover状态（禁用时不显示hover）
        mouse_pos = self.mapFromGlobal(self.cursor().pos())
        hover_index = self.tabAt(mouse_pos) if not is_disabled else -1

        # 颜色定义
        bg_color = QColor("#F3F3F3")          # 标签栏背景色
        selected_bg = QColor("#FFFFFF") if not is_disabled else QColor("#E5E5E5")  # 选中标签背景
        text_color = QColor("#4772c3") if not is_disabled else QColor("#999999")   # 文字颜色
        text_color_inactive = QColor("#666666") if not is_disabled else QColor("#BBBBBB")  # 未选中文字颜色

        # 1. 填充整个标签栏背景
        painter.fillRect(self.rect(), bg_color)

        # 顶部间距
        top_margin = 4

        # 2. 遍历绘制每个标签
        for i in range(count):
            rect = self.tabRect(i)
            is_selected = (i == current_index)
            is_hovered = (i == hover_index) and not is_selected and not is_disabled

            # 调整rect添加顶部间距
            adjusted_top = top_margin

            # 第一个标签左边距（让向外圆角完整显示）
            left_margin = 10 if i == 0 else 0
            adjusted_left = rect.left() + left_margin

            if is_selected:
                # 绘制选中标签的复杂形状
                path = QPainterPath()

                # 几何参数定义
                r_top = 8        # 顶部圆角半径
                r_bottom = 8     # 底部反向圆角半径
                overlap = 10     # 反向圆角的水平延伸宽度

                # 使用实际高度确保覆盖到底部
                bottom = self.height()

                # A. 起点：左下角向外延伸处
                path.moveTo(adjusted_left - overlap, bottom)

                # B. 左下反向圆角（使用三次贝塞尔曲线）
                path.cubicTo(
                    adjusted_left - overlap / 2, bottom,
                    adjusted_left, bottom,
                    adjusted_left, bottom - r_bottom
                )

                # C. 左侧直线 -> 左上标准圆角（从adjusted_top开始）
                path.lineTo(adjusted_left, adjusted_top + r_top)
                path.quadTo(adjusted_left, adjusted_top, adjusted_left + r_top, adjusted_top)

                # D. 顶部直线 -> 右上标准圆角
                path.lineTo(rect.right() - r_top, adjusted_top)
                path.quadTo(rect.right(), adjusted_top, rect.right(), adjusted_top + r_top)

                # E. 右侧直线
                path.lineTo(rect.right(), bottom - r_bottom)

                # F. 右下反向圆角
                path.cubicTo(
                    rect.right(), bottom,
                    rect.right() + overlap / 2, bottom,
                    rect.right() + overlap, bottom
                )

                # G. 闭合路径
                path.closeSubpath()

                # 填充白色背景
                painter.setPen(Qt.NoPen)
                painter.setBrush(selected_bg)
                painter.drawPath(path)

            # 绘制标签内容（图标、文字）
            # 调整内容区域考虑顶部间距和左边距
            content_rect = QRect(adjusted_left + 12, adjusted_top, rect.width() - left_margin - 24, self.height() - adjusted_top)

            # 绘制图标
            icon = self.tabIcon(i)
            if not icon.isNull():
                # 选中时图标最大，hover时中等，未选中时最小
                if is_selected:
                    icon_size = 20
                elif is_hovered:
                    icon_size = 18
                else:
                    icon_size = 16
                # 计算垂直居中位置
                icon_y = adjusted_top + (self.height() - adjusted_top - icon_size) // 2
                icon_rect = QRect(
                    content_rect.left(),
                    icon_y,
                    icon_size, icon_size
                )
                icon.paint(painter, icon_rect)
                content_rect.setLeft(icon_rect.right() + 8)

            # 绘制文字 - hover时使用主题色
            if is_selected:
                painter.setPen(text_color)
            elif is_hovered:
                painter.setPen(text_color)  # hover时也用蓝色
            else:
                painter.setPen(text_color_inactive)

            font = self.font()
            font.setBold(is_selected)
            painter.setFont(font)

            # 使用省略号处理过长文字
            title = self.fontMetrics().elidedText(
                self.tabText(i), Qt.ElideRight, content_rect.width()
            )
            painter.drawText(content_rect, Qt.AlignCenter, title)

    def add_tab(self, text: str, icon_path: str = None) -> int:
        """添加标签页

        Args:
            text: 标签文字
            icon_path: 图标路径（可选）

        Returns:
            int: 标签索引
        """
        if icon_path:
            return self.addTab(QIcon(icon_path), text)
        return self.addTab(text)

    def set_current_index(self, index: int):
        """设置当前选中的标签"""
        self.setCurrentIndex(index)

    def current_index(self) -> int:
        """获取当前选中的标签索引"""
        return self.currentIndex()

    def tab_text(self, index: int) -> str:
        """获取指定标签的文字"""
        return self.tabText(index)

    def set_tab_text(self, index: int, text: str):
        """设置指定标签的文字"""
        self.setTabText(index, text)
