"""命令栏组件

提供类似Windows 11风格的命令栏，包含图标按钮和下拉菜单。
"""

from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QMenu,
    QAction,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QDateTime
from PyQt5.QtGui import QIcon


from common.paths import Paths

class CommandButton(QPushButton):
    """命令栏按钮"""

    def __init__(self, icon_path: str = None, text: str = "", parent=None):
        super().__init__(parent)
        if icon_path:
            self.setIcon(QIcon(icon_path))
        if text:
            # 在文本前添加空格以创建图标与文字间距
            self.setText(" " + text)

        # 设置图标大小为20px
        self.setIconSize(QSize(16, 16))

        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 6px 6px;
                color: #4772c3;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)


class DropdownButton(QWidget):
    """带下拉箭头的按钮"""

    clicked = pyqtSignal()

    def __init__(self, icon_path: str = None, text: str = "", parent=None):
        super().__init__(parent)
        self._is_expanded = False
        self._is_hovered = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 主按钮部分
        self._main_btn = QPushButton()
        self._main_btn.setCursor(Qt.PointingHandCursor)
        if icon_path:
            self._main_btn.setIcon(QIcon(icon_path))
        if text:
            self._main_btn.setText(" " + text)
        self._main_btn.setIconSize(QSize(16, 16))
        self._main_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px;
                color: #4772c3;
                font-size: 12px;
            }
        """)
        layout.addWidget(self._main_btn)

        # 箭头图标
        from PyQt5.QtWidgets import QLabel
        from PyQt5.QtGui import QPixmap
        self._arrow_label = QLabel()
        self._arrow_label.setStyleSheet("border: none; background: transparent;")# 加载箭头图标
        self._arrow_down = QPixmap(str(Paths.get_resource_path("resources/icons/down.png"))).scaled(12, 12, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._arrow_up = QPixmap(str(Paths.get_resource_path("resources/icons/up.png"))).scaled(12, 12, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._arrow_label.setPixmap(self._arrow_down)
        self._arrow_label.setFixedSize(12, 12)
        layout.addWidget(self._arrow_label)

        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

        # 连接信号
        self._main_btn.clicked.connect(self._on_click)

    def _on_click(self):
        """点击事件"""
        self._is_expanded = not self._is_expanded
        self._update_arrow()
        self.clicked.emit()

    def _update_arrow(self):
        """更新箭头方向"""
        if self._is_expanded:
            self._arrow_label.setPixmap(self._arrow_up)
        else:
            self._arrow_label.setPixmap(self._arrow_down)

    def set_expanded(self, expanded: bool):
        """设置展开状态"""
        self._is_expanded = expanded
        self._update_arrow()

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        self._on_click()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        """鼠标进入"""
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        """绘制hover背景"""
        from PyQt5.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._is_hovered:
            painter.setBrush(QColor(0, 0, 0, 13))  # rgba(0,0,0,0.05)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 4, 4)

        super().paintEvent(event)



class CommandBar(QWidget):
    """命令栏组件

    提供刷新、删除、排序等操作按钮。

    Signals:
        refresh_clicked: 刷新按钮点击信号
        delete_clicked: 删除按钮点击信号
        sort_changed: 排序方式改变信号，参数为排序类型字符串
    """

    refresh_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    sort_changed = pyqtSignal(str)
    parse_clicked = pyqtSignal()
    strategy_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_menu_close_time = 0
        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        # 刷新按钮
        self._refresh_btn = CommandButton(
            icon_path=str(Paths.get_resource_path("resources/icons/refresh.png")),
            text="刷新"
        )
        self._refresh_btn.clicked.connect(self.refresh_clicked.emit)
        layout.addWidget(self._refresh_btn)

        # 删除按钮
        self._delete_btn = CommandButton(
            icon_path=str(Paths.get_resource_path("resources/icons/delete.png")),
            text="移除"
        )
        self._delete_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self._delete_btn)

        # 分隔线
        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #E5E5E5;")
        layout.addWidget(separator)

        # 排序下拉按钮
        self._sort_btn = DropdownButton(
            icon_path=str(Paths.get_resource_path("resources/icons/sort.png")),
            text="排序"
        )
        self._sort_btn.clicked.connect(self._show_sort_menu)
        layout.addWidget(self._sort_btn)

        # === BIN文件选项区域（默认隐藏） ===
        # 分隔线2
        self._strategy_separator = QWidget()
        self._strategy_separator.setFixedWidth(1)
        self._strategy_separator.setStyleSheet("background-color: #E5E5E5;")
        self._strategy_separator.hide()
        layout.addWidget(self._strategy_separator)

        # 选项下拉按钮
        self._strategy_btn = DropdownButton(
            icon_path=str(Paths.get_resource_path("resources/icons/option.png")),
            text="选项"
        )
        self._strategy_btn.clicked.connect(self._show_strategy_menu)
        self._strategy_btn.hide()
        layout.addWidget(self._strategy_btn)

        # 右侧弹性空间
        layout.addStretch(1)

        # 解析按钮（最右侧）
        self._parse_btn = CommandButton(
            icon_path=str(Paths.get_resource_path("resources/icons/parse.png")),
            text=" 解析"
        )
        self._parse_btn.clicked.connect(self.parse_clicked.emit)
        layout.addWidget(self._parse_btn)

        # 创建排序菜单
        self._sort_menu = QMenu(self)
        # 移除菜单阴影
        self._sort_menu.setWindowFlags(self._sort_menu.windowFlags() | Qt.NoDropShadowWindowHint)
        self._sort_menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
            }
            QMenu::item {
                border-radius: 4px;
                padding: 2px 15px 2px 0px;
                color: #4772c3;
            }
            QMenu::item:selected {
                background-color: rgba(71, 114, 195, 0.1);
            }
            QMenu::indicator {
                width: 6px;
                height: 6px;
                margin-left: 15px;
                margin-right: 15px;
                border-radius: 3px;
            }
            QMenu::indicator:checked {
                background-color: #4772c3;
            }
            QMenu::indicator:unchecked {
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e0e0e0;
                margin: 5px 10px;
            }
        """)

        # 排序选项（排序字段）
        self._sort_field_actions = {}
        self._current_sort_field = "name"
        self._add_sort_field_action("名称", "name")
        self._add_sort_field_action("修改日期", "date")
        self._add_sort_field_action("大小", "size")

        self._sort_menu.addSeparator()

        # 排序方向
        self._sort_order_actions = {}
        self._current_sort_order = "asc"
        self._add_sort_order_action("升序", "asc")
        self._add_sort_order_action("降序", "desc")

        # === 创建策略菜单 ===
        self._strategy_menu = QMenu(self)
        self._strategy_menu.setWindowFlags(self._strategy_menu.windowFlags() | Qt.NoDropShadowWindowHint)
        self._strategy_menu.setStyleSheet(self._sort_menu.styleSheet())  # 复用排序菜单样式

        # 策略选项
        self._strategy_actions = {}
        self._current_strategy = "amplitude"  # 默认使用比幅
        self._add_strategy_action("使用比幅", "amplitude")
        self._add_strategy_action("使用干涉仪", "interferometer")

    def _add_sort_field_action(self, text: str, sort_type: str):
        """添加排序字段选项"""
        action = QAction(text, self)
        action.setCheckable(True)
        action.setChecked(sort_type == self._current_sort_field)
        action.triggered.connect(lambda: self._on_sort_field_selected(sort_type))
        self._sort_menu.addAction(action)
        self._sort_field_actions[sort_type] = action

    def _add_sort_order_action(self, text: str, sort_type: str):
        """添加排序方向选项"""
        action = QAction(text, self)
        action.setCheckable(True)
        action.setChecked(sort_type == self._current_sort_order)
        action.triggered.connect(lambda: self._on_sort_order_selected(sort_type))
        self._sort_menu.addAction(action)
        self._sort_order_actions[sort_type] = action

    def _show_sort_menu(self):
        """显示排序菜单"""
        # 防止菜单刚关闭时立即重新打开
        current_time = QDateTime.currentMSecsSinceEpoch()
        if current_time - self._last_menu_close_time < 300:
            self._sort_btn.set_expanded(False)
            return

        # 在按钮下方显示菜单
        pos = self._sort_btn.mapToGlobal(
            self._sort_btn.rect().bottomLeft()
        )
        self._sort_menu.exec_(pos)
        # 记录关闭时间
        self._last_menu_close_time = QDateTime.currentMSecsSinceEpoch()
        # 菜单关闭后重置箭头状态
        self._sort_btn.set_expanded(False)

    def _on_sort_field_selected(self, sort_type: str):
        """排序字段选中"""
        self._current_sort_field = sort_type
        # 更新选中状态
        for key, action in self._sort_field_actions.items():
            action.setChecked(key == sort_type)
        self.sort_changed.emit(sort_type)

    def _on_sort_order_selected(self, sort_type: str):
        """排序方向选中"""
        self._current_sort_order = sort_type
        # 更新选中状态
        for key, action in self._sort_order_actions.items():
            action.setChecked(key == sort_type)
        self.sort_changed.emit(sort_type)

    def _add_strategy_action(self, text: str, strategy_type: str):
        """添加策略选项"""
        action = QAction(text, self)
        action.setCheckable(True)
        action.setChecked(strategy_type == self._current_strategy)
        action.triggered.connect(lambda: self._on_strategy_selected(strategy_type))
        self._strategy_menu.addAction(action)
        self._strategy_actions[strategy_type] = action

    def _show_strategy_menu(self):
        """显示策略菜单"""
        # 防止菜单刚关闭时立即重新打开
        current_time = QDateTime.currentMSecsSinceEpoch()
        if current_time - self._last_menu_close_time < 300:
            self._strategy_btn.set_expanded(False)
            return

        pos = self._strategy_btn.mapToGlobal(
            self._strategy_btn.rect().bottomLeft()
        )
        self._strategy_menu.exec_(pos)
        # 记录关闭时间
        self._last_menu_close_time = QDateTime.currentMSecsSinceEpoch()
        # 菜单关闭后重置箭头状态
        self._strategy_btn.set_expanded(False)

    def _on_strategy_selected(self, strategy_type: str):
        """策略选项选中"""
        self._current_strategy = strategy_type
        # 更新选中状态
        for key, action in self._strategy_actions.items():
            action.setChecked(key == strategy_type)
        self.strategy_changed.emit(strategy_type)

    def set_bin_mode(self, is_bin: bool):
        """设置是否为BIN文件模式，控制选项按钮的显示
        
        Args:
            is_bin: True表示当前为BIN文件模式，显示选项按钮
        """
        self._strategy_separator.setVisible(is_bin)
        self._strategy_btn.setVisible(is_bin)

    def get_current_strategy(self) -> str:
        """获取当前策略
        
        Returns:
            str: 'amplitude' 或 'interferometer'
        """
        return self._current_strategy
