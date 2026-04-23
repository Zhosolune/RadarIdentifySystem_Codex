# -*- coding: utf-8 -*-
"""整数微调框设置卡片组件。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import SettingCard, FluentIconBase, SpinBox, qconfig

class SpinBoxSettingCard(SettingCard):
    """整数配置卡片。

    功能描述：
        包含一个 SpinBox  的设置卡片，用于配置整型数值。
        自动与全局配置项绑定，并根据配置项的校验器设定输入范围。

    Attributes:
        configItem (ConfigItem): 绑定的配置项对象。
        spinBox (SpinBox): 右侧的数值微调框。
    """

    def __init__(self, configItem, icon: FluentIconBase, title: str, content: str | None = None, parent: QWidget | None = None):
        """初始化整型配置卡片。

        功能描述：
            创建卡片，配置右侧的微调框并绑定配置项。

        Args:
            configItem (ConfigItem): 需要绑定的配置项。
            icon (FluentIconBase): 卡片左侧显示的图标。
            title (str): 卡片主标题。
            content (str | None, optional): 卡片副标题/描述内容。默认为 None。
            parent (QWidget | None, optional): 挂载的父级组件。默认为 None。
        """
        super().__init__(icon, title, content, parent)
        self.configItem = configItem
        self.spinBox = SpinBox(self)

        # 从配置项提取合法范围并设置
        if hasattr(configItem, "validator") and configItem.validator is not None:
            self.spinBox.setRange(int(configItem.validator.min), int(configItem.validator.max))

        # 设置初始值并连接信号
        self.spinBox.setValue(qconfig.get(configItem))
        self.spinBox.valueChanged.connect(self._onValueChanged)

        # 添加到卡片布局
        self.hBoxLayout.addWidget(self.spinBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _onValueChanged(self, value: int) -> None:
        """处理数值改变事件。

        功能描述：
            当微调框的数值改变时，同步更新到全局配置。

        Args:
            value (int): 新的数值。
        """
        qconfig.set(self.configItem, value)
