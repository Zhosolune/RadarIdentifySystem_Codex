"""识别处理卡片组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CheckBox, PrimaryPushButton, PushButton, SimpleCardWidget


class RecognitionProcCard(SimpleCardWidget):
    """识别处理卡片。

    功能描述：
        提供“识别”、“上一类”、“下一类”、“上一片”、“下一片”、“重置当前切片”等操作按钮。
        包含一个“点击下一片直接识别”复选框。
        整体采用垂直布局划分区域，内部按钮按逻辑分组为水平布局。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        start_recognition_button (PrimaryPushButton): 触发识别的按钮（主题色）。
        prev_cluster_button (PushButton): 切换上一类的按钮。
        next_cluster_button (PushButton): 切换下一类的按钮。
        prev_slice_button (PushButton): 切换上一片的按钮。
        next_slice_button (PushButton): 切换下一片的按钮。
        reset_slice_button (PushButton): 重置当前切片的按钮。
        auto_recognize_checkbox (CheckBox): 切换下一片时是否自动识别的复选框。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化识别处理卡片。

        功能描述：
            创建布局并实例化内部的所有按钮和复选框组件。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(parent)
        self.setObjectName("recognitionProcCard")

        # 1. 核心识别与选项
        self.start_recognition_button = PrimaryPushButton("开始识别", self)
        self.start_recognition_button.setFixedWidth(80)
        self.auto_recognize_checkbox = CheckBox("切换下一片直接识别", self)
        self.auto_recognize_checkbox.setFixedWidth(250)
        self.auto_recognize_checkbox.setChecked(False)

        # 2. 类别导航
        self.prev_cluster_button = PushButton("上一类", self)
        self.prev_cluster_button.setFixedWidth(80)
        self.next_cluster_button = PushButton("下一类", self)
        self.next_cluster_button.setFixedWidth(80)

        # 3. 切片导航与重置
        self.prev_slice_button = PushButton("上一片", self)
        self.prev_slice_button.setFixedWidth(80)
        self.next_slice_button = PushButton("下一片", self)
        self.next_slice_button.setFixedWidth(80)
        self.reset_slice_button = PushButton("重置切片", self)
        self.reset_slice_button.setFixedWidth(80)

        self._init_layout()

    def _init_layout(self) -> None:
        """初始化卡片内部布局。

        功能描述：
            将按钮分组并采用垂直+水平的嵌套布局进行排版。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(0)

        # 第一行：识别按钮与自动复选框
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(self.start_recognition_button)
        row1_layout.addStretch(1)
        row1_layout.addWidget(self.auto_recognize_checkbox)
        
        # 第二行：类别导航
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(8)
        row2_layout.addWidget(self.prev_cluster_button)
        row2_layout.addWidget(self.next_cluster_button)
        row2_layout.addStretch(1)

        # 第三行：切片导航与重置
        row3_layout = QHBoxLayout()
        row3_layout.setSpacing(8)
        row3_layout.addWidget(self.prev_slice_button)
        row3_layout.addWidget(self.next_slice_button)
        row3_layout.addWidget(self.reset_slice_button)
        row3_layout.addStretch(1)

        main_layout.addLayout(row1_layout)
        main_layout.addSpacing(10)
        main_layout.addLayout(row2_layout)
        main_layout.addSpacing(5)
        main_layout.addLayout(row3_layout)
