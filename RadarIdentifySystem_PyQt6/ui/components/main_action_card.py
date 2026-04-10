"""主操作组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, CheckBox
from .action_button_widget import ActionButtonCard, PrimaryActionButtonCard


class MainActionCard(QWidget):
    """主操作组件。

    功能描述：
        提供“开始切片”与“开始识别”按钮（使用 ActionButtonCard），并在下方包含自适应切片的复选框。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        start_slicing_button (ActionButtonCard): 触发切片工作流的按钮。
        start_recognition_button (ActionButtonCard): 触发识别的按钮。
        adaptive_slicing_checkbox (CheckBox): 是否启用自适应切片的复选框。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化主操作组件。

        功能描述：
            创建垂直布局，第一行放置按钮，第二行放置复选框。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(parent)
        self.setObjectName("mainActionCard")

        # 初始化内部组件
        self.start_slicing_button = ActionButtonCard(FluentIcon.CUT, "开始切片", self)
        self.start_recognition_button = PrimaryActionButtonCard(FluentIcon.SEARCH, "开始识别", self)
        
        self.adaptive_slicing_checkbox = CheckBox("启用自适应切片", self)

        # 构建布局
        self._init_layout()
        self.setFixedHeight(60)

    def _init_layout(self) -> None:
        """初始化内部布局。

        功能描述：
            创建垂直布局，第一行水平放置切片和识别按钮，第二行放置复选框。
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # 第一行按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addWidget(self.start_slicing_button)
        button_layout.addWidget(self.start_recognition_button)
        
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.adaptive_slicing_checkbox)
