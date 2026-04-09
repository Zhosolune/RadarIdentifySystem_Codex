"""绘图控制卡片组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import SimpleCardWidget

from .plot_option_card import PlotOptionCard
from .redraw_option_card import RedrawOptionCard


class PlotControlCard(SimpleCardWidget):
    """绘图控制卡片。

    功能描述：
        作为绘图相关操作的容器卡片，包裹绘图选项卡（PlotOptionCard）和重绘选项卡（RedrawOptionCard）。
        整体采用垂直布局划分区域。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        plot_option_card (PlotOptionCard): 绘图选项卡（包含展示模式与绘制模式）。
        redraw_option_card (RedrawOptionCard): 重绘选项卡（包含指定切片重绘功能）。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化绘图控制卡片。

        功能描述：
            创建布局并实例化内部的绘图选项卡与重绘选项卡组件。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(parent)
        self.setObjectName("PlotControlCard")

        # 绘图选项卡
        self.plot_option_card = PlotOptionCard(self)
        
        # 重绘选项卡
        self.redraw_option_card = RedrawOptionCard(self)

        self._init_layout()

    def _init_layout(self) -> None:
        """初始化卡片内部布局。

        功能描述：
            采用垂直布局排版内部的绘图选项卡与重绘选项卡。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(5)

        # 绘图选项卡
        main_layout.addWidget(self.plot_option_card)
        # 重绘选项卡
        main_layout.addWidget(self.redraw_option_card)
