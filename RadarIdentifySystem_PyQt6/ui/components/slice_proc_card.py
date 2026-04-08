"""切片操作卡片组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import CheckBox, PrimaryPushButton, SimpleCardWidget


class SliceProcCard(SimpleCardWidget):
    """切片操作卡片。

    功能描述：
        提供“开始切片”按钮与“启用自适应切片”复选框组合的水平布局卡片组件。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        start_slicing_button (PrimaryPushButton): 触发切片工作流的按钮。
        adaptive_slicing_checkbox (CheckBox): 是否启用自适应切片的复选框。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化切片操作卡片。

        功能描述：
            创建水平布局，依次添加按钮和复选框组件。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(parent)
        self.setObjectName("sliceProcCard")

        # 初始化内部组件
        self.start_slicing_button = PrimaryPushButton("开始切片", self)
        self.start_slicing_button.setFixedWidth(80)
        self.adaptive_slicing_checkbox = CheckBox("启用自适应切片       ", self)
        self.adaptive_slicing_checkbox.setFixedWidth(250)
        self.adaptive_slicing_checkbox.setChecked(False)

        # 构建水平布局
        self._init_layout()

    def _init_layout(self) -> None:
        """初始化内部布局。

        功能描述：
            创建水平布局，设置边距并将按钮与复选框放入其中。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(0)

        # 左侧为按钮，右侧为复选框
        layout.addWidget(self.start_slicing_button)
        layout.addStretch(1)
        layout.addWidget(self.adaptive_slicing_checkbox)
        
