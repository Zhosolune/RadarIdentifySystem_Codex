# -*- coding: utf-8 -*-
"""浮点数微调框设置卡片组件。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import SettingCard, FluentIconBase, DoubleSpinBox, qconfig

class DoubleSpinBoxSettingCard(SettingCard):
    """浮点数配置卡片。

    功能描述：
        包含一个 DoubleSpinBox 的设置卡片，用于配置浮点型数值。
        自动与全局配置项绑定，并根据配置项的校验器设定输入范围。

    Attributes:
        configItem (ConfigItem): 绑定的配置项对象。
        spinBox (DoubleSpinBox): 右侧的浮点数值微调框。
    """

    def __init__(self, configItem, icon: FluentIconBase, title: str, content: str | None = None, parent: QWidget | None = None, decimals: int = 2, singleStep: float = 1.0):
        """初始化浮点型配置卡片。

        功能描述：
            创建卡片，配置右侧的浮点微调框并绑定配置项，同时可指定小数位数和单步步长。

        Args:
            configItem (ConfigItem): 需要绑定的配置项。
            icon (FluentIconBase): 卡片左侧显示的图标。
            title (str): 卡片主标题。
            content (str | None, optional): 卡片副标题/描述内容。默认为 None。
            parent (QWidget | None, optional): 挂载的父级组件。默认为 None。
            decimals (int, optional): 显示的小数位数。默认为 2。
            singleStep (float, optional): 每次微调的步长大小。默认为 1.0。
        """
        super().__init__(icon, title, content, parent)
        self.configItem = configItem
        self.spinBox = DoubleSpinBox(self)

        # 设置小数位数和微调步长
        self.spinBox.setDecimals(decimals)
        self.spinBox.setSingleStep(singleStep)

        # 从配置项提取合法范围并设置
        if hasattr(configItem, "validator") and configItem.validator is not None:
            self.spinBox.setRange(float(configItem.validator.min), float(configItem.validator.max))

        # 设置初始值并连接信号
        self.spinBox.setValue(qconfig.get(configItem))
        self.spinBox.valueChanged.connect(self._onValueChanged)

        # 添加到卡片布局
        self.hBoxLayout.addWidget(self.spinBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _onValueChanged(self, value: float) -> None:
        """处理数值改变事件。

        功能描述：
            当微调框的数值改变时，同步更新到全局配置。

        Args:
            value (float): 新的浮点数值。
        """
        qconfig.set(self.configItem, value)
