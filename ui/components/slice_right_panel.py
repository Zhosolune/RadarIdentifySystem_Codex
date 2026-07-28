"""切片页面右侧业务面板组件。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SimpleCardWidget
from qfluentwidgets.common.style_sheet import addStyleSheet

from app.style_sheet import StyleSheet
from core.models.processing_session import ProcessingSession

from .analysis_result_card import AnalysisResultCard
from .jitter_free_container import JitterFreeCardGroup
from .navigation_control_card import NavigationControlCard
from .plot_option_card import PlotOptionCard
from .redraw_option_card import RedrawOptionCard


class SliceRightPanel(QWidget):
    """管理切片页右侧导航、绘图选项和分析结果区域。

    页面级参数抽屉不属于普通列布局，仍由 ``SliceInterface`` 管理。

    Attributes:
        slice_info_label [QLabel]: 切片数量信息标签。
        operate_panel_card [SimpleCardWidget]: 固定在表格上方的操作卡片。
        navigation_control_card [NavigationControlCard]: 页面主操作与导航控件。
        option_cards_group [JitterFreeCardGroup]: 绘图与重绘选项容器。
        plot_option_card [PlotOptionCard]: 图像展示选项控件。
        redraw_option_card [RedrawOptionCard]: 图像重绘选项控件。
        analysis_result_card [AnalysisResultCard]: 当前类别分析结果卡片。
    """

    def __init__(
        self,
        session: ProcessingSession,
        on_config_changed: Callable[[], None] | None = None,
        on_scale_mode_changed: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """初始化切片页面右侧业务面板。

        Args:
            session [ProcessingSession]: 当前页面绑定的处理会话。
            on_config_changed [Callable[[], None] | None]: 配置变更后的保存回调。
            on_scale_mode_changed [Callable[[str], None] | None]: 图像缩放模式变更回调。
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("sliceRightColumn")

        self.slice_info_label = QLabel("预计将获得 0 个250ms切片", self)
        self.slice_info_label.setObjectName("sliceInfoLabel")
        self.slice_info_label.setFixedHeight(25)

        self.operate_panel_card = SimpleCardWidget(self)
        self.operate_panel_card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        operate_panel_layout = QVBoxLayout(self.operate_panel_card)
        operate_panel_layout.setContentsMargins(12, 12, 12, 12)
        operate_panel_layout.setSpacing(8)

        self.navigation_control_card = NavigationControlCard(
            self.operate_panel_card
        )
        self.option_cards_group = JitterFreeCardGroup(self.operate_panel_card)
        self.plot_option_card = PlotOptionCard(
            session=session,
            on_config_changed=on_config_changed,
            parent=self.option_cards_group,
        )
        if on_scale_mode_changed is not None:
            self.plot_option_card.scaleModeChanged.connect(on_scale_mode_changed)
        self.redraw_option_card = RedrawOptionCard(self.option_cards_group)
        self.option_cards_group.addSettingCard(self.plot_option_card)
        self.option_cards_group.addSettingCard(self.redraw_option_card)
        operate_panel_layout.addWidget(self.navigation_control_card)
        operate_panel_layout.addWidget(self.option_cards_group)

        self.analysis_result_card = AnalysisResultCard(self)
        addStyleSheet(self.analysis_result_card.table, StyleSheet.SLICE_INTERFACE)

        self._init_layout()

    def _init_layout(self) -> None:
        """创建上部固定、结果表纵向伸缩的业务内容布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(self.slice_info_label, 1)

        layout.addLayout(header_layout)
        # 操作区域始终固定在结果表上方，不参与右栏滚动。
        layout.addWidget(self.operate_panel_card)
        # 结果卡优先使用完整内容高度，空间不足时收缩并保留无滚动条的滚轮浏览。
        layout.addWidget(self.analysis_result_card)
        layout.addStretch(1)
