# -*- coding: utf-8 -*-
"""整数微调框设置卡片组件。"""

from typing import Protocol

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import SettingCard, FluentIconBase, SpinBox, BodyLabel, qconfig


class ConfigWriterProtocol(Protocol):
    """设置卡读写器协议。"""

    def get(self, item: object) -> object:
        """读取配置项当前值。"""
        ...

    def set(self, item: object, value: object) -> None:
        """写入配置项当前值。"""
        ...


class SpinBoxSettingCard(SettingCard):
    """整数配置卡片。

    功能描述：
        包含一个 SpinBox  的设置卡片，用于配置整型数值。
        自动与全局配置项绑定，并根据配置项的校验器设定输入范围。

    Attributes:
        configItem (ConfigItem): 绑定的配置项对象。
        config_writer (ConfigWriterProtocol): 配置项读写器。
        spinBox (SpinBox): 右侧的数值微调框。
    """

    def __init__(
        self,
        configItem: object,
        icon: FluentIconBase,
        title: str,
        content: str | None = None,
        unit: str | None = None,
        parent: QWidget | None = None,
        config_writer: ConfigWriterProtocol = qconfig,
    ) -> None:
        """初始化整型配置卡片。

        功能描述：
            创建卡片，配置右侧的微调框并绑定配置项。默认读写全局配置，
            也可注入 session 级 writer 写入独立子配置。

        Args:
            configItem [object]: 需要绑定的配置项。
            icon [FluentIconBase]: 卡片左侧显示的图标。
            title [str]: 卡片主标题。
            content [str | None]: 卡片副标题或描述内容，默认值为 ``None``。
            unit [str | None]: 单位字符串，默认值为 ``None``。
            parent [QWidget | None]: 挂载的父级组件，默认值为 ``None``。
            config_writer [ConfigWriterProtocol]: 配置读写器，默认使用全局 ``qconfig``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from qfluentwidgets import FluentIcon
            >>> hasattr(FluentIcon, "SETTING")
            True
        """
        super().__init__(icon, title, content, parent)
        self.configItem = configItem
        self.config_writer: ConfigWriterProtocol = config_writer
        self.unit = BodyLabel(self)
        self.unit.setFixedWidth(40)
        self.unit.setText(unit or " ")
        self.spinBox = SpinBox(self)

        # 从配置项提取合法范围并设置
        if hasattr(configItem, "validator") and configItem.validator is not None:
            self.spinBox.setRange(int(configItem.validator.min), int(configItem.validator.max))

        # 设置初始值并连接信号
        self.spinBox.setValue(int(self.config_writer.get(configItem)))
        self.spinBox.valueChanged.connect(self._onValueChanged)

        # 添加到卡片布局
        self.hBoxLayout.addWidget(self.spinBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _onValueChanged(self, value: int) -> None:
        """处理数值改变事件。

        功能描述：
            当微调框的数值改变时，同步更新到全局配置。

        Args:
            value (int): 新的数值。
        """
        self.config_writer.set(self.configItem, value)
