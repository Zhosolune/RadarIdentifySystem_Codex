"""选项设置卡组件

提供选项设置功能的卡片组件，使用 QScrollArea 实现无抖动的展开/折叠动画。
header 从左到右依次是：图标、垂直布局的主标签和副标签、弹性空间、选项显示标签、下拉按钮。
content 区域包含可动态添加的单选选项卡。

设计原理：
1. 基于 QScrollArea，利用滚动条动画实现平滑展开/折叠
2. header 固定在 viewport 顶部，content 在 scrollWidget 内
3. 使用 spaceWidget 占位，高度等于 content 高度，确保滚动范围正确
4. 展开时滚动条从 content高度 → 0，折叠时从 0 → maximum
5. 通过 setFixedHeight(header + content - scrollValue) 实时更新整体高度
"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QRadioButton,
    QButtonGroup,
    QScrollArea,
    QFrame,
    QLineEdit,
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve, QPoint, QRect, QRectF, QEvent
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPainterPath, QFont, QPen


class FluentRadioButton(QRadioButton):
    """流畅设计风格的单选按钮"""

    def __init__(self, text: str = "", parent: QWidget = None):
        super().__init__(text, parent)
        self._indicatorColor = QColor("#4772c3")
        self._textColor = QColor("#4772c3")
        self._indicatorPos = QPoint(10, 12)
        self._indicatorRadius = 9
        self._isHover = False
        self.setFixedHeight(24)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFont(QFont("Microsoft YaHei", 10))

    def enterEvent(self, event):
        self._isHover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._isHover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self._drawIndicator(painter)
        self._drawText(painter)

    def _drawText(self, painter: QPainter):
        if not self.isEnabled():
            painter.setOpacity(0.36)
        painter.setFont(self.font())
        painter.setPen(self._textColor)
        text_rect = QRect(28, 0, self.width() - 28, self.height())
        painter.drawText(text_rect, Qt.AlignVCenter, self.text())

    def _drawIndicator(self, painter: QPainter):
        center = self._indicatorPos
        if self.isChecked():
            borderColor = self._indicatorColor if self.isEnabled() else QColor(0, 0, 0, 55)
            filledColor = QColor(255, 255, 255)
            thickness = 4 if (self._isHover and not self.isDown()) else 5
            self._drawCircle(painter, center, self._indicatorRadius, thickness, borderColor, filledColor)
        else:
            if self.isEnabled():
                borderColor = self._indicatorColor if self._isHover else QColor(0, 0, 0, 100)
                filledColor = QColor(0, 0, 0, 15) if self._isHover else QColor(0, 0, 0, 6)
            else:
                borderColor = QColor(0, 0, 0, 55)
                filledColor = Qt.transparent
            self._drawCircle(painter, center, self._indicatorRadius, 1, borderColor, filledColor)

    def _drawCircle(self, painter: QPainter, center: QPoint, radius: int, thickness: int,
                    borderColor: QColor, filledColor: QColor):
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        outerRect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        path.addEllipse(outerRect)
        ir = radius - thickness
        innerRect = QRectF(center.x() - ir, center.y() - ir, 2 * ir, 2 * ir)
        innerPath = QPainterPath()
        innerPath.addEllipse(innerRect)
        ringPath = path.subtracted(innerPath)
        painter.setPen(Qt.NoPen)
        painter.fillPath(ringPath, borderColor)
        painter.fillPath(innerPath, filledColor)

    def setIndicatorColor(self, color: QColor):
        self._indicatorColor = QColor(color)
        self.update()

    def setTextColor(self, color: QColor):
        self._textColor = QColor(color)
        self.update()


class ArrowToggleButton(QPushButton):
    """自定义绘制的箭头切换按钮，带旋转动画"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._arrowColor = QColor("#4772c3")
        self._rotationAngle = 0  # 0度为向下，180度为向上
        self._isHover = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 旋转动画
        self._rotateAni = QPropertyAnimation(self, b'rotationAngle', self)
        self._rotateAni.setEasingCurve(QEasingCurve.OutQuad)
        self._rotateAni.setDuration(200)

    def getRotationAngle(self):
        return self._rotationAngle

    def setRotationAngle(self, angle):
        self._rotationAngle = angle
        self.update()

    # 使用 pyqtProperty 定义 Qt 属性，供动画使用
    rotationAngle = pyqtProperty(float, getRotationAngle, setRotationAngle)

    def enterEvent(self, event):
        self._isHover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._isHover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        # 禁用状态下不绘制 hover 效果
        if self._isHover and self.isEnabled():
            painter.setBrush(QColor("#e6f3ff"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 3, 3)
        self._drawArrow(painter)

    def _drawArrow(self, painter: QPainter):
        center_x = self.width() / 2
        center_y = self.height() / 2
        arrow_width = 4
        arrow_height = 4

        # 应用旋转变换
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self._rotationAngle)
        painter.translate(-center_x, -center_y)

        pen = QPen(self._arrowColor)
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # 始终绘制向下箭头，通过旋转实现方向变化
        path = QPainterPath()
        path.moveTo(center_x - arrow_width, center_y - arrow_height / 2)
        path.lineTo(center_x, center_y + arrow_height / 2)
        path.lineTo(center_x + arrow_width, center_y - arrow_height / 2)
        painter.drawPath(path)
        painter.restore()

    def setExpanded(self, expanded: bool):
        """设置展开状态，触发旋转动画"""
        target_angle = 180 if expanded else 0
        if self._rotationAngle != target_angle:
            self._rotateAni.stop()
            self._rotateAni.setStartValue(self._rotationAngle)
            self._rotateAni.setEndValue(target_angle)
            self._rotateAni.start()

    def setArrowColor(self, color: QColor):
        self._arrowColor = QColor(color)
        self.update()


class CheckConfirmButton(QPushButton):
    """自定义绘制的确认按钮，绘制对号图案"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._bgColor = QColor("#4772c3")
        self._hoverBgColor = QColor("#5c8ad4")
        self._pressBgColor = QColor("#3c61a5")
        self._isHover = False
        self._isPressed = False
        self.setFixedSize(28, 28)  # 与输入框高度一致
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def enterEvent(self, event):
        self._isHover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._isHover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._isPressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._isPressed = False
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)

        # 禁用状态下使用灰色
        if not self.isEnabled():
            painter.setBrush(QColor("#cccccc"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 4, 4)
            # 绘制灰色对号
            self._drawCheck(painter, QColor("#999999"))
            return

        # 绘制背景
        if self._isPressed:
            painter.setBrush(self._pressBgColor)
        elif self._isHover:
            painter.setBrush(self._hoverBgColor)
        else:
            painter.setBrush(self._bgColor)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 4, 4)

        # 绘制对号
        self._drawCheck(painter)

    def _drawCheck(self, painter: QPainter, color: QColor = None):
        """绘制对号图案"""
        # 对号绘制参数
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        # 对号的两个线段
        # 短线：从左下到中间
        short_start_x = center_x - 5
        short_start_y = center_y
        short_end_x = center_x - 1.5
        short_end_y = center_y + 4.5
        
        # 长线：从中间到右上
        long_end_x = center_x + 6
        long_end_y = center_y - 5

        pen = QPen(color if color else QColor("white"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # 绘制对号路径
        path = QPainterPath()
        path.moveTo(short_start_x, short_start_y)
        path.lineTo(short_end_x, short_end_y)
        path.lineTo(long_end_x, long_end_y)
        painter.drawPath(path)


class OptionSettingCard(QScrollArea):
    """选项设置卡组件
    
    基于 QScrollArea 实现无抖动的展开/折叠动画。
    
    Signals:
        option_changed: 选项变化信号，参数为 (选项索引, 选项标签)
    """

    option_changed = pyqtSignal(int, str)
    HEADER_HEIGHT = 60

    def __init__(self, title: str, subtitle: str = "", icon_path: str = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon_path = icon_path
        self._is_expanded = False
        self._options = []
        self._button_group = QButtonGroup(self)
        self._button_group.buttonClicked.connect(self._on_option_clicked)
        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        # 滚动区域基本设置
        self.setWidgetResizable(True)
        self.setFixedHeight(self.HEADER_HEIGHT)
        self.setViewportMargins(0, self.HEADER_HEIGHT, 0, 0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        # 滚动内容容器
        self._scroll_widget = QFrame(self)
        self._scroll_widget.setStyleSheet("background: transparent;")
        self.setWidget(self._scroll_widget)

        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(0)

        # Content 区域（选项列表）
        self._view = QFrame(self._scroll_widget)
        self._view.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #4772c3;
                border-top: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 5px;
                border-bottom-right-radius: 5px;
            }
        """)
        self._view_layout = QVBoxLayout(self._view)
        # 根据是否有图标设置 content 左边距（图标32px + 间距12px = 44px）
        left_margin = 15 + (44 if self._icon_path else 0)
        self._view_layout.setContentsMargins(left_margin, 16, 15, 16)
        self._view_layout.setSpacing(16)

        self._scroll_layout.addWidget(self._view)

        # 占位控件（高度等于 content 高度，确保滚动范围正确）
        self._space_widget = QWidget(self._scroll_widget)
        self._space_widget.setFixedHeight(0)
        self._scroll_layout.addWidget(self._space_widget)

        # Header 区域（固定在 viewport 顶部）
        self._header = QWidget(self)
        self._header.setFixedHeight(self.HEADER_HEIGHT)
        self._header.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #4772c3;
                border-radius: 5px;
            }
        """)

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(15, 10, 15, 10)
        header_layout.setSpacing(12)

        # 左侧图标
        if self._icon_path:
            self._icon_label = QLabel()
            pixmap = QPixmap(self._icon_path)
            if not pixmap.isNull():
                self._icon_label.setPixmap(
                    pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            self._icon_label.setFixedSize(32, 32)
            self._icon_label.setStyleSheet("QLabel { background-color: transparent; border: none; }")
            header_layout.addWidget(self._icon_label)

        # 标签区域
        labels_widget = QWidget()
        labels_widget.setStyleSheet("background-color: transparent; border: none;")
        labels_layout = QVBoxLayout(labels_widget)
        labels_layout.setContentsMargins(0, 0, 0, 0)
        labels_layout.setSpacing(0)

        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet("""
            QLabel { font-size: 16px; color: #4772c3; background-color: transparent; 
                     font-family: "Microsoft YaHei"; border: none; }
        """)
        labels_layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(self._subtitle)
        self._subtitle_label.setStyleSheet("""
            QLabel { font-size: 12px; color: #7a9ad4; background-color: transparent; 
                     font-family: "Microsoft YaHei"; border: none; }
        """)
        labels_layout.addWidget(self._subtitle_label)

        header_layout.addWidget(labels_widget)
        header_layout.addStretch(1)

        # 选项显示标签
        self._option_display_label = QLabel("")
        self._option_display_label.setStyleSheet("""
            QLabel { font-size: 14px; color: #4772c3; background-color: transparent; 
                     font-family: "Microsoft YaHei"; border: none; padding-right: 4px; }
        """)
        header_layout.addWidget(self._option_display_label)

        # 下拉按钮
        self._toggle_btn = ArrowToggleButton()
        self._toggle_btn.clicked.connect(self.toggle)
        header_layout.addWidget(self._toggle_btn)

        # 展开动画 - 对滚动条值进行动画
        self._expand_ani = QPropertyAnimation(self.verticalScrollBar(), b'value', self)
        self._expand_ani.setEasingCurve(QEasingCurve.OutQuad)
        self._expand_ani.setDuration(200)
        self._expand_ani.valueChanged.connect(self._on_expand_value_changed)
        self._expand_ani.finished.connect(self._on_expand_finished)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 安装事件过滤器，防止闪烁
        self._header.installEventFilter(self)

    def eventFilter(self, obj, event):
        """事件过滤器，处理 header 的鼠标事件"""
        if hasattr(self, '_header') and obj is self._header:
            if event.type() == QEvent.Enter:
                self._toggle_btn._isHover = True
                self._toggle_btn.update()
            elif event.type() == QEvent.Leave:
                self._toggle_btn._isHover = False
                self._toggle_btn.update()
            elif event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                pass  # 可以添加按下效果
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._toggle_btn.click()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """调整大小时同步 header 和 scroll_widget 宽度"""
        self._header.resize(self.width(), self.HEADER_HEIGHT)
        self._scroll_widget.resize(self.width(), self._scroll_widget.height())
        super().resizeEvent(event)

    def wheelEvent(self, event):
        """禁用滚轮事件"""
        pass

    def _adjust_view_size(self):
        """调整 view 和 space_widget 大小"""
        h = self._view.sizeHint().height()  # 使用 _view 的 sizeHint，包含边框和边距
        self._space_widget.setFixedHeight(h)
        if self._is_expanded:
            self.setFixedHeight(self.HEADER_HEIGHT + h)

    def _on_expand_value_changed(self):
        """展开动画值变化时更新整体高度"""
        vh = self._view.sizeHint().height()  # content 高度（包含边框和边距）
        h = self.viewportMargins().top()      # header 高度
        # 公式：整体高度 = header + content - 滚动条当前值
        self.setFixedHeight(max(h + vh - self.verticalScrollBar().value(), h))

    def toggle(self):
        """切换展开/折叠状态"""
        self.set_expand(not self._is_expanded)

    def expand(self):
        self.set_expand(True)

    def collapse(self):
        self.set_expand(False)

    def set_expand(self, is_expand: bool):
        """设置展开状态"""
        if self._is_expanded == is_expand:
            return
        if len(self._options) == 0:
            return

        self._adjust_view_size()
        self._is_expanded = is_expand
        self._toggle_btn.setExpanded(is_expand)
        self._header.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #4772c3;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)

        # 启动动画
        if is_expand:
            h = self._view.sizeHint().height()
            self.verticalScrollBar().setValue(h)
            self._expand_ani.setStartValue(h)
            self._expand_ani.setEndValue(0)
            
            # 检测展开后是否会超出父级滚动区域，如果超出则自动滚动
            self._scroll_parent_if_needed(h)
        else:
            self._expand_ani.setStartValue(0)
            self._expand_ani.setEndValue(self.verticalScrollBar().maximum())

        self._expand_ani.start()

    def _scroll_parent_if_needed(self, expand_height: int):
        """检测并滚动父级滚动区域使展开内容可见"""
        # 查找父级 QScrollArea
        parent_scroll_area = None
        parent = self.parent()
        while parent:
            if isinstance(parent, QScrollArea):
                parent_scroll_area = parent
                break
            parent = parent.parent()
        
        if not parent_scroll_area:
            return
        
        # 获取卡片在父级滚动区域中的位置
        card_pos = self.mapTo(parent_scroll_area.viewport(), QPoint(0, 0))
        card_bottom_after_expand = card_pos.y() + self.HEADER_HEIGHT + expand_height
        
        # 获取父级滚动区域的可视高度
        viewport_height = parent_scroll_area.viewport().height()
        current_scroll = parent_scroll_area.verticalScrollBar().value()
        
        # 如果展开后底部超出可视区域，滚动父级使内容可见
        if card_bottom_after_expand > viewport_height:
            # 计算需要滚动的距离
            scroll_needed = card_bottom_after_expand - viewport_height + 10  # 额外10px边距
            new_scroll_value = current_scroll + scroll_needed
            
            # 使用动画平滑滚动
            from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
            scroll_ani = QPropertyAnimation(parent_scroll_area.verticalScrollBar(), b'value', self)
            scroll_ani.setEasingCurve(QEasingCurve.OutCubic)
            scroll_ani.setDuration(250)
            scroll_ani.setStartValue(current_scroll)
            scroll_ani.setEndValue(new_scroll_value)
            scroll_ani.start()

    def _on_expand_finished(self):
        """动画完成回调"""
        if not self._is_expanded:
            # 折叠动画完成后恢复 header 圆角
            self._header.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border: 1px solid #4772c3;
                    border-radius: 5px;
                }
            """)

    def add_option(self, label: str, checked: bool = False) -> int:
        """添加选项"""
        radio_btn = FluentRadioButton(label, self._view)
        radio_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._button_group.addButton(radio_btn, len(self._options))
        self._view_layout.addWidget(radio_btn)
        self._options.append((radio_btn, label))

        if checked:
            radio_btn.setChecked(True)
            self._option_display_label.setText(label)

        self._adjust_view_size()
        return len(self._options) - 1

    def _on_option_clicked(self, button):
        """选项点击处理"""
        index = self._button_group.id(button)
        if 0 <= index < len(self._options):
            label = self._options[index][1]
            self._option_display_label.setText(label)
            self.option_changed.emit(index, label)
            # 点击选项后自动折叠
            if self._is_expanded:
                self.collapse()

    def get_selected_option(self) -> tuple:
        """获取当前选中的选项"""
        checked_btn = self._button_group.checkedButton()
        if checked_btn:
            index = self._button_group.id(checked_btn)
            if 0 <= index < len(self._options):
                return (index, self._options[index][1])
        return (-1, "")

    def get_selected_index(self) -> int:
        """获取当前选中选项的索引"""
        checked_btn = self._button_group.checkedButton()
        if checked_btn:
            return self._button_group.id(checked_btn)
        return -1

    def set_selected_option(self, index: int):
        """设置选中的选项"""
        if 0 <= index < len(self._options):
            self._options[index][0].setChecked(True)
            self._option_display_label.setText(self._options[index][1])

    def clear_options(self):
        """清空所有选项"""
        for radio_btn, label in self._options:
            self._button_group.removeButton(radio_btn)
            self._view_layout.removeWidget(radio_btn)
            radio_btn.deleteLater()
        self._options.clear()
        self._option_display_label.setText("")

    def is_expanded(self) -> bool:
        return self._is_expanded

    def set_title(self, title: str):
        self._title = title
        self._title_label.setText(title)

    def set_subtitle(self, subtitle: str):
        self._subtitle = subtitle
        self._subtitle_label.setText(subtitle)

    def set_enabled(self, enabled: bool):
        """设置启用/禁用状态"""
        self.set_header_enabled(enabled)
        self.set_options_enabled(enabled)
    
    def set_header_enabled(self, enabled: bool):
        """设置 header 区域的启用/禁用状态
        
        当 header 禁用时，无法展开卡片，option 区域的状态不重要
        """
        self._toggle_btn.setEnabled(enabled)
        
        if not enabled:
            if self._is_expanded:
                self.collapse()
            self._header.setStyleSheet("""
                QWidget { background-color: #f5f5f5; border: 1px solid #cccccc; border-radius: 5px; }
            """)
            self._title_label.setStyleSheet("""
                QLabel { font-size: 16px; color: #999999; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._option_display_label.setStyleSheet("""
                QLabel { font-size: 14px; color: #999999; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._toggle_btn.setArrowColor(QColor("#999999"))
        else:
            self._header.setStyleSheet("""
                QWidget { background-color: white; border: 1px solid #4772c3; border-radius: 5px; }
            """)
            self._title_label.setStyleSheet("""
                QLabel { font-size: 16px; color: #4772c3; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._option_display_label.setStyleSheet("""
                QLabel { font-size: 14px; color: #4772c3; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._toggle_btn.setArrowColor(QColor("#4772c3"))
    
    def set_options_enabled(self, enabled: bool):
        """设置选项区域的启用/禁用状态"""
        for radio_btn, label in self._options:
            radio_btn.setEnabled(enabled)

    def is_enabled(self) -> bool:
        return self._toggle_btn.isEnabled()


class InputOptionSettingCard(OptionSettingCard):
    """带输入框的选项设置卡组件
    
    继承自 OptionSettingCard，每个选项后面可附加输入框和单位标签。
    
    Signals:
        value_changed: 值变化信号，参数为 (选项索引, 选项标签, 输入值)
        confirmed: 确认按钮点击后发出，用于通知值已保存
    """

    value_changed = pyqtSignal(int, str, str)
    confirmed = pyqtSignal(int, str, str)  # 确认后发出 (索引, 标签, 值)

    def __init__(self, title: str, subtitle: str = "", icon_path: str = None, parent=None):
        self._input_widgets = []  # 存储 (input, unit_label, unit, confirm_btn) 元组
        self._saved_values = {}   # 存储已保存的值 {index: value}
        super().__init__(title, subtitle, icon_path, parent)

    def add_option_with_input(
        self,
        label: str,
        default_value: str = "",
        unit: str = "",
        placeholder: str = "",
        input_width: int = 120,
        checked: bool = False
    ) -> int:
        """添加带输入框的选项
        
        Args:
            label: 选项标签文字
            default_value: 输入框默认值
            unit: 单位标签（如 "MB", "条"）
            placeholder: 输入框占位文字
            input_width: 输入框宽度
            checked: 是否默认选中
            
        Returns:
            int: 选项索引
        """
        # 创建选项行
        option_row = QWidget()
        option_row.setStyleSheet("background-color: transparent; border: none;")
        option_row.setFixedHeight(32)
        option_layout = QHBoxLayout(option_row)
        option_layout.setContentsMargins(0, 0, 0, 0)
        option_layout.setSpacing(5)

        # 单选按钮
        radio_btn = FluentRadioButton(label, self._view)
        radio_btn.setFixedHeight(24)
        radio_btn.setFixedWidth(240)
        self._button_group.addButton(radio_btn, len(self._options))
        option_layout.addWidget(radio_btn)

        # 输入框
        input_edit = QLineEdit()
        input_edit.setText(default_value)
        input_edit.setPlaceholderText(placeholder)
        input_edit.setFixedSize(input_width, 28)  # 与确认按钮高度一致
        input_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #4772c3;
                border-radius: 3px;
                padding: 3px 5px;
                font-size: 14px;
                color: #4772c3;
                background-color: white;
                font-family: "Microsoft YaHei";
            }
            QLineEdit:focus {
                border: 2px solid #4772c3;
                padding: 2px 5px;
            }
            QLineEdit:disabled {
                border: 1px solid #cccccc;
                background-color: #f5f5f5;
                color: #999999;
            }
        """)
        # 连接 textChanged 用于更新 header 显示，但不发射 value_changed 信号
        input_edit.textChanged.connect(lambda text, idx=len(self._options): self._on_input_changed(idx, text))
        option_layout.addStretch(1)
        option_layout.addWidget(input_edit)

        # 确认按钮
        confirm_btn = CheckConfirmButton(self._view)
        confirm_btn.clicked.connect(lambda checked, idx=len(self._options): self._on_confirm_clicked(idx))
        option_layout.addWidget(confirm_btn)

        # 单位标签
        unit_label = QLabel(unit)
        unit_label.setFixedWidth(30)
        unit_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #4772c3;
                background-color: transparent;
                font-family: "Microsoft YaHei";
                border: none;
            }
        """)
        option_layout.addSpacing(10)
        option_layout.addWidget(unit_label)

        # option_layout.addStretch(1)

        self._view_layout.addWidget(option_row)
        self._options.append((radio_btn, label, option_row))
        self._input_widgets.append((input_edit, unit_label, unit, confirm_btn))  # 增加 confirm_btn

        if checked:
            radio_btn.setChecked(True)
            self._update_display_label(len(self._options) - 1)
            # 启用输入框和按钮
            input_edit.setEnabled(True)
            confirm_btn.setEnabled(True)
        else:
            # 禁用输入框和按钮
            input_edit.setEnabled(False)
            confirm_btn.setEnabled(False)

        self._adjust_view_size()
        return len(self._options) - 1

    def add_option(self, label: str, checked: bool = False) -> int:
        """重写 add_option 方法，为普通选项添加 None 占位符"""
        index = super().add_option(label, checked)
        # 为普通选项添加 None 占位符，保持索引一致
        self._input_widgets.append(None)
        return index

    def _on_input_changed(self, index: int, text: str):
        """输入框值变化处理（不自动更新 header，需点击确认按钮）"""
        # 输入框变化时不再自动更新 header，改为确认后更新
        pass

    def _update_display_label(self, index: int):
        """更新 header 的选项显示标签"""
        if 0 <= index < len(self._options):
            label = self._options[index][1]
            
            # 检查是否有输入框
            if 0 <= index < len(self._input_widgets) and self._input_widgets[index] is not None:
                input_edit, unit_label, unit, confirm_btn = self._input_widgets[index]
                value = input_edit.text()
                if value:
                    display_text = f"{label} {value}{unit}"
                else:
                    display_text = label
            else:
                # 普通选项，只显示标签
                display_text = label
            
            self._option_display_label.setText(display_text)

    def _on_option_clicked(self, button):
        """重写选项点击处理，在选项切换时发射 value_changed 信号"""
        index = self._button_group.id(button)
        if 0 <= index < len(self._options):
            label = self._options[index][1]
            self._update_display_label(index)
            
            # 更新所有选项的启用状态
            for i in range(len(self._input_widgets)):
                widget_tuple = self._input_widgets[i]
                if widget_tuple is not None:  # 只处理带输入框的选项
                    input_edit, unit_label, unit, confirm_btn = widget_tuple
                    if i == index:
                        input_edit.setEnabled(True)
                        confirm_btn.setEnabled(True)
                        unit_label.setStyleSheet("color: #4772c3;") 
                    else:
                        input_edit.setEnabled(False)
                        confirm_btn.setEnabled(False)
                        unit_label.setStyleSheet("color: #999999;")
            
            # 获取当前输入值（如果有）
            if 0 <= index < len(self._input_widgets) and self._input_widgets[index] is not None:
                input_edit = self._input_widgets[index][0]
                current_value = input_edit.text()
                
                # 如果该选项从未保存过值，将当前值视为已保存的初始值
                if index not in self._saved_values:
                    self._saved_values[index] = current_value
                
                self.value_changed.emit(index, label, current_value)
            else:
                # 普通选项，发射0
                self.value_changed.emit(index, label, "0")
            
            self.option_changed.emit(index, label)
            # InputOptionSettingCard 不自动折叠

    def _on_confirm_clicked(self, index: int):
        """确认按钮点击处理"""
        if 0 <= index < len(self._options) and 0 <= index < len(self._input_widgets):
            if self._input_widgets[index] is None:
                return
                
            label = self._options[index][1]
            input_edit = self._input_widgets[index][0]
            value = input_edit.text()
            
            # 保存值
            self._saved_values[index] = value
            
            # 更新 header 显示
            self._update_display_label(index)
            
            # 发射信号
            self.value_changed.emit(index, label, value)
            self.confirmed.emit(index, label, value)
            
            # 自动折叠
            if self._is_expanded:
                self.collapse()

    def get_input_value(self, index: int) -> str:
        """获取指定选项的输入值"""
        if 0 <= index < len(self._input_widgets) and self._input_widgets[index] is not None:
            return self._input_widgets[index][0].text()
        return ""

    def set_input_value(self, index: int, value: str):
        """设置指定选项的输入值，同时标记为已保存"""
        if 0 <= index < len(self._input_widgets) and self._input_widgets[index] is not None:
            self._input_widgets[index][0].setText(value)
            # 同时保存到已保存值，因为这是外部设置的初始值
            self._saved_values[index] = value
            # 更新显示
            checked_btn = self._button_group.checkedButton()
            if checked_btn and self._button_group.id(checked_btn) == index:
                self._update_display_label(index)

    def has_unsaved_changes(self) -> bool:
        """检查是否有未保存的修改
        
        Returns:
            bool: 如果当前输入框的值与已保存的值不同，返回 True
        """
        checked_btn = self._button_group.checkedButton()
        if not checked_btn:
            return False
            
        index = self._button_group.id(checked_btn)
        if index < 0 or index >= len(self._input_widgets):
            return False
            
        if self._input_widgets[index] is None:
            return False  # 普通选项，无输入框
            
        current_value = self._input_widgets[index][0].text()
        saved_value = self._saved_values.get(index, "")
        
        return current_value != saved_value

    def get_selected_value(self) -> tuple:
        """获取当前选中选项的标签和输入值
        
        Returns:
            tuple: (索引, 标签, 输入值)
        """
        checked_btn = self._button_group.checkedButton()
        if checked_btn:
            index = self._button_group.id(checked_btn)
            if 0 <= index < len(self._options):
                label = self._options[index][1]
                value = self.get_input_value(index)
                return (index, label, value)
        return (-1, "", "")

    def clear_options(self):
        """清空所有选项"""
        super().clear_options()
        self._input_widgets.clear()
        self._saved_values.clear()

    def set_enabled(self, enabled: bool):
        """重写设置启用/禁用状态，正确处理3元素元组"""
        self.set_header_enabled(enabled)
        self.set_options_enabled(enabled)
    
    def set_header_enabled(self, enabled: bool):
        """重写设置 header 区域的启用/禁用状态"""
        self._toggle_btn.setEnabled(enabled)
        
        # 根据展开状态确定圆角样式
        if self._is_expanded:
            border_radius_style = "border-top-left-radius: 5px; border-top-right-radius: 5px; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;"
        else:
            border_radius_style = "border-radius: 5px;"
        
        if not enabled:
            if self._is_expanded:
                self.collapse()
            self._header.setStyleSheet("""
                QWidget { background-color: #f5f5f5; border: 1px solid #cccccc; border-radius: 5px; }
            """)
            self._title_label.setStyleSheet("""
                QLabel { font-size: 16px; color: #999999; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._subtitle_label.setStyleSheet("""
                QLabel { font-size: 12px; color: #999999; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._option_display_label.setStyleSheet("""
                QLabel { font-size: 14px; color: #999999; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._toggle_btn.setArrowColor(QColor("#999999"))
        else:
            self._header.setStyleSheet(f"""
                QWidget {{ background-color: white; border: 1px solid #4772c3; {border_radius_style} }}
            """)
            self._title_label.setStyleSheet("""
                QLabel { font-size: 16px; color: #4772c3; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._subtitle_label.setStyleSheet("""
                QLabel { font-size: 12px; color: #7a9ad4; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._option_display_label.setStyleSheet("""
                QLabel { font-size: 14px; color: #4772c3; background-color: transparent; 
                         font-family: "Microsoft YaHei"; border: none; }
            """)
            self._toggle_btn.setArrowColor(QColor("#4772c3"))
    
    def set_options_enabled(self, enabled: bool):
        """重写设置选项区域的启用/禁用状态"""
        for option_tuple in self._options:
            radio_btn = option_tuple[0]
            radio_btn.setEnabled(enabled)
        
        # 同时控制所有输入框组合
        for idx in range(len(self._input_widgets)):
            self.set_input_widget_enabled(idx, enabled)
    
    def set_input_widget_enabled(self, index: int, enabled: bool):
        """设置指定选项的输入框组合组件（输入框+确认按钮+标签）的启用/禁用状态
        
        Args:
            index: 选项索引
            enabled: 是否启用
        """
        if 0 <= index < len(self._input_widgets):
            widget_tuple = self._input_widgets[index]
            if widget_tuple is not None:
                input_edit, unit_label, unit, confirm_btn = widget_tuple
                input_edit.setEnabled(enabled)
                confirm_btn.setEnabled(enabled)
                
                if not enabled:
                    input_edit.setStyleSheet("""
                        QLineEdit {
                            border: 1px solid #cccccc;
                            border-radius: 3px;
                            padding: 2px 6px;
                            background-color: #f5f5f5;
                            color: #999999;
                        }
                    """)
                    unit_label.setStyleSheet("color: #999999; font-size: 12px;")
                else:
                    input_edit.setStyleSheet("""
                        QLineEdit {
                            border: 1px solid #4772c3;
                            border-radius: 3px;
                            padding: 2px 6px;
                            background-color: white;
                            color: #4772c3;
                        }
                        QLineEdit:focus {
                            border: 1.5px solid #4772c3;
                        }
                    """)
                    unit_label.setStyleSheet("color: #4772c3; font-size: 12px;")

