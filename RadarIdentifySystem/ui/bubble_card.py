from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QSizePolicy
from PyQt5.QtCore import (
    Qt,
    QPropertyAnimation,
    QRect,
    QRectF,
    QEasingCurve,
    QPoint,
    QSize,
    QTimer,
)
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QFontMetrics
import sys
from typing import Optional

# 处理相对导入问题，支持直接运行
try:
    from .style_manager import StyleManager
except ImportError:
    # 当直接运行此文件时，使用绝对导入
    try:
        from style_manager import StyleManager
    except ImportError:
        # 如果都失败了，定义一个简单的替代类
        class StyleManager:
            def get_style(self, style_name):
                return ""

            def __getitem__(self, key):
                return ""


class BubbleCard(QWidget):
    """智能气泡卡片组件

    提供带箭头的气泡提示框，支持点击切换显示/隐藏，自动定位和动画效果。
    支持点击响应和hover响应两种交互模式。
    """

    def __init__(
        self,
        text: str,
        parent: Optional[QWidget] = None,
        text_color: str = "#4772c3",
        response_mode: str = "hover",
        arrow_direction: str = "auto",
        label_style: Optional[str] = None,
    ):
        """初始化气泡卡片

        Args:
            text: 显示的文本内容
            parent: 父控件
            text_color: 文字颜色，默认为蓝色（当label_style为None时生效）
            response_mode: 响应方式，"click"为点击响应，"hover"为悬浮响应
            arrow_direction: 箭头方向，可选值："up", "down", "left", "right", "auto"（自动计算）
            label_style: 标签样式表，支持完整的QLabel样式定义，如果提供则覆盖默认样式
        """
        super().__init__(parent)
        self.text_color = QColor(text_color)
        self.bg_color = QColor("#F9F9F9")  # 白色背景
        self.arrow_direction = arrow_direction  # 保存用户指定的箭头方向
        self.arrow_dir = (
            "down" if arrow_direction == "auto" else arrow_direction
        )  # 当前箭头方向
        self.arrow_pos = 0  # 箭头中心位置（相对于气泡边）
        self.arrow_size = 10
        self.distance_offset = 5  # 气泡与控件之间的额外距离偏移
        self.is_visible = False  # 当前显示状态
        self.target_widget = None  # 目标控件引用
        self.main_window = None  # 主窗口引用
        self.response_mode = response_mode  # 响应模式：click 或 hover
        self.hover_timer = None  # hover模式的延时器
        self.label_style = label_style  # 保存用户自定义样式

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 禁用阴影效果，改为手动绘制，避免系统层面的渲染问题
        # shadow = QGraphicsDropShadowEffect(self)
        # shadow.setBlurRadius(15)
        # shadow.setXOffset(0)
        # shadow.setYOffset(2)
        # shadow.setColor(QColor(0, 0, 0, 60))
        # self.setGraphicsEffect(shadow)

        # 内容布局
        layout = QVBoxLayout(self)
        self.label = QLabel(text)

        # 应用样式：优先使用自定义样式，否则使用默认样式
        if self.label_style:
            self.label.setStyleSheet(self.label_style)
        else:
            self.label.setStyleSheet(
                """
                QLabel {
                    font-size: 16px;
                    color: #4772c3;
                    margin: 0;
                    background-color: transparent;
                    font-family: "Microsoft YaHei";
                }
            """
            )

        # 启用自动换行
        self.label.setWordWrap(True)
        # 设置文本对齐方式
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # 设置尺寸策略，让标签能够扩展到最大宽度
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(self.label)
        layout.setContentsMargins(10, 10, 10, 10)

        # 动画
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(100)
        self.opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.opacity_anim.finished.connect(self._on_animation_finished)

        # 初始化hover模式的定时器
        if self.response_mode == "hover":
            self.hover_timer = QTimer()
            self.hover_timer.setSingleShot(True)
            self.hover_timer.timeout.connect(self.hide_bubble)
            self.hover_timer.setInterval(100)  # 100ms延时

    def paintEvent(self, event):
        """绘制气泡卡片

        Args:
            event: 绘制事件
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 创建完整的气泡路径（包含箭头）
        path = self._create_bubble_path()

        # 绘制多层阴影效果，创建更自然的阴影
        shadow_offsets = [(2, 3), (1, 2)]  # 多层阴影偏移
        shadow_alphas = [15, 25]  # 对应的透明度

        for i, (offset_x, offset_y) in enumerate(shadow_offsets):
            shadow_path = QPainterPath(path)
            shadow_path.translate(offset_x, offset_y)
            painter.fillPath(shadow_path, QColor(0, 0, 0, shadow_alphas[i]))

        # 填充白色背景
        painter.fillPath(path, self.bg_color)

    def _create_bubble_path(self):
        """创建完整的气泡路径，包含圆角矩形主体和箭头

        Returns:
            QPainterPath: 完整的气泡路径
        """
        # 获取绘制区域，为阴影预留空间
        rect = self.rect()
        # 减去阴影偏移量，确保主要内容在可见区域内
        shadow_offset_x = 3
        shadow_offset_y = 3
        draw_rect = QRectF(
            rect.left(),
            rect.top(),
            rect.width() - shadow_offset_x,
            rect.height() - shadow_offset_y,
        )

        path = QPainterPath()
        radius = 10  # 圆角半径

        if self.arrow_dir == "down":
            # 箭头朝下，气泡在上方
            body_rect = QRectF(
                draw_rect.left(),
                draw_rect.top(),
                draw_rect.width(),
                draw_rect.height() - self.arrow_size,
            )

            # 从左上角开始，顺时针绘制
            path.moveTo(body_rect.left() + radius, body_rect.top())
            # 顶边
            path.lineTo(body_rect.right() - radius, body_rect.top())
            # 右上角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.top(),
                2 * radius,
                2 * radius,
                90,
                -90,
            )
            # 右边
            path.lineTo(body_rect.right(), body_rect.bottom() - radius)
            # 右下角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                0,
                -90,
            )

            # 底边到箭头左侧
            arrow_left = self.arrow_pos - self.arrow_size
            arrow_right = self.arrow_pos + self.arrow_size
            path.lineTo(arrow_right, body_rect.bottom())
            # 箭头
            path.lineTo(self.arrow_pos, body_rect.bottom() + self.arrow_size)
            path.lineTo(arrow_left, body_rect.bottom())

            # 继续底边到左下角
            path.lineTo(body_rect.left() + radius, body_rect.bottom())
            # 左下角
            path.arcTo(
                body_rect.left(),
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                270,
                -90,
            )
            # 左边
            path.lineTo(body_rect.left(), body_rect.top() + radius)
            # 左上角
            path.arcTo(
                body_rect.left(), body_rect.top(), 2 * radius, 2 * radius, 180, -90
            )

        elif self.arrow_dir == "up":
            # 箭头朝上，气泡在下方
            body_rect = QRectF(
                draw_rect.left(),
                draw_rect.top() + self.arrow_size,
                draw_rect.width(),
                draw_rect.height() - self.arrow_size,
            )

            # 从箭头开始绘制
            arrow_left = self.arrow_pos - self.arrow_size
            arrow_right = self.arrow_pos + self.arrow_size
            path.moveTo(arrow_left, body_rect.top())
            path.lineTo(self.arrow_pos, body_rect.top() - self.arrow_size)
            path.lineTo(arrow_right, body_rect.top())

            # 顶边到右上角
            path.lineTo(body_rect.right() - radius, body_rect.top())
            # 右上角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.top(),
                2 * radius,
                2 * radius,
                90,
                -90,
            )
            # 右边
            path.lineTo(body_rect.right(), body_rect.bottom() - radius)
            # 右下角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                0,
                -90,
            )
            # 底边
            path.lineTo(body_rect.left() + radius, body_rect.bottom())
            # 左下角
            path.arcTo(
                body_rect.left(),
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                270,
                -90,
            )
            # 左边
            path.lineTo(body_rect.left(), body_rect.top() + radius)
            # 左上角
            path.arcTo(
                body_rect.left(), body_rect.top(), 2 * radius, 2 * radius, 180, -90
            )
            # 顶边到箭头
            path.lineTo(arrow_left, body_rect.top())

        elif self.arrow_dir == "right":
            # 箭头朝右，气泡在左侧
            body_rect = QRectF(
                draw_rect.left(),
                draw_rect.top(),
                draw_rect.width() - self.arrow_size,
                draw_rect.height(),
            )

            # 从左上角开始
            path.moveTo(body_rect.left() + radius, body_rect.top())
            # 顶边
            path.lineTo(body_rect.right() - radius, body_rect.top())
            # 右上角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.top(),
                2 * radius,
                2 * radius,
                90,
                -90,
            )

            # 右边到箭头上方
            arrow_top = self.arrow_pos - self.arrow_size
            arrow_bottom = self.arrow_pos + self.arrow_size
            path.lineTo(body_rect.right(), arrow_top)
            # 箭头
            path.lineTo(body_rect.right() + self.arrow_size, self.arrow_pos)
            path.lineTo(body_rect.right(), arrow_bottom)

            # 继续右边到右下角
            path.lineTo(body_rect.right(), body_rect.bottom() - radius)
            # 右下角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                0,
                -90,
            )
            # 底边
            path.lineTo(body_rect.left() + radius, body_rect.bottom())
            # 左下角
            path.arcTo(
                body_rect.left(),
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                270,
                -90,
            )
            # 左边
            path.lineTo(body_rect.left(), body_rect.top() + radius)
            # 左上角
            path.arcTo(
                body_rect.left(), body_rect.top(), 2 * radius, 2 * radius, 180, -90
            )

        elif self.arrow_dir == "left":
            # 箭头朝左，气泡在右侧
            body_rect = QRectF(
                draw_rect.left() + self.arrow_size,
                draw_rect.top(),
                draw_rect.width() - self.arrow_size,
                draw_rect.height(),
            )

            # 从左上角开始绘制（避免从箭头开始导致的路径问题）
            arrow_top = self.arrow_pos - self.arrow_size
            arrow_bottom = self.arrow_pos + self.arrow_size

            # 从左上角开始
            path.moveTo(body_rect.left() + radius, body_rect.top())
            # 顶边
            path.lineTo(body_rect.right() - radius, body_rect.top())
            # 右上角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.top(),
                2 * radius,
                2 * radius,
                90,
                -90,
            )
            # 右边
            path.lineTo(body_rect.right(), body_rect.bottom() - radius)
            # 右下角
            path.arcTo(
                body_rect.right() - 2 * radius,
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                0,
                -90,
            )
            # 底边
            path.lineTo(body_rect.left() + radius, body_rect.bottom())
            # 左下角
            path.arcTo(
                body_rect.left(),
                body_rect.bottom() - 2 * radius,
                2 * radius,
                2 * radius,
                270,
                -90,
            )
            # 左边到箭头下方
            path.lineTo(body_rect.left(), arrow_bottom)
            # 箭头
            path.lineTo(body_rect.left() - self.arrow_size, self.arrow_pos)
            path.lineTo(body_rect.left(), arrow_top)
            # 左边到左上角
            path.lineTo(body_rect.left(), body_rect.top() + radius)
            # 左上角
            path.arcTo(
                body_rect.left(), body_rect.top(), 2 * radius, 2 * radius, 180, -90
            )

        path.closeSubpath()
        return path

    def mousePressEvent(self, event):
        """处理鼠标点击事件

        Args:
            event: 鼠标事件
        """
        # 点击气泡卡片本身不关闭
        event.accept()

    def enterEvent(self, event):
        """鼠标进入气泡区域事件

        Args:
            event: 鼠标事件
        """
        if self.response_mode == "hover" and self.hover_timer:
            self.hover_timer.stop()  # 停止隐藏定时器
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开气泡区域事件

        Args:
            event: 鼠标事件
        """
        if self.response_mode == "hover" and self.hover_timer and self.is_visible:
            self.hover_timer.start()  # 启动隐藏定时器
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        """全局事件过滤器，用于检测点击气泡外区域

        Args:
            obj: 事件对象
            event: 事件

        Returns:
            bool: 是否处理了事件
        """
        if (
            event.type() == event.MouseButtonPress
            and self.is_visible
            and self.response_mode == "click"
        ):
            # 检查点击位置是否在气泡卡片内
            click_pos = event.globalPos()
            bubble_rect = QRect(self.pos(), self.size())

            # 检查点击位置是否在目标控件内
            target_rect = None
            if self.target_widget:
                target_global_pos = self.target_widget.mapToGlobal(QPoint(0, 0))
                target_rect = QRect(target_global_pos, self.target_widget.size())

            # 如果点击位置不在气泡内且不在目标控件内，则关闭气泡
            if not bubble_rect.contains(click_pos) and (
                not target_rect or not target_rect.contains(click_pos)
            ):
                self.hide_bubble()

        return super().eventFilter(obj, event)

    def showAt(self, target_widget, main_window):
        self.target_widget = target_widget
        self.main_window = main_window

        if self.is_visible:
            self.hide_bubble()
            return

        # 目标与主窗口相对坐标
        target_pos = target_widget.mapTo(main_window, QPoint(0, 0))
        target_rect = QRect(target_pos, target_widget.size())

        main_rect = QRect(0, 0, main_window.width(), main_window.height())

        margin = 30

        # 先用一个合理的候选宽度判断方向（不会最终使用）
        candidate_width = min(400, main_rect.width() - margin * 2)
        candidate_size = QSize(candidate_width, 100)
        _x, _y = self._calculate_position(target_rect, main_rect, candidate_size)

        # 根据确定的箭头方向计算实际可用的最大宽度
        # 注意：这里计算的是气泡主体的最大宽度，不包含箭头部分
        if self.arrow_dir == "left":
            # 箭头朝左，气泡在控件右侧，最大宽度受右侧空间限制
            max_width = max(
                80,
                main_rect.right() - target_rect.right() - margin - self.distance_offset,
            )

        elif self.arrow_dir == "right":
            # 箭头朝右，气泡在控件左侧，最大宽度受左侧空间限制
            max_width = max(
                80,
                target_rect.left() - main_rect.left() - margin - self.distance_offset,
            )

        else:
            # 上下方向，使用整个窗口宽度
            max_width = max(80, main_rect.width() - margin * 2)

        # 更新布局内边距（基于箭头方向）
        self._update_layout_margins()
        margins = self.layout().contentsMargins()

        # 计算标签可用宽度（减去箭头和布局左右边距）
        available_width = max_width - margins.left() - margins.right()

        # 用 QFontMetrics 计算文本在单行下的自然宽度（取每一行的最大宽度）
        fm = QFontMetrics(self.label.font())
        text = self.label.text() or ""
        lines = text.splitlines() if text else [""]
        natural_line_width = 0
        for line in lines:
            line_width = fm.horizontalAdvance(line)
            # 添加一点额外空间防止截断
            natural_line_width = max(natural_line_width, line_width + 5)

        # 决策逻辑：
        # 1. 如果自然宽度小于等于可用宽度，使用自然宽度（自适应）
        # 2. 如果自然宽度大于可用宽度，使用可用宽度（换行显示）
        if natural_line_width <= available_width:
            # 文本能在一行内显示，使用自然宽度
            chosen_label_width = natural_line_width
        else:
            # 文本需要换行，使用可用宽度，但确保不小于最小宽度
            chosen_label_width = available_width

        # 将标签设为固定宽度（这样布局会把它撑开/换行）
        self.label.setFixedWidth(int(chosen_label_width))

        # 激活布局并根据内容计算高度
        self.layout().activate()
        # 整体气泡宽度 = 标签宽 + 左右边距（箭头空间已通过布局边距考虑）
        bubble_w = int(chosen_label_width + margins.left() + margins.right())
        # 计算高度（sizeHint 在 label 固定宽度后会给出合理高度）
        bubble_h = self.sizeHint().height()

        # 限制不超过最大宽度（保险）
        bubble_w = min(bubble_w, max_width)

        # 先 resize，后重新计算精确位置
        self.resize(bubble_w, bubble_h)

        x, y = self._calculate_position(
            target_rect, main_rect, QSize(bubble_w, bubble_h)
        )

        x = max(margin, min(x, main_rect.width() - bubble_w - margin))
        y = max(margin, min(y, main_rect.height() - bubble_h - margin))

        self._update_arrow_position(target_rect, x, y, QSize(bubble_w, bubble_h))

        global_pos = main_window.mapToGlobal(QPoint(x, y))
        self.move(global_pos)

        # 显示动画
        self.setWindowOpacity(0)
        self.show()
        self.is_visible = True
        self.opacity_anim.setStartValue(0)
        self.opacity_anim.setEndValue(1)
        self.opacity_anim.start()

        # 安装全局事件过滤器，用于检测点击气泡外区域
        if self.response_mode == "click":
            QApplication.instance().installEventFilter(self)

    def _calculate_position(self, target_rect, main_rect, bubble_size):
        """计算气泡位置和箭头方向

        Args:
            target_rect: 目标控件矩形
            main_rect: 主窗口矩形
            bubble_size: 气泡大小

        Returns:
            tuple: (x, y) 位置坐标
        """
        space_top = target_rect.top() - main_rect.top()
        space_bottom = main_rect.bottom() - target_rect.bottom()
        space_left = target_rect.left() - main_rect.left()
        space_right = main_rect.right() - target_rect.right()

        # 如果指定了箭头方向，直接使用指定方向
        if self.arrow_direction != "auto":
            self.arrow_dir = self.arrow_direction
            return self._calculate_position_for_direction(target_rect, bubble_size)

        # 自动模式：优先显示在上方（箭头朝下），如果空间不够再选择其他方向
        if space_top >= bubble_size.height() + self.arrow_size:
            self.arrow_dir = "down"  # 箭头朝下，显示在控件上方
            x = target_rect.center().x() - bubble_size.width() // 2
            y = (
                target_rect.top()
                - bubble_size.height()
                - self.arrow_size
                + self.distance_offset
            )
            self.arrow_pos = bubble_size.width() // 2
        elif space_bottom >= bubble_size.height() + self.arrow_size:
            self.arrow_dir = "up"  # 箭头朝上，显示在控件下方
            x = target_rect.center().x() - bubble_size.width() // 2
            y = target_rect.bottom() + self.arrow_size - self.distance_offset
            self.arrow_pos = bubble_size.width() // 2
        elif space_right >= bubble_size.width() + self.arrow_size:
            self.arrow_dir = "left"  # 箭头朝左，显示在控件右侧
            x = target_rect.right() + self.arrow_size - self.distance_offset
            y = target_rect.center().y() - bubble_size.height() // 2
            self.arrow_pos = bubble_size.height() // 2
        elif space_left >= bubble_size.width() + self.arrow_size:
            self.arrow_dir = "right"  # 箭头朝右，显示在控件左侧
            x = (
                target_rect.left()
                - bubble_size.width()
                - self.arrow_size
                + self.distance_offset
            )
            y = target_rect.center().y() - bubble_size.height() // 2
            self.arrow_pos = bubble_size.height() // 2
        else:
            # 如果没有足够空间，选择空间最大的方向
            spaces = {
                "down": space_top,
                "up": space_bottom,
                "left": space_right,
                "right": space_left,
            }
            self.arrow_dir = max(spaces, key=spaces.get)

            # 根据选择的方向设置位置
            if self.arrow_dir == "down":
                x = target_rect.center().x() - bubble_size.width() // 2
                y = (
                    target_rect.top()
                    - bubble_size.height()
                    - self.arrow_size
                    + self.distance_offset
                )
                self.arrow_pos = bubble_size.width() // 2
            elif self.arrow_dir == "up":
                x = target_rect.center().x() - bubble_size.width() // 2
                y = target_rect.bottom() + self.arrow_size - self.distance_offset
                self.arrow_pos = bubble_size.width() // 2
            elif self.arrow_dir == "left":
                x = target_rect.right() + self.arrow_size - self.distance_offset
                y = target_rect.center().y() - bubble_size.height() // 2
                self.arrow_pos = bubble_size.height() // 2
            else:  # right
                x = (
                    target_rect.left()
                    - bubble_size.width()
                    - self.arrow_size
                    + self.distance_offset
                )
                y = target_rect.center().y() - bubble_size.height() // 2
                self.arrow_pos = bubble_size.height() // 2

        return x, y

    def _calculate_position_for_direction(self, target_rect, bubble_size):
        """根据指定的箭头方向计算气泡位置

        Args:
            target_rect: 目标控件矩形
            bubble_size: 气泡大小

        Returns:
            tuple: (x, y) 位置坐标
        """
        if self.arrow_dir == "down":
            # 箭头朝下，显示在控件上方
            x = target_rect.center().x() - bubble_size.width() // 2
            y = (
                target_rect.top()
                - bubble_size.height()
                - self.arrow_size
                + self.distance_offset
            )
            self.arrow_pos = bubble_size.width() // 2
        elif self.arrow_dir == "up":
            # 箭头朝上，显示在控件下方
            x = target_rect.center().x() - bubble_size.width() // 2
            y = target_rect.bottom() + self.arrow_size - self.distance_offset
            self.arrow_pos = bubble_size.width() // 2
        elif self.arrow_dir == "left":
            # 箭头朝左，显示在控件右侧
            x = target_rect.right() + self.arrow_size - self.distance_offset
            y = target_rect.center().y() - bubble_size.height() // 2
            self.arrow_pos = bubble_size.height() // 2
        elif self.arrow_dir == "right":
            # 箭头朝右，显示在控件左侧
            x = (
                target_rect.left()
                - bubble_size.width()
                - self.arrow_size
                + self.distance_offset
            )
            y = target_rect.center().y() - bubble_size.height() // 2
            self.arrow_pos = bubble_size.height() // 2
        else:
            # 默认情况，使用down方向
            x = target_rect.center().x() - bubble_size.width() // 2
            y = (
                target_rect.top()
                - bubble_size.height()
                - self.arrow_size
                + self.distance_offset
            )
            self.arrow_pos = bubble_size.width() // 2

        return x, y

    def _update_layout_margins(self):
        """根据箭头方向动态更新布局内边距

        确保文本内容不会紧贴箭头，在箭头方向增加合理的内边距
        """
        base_margin = 10  # 基础内边距
        arrow_margin = self.arrow_size + 10  # 箭头方向的额外内边距

        if self.arrow_dir == "up":
            # 箭头朝上，增加顶部内边距
            self.layout().setContentsMargins(
                base_margin, arrow_margin, base_margin, base_margin
            )
        elif self.arrow_dir == "down":
            # 箭头朝下，增加底部内边距
            self.layout().setContentsMargins(
                base_margin, base_margin, base_margin, arrow_margin
            )
        elif self.arrow_dir == "left":
            # 箭头朝左，增加左侧内边距
            self.layout().setContentsMargins(
                arrow_margin, base_margin, base_margin, base_margin
            )
        elif self.arrow_dir == "right":
            # 箭头朝右，增加右侧内边距
            self.layout().setContentsMargins(
                base_margin, base_margin, arrow_margin, base_margin
            )
        else:
            # 默认情况，使用基础内边距
            self.layout().setContentsMargins(
                base_margin, base_margin, base_margin, base_margin
            )

    def _update_arrow_position(self, target_rect, bubble_x, bubble_y, bubble_size):
        """更新箭头位置，确保箭头指向目标控件中心

        Args:
            target_rect: 目标控件矩形
            bubble_x: 气泡X坐标
            bubble_y: 气泡Y坐标
            bubble_size: 气泡尺寸
        """
        target_center_x = target_rect.center().x()
        target_center_y = target_rect.center().y()

        if self.arrow_dir in ["up", "down"]:
            # 水平方向的箭头位置
            relative_x = target_center_x - bubble_x
            # 限制箭头位置在气泡边界内，保持20像素边距
            self.arrow_pos = max(20, min(relative_x, bubble_size.width() - 20))
        else:  # left, right
            # 垂直方向的箭头位置
            relative_y = target_center_y - bubble_y
            # 限制箭头位置在气泡边界内，保持20像素边距
            self.arrow_pos = max(20, min(relative_y, bubble_size.height() - 20))

    def hide_bubble(self):
        """隐藏气泡卡片"""
        if not self.is_visible:
            return

        # 移除全局事件过滤器
        if self.response_mode == "click":
            QApplication.instance().removeEventFilter(self)

        # 停止hover定时器
        if self.response_mode == "hover" and self.hover_timer:
            self.hover_timer.stop()

        self.opacity_anim.stop()
        self.opacity_anim.setStartValue(1)
        self.opacity_anim.setEndValue(0)
        self.opacity_anim.start()

    def toggle_visibility(self):
        """切换气泡卡片的显示状态"""
        if self.target_widget and self.main_window:
            self.showAt(self.target_widget, self.main_window)

    def _on_animation_finished(self):
        """动画完成回调"""
        if self.windowOpacity() == 0:
            self.hide()
            self.is_visible = False

    def fadeOutAndClose(self):
        self.opacity_anim.stop()
        self.opacity_anim.setStartValue(1)
        self.opacity_anim.setEndValue(0)
        self.opacity_anim.finished.connect(self.close)
        self.opacity_anim.start()

    def update_label_style(self, style: str):
        """动态更新标签样式

        Args:
            style: 新的样式表字符串
        """
        self.label_style = style
        self.label.setStyleSheet(style)
        # 强制重新计算布局
        self.label.updateGeometry()
        self.updateGeometry()

    @staticmethod
    def create_toggle_bubble(
        text: str,
        target_widget,
        main_window,
        text_color: str = "#4772c3",
        response_mode: str = "click",
        arrow_direction: str = "auto",
        label_style: Optional[str] = None,
    ):
        """创建带交互功能的气泡卡片

        Args:
            text: 显示的文本内容
            target_widget: 目标控件
            main_window: 主窗口
            text_color: 文字颜色（当label_style为None时生效）
            response_mode: 响应方式，"click"为点击响应，"hover"为悬浮响应
            arrow_direction: 箭头方向，可选值："up", "down", "left", "right", "auto"（自动计算）
            label_style: 标签样式表，支持完整的QLabel样式定义，如果提供则覆盖默认样式

        Returns:
            BubbleCard: 气泡卡片实例
        """
        bubble = BubbleCard(
            text, main_window, text_color, response_mode, arrow_direction, label_style
        )

        if response_mode == "click":
            # 点击模式：为目标控件添加点击事件
            def on_click():
                bubble.showAt(target_widget, main_window)

            # 保存原始的mousePressEvent
            original_mouse_press = target_widget.mousePressEvent

            def new_mouse_press(event):
                # 先调用原始事件处理
                if original_mouse_press:
                    original_mouse_press(event)
                # 然后处理气泡显示
                on_click()

            target_widget.mousePressEvent = new_mouse_press

        elif response_mode == "hover":
            # hover模式：为目标控件添加鼠标进入/离开事件
            def on_enter():
                if bubble.hover_timer:
                    bubble.hover_timer.stop()
                if not bubble.is_visible:
                    bubble.showAt(target_widget, main_window)

            def on_leave():
                if bubble.hover_timer and bubble.is_visible:
                    bubble.hover_timer.start()

            # 保存原始的enterEvent和leaveEvent
            original_enter = target_widget.enterEvent
            original_leave = target_widget.leaveEvent

            def new_enter_event(event):
                if original_enter:
                    original_enter(event)
                on_enter()

            def new_leave_event(event):
                if original_leave:
                    original_leave(event)
                on_leave()

            target_widget.enterEvent = new_enter_event
            target_widget.leaveEvent = new_leave_event

        return bubble
