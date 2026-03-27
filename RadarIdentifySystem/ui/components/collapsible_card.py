"""可折叠卡片组件

提供可折叠/展开的卡片容器，包含 header 和 contents 两个区域。
header 包含图标、标签、操作按钮和展开/折叠按钮。
contents 区域可容纳多个 ContentItemCard 子项。
"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QPixmap

from .content_item_card import ContentItemCard


class CollapsibleCard(QWidget):
    """可折叠卡片组件

    可展开/折叠的卡片容器，header 区域始终显示，contents 区域可折叠。

    Signals:
        expanded: 卡片展开信号
        collapsed: 卡片折叠信号
        action_clicked: 操作按钮点击信号
    """

    expanded = pyqtSignal()
    collapsed = pyqtSignal()
    action_clicked = pyqtSignal()

    def __init__(
        self, title: str, icon_path: str = None, action_text: str = None, parent=None
    ):
        """初始化可折叠卡片

        Args:
            title: 卡片标题
            icon_path: 图标路径（可选）
            action_text: 操作按钮文字（可选，为空则不显示）
            parent: 父控件
        """
        super().__init__(parent)
        self._title = title
        self._icon_path = icon_path
        self._action_text = action_text
        self._is_expanded = False
        self._animation_duration = 200

        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 设置整体样式
        self.setStyleSheet("""
            CollapsibleCard {
                background-color: white;
                border: 2px solid #4772c3;
            }
        """)

        # Header 区域
        self._header = QWidget()
        self._header.setFixedHeight(50)
        self._header.setStyleSheet("""
            QWidget {
                border: 1px solid #4772c3;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
            }
        """)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(15, 10, 15, 10)
        header_layout.setSpacing(8)

        # 左侧图标
        if self._icon_path:
            self._icon_label = QLabel()
            pixmap = QPixmap(self._icon_path)
            if not pixmap.isNull():
                self._icon_label.setPixmap(
                    pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            self._icon_label.setFixedSize(24, 24)
            header_layout.addWidget(self._icon_label)
            self._icon_label.setStyleSheet("""
                QLabel {
                    margin: 0;
                    background-color: transparent;
                    border: none;
                }
            """)

        # 标题标签
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    color: #4772c3;
                    margin: 0;
                    background-color: transparent;
                    font-family: "Microsoft YaHei";
                    border: none;
                }
            """)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)

        # 操作按钮
        if self._action_text:
            self._action_btn = QPushButton(self._action_text)
            self._action_btn.setCursor(Qt.PointingHandCursor)
            self._action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4772c3;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 4px 12px;
                }
                QPushButton:hover {
                    background-color: #5c8ad4;
                }
                QPushButton:pressed {
                    background-color: #3c61a5;
                }
            """)
            self._action_btn.clicked.connect(self.action_clicked.emit)
            header_layout.addWidget(self._action_btn)

        # 展开/折叠按钮
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #4772c3;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e6f3ff;
                border-radius: 12px;
            }
        """)
        self._update_toggle_icon()
        self._toggle_btn.clicked.connect(self.toggle)
        header_layout.addWidget(self._toggle_btn)

        main_layout.addWidget(self._header)

        # Contents 区域（可折叠部分）
        self._contents_wrapper = QWidget()
        self._contents_wrapper.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #4772c3;
                border-top: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 3px;
                border-bottom-right-radius: 3px;
            }
        """)

        self._contents_layout = QVBoxLayout(self._contents_wrapper)
        self._contents_layout.setContentsMargins(39, 10, 10, 10)
        self._contents_layout.setSpacing(8)  # 固定间距，不可压缩

        # 默认折叠状态
        self._contents_wrapper.setMaximumHeight(0)
        self._contents_wrapper.setVisible(False)

        main_layout.addWidget(self._contents_wrapper)

        # 设置大小策略
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def _update_toggle_icon(self):
        """更新展开/折叠按钮图标"""
        if self._is_expanded:
            self._toggle_btn.setText("∧")  # 向上箭头
        else:
            self._toggle_btn.setText("∨")  # 向下箭头

    def toggle(self):
        """切换展开/折叠状态"""
        if self._is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        """展开卡片"""
        if self._is_expanded:
            return

        self._is_expanded = True
        self._update_toggle_icon()

        # 如果没有内容项，不展开
        if self._contents_layout.count() == 0:
            return

        # 展开时取消header下部圆角
        self._header.setStyleSheet("""
            QWidget {
                border: 1px solid #4772c3;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)

        # 显示 contents
        self._contents_wrapper.setVisible(True)

        # 计算目标高度
        self._contents_wrapper.setMaximumHeight(16777215)  # 移除高度限制
        self._contents_wrapper.adjustSize()
        target_height = self._contents_wrapper.sizeHint().height()

        # 动画展开
        self._animation = QPropertyAnimation(self._contents_wrapper, b"maximumHeight")
        self._animation.setDuration(self._animation_duration)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.setStartValue(0)
        self._animation.setEndValue(target_height)
        self._animation.finished.connect(self._on_expand_finished)
        self._animation.start()

        self.expanded.emit()

    def _on_expand_finished(self):
        """展开动画完成"""
        self._contents_wrapper.setMaximumHeight(16777215)  # 移除高度限制以允许内容延展

    def collapse(self):
        """折叠卡片"""
        if not self._is_expanded:
            return

        self._is_expanded = False
        self._update_toggle_icon()

        # 动画折叠
        current_height = self._contents_wrapper.height()
        self._animation = QPropertyAnimation(self._contents_wrapper, b"maximumHeight")
        self._animation.setDuration(self._animation_duration)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.setStartValue(current_height)
        self._animation.setEndValue(0)
        self._animation.finished.connect(self._on_collapse_finished)
        self._animation.start()

        self.collapsed.emit()

    def _on_collapse_finished(self):
        """折叠动画完成"""
        self._contents_wrapper.setVisible(False)
        # 折叠后恢复header下部圆角
        self._header.setStyleSheet("""
            QWidget {
                border: 1px solid #4772c3;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                border-bottom-left-radius: 3px;
                border-bottom-right-radius: 3px;
            }
        """)

    def is_expanded(self) -> bool:
        """获取当前展开状态"""
        return self._is_expanded

    def add_content_item(self, text: str) -> ContentItemCard:
        """添加内容项卡片

        Args:
            text: 内容项文字

        Returns:
            ContentItemCard: 创建的内容项卡片实例
        """
        item = ContentItemCard(text)
        item.delete_clicked.connect(self._on_item_delete)
        self._contents_layout.addWidget(item)
        return item

    def _on_item_delete(self, item: ContentItemCard):
        """处理内容项删除"""
        self._contents_layout.removeWidget(item)
        item.deleteLater()

    def remove_content_item(self, item: ContentItemCard):
        """移除指定内容项

        Args:
            item: 要移除的内容项卡片
        """
        self._contents_layout.removeWidget(item)
        item.deleteLater()

    def clear_contents(self):
        """清空所有内容项"""
        while self._contents_layout.count() > 0:
            item = self._contents_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def get_content_items(self) -> list:
        """获取所有内容项

        Returns:
            list: 内容项卡片列表
        """
        items = []
        for i in range(self._contents_layout.count()):
            item = self._contents_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ContentItemCard):
                items.append(item.widget())
        return items

    def set_title(self, title: str):
        """设置卡片标题"""
        self._title = title
        self._title_label.setText(title)

    def get_title(self) -> str:
        """获取卡片标题"""
        return self._title
