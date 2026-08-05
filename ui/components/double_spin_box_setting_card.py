# -*- coding: utf-8 -*-
"""浮点数微调框设置卡片组件。"""

from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Protocol

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import SettingCard, FluentIconBase, DoubleSpinBox, BodyLabel, qconfig

from .spin_box_setting_card import _forward_wheel_to_scroll_area

LOGGER = logging.getLogger(__name__)


class ConfigWriterProtocol(Protocol):
    """设置卡读写器协议。"""

    def get(self, item: object) -> object:
        """读取配置项当前值。"""
        ...

    def set(self, item: object, value: object) -> None:
        """写入配置项当前值。"""
        ...


class _WheelDisabledDoubleSpinBox(DoubleSpinBox):
    """忽略滚轮改值并将事件交还外层滚动区域。"""

    def wheelEvent(self, event: QWheelEvent) -> None:
        """忽略滚轮事件，避免滚动参数页时误修改浮点值。"""
        _forward_wheel_to_scroll_area(self, event)


class DoubleSpinBoxSettingCard(SettingCard):
    """浮点数配置卡片。

    功能描述：
        包含一个 DoubleSpinBox 的设置卡片，用于配置浮点型数值。
        自动与全局配置项绑定，并根据配置项的校验器设定输入范围。
        滚轮事件仅用于滚动外层参数页面，不会修改当前数值。

    Attributes:
        configItem (ConfigItem): 绑定的配置项对象。
        config_writer (ConfigWriterProtocol): 配置项读写器。
        spinBox (DoubleSpinBox): 右侧的浮点数值微调框。
    """

    def __init__(
        self,
        configItem: object,
        icon: FluentIconBase,
        title: str,
        content: str | None = None,
        unit: str | None = None,
        decimals: int = 2,
        singleStep: float = 1.0,
        parent: QWidget | None = None,
        config_writer: ConfigWriterProtocol = qconfig,
    ) -> None:
        """初始化浮点型配置卡片。

        功能描述：
            创建卡片，配置右侧的浮点微调框并绑定配置项，同时可指定小数位数和单步步长。
            默认读写全局配置，也可注入 session 级 writer 写入独立子配置。

        Args:
            configItem [object]: 需要绑定的配置项。
            icon [FluentIconBase]: 卡片左侧显示的图标。
            title [str]: 卡片主标题。
            content [str | None]: 卡片副标题或描述内容，默认值为 ``None``。
            unit [str | None]: 数值单位文本，显示在微调框右侧，默认值为 ``None``。
            decimals [int]: 显示的小数位数，默认值为 2。
            singleStep [float]: 每次微调的步长大小，默认值为 1.0。
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
        self.spinBox = _WheelDisabledDoubleSpinBox(self)
        self.unit = BodyLabel(self)
        self.unit.setFixedWidth(40)
        self.unit.setText(unit or " ")
        self._decimals = decimals

        # 设置小数位数和微调步长
        self.spinBox.setDecimals(decimals)
        self.spinBox.setSingleStep(singleStep)

        # 从配置项提取合法范围并设置
        if hasattr(configItem, "validator") and configItem.validator is not None:
            self.spinBox.setRange(float(configItem.validator.min), float(configItem.validator.max))

        # 归一化初始值，确保显示精度与控件精度一致
        initial_value = self._normalize_value(float(self.config_writer.get(configItem)))
        self.spinBox.setValue(initial_value)
        self.spinBox.valueChanged.connect(self._onValueChanged)

        # 添加到卡片布局
        self.hBoxLayout.addWidget(self.spinBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _normalize_value(self, value: float) -> float:
        """按当前显示精度归一化浮点值。

        功能描述：
            将微调框产生的二进制浮点值按当前显示小数位进行量化，
            让界面显示值与配置文件中的持久化值保持一致。

        Args:
            value (float): 需要归一化的原始浮点数值。

        Returns:
            float: 按当前小数位四舍五入后的浮点数值。

        Raises:
            无。
        """
        quantize_pattern = "1" if self._decimals <= 0 else f"1.{'0' * self._decimals}"
        return float(
            Decimal(str(value)).quantize(
                Decimal(quantize_pattern),
                rounding=ROUND_HALF_UP,
            )
        )

    def _onValueChanged(self, value: float) -> None:
        """处理数值改变事件。

        功能描述：
            当微调框的数值改变时，先按当前显示小数位归一化浮点值，
            再回写控件并同步更新到全局配置，避免配置文件出现长尾浮点表示。

        Args:
            value (float): 新的浮点数值。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 归一化浮点值，避免 JSON 中出现长尾浮点表示
        normalized_value = self._normalize_value(value)

        if normalized_value != value:
            LOGGER.debug("归一化浮点配置值：%s -> %s", value, normalized_value)

            # 回写归一化值，确保控件显示与实际保存值一致
            self.spinBox.blockSignals(True)
            try:
                self.spinBox.setValue(normalized_value)
            finally:
                self.spinBox.blockSignals(False)

        # 持久化配置值
        self.config_writer.set(self.configItem, normalized_value)
