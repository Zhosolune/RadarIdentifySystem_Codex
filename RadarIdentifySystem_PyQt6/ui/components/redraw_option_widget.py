"""重绘选项卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, LineEdit, PrimaryPushButton, SettingCard


class RedrawOptionWidget(SettingCard):
    """重绘选项卡片组件。

    功能描述：
        提供输入切片编号并触发重绘操作的界面组件，继承自组件库的通用设置卡样式。
        包含一个整数约束的输入框和一个主题色重绘按钮。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        redraw_requested (pyqtSignal(int)): 请求重绘信号，携带用户输入的切片编号。
    """

    redraw_requested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化重绘选项卡片。

        功能描述：
            设置卡片的图标和文本，将输入框与重绘按钮添加到右侧布局，并绑定事件。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(
            icon=FluentIcon.EDIT,
            title="指定切片编号",
            content="输入切片编号进行重绘画布",
            parent=parent
        )
        self.setObjectName("RedrawOptionCard")

        self._init_layout()
        self._connect_signals()

    def _init_layout(self) -> None:
        """初始化卡片内部布局与控件。

        功能描述：
            实例化输入框与重绘按钮，并将它们添加到 SettingCard 自带的右侧布局中。
        """
        self.slice_input = LineEdit(self)
        self.slice_input.setPlaceholderText("切片编号 (≥1)")
        # 约束输入框输入为整数，从 1 开始计数
        self.slice_input.setValidator(QIntValidator(1, 999999, self))
        self.slice_input.setFixedWidth(140)

        self.redraw_button = PrimaryPushButton("重绘", self)
        self.redraw_button.setFixedWidth(80)

        # 添加到 SettingCard 内部自带的 hBoxLayout
        self.hBoxLayout.addWidget(self.slice_input, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.hBoxLayout.addWidget(self.redraw_button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _connect_signals(self) -> None:
        """连接信号与槽函数。"""
        self.redraw_button.clicked.connect(self._on_redraw_clicked)

    def _on_redraw_clicked(self) -> None:
        """处理重绘按钮点击事件。

        功能描述：
            获取输入框文本，校验其是否为合法整数后，发射 redraw_requested 信号。
        """
        text = self.slice_input.text()
        if text.isdigit() and int(text) >= 1:
            self.redraw_requested.emit(int(text))
