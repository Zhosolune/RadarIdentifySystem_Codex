"""目录选取卡片组件

提供目录选取功能的卡片组件。
header 从左到右依次是：图标、垂直布局的主标签和副标签、弹性空间、选取按钮。
"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QFileDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap


class DirectoryPickerCard(QWidget):
    """目录选取卡片组件

    用于选取目录的卡片容器，header 区域包含图标、主副标签和选取按钮。

    Signals:
        directory_selected: 目录选取信号，参数为选取的目录路径
    """

    directory_selected = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        icon_path: str = None,
        button_text: str = "选择目录",
        parent=None,
    ):
        """初始化目录选取卡片

        Args:
            title: 主标签文字
            subtitle: 副标签文字（可选）
            icon_path: 图标路径（可选）
            button_text: 按钮文字（默认为"选择目录"）
            parent: 父控件
        """
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._icon_path = icon_path
        self._button_text = button_text
        self._selected_directory = ""

        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header 区域
        self._header = QWidget()
        self._header.setFixedHeight(60)
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
            header_layout.addWidget(self._icon_label)
            self._icon_label.setStyleSheet("""
                QLabel {
                    margin: 0;
                    background-color: transparent;
                    border: none;
                }
            """)

        # 垂直布局的主标签和副标签
        labels_widget = QWidget()
        labels_widget.setStyleSheet("background-color: transparent; border: none;")
        labels_layout = QVBoxLayout(labels_widget)
        labels_layout.setContentsMargins(0, 0, 0, 0)
        labels_layout.setSpacing(0)

        # 主标签
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
        labels_layout.addWidget(self._title_label)

        # 副标签
        self._subtitle_label = QLabel(self._subtitle)
        self._subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #7a9ad4;
                margin: 0;
                background-color: transparent;
                font-family: "Microsoft YaHei";
                border: none;
            }
        """)
        labels_layout.addWidget(self._subtitle_label)

        header_layout.addWidget(labels_widget)

        # 弹性空间
        header_layout.addStretch(1)

        # 选取按钮
        self._action_btn = QPushButton(self._button_text)
        self._action_btn.setCursor(Qt.PointingHandCursor)
        self._action_btn.setStyleSheet("""
            QPushButton {
                background-color: #4772c3;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 16px;
                font-size: 13px;
                font-family: "Microsoft YaHei";
            }
            QPushButton:hover {
                background-color: #5c8ad4;
            }
            QPushButton:pressed {
                background-color: #3c61a5;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self._action_btn.clicked.connect(self._on_button_clicked)
        header_layout.addWidget(self._action_btn)

        main_layout.addWidget(self._header)

        # 设置大小策略
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def _on_button_clicked(self):
        """按钮点击处理 - 打开目录选择对话框"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择目录",
            self._selected_directory or "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if directory:
            self._selected_directory = directory
            # 更新副标题显示选择的路径
            self._subtitle_label.setText(directory)
            # 发射目录选择信号
            self.directory_selected.emit(directory)

    def set_button_enabled(self, enabled: bool):
        """设置按钮启用状态"""
        self._action_btn.setEnabled(enabled)

    def set_directory(self, directory: str):
        """设置当前目录路径
        
        Args:
            directory: 目录路径
        """
        self._selected_directory = directory
        if directory:
            self._subtitle_label.setText(directory)
        else:
            self._subtitle_label.setText(self._subtitle)

    def get_directory(self) -> str:
        """获取当前选择的目录路径"""
        return self._selected_directory
