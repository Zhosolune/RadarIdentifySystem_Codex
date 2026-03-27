"""流式复选设置卡组件

提供流式布局的复选选项设置卡片，用于多选波段导出等场景。
"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QEvent
from PyQt5.QtGui import QPixmap, QColor, QMouseEvent, QResizeEvent

from .option_setting_card import ArrowToggleButton


class FluentCheckBox(QFrame):
    """流畅设计风格的复选框 - 仿DashboardCard样式"""
    stateChanged = pyqtSignal(int)

    def __init__(self, text: str = "", parent: QWidget = None, height: int = 60, font_size: int = 16) -> None:
        """初始化流畅设计风格的复选框

        Args:
            text (str): 显示文本
            parent (QWidget): 父组件，默认None
            height (int): 卡片高度，默认60
            font_size (int): 文本字号，默认16

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        super().__init__(parent)
        self._text = text
        self._checked = False
        self._height = height
        self._font_size = font_size
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """设置界面并复用 DashboardCard 样式

        Args:
            None: 无参数

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(self._height)
        
        # 添加阴影效果 (与 DashboardCard 一致)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setAlignment(Qt.AlignCenter)

        # 标签
        self._label_widget = QLabel(self._text)
        self._label_widget.setObjectName("text_label")
        self._label_widget.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label_widget)

        self._check_badge = QLabel(self)
        self._check_badge.setObjectName("check_badge")
        self._check_badge.setAlignment(Qt.AlignCenter)
        self._check_badge.setFixedSize(18, 18)
        self._check_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._set_check_badge_icon()
        self._update_check_badge_position()

        # 初始样式
        self._update_style()

    def _update_style(self) -> None:
        """更新选中与未选中样式

        Args:
            None: 无参数

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        # 基础样式复用 DashboardCard，选中时添加蓝色边框
        border = "1px solid #4772c3" if self._checked else "1px solid transparent"
        
        self.setStyleSheet(f"""
            FluentCheckBox {{
                background-color: white;
                border: {border};
                border-radius: 8px;
            }}
            QLabel#text_label {{
                color: #4772c3;
                font-size: {self._font_size}px;
                font-family: "Microsoft YaHei";
                background: transparent;
                border: none;
            }}
            QLabel#check_badge {{
                background: transparent;
                border: none;
            }}
        """)
        self._check_badge.setVisible(self._checked)

    def _set_check_badge_icon(self) -> None:
        """设置对号图标

        Args:
            None: 无参数

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        icon_path = str(Paths.get_resource_path("resources/icons/checked.png"))
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            self._check_badge.setPixmap(
                pixmap.scaled(
                    self._check_badge.width(),
                    self._check_badge.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

    def _update_check_badge_position(self) -> None:
        """更新对号标记位置

        Args:
            None: 无参数

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        margin = -2
        x = self.width() - self._check_badge.width() - margin
        y = self.height() - self._check_badge.height() - margin
        self._check_badge.move(max(x, 0), max(y, 0))

    def isChecked(self) -> bool:
        """获取当前选中状态

        Returns:
            bool: 是否选中

        Raises:
            None: 不抛出异常
        """
        return self._checked

    def setChecked(self, checked: bool) -> None:
        """设置选中状态

        Args:
            checked (bool): 是否选中

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        if self._checked != checked:
            self._checked = checked
            self._update_style()
            self.stateChanged.emit(Qt.Checked if checked else Qt.Unchecked)

    def text(self) -> str:
        """获取显示文本

        Returns:
            str: 文本内容

        Raises:
            None: 不抛出异常
        """
        return self._text

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """点击切换状态"""
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setChecked(not self._checked)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """尺寸变化事件"""
        super().resizeEvent(event)
        self._update_check_badge_position()

    # 移除 paintEvent 相关方法，使用原生样式


    def setIndicatorColor(self, color: QColor) -> None:
        """设置指示器颜色

        Args:
            color (QColor): 颜色值

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        self._indicatorColor = QColor(color)
        self.update()

    def setTextColor(self, color: QColor) -> None:
        """设置文本颜色

        Args:
            color (QColor): 颜色值

        Returns:
            None: 无返回值

        Raises:
            None: 不抛出异常
        """
        self._textColor = QColor(color)
        self.update()


class FlowLayout(QVBoxLayout):
    """简易流式布局 - 使用多行水平布局模拟"""
    
    def __init__(self, parent=None, items_per_row=4, h_spacing=10, v_spacing=10):
        super().__init__(parent)
        self._items_per_row = items_per_row
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._widgets = []
        self._rows = []  # 存储行布局
        self.setSpacing(v_spacing)
        self.setContentsMargins(0, 0, 0, 0)
    
    def addFlowWidget(self, widget: QWidget):
        """添加流式布局的组件"""
        self._widgets.append(widget)
        self._relayout()
    
    def clearWidgets(self):
        """清空所有组件"""
        for widget in self._widgets:
            widget.setParent(None)
        self._widgets.clear()
        
        # 清空行布局
        for row in self._rows:
            self.removeItem(row)
            while row.count():
                item = row.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
        self._rows.clear()
    
    def _relayout(self):
        """重新布局"""
        # 清空旧行布局
        for row in self._rows:
            while row.count():
                row.takeAt(0)
            self.removeItem(row)
        self._rows.clear()
        
        # 创建新行布局
        current_row = None
        for i, widget in enumerate(self._widgets):
            if i % self._items_per_row == 0:
                current_row = QHBoxLayout()
                current_row.setSpacing(self._h_spacing)
                current_row.setContentsMargins(0, 0, 0, 0)
                self._rows.append(current_row)
                self.addLayout(current_row)
            current_row.addWidget(widget)
        
        # 最后一行添加弹性空间
        if current_row and current_row.count() < self._items_per_row:
            current_row.addStretch()


from common.paths import Paths

class FlowCheckSettingCard(QScrollArea):
    """流式复选设置卡组件
    
    使用流式布局展示可多选的复选框选项，用于波段选择等场景。
    
    Signals:
        selection_changed: 选择变化信号，参数为选中的标签列表
    """

    selection_changed = pyqtSignal(list)
    HEADER_HEIGHT = 60

    def __init__(self, title: str, subtitle: str = "", icon_path: str = None, 
                 items_per_row: int = 4, parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon_path = icon_path
        self._is_expanded = False
        self._items_per_row = items_per_row
        self._checkboxes = []  # 存储 (checkbox, label) 元组
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

        # Content 区域（流式布局的复选框）
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
        left_margin = 15 + (44 if self._icon_path else 0)
        self._view_layout.setContentsMargins(left_margin, 16, 15, 16)
        self._view_layout.setSpacing(10)
        
        # 流式布局容器
        self._flow_layout = FlowLayout(items_per_row=self._items_per_row)
        self._view_layout.addLayout(self._flow_layout)

        self._scroll_layout.addWidget(self._view)

        # 占位控件
        self._space_widget = QWidget(self._scroll_widget)
        self._space_widget.setFixedHeight(0)
        self._scroll_layout.addWidget(self._space_widget)

        # Header 区域
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

        # 展开动画
        self._expand_ani = QPropertyAnimation(self.verticalScrollBar(), b'value', self)
        self._expand_ani.setEasingCurve(QEasingCurve.OutQuad)
        self._expand_ani.setDuration(200)
        self._expand_ani.valueChanged.connect(self._on_expand_value_changed)
        self._expand_ani.finished.connect(self._on_expand_finished)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._header.installEventFilter(self)

    def eventFilter(self, obj, event):
        """事件过滤器"""
        if hasattr(self, '_header') and obj is self._header:
            if event.type() == QEvent.Enter:
                self._toggle_btn._isHover = True
                self._toggle_btn.update()
            elif event.type() == QEvent.Leave:
                self._toggle_btn._isHover = False
                self._toggle_btn.update()
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._toggle_btn.click()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """调整大小事件"""
        super().resizeEvent(event)
        self._header.setFixedWidth(self.width())
        self._scroll_widget.setFixedWidth(self.width())

    def wheelEvent(self, event):
        """禁用滚轮事件"""
        event.ignore()

    def _adjust_view_size(self):
        """调整大小"""
        view_height = self._view.sizeHint().height()
        self._view.setFixedHeight(view_height)
        self._space_widget.setFixedHeight(view_height)

    def _on_expand_value_changed(self):
        """展开动画值变化"""
        scroll_value = self.verticalScrollBar().value()
        expand_height = self._view.height() - scroll_value
        new_height = self.HEADER_HEIGHT + expand_height
        self.setFixedHeight(new_height)

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

        self._is_expanded = is_expand
        self._toggle_btn.setExpanded(is_expand)

        if is_expand:
            self._adjust_view_size()
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
            self._expand_ani.stop()
            self._expand_ani.setStartValue(self._view.height())
            self._expand_ani.setEndValue(0)
            self._expand_ani.start()
        else:
            self._expand_ani.stop()
            self._expand_ani.setStartValue(self.verticalScrollBar().value())
            self._expand_ani.setEndValue(self._view.height())
            self._expand_ani.start()

    def _on_expand_finished(self):
        """动画完成回调"""
        if not self._is_expanded:
            self.setFixedHeight(self.HEADER_HEIGHT)
            self._header.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border: 1px solid #4772c3;
                    border-radius: 5px;
                }
            """)

    def add_option(self, label: str, checked: bool = True) -> int:
        """添加复选选项
        
        Args:
            label: 选项标签
            checked: 是否默认选中
            
        Returns:
            int: 选项索引
        """
        # 使用较小的高度和字体，以适应设置卡片
        checkbox = FluentCheckBox(f"{label}", height=36, font_size=16)
        checkbox.setChecked(checked)
        checkbox.setFixedWidth(80)
        checkbox.stateChanged.connect(self._on_checkbox_changed)
        
        self._checkboxes.append((checkbox, label))
        self._flow_layout.addFlowWidget(checkbox)
        self._adjust_view_size()
        self._update_display_label()
        
        return len(self._checkboxes) - 1

    def _on_checkbox_changed(self, state):
        """复选框状态变化处理"""
        self._update_display_label()
        selected = self.get_selected_labels()
        self.selection_changed.emit(selected)

    def _update_display_label(self):
        """更新 header 的选项显示标签"""
        selected = self.get_selected_labels()
        if selected:
            display_text = "、".join([f"{label}" for label in selected])
            # 如果太长，截断显示
            if len(display_text) > 30:
                display_text = display_text[:27] + "..."
            self._option_display_label.setText(display_text)
        else:
            self._option_display_label.setText("未选择")

    def get_selected_labels(self) -> list:
        """获取选中的标签列表"""
        return [label for checkbox, label in self._checkboxes if checkbox.isChecked()]

    def get_selected_indices(self) -> list:
        """获取选中的索引列表"""
        return [i for i, (checkbox, _) in enumerate(self._checkboxes) if checkbox.isChecked()]

    def set_option_checked(self, index: int, checked: bool):
        """设置指定选项的选中状态"""
        if 0 <= index < len(self._checkboxes):
            self._checkboxes[index][0].setChecked(checked)

    def select_all(self):
        """全选"""
        for checkbox, _ in self._checkboxes:
            checkbox.setChecked(True)

    def select_none(self):
        """取消全选"""
        for checkbox, _ in self._checkboxes:
            checkbox.setChecked(False)

    def clear_options(self):
        """清空所有选项"""
        self._flow_layout.clearWidgets()
        self._checkboxes.clear()
        self._update_display_label()
        self._adjust_view_size()

    def is_expanded(self) -> bool:
        return self._is_expanded

    def set_enabled(self, enabled: bool):
        """设置启用/禁用状态"""
        self._toggle_btn.setEnabled(enabled)
        for checkbox, _ in self._checkboxes:
            checkbox.setEnabled(enabled)
        
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
