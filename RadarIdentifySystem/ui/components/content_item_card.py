"""内容项卡片组件

用于在可折叠卡片的 contents 区域中显示的子卡片项。
左侧显示标签文字，右侧显示删除按钮。
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QScrollArea, QFrame
from PyQt5.QtCore import Qt, pyqtSignal, QTimer


class ContentItemCard(QWidget):
    """内容项卡片组件

    用于显示在可折叠卡片 contents 区域中的子项。
    包含左侧标签和右侧删除按钮。

    Signals:
        delete_clicked: 删除按钮点击信号，传递卡片实例
    """

    delete_clicked = pyqtSignal(object)  # 传递被删除的卡片实例

    def __init__(self, text: str, parent=None):
        """初始化内容项卡片

        Args:
            text: 显示的标签文字
            parent: 父控件
        """
        super().__init__(parent)
        self._text = text
        self._marquee_timer = QTimer(self)
        self._marquee_timer.setInterval(30)
        self._marquee_timer.timeout.connect(self._on_marquee_tick)
        self._marquee_step = 1
        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # 设置卡片样式
        self.setStyleSheet("""
            ContentItemCard {
                background-color: #f5f9ff;
                border: none;
                border-radius: 5px;
            }
            ContentItemCard:hover {
                background-color: #e6f3ff;
            }
        """)
        # 固定高度，不可因尺寸影响而受到挤压
        self.setMinimumHeight(36)
        self.setMaximumHeight(36)
        # 设置大小策略：水平扩展，垂直固定
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._label = QLabel(self._text)
        self._label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #4772c3;
                margin: 0;
                background-color: transparent;
                font-family: "Microsoft YaHei";
                border: none;
            }
        """)
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
        layout.addWidget(self._label_scroll_area, 1)

        # 右侧删除按钮（X号）
        self._delete_btn = QPushButton("×")
        self._delete_btn.setFixedSize(24, 24)
        self._delete_btn.setCursor(Qt.PointingHandCursor)
        self._delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #999999;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff5555;
                background-color: rgba(255, 85, 85, 0.1);
                border-radius: 12px;
            }
            QPushButton:pressed {
                color: #cc4444;
                background-color: rgba(255, 85, 85, 0.2);
            }
        """)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self._delete_btn)

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

    def _on_delete_clicked(self):
        """删除按钮点击处理"""
        self.delete_clicked.emit(self)

    def get_text(self) -> str:
        """获取标签文字"""
        return self._text

    def set_text(self, text: str):
        """设置标签文字"""
        self._text = text
        self._label.setText(text)
        self._update_marquee_state()
