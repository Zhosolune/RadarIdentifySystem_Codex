"""可折叠卡片组件测试

运行方式：
    python test/test_collapsible_card.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, 
    QPushButton, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt

from ui.components import CollapsibleCard, ContentItemCard


class TestWindow(QMainWindow):
    """测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("可折叠卡片组件测试")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("background-color: white;")
        
        # 中央控件 - 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
        """)
        self.setCentralWidget(scroll_area)
        
        # 滚动区域内的容器
        container = QWidget()
        scroll_area.setWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 创建可折叠卡片1（带图标和操作按钮）
        self.card1 = CollapsibleCard(
            title="已选择的文件",
            icon_path=None,  # 可以替换为实际图标路径
            action_text="添加"
        )
        self.card1.action_clicked.connect(self._on_add_clicked)
        
        # 添加一些初始内容项
        self.card1.add_content_item("data_file_001.xlsx")
        self.card1.add_content_item("data_file_002.xlsx")
        self.card1.add_content_item("radar_signal_003.xlsx")
        
        layout.addWidget(self.card1)
        
        # 创建可折叠卡片2（无操作按钮）
        self.card2 = CollapsibleCard(
            title="处理参数",
            action_text=None
        )
        self.card2.add_content_item("epsilon_CF: 10 MHz")
        self.card2.add_content_item("epsilon_PW: 0.5 us")
        self.card2.add_content_item("min_pts: 3")
        
        layout.addWidget(self.card2)
        
        # 创建可折叠卡片3（空内容）
        self.card3 = CollapsibleCard(
            title="识别结果",
            action_text="导出"
        )
        layout.addWidget(self.card3)
        
        # 控制按钮区域
        btn_layout = QVBoxLayout()
        
        expand_all_btn = QPushButton("全部展开")
        expand_all_btn.clicked.connect(self._expand_all)
        expand_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4772c3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5c8ad4;
            }
        """)
        btn_layout.addWidget(expand_all_btn)
        
        collapse_all_btn = QPushButton("全部折叠")
        collapse_all_btn.clicked.connect(self._collapse_all)
        collapse_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #888888;
            }
        """)
        btn_layout.addWidget(collapse_all_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self._item_counter = 4
        
    def _on_add_clicked(self):
        """添加按钮点击"""
        self.card1.add_content_item(f"new_file_{self._item_counter:03d}.xlsx")
        self._item_counter += 1
        # 确保卡片展开以显示新添加的项
        if not self.card1.is_expanded():
            self.card1.expand()
            
    def _expand_all(self):
        """展开所有卡片"""
        self.card1.expand()
        self.card2.expand()
        self.card3.expand()
        
    def _collapse_all(self):
        """折叠所有卡片"""
        self.card1.collapse()
        self.card2.collapse()
        self.card3.collapse()


def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
