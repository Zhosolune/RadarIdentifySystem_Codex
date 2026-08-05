"""识别策略双标签拨动开关设置卡。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import BodyLabel, FluentIconBase, SwitchSettingCard


class RecognitionStrategySettingCard(SwitchSettingCard):
    """在拨动开关两侧显示“严格”和“贪婪”的识别策略设置卡。

    开关关闭时滑块位于左侧，对应严格策略；开关开启时滑块位于右侧，
    对应贪婪策略。控件继续复用 ``SwitchSettingCard`` 的配置读写和信号。

    Attributes:
        strict_label [BodyLabel]: 位于开关左侧的严格策略标签。
        greedy_label [BodyLabel]: 位于开关右侧的贪婪策略标签。

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> from qfluentwidgets import FluentIcon
        >>> app = QApplication.instance() or QApplication([])
        >>> card = RecognitionStrategySettingCard(
        ...     icon=FluentIcon.SEARCH,
        ...     title="识别策略",
        ... )
        >>> (card.strict_label.text(), card.greedy_label.text())
        ('严格', '贪婪')
    """

    def __init__(
        self,
        icon: FluentIconBase,
        title: str,
        content: str | None = None,
        configItem: object | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """初始化双标签策略开关。

        Args:
            icon [FluentIconBase]: 卡片左侧图标。
            title [str]: 卡片标题。
            content [str | None]: 策略说明，默认不显示说明。
            configItem [object | None]: 可选全局布尔配置项；为 ``None`` 时由外部绑定。
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(
            icon=icon,
            title=title,
            content=content,
            configItem=configItem,
            parent=parent,
        )
        self.strict_label = BodyLabel("严格", self)
        self.greedy_label = BodyLabel("贪婪", self)

        # 隐藏组件库随状态切换的“开/关”文字，只保留拨动指示器。
        self.switchButton.label.hide()
        self.switchButton.setFixedWidth(self.switchButton.indicator.width() + 4)
        switch_index = self.hBoxLayout.indexOf(self.switchButton)
        self.hBoxLayout.insertWidget(
            switch_index,
            self.strict_label,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        self.hBoxLayout.insertWidget(
            switch_index + 2,
            self.greedy_label,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
