"""提供切片参数抽屉的独立内容面板。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    BoolValidator,
    FluentIcon,
    ScrollArea,
    SwitchSettingCard,
    SettingCardGroup,
)

from app.session_config_item import SessionConfigItem
from core.models.processing_session import ProcessingSession
from .export_option_card import ExportOptionCard
from .model_selection_card import ModelSelectionCard


class SliceParamPanel(QWidget):
    """集中承载当前切片页面的参数设置卡片。

    该组件只负责抽屉内容布局，不创建或继承抽屉。未来与 Session 子配置相关的
    设置卡可继续加入此面板。

    Attributes:
        session: 当前切片页面所属的处理 session。
        auto_recognize_item: 绑定到当前 session 子配置的自动识别设置项。
        auto_recognize_card: 切换下一片时自动识别的设置卡。
        model_selection_card: 当前页面使用的 PA 与 DTOA 模型选择卡。
        export_path_card: 导出路径与自动保存设置卡。
        drawer_scroll_area: 支持内容溢出的滚动区域。
        drawer_scroll_widget: 滚动区域承载的内容控件。
        drawer_scroll_layout: 提供抽屉内容边距的布局。
        cards_group: 管理可展开卡片高度的无抖动卡片组。
    """

    def __init__(
        self,
        session: ProcessingSession,
        on_config_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """创建抽屉内容卡片并完成纵向布局。

        Args:
            session [ProcessingSession]: 当前页面所属 session，用于读写独立子配置。
            on_config_changed [Callable[[], None] | None]: 子配置变更后的保存回调，默认不回调。
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 模型目录扫描失败时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> panel = SliceParamPanel(ProcessingSession())
            >>> panel.objectName()
            'sliceParamPanel'
        """
        super().__init__(parent)
        self.setObjectName("sliceParamPanel")

        self.session: ProcessingSession = session
        self._on_config_changed = on_config_changed
        self.auto_recognize_item: SessionConfigItem = SessionConfigItem(
            self.session.config_snapshot,
            "business.auto_recognize_next_slice",
            True,
            validator=BoolValidator(),
            on_changed=on_config_changed,
        )
        self.auto_recognize_card: SwitchSettingCard = SwitchSettingCard(
            icon=FluentIcon.PLAY,
            title="自动识别",
            content="切换下一片时自动执行识别工作流",
            configItem=None,
            parent=self,
        )
        self.auto_recognize_card.setChecked(bool(self.auto_recognize_item.value))
        self.auto_recognize_card.checkedChanged.connect(self.auto_recognize_item.set)
        self.auto_recognize_item.valueChanged.connect(
            self.auto_recognize_card.setChecked
        )
        self.model_selection_card: ModelSelectionCard = ModelSelectionCard(self)
        self._sync_initial_model_selection()
        self.model_selection_card.modelChanged.connect(self._on_model_changed)
        self.export_path_card: ExportOptionCard = ExportOptionCard(self)

        self._init_layout()

    def _sync_initial_model_selection(self) -> None:
        """将模型卡片的初始选择复制到当前 session。"""
        self.session.model_selection.pa_model_path = (
            self.model_selection_card.selected_model_path("PA")
        )
        self.session.model_selection.dtoa_model_path = (
            self.model_selection_card.selected_model_path("DTOA")
        )

    def _on_model_changed(self, model_type: str, model_path: str) -> None:
        """将模型卡片选择写入当前 session 并触发保存回调。"""
        if model_type == "PA":
            self.session.model_selection.pa_model_path = model_path
        elif model_type == "DTOA":
            self.session.model_selection.dtoa_model_path = model_path
        else:
            return

        if self._on_config_changed:
            self._on_config_changed()

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
