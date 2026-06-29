"""绘图选项卡片组件。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import ComboBox, ExpandGroupSettingCard, FluentIcon, OptionsValidator

from app.session_config_item import SessionConfigItem
from core.models.processing_session import ProcessingSession

LOGGER = logging.getLogger(__name__)


class PlotOptionCard(ExpandGroupSettingCard):
    """绘图选项卡片组件。

    使用 ExpandGroupSettingCard 包裹当前 session 的绘图相关子配置卡片，
    包含“图像展示模式”和“图像绘制模式”两项下拉选择配置。

    Attributes:
        session: 当前切片页面所属的处理 session。
        show_mode_item: 绑定到当前 session 的图像展示模式设置项。
        scale_mode_item: 绑定到当前 session 的图像绘制模式设置项。
        show_mode_combo: 图像展示模式下拉框。
        scale_mode_combo: 图像绘制模式下拉框。
    """

    showModeChanged = pyqtSignal(str)
    scaleModeChanged = pyqtSignal(str)

    _SHOW_MODE_OPTIONS: list[str] = ["ALL", "IDENTIFIED_ONLY"]
    _SCALE_MODE_OPTIONS: list[str] = [
        "STRETCH",
        "STRETCH_BILINEAR",
        "STRETCH_NEAREST_PRESERVE",
    ]

    def __init__(
        self,
        session: ProcessingSession,
        on_config_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """初始化绘图控制卡片。

        Args:
            session: 当前页面所属 session，用于读写 session 级绘图配置。
            on_config_changed: 子配置变更后的保存回调，默认不回调。
            parent: 父级控件。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(
            icon=FluentIcon.PHOTO,
            title="绘图选项",
            content="调整图像的展示规则与绘制算法",
            parent=parent,
        )
        self.setObjectName("PlotControlSettingCard")
        self.session = session
        self.show_mode_item = SessionConfigItem(
            self.session.config_snapshot,
            "plot.only_show_identified",
            "IDENTIFIED_ONLY",
            validator=OptionsValidator(self._SHOW_MODE_OPTIONS),
            on_changed=on_config_changed,
        )
        self.scale_mode_item = SessionConfigItem(
            self.session.config_snapshot,
            "plot.scale_mode",
            "STRETCH",
            validator=OptionsValidator(self._SCALE_MODE_OPTIONS),
            on_changed=on_config_changed,
        )

        # 构建展示模式下拉框并绑定 session 级配置项。
        self.show_mode_combo = self._create_combobox(
            self.show_mode_item,
            ["展示全部聚类结果", "仅展示识别后结果"],
        )
        self.addGroup(FluentIcon.FILTER, "图像展示模式", None, self.show_mode_combo)

        # 构建绘制模式下拉框并绑定 session 级配置项。
        self.scale_mode_combo = self._create_combobox(
            self.scale_mode_item,
            ["模式一：原始拉伸", "模式二：双线性插值", "模式三：最近邻保留"],
        )
        self.addGroup(FluentIcon.BRUSH, "图像绘制模式", None, self.scale_mode_combo)

        self.show_mode_item.valueChanged.connect(self._on_show_mode_value_changed)
        self.scale_mode_item.valueChanged.connect(self._on_scale_mode_value_changed)

    def _create_combobox(
        self,
        config_item: SessionConfigItem,
        texts: list[str],
    ) -> ComboBox:
        """创建绑定 session 配置项的下拉框。"""
        combo_box = ComboBox()
        combo_box.addItems(texts)
        combo_box.setCurrentIndex(self._index_of_value(config_item, config_item.value))
        combo_box.currentIndexChanged.connect(
            lambda index, item=config_item: self._on_combo_changed(item, index)
        )
        config_item.valueChanged.connect(
            lambda value, box=combo_box, item=config_item: self._on_config_changed(
                box, item, value
            )
        )
        return combo_box

    def _index_of_value(self, config_item: SessionConfigItem, value: object) -> int:
        """返回配置值在可选项中的索引。"""
        options = getattr(config_item.validator, "options", [])
        return options.index(value) if value in options else 0

    def _on_combo_changed(self, config_item: SessionConfigItem, index: int) -> None:
        """当下拉框选择改变时，同步更新当前 session 配置。"""
        options = getattr(config_item.validator, "options", [])
        if not 0 <= index < len(options):
            return
        config_item.set(options[index])

    def _on_config_changed(
        self,
        combobox: ComboBox,
        config_item: SessionConfigItem,
        new_value: object,
    ) -> None:
        """当 session 配置改变时，同步更新下拉框显示。"""
        index = self._index_of_value(config_item, new_value)
        if combobox.currentIndex() != index:
            combobox.setCurrentIndex(index)

    def _on_show_mode_value_changed(self, new_value: object) -> None:
        """记录展示模式变更并通知页面刷新。"""
        rendered_value = str(new_value)
        LOGGER.info(
            "更新当前 Session 聚类展示模式：%s",
            rendered_value,
            extra={"session_id": self.session.session_id},
        )
        self.showModeChanged.emit(rendered_value)

    def _on_scale_mode_value_changed(self, new_value: object) -> None:
        """记录绘制模式变更并通知页面刷新。"""
        rendered_value = str(new_value)
        LOGGER.info(
            "更新当前 Session 图像绘制模式：%s",
            rendered_value,
            extra={"session_id": self.session.session_id},
        )
        self.scaleModeChanged.emit(rendered_value)
