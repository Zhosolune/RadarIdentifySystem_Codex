# -*- coding: utf-8 -*-
"""圆形进度条组件测试"""

import sys
sys.path.insert(0, "e:/myProjects_Trae/RadarIdentifySystem")

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from ui.components.circle_progress import CircleProgressBar


class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("圆形进度条测试")
        self.setFixedSize(200, 180)
        
        layout = QVBoxLayout(self)
        
        # 创建圆形进度条
        self.progress = CircleProgressBar()
        self.progress.setProgress(50)
        layout.addWidget(self.progress)
        
        # 创建按钮
        btn_layout = QHBoxLayout()
        
        minus_btn = QPushButton("-1")
        minus_btn.clicked.connect(lambda: self.change_progress(-1))
        btn_layout.addWidget(minus_btn)
        
        plus_btn = QPushButton("+1")
        plus_btn.clicked.connect(lambda: self.change_progress(1))
        btn_layout.addWidget(plus_btn)
        
        layout.addLayout(btn_layout)
    
    def change_progress(self, delta):
        current = self.progress.value()
        new_value = current + delta
        print(f"当前值: {current}, 变化: {delta}, 新值: {new_value}")
        self.progress.setProgress(new_value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())
