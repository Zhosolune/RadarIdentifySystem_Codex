"""标签栏组件测试

运行方式：
    python test/test_tab_bar.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QStackedWidget,
)
from PyQt5.QtCore import Qt

from ui.components import TabBar


class TestWindow(QMainWindow):
    """测试窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("标签栏组件测试")
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background-color: #f0f0f0;")

        # 中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(0)

        # 创建标签栏
        self.tab_bar = TabBar()
        self.tab_bar.add_tab("首页")
        self.tab_bar.add_tab("数据处理")
        self.tab_bar.add_tab("参数设置")
        self.tab_bar.add_tab("结果分析")

        layout.addWidget(self.tab_bar)

        # 创建内容区域
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: white;
            }
        """)

        # 添加各页面内容
        pages = ["首页内容", "数据处理页面", "参数设置页面", "结果分析页面"]

        for text in pages:
            page = QWidget()
            page.setStyleSheet("background-color: white;")
            page_layout = QVBoxLayout(page)
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    color: #4772c3;
                    font-size: 24px;
                    font-weight: bold;
                }
            """)
            page_layout.addWidget(label)
            self.content_stack.addWidget(page)

        layout.addWidget(self.content_stack)

        # 连接标签切换信号
        self.tab_bar.tab_changed.connect(self.content_stack.setCurrentIndex)


def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
