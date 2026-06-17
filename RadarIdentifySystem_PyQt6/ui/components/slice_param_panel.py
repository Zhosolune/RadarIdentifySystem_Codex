"""提供切片参数抽屉的独立内容面板。"""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, SwitchSettingCard

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
        """按固定顺序排列参数设置卡片。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.auto_recognize_card)
        layout.addWidget(self.model_selection_card)
        layout.addWidget(self.export_path_card)
        layout.addStretch(1)
