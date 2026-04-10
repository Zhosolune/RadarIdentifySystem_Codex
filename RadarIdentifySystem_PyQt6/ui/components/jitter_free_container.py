"""无抖动容器组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QStyleOption
from PyQt6.QtGui import QPainter
from qfluentwidgets import SettingCardGroup
from app.style_sheet import StyleSheet


class JitterFreeCardGroup(SettingCardGroup):
    """无抖动设置卡组。

    功能描述：
        继承自组件库的 SettingCardGroup。
        SettingCardGroup 内部使用了 ExpandLayout 来消除展开折叠时的动画抖动问题。
        但原生的 SettingCardGroup 会强制显示一个组标题并占用 46px 的额外高度（标题高度+间距）。
        该类移除了原生的组标题占位和间距，仅保留其消除抖动的核心布局能力。

    参数说明：
        parent (QWidget | None): 父级控件。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化无抖动设置卡组。

        功能描述：
            隐藏原生标题标签，并移除多余的间距占位。
        """
        super().__init__("", parent)
        self.setObjectName("JitterFreeCardGroup")
        # StyleSheet.JITTER_FREE_CONTAINER.apply(self)
        
        # 隐藏原生组标题
        self.titleLabel.hide()
        
        item = self.vBoxLayout.itemAt(1)
        if item and item.spacerItem():
            self.vBoxLayout.removeItem(item)

    def adjustSize(self) -> None:
        """调整自身尺寸。

        功能描述：
            重写原生 adjustSize 方法，移除原生的 '+ 46'（由于标题产生的额外高度），
            仅返回内部卡片布局所需的高度，实现真正的零占位包裹。
        """
        h = self.cardLayout.heightForWidth(self.width())
        self.resize(self.width(), h)

    def paintEvent(self, e):
        """取消重写 paintEvent。
        
        原生 QWidget 的透明背景不应该通过重写带 opt.initFrom(self) 的 paintEvent 来维持，
        这反而会触发某些环境下的不透明绘制机制。
        """
        pass