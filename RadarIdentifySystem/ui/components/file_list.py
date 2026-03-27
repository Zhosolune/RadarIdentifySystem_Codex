"""文件列表组件

提供文件列表显示功能，包含文件名、修改日期、大小信息。
"""

import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer


class FileListItem(QFrame):
    """文件列表项"""

    clicked = pyqtSignal(str)  # 点击信号，传递文件路径
    selected_changed = pyqtSignal(str, bool)  # 选中状态改变

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._is_selected = False
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(5)

        # 获取文件信息
        file_name = os.path.basename(self._file_path)
        try:
            stat = os.stat(self._file_path)
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            size = self._format_size(stat.st_size)
        except OSError:
            mod_time = "未知"
            size = "未知"
        
        label_style = """
            color: #4772c3;
            font-size: 12px;
            font-family: "Microsoft YaHei";
        """

        # 文件名
        name_label = QLabel(file_name)
        name_label.setStyleSheet(label_style)
        name_label.setMinimumWidth(200)
        layout.addWidget(name_label, 3)

        # 修改日期
        date_label = QLabel(mod_time)
        date_label.setStyleSheet(label_style)
        date_label.setMinimumWidth(120)
        layout.addWidget(date_label, 2)

        # 大小
        size_label = QLabel(size)
        size_label.setStyleSheet(label_style)
        size_label.setMinimumWidth(80)
        size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(size_label, 1)

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def _update_style(self):
        """更新样式"""
        if self._is_selected:
            self.setStyleSheet("""
                FileListItem {
                    background-color: rgba(71, 114, 195, 0.1);
                    border-top: 1px dashed #4772c3;
                    border-bottom: 1px dashed #4772c3;
                    padding: 2px;
                    border-radius: none;
                }
            """)
        else:
            self.setStyleSheet("""
                FileListItem {
                    background-color: transparent;
                    border: none;
                    padding: 3px;
                }
                FileListItem:hover {
                    background-color: rgba(0, 0, 0, 0.03);
                }
            """)

    def mousePressEvent(self, event):
        """鼠标点击 - 只发出信号，由父组件处理选中逻辑"""
        self.clicked.emit(self._file_path)
        super().mousePressEvent(event)

    def file_path(self) -> str:
        """获取文件路径"""
        return self._file_path

    def is_selected(self) -> bool:
        """是否被选中"""
        return self._is_selected

    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        self._update_style()


class DirectorySeparatorItem(QFrame):
    """目录分组分割线组件"""

    def __init__(self, directory_path: str, parent=None):
        """初始化分割线组件

        Args:
            directory_path: 目录路径
            parent: 父控件
        """
        super().__init__(parent)
        self._directory_path = directory_path
        self._marquee_timer = QTimer(self)
        self._marquee_timer.setInterval(30)
        self._marquee_timer.timeout.connect(self._on_marquee_tick)
        self._marquee_step = 1
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background-color: #eaf2ff;")
        self.setMinimumHeight(17)
        self.setMaximumHeight(17)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_line = QFrame()
        top_line.setFixedHeight(1)
        top_line.setStyleSheet("background-color: #d0d0d0;")
        top_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        bottom_line = QFrame()
        bottom_line.setFixedHeight(1)
        bottom_line.setStyleSheet("background-color: #d0d0d0;")
        bottom_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._label = QLabel(self._directory_path)
        self._label.setStyleSheet("""
            QLabel {
                color: #6c7a99;
                font-size: 10px;
                font-family: "Microsoft YaHei";
                background-color: transparent;
                margin-left: 15px;
            }
        """)
        # self._label.setFixedHeight(10)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._label_scroll_area = QScrollArea()
        self._label_scroll_area.setFrameShape(QFrame.NoFrame)
        self._label_scroll_area.setWidgetResizable(False)
        self._label_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._label_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._label_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._label_scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        self._label_scroll_area.setWidget(self._label)

        layout.addWidget(top_line)
        layout.addWidget(self._label_scroll_area)
        # layout.addWidget(bottom_line)

    def showEvent(self, event):
        """显示事件处理"""
        super().showEvent(event)
        self._update_marquee_state()

    def resizeEvent(self, event):
        """尺寸变化事件处理"""
        super().resizeEvent(event)
        self._update_marquee_state()

    def _on_marquee_tick(self):
        """走马灯滚动步进处理"""
        scroll_bar = self._label_scroll_area.horizontalScrollBar()
        if scroll_bar.maximum() <= 0:
            self._marquee_timer.stop()
            return
        value = scroll_bar.value() + self._marquee_step
        if value > scroll_bar.maximum():
            value = 0
        scroll_bar.setValue(value)

    def _update_marquee_state(self):
        """更新走马灯状态"""
        if not self.isVisible():
            return
        self._label.adjustSize()
        scroll_bar = self._label_scroll_area.horizontalScrollBar()
        if scroll_bar.maximum() > 0:
            if not self._marquee_timer.isActive():
                self._marquee_timer.start()
        else:
            self._marquee_timer.stop()
            scroll_bar.setValue(0)

    def directory_path(self) -> str:
        """获取目录路径"""
        return self._directory_path


class FileListWidget(QWidget):
    """文件列表组件"""

    file_selected = pyqtSignal(str)  # 文件选中信号
    selection_changed = pyqtSignal(bool)  # 选中状态改变（True=有文件被选中）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._selected_item = None  # 当前选中的项
        self._last_directory = None
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_style = """
            color: #4772c3;
            font-size: 12px;
            font-family: "Microsoft YaHei";
        """

        # 列表头
        header = QWidget()
        header.setStyleSheet(header_style)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 4, 15, 4)
        header_layout.setSpacing(10)

        header_name = QLabel("文件名")
        header_name.setStyleSheet(header_style)
        header_name.setMinimumWidth(200)
        header_layout.addWidget(header_name, 3)

        header_date = QLabel("修改日期")
        header_date.setStyleSheet(header_style)
        header_date.setMinimumWidth(120)
        header_layout.addWidget(header_date, 2)

        header_size = QLabel("大小")
        header_size.setStyleSheet(header_style)
        header_size.setMinimumWidth(80)
        header_size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(header_size, 1)

        layout.addWidget(header)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #4772c3;
                min-height: 30px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3a5fa0;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        # 列表容器
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background-color: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)

        scroll.setWidget(self._list_container)
        
        # 为滚动区域添加点击事件，点击空白区域取消选中
        self._scroll_area = scroll
        scroll.viewport().installEventFilter(self)
        
        layout.addWidget(scroll, 1)

        # 空状态提示
        self._empty_label = QLabel("暂无文件")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #999999; font-size: 14px;")
        self._empty_label.hide()

    def clear(self):
        """清空列表"""
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._items.clear()
        self._selected_item = None
        self._last_directory = None
        self.selection_changed.emit(False)

    def add_file(self, file_path: str):
        """添加文件"""
        directory = os.path.dirname(file_path)
        if self._last_directory != directory:
            separator = DirectorySeparatorItem(directory)
            self._list_layout.insertWidget(self._list_layout.count() - 1, separator)
            self._last_directory = directory
        item = FileListItem(file_path)
        item.clicked.connect(lambda path: self._on_item_clicked(item))
        self._items.append(item)
        # 在stretch之前插入
        self._list_layout.insertWidget(self._list_layout.count() - 1, item)

    def _on_item_clicked(self, item: FileListItem):
        """处理列表项点击，实现单选逻辑"""
        if self._selected_item == item:
            # 点击已选中的项，取消选中
            item.set_selected(False)
            self._selected_item = None
            self.selection_changed.emit(False)
        else:
            # 取消之前的选中
            if self._selected_item:
                self._selected_item.set_selected(False)
            # 选中当前项
            self._selected_item = item
            item.set_selected(True)
            self.selection_changed.emit(True)
            self.file_selected.emit(item.file_path())

    def set_files(self, file_paths: list):
        """设置文件列表"""
        self.clear()
        sorted_files = sorted(
            file_paths,
            key=lambda path: (os.path.normcase(os.path.dirname(path)), os.path.normcase(path)),
        )
        for path in sorted_files:
            self.add_file(path)

    def get_selected_file(self) -> str:
        """获取选中的文件（单选）"""
        if self._selected_item:
            return self._selected_item.file_path()
        return None

    def get_selected_files(self) -> list:
        """获取选中的文件列表（兼容）"""
        if self._selected_item:
            return [self._selected_item.file_path()]
        return []

    def has_selection(self) -> bool:
        """是否有文件被选中"""
        return self._selected_item is not None

    def clear_selection(self):
        """清除选中状态"""
        if self._selected_item:
            self._selected_item.set_selected(False)
            self._selected_item = None
            self.selection_changed.emit(False)

    def file_count(self) -> int:
        """获取文件数量"""
        return len(self._items)

    def eventFilter(self, obj, event):
        """事件过滤器 - 点击滚动区域空白处取消选中"""
        from PyQt5.QtCore import QEvent
        
        if obj == self._scroll_area.viewport() and event.type() == QEvent.MouseButtonPress:
            # 检查点击位置是否在文件项上
            click_pos = event.pos()
            widget_at_pos = self._scroll_area.viewport().childAt(click_pos)
            
            # 如果没有点击到任何子widget，或者点击的是容器本身
            if widget_at_pos is None or widget_at_pos == self._list_container:
                self.clear_selection()
                
        return super().eventFilter(obj, event)
