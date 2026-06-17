"""提供切片参数抽屉的独立内容面板。"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, ScrollArea, SimpleCardWidget, SwitchSettingCard, SettingCardGroup

from app.app_config import appConfig
from .export_option_card import ExportOptionCard
from .model_selection_card import ModelSelectionCard


class SliceParamPanel(QWidget):
    """集中承载当前切片页面的参数设置卡片。

    该组件只负责抽屉内容布局，不创建或继承抽屉。未来与 Session 子配置相关的
    设置卡可继续加入此面板。

    Attributes:
        auto_recognize_card: 切换下一片时自动识别的设置卡。
        model_selection_card: 当前页面使用的 PA 与 DTOA 模型选择卡。
        export_path_card: 导出路径与自动保存设置卡。
        scroll_area: 支持内容溢出的滚动区域。
        scroll_content_widget: 滚动区域承载的内容控件。
        scroll_content_layout: 提供抽屉内容边距的布局。
        panel_card: 包裹无抖动卡片组的简单卡片容器。
        cards_group: 管理可展开卡片高度的无抖动卡片组。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """创建抽屉内容卡片并完成纵向布局。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 模型目录扫描失败时抛出。

        Example:
            >>> panel = SliceParamPanel()
            >>> panel.layout().count() >= 3
            True
        """
        super().__init__(parent)
        self.setObjectName("sliceParamPanel")

        self.auto_recognize_card: SwitchSettingCard = SwitchSettingCard(
            icon=FluentIcon.PLAY,
            title="自动识别",
            content="切换下一片时自动执行识别工作流",
            configItem=appConfig.autoRecognizeNextSlice,
            parent=self,
        )
        self.model_selection_card: ModelSelectionCard = ModelSelectionCard(self)
        self.export_path_card: ExportOptionCard = ExportOptionCard(self)

        self._init_layout()

    def _init_layout(self) -> None:
        """使用滚动区和无抖动卡片组排列参数设置卡片。"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.drawer_scroll_area: ScrollArea = ScrollArea(self)
        self.drawer_scroll_area.setObjectName("drawerPanelScrollArea")
        self.drawer_scroll_area.setWidgetResizable(True)

        self.drawer_scroll_widget: QWidget = QWidget()
        self.drawer_scroll_widget.setObjectName("drawerPanelContentWidget")
        self.drawer_scroll_layout: QVBoxLayout = QVBoxLayout(
            self.drawer_scroll_widget
        )
        self.drawer_scroll_layout.setContentsMargins(16, 8, 16, 16)
        self.drawer_scroll_layout.setSpacing(8)

        # ExpandLayout 统一管理展开高度，避免多张设置卡互相挤压抖动。
        self.cards_group: SettingCardGroup = SettingCardGroup(
            "额外配置项",
            self.drawer_scroll_widget
        )
        self.cards_group.addSettingCard(self.auto_recognize_card)
        self.cards_group.addSettingCard(self.model_selection_card)
        self.cards_group.addSettingCard(self.export_path_card)

        # TODO: 其他设置卡组可添加到此。

        self.drawer_scroll_layout.addWidget(self.cards_group)
        self.drawer_scroll_layout.addStretch(1)
        self.drawer_scroll_area.setWidget(self.drawer_scroll_widget)
        root_layout.addWidget(self.drawer_scroll_area)
