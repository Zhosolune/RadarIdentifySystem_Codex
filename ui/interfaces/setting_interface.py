"""设置页面视图。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import (
    CustomColorSettingCard,
    ExpandLayout,
    FluentIcon,
    InfoBar,
    OptionsSettingCard,
    ScrollArea,
    SettingCardGroup,
    setTheme,
    setThemeColor,
)

from app.app_config import appConfig
from app.style_sheet import StyleSheet
from ui.adapters import ResponsiveContentWidthAdapter
from ui.components import LogSettingCard
from ui.components.spin_box_setting_card import SpinBoxSettingCard
from ui.controllers.setting_controller import SettingController


class SettingInterface(ScrollArea):
    """组合外观与日志设置卡片。

    Attributes:
        settingScrollWidget [QWidget]: 滚动区域的内容容器。
        cardGroupsLayout [ExpandLayout]: 设置卡片组布局。
        log_card [LogSettingCard]: 日志设置卡片。
    """

    MAX_CONTENT_WIDTH = 860

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化设置页面。

        Args:
            parent [QWidget | None]: 父组件。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.settingScrollWidget = QWidget()
        self.cardGroupsLayout = ExpandLayout(self.settingScrollWidget)

        self._interfaceGroup = SettingCardGroup(
            "外观",
            self.settingScrollWidget,
        )
        self._themeCard = OptionsSettingCard(
            appConfig.themeMode,
            FluentIcon.BRUSH,
            "主题",
            "选择应用显示主题",
            texts=["浅色", "深色", "跟随系统"],
            parent=self._interfaceGroup,
        )
        self._themeColorCard = CustomColorSettingCard(
            appConfig.themeColor,
            FluentIcon.PALETTE,
            "主题色",
            "改变应用显示的主题色",
            parent=self._interfaceGroup,
        )
        self._zoomCard = OptionsSettingCard(
            appConfig.dpiScale,
            FluentIcon.ZOOM,
            "界面缩放",
            "改变应用显示的界面缩放比例",
            texts=[
                "100%",
                "125%",
                "150%",
                "175%",
                "200%",
                "使用系统设置",
            ],
            parent=self._interfaceGroup,
        )

        self._advancedGroup = SettingCardGroup(
            "高级",
            self.settingScrollWidget,
        )
        self._full_speed_device_card = OptionsSettingCard(
            appConfig.fullSpeedComputeDevice,
            FluentIcon.ROBOT,
            "全速推理设备",
            "自动模式优先使用可用 GPU Provider，否则回退到 CPU",
            texts=["自动", "仅 CPU", "GPU 优先"],
            parent=self._advancedGroup,
        )
        self._full_speed_concurrency_card = SpinBoxSettingCard(
            appConfig.fullSpeedMaxConcurrentTasks,
            FluentIcon.SPEED_HIGH,
            "同时运行的全速任务数",
            "达到上限时拒绝启动新任务，不影响正在执行的任务",
            unit="个",
            parent=self._advancedGroup,
        )
        self._full_speed_workers_card = SpinBoxSettingCard(
            appConfig.fullSpeedRecognitionWorkers,
            FluentIcon.SPEED_MEDIUM,
            "单任务识别线程上限",
            "限制簇级并发；ONNX 单次推理固定使用一个内部线程",
            unit="线程",
            parent=self._advancedGroup,
        )
        # 实际路径由 SettingController 从配置边界读取后写回。
        self.log_card = LogSettingCard(
            "正在读取日志目录",
            self._advancedGroup,
        )

        self._init_widget()
        self._responsive_width_adapter = ResponsiveContentWidthAdapter(
            self.viewport(),
            self.cardGroupsLayout,
            max_content_width=self.MAX_CONTENT_WIDTH,
        )
        self._controller = SettingController(self)

    def _init_widget(self) -> None:
        """初始化页面属性、样式和布局。"""
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setViewportMargins(0, 28, 0, 20)
        self.setWidget(self.settingScrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setObjectName("settingInterface")
        self.settingScrollWidget.setObjectName("settingScrollWidget")
        StyleSheet.SETTING_INTERFACE.apply(self)

        self.cardGroupsLayout.setSpacing(28)
        self.cardGroupsLayout.setContentsMargins(36, 10, 36, 0)
        self._interfaceGroup.addSettingCard(self._themeCard)
        self._interfaceGroup.addSettingCard(self._themeColorCard)
        self._interfaceGroup.addSettingCard(self._zoomCard)
        self._advancedGroup.addSettingCard(
            self._full_speed_device_card
        )
        self._advancedGroup.addSettingCard(
            self._full_speed_concurrency_card
        )
        self._advancedGroup.addSettingCard(
            self._full_speed_workers_card
        )
        self._advancedGroup.addSettingCard(self.log_card)
        self.cardGroupsLayout.addWidget(self._interfaceGroup)
        self.cardGroupsLayout.addWidget(self._advancedGroup)

        appConfig.dpiScale.valueChanged.connect(
            self._on_dpi_scale_changed
        )
        appConfig.themeChanged.connect(setTheme)
        self._themeColorCard.colorChanged.connect(setThemeColor)

    def _on_dpi_scale_changed(self, _scale: object) -> None:
        """提示缩放配置将在重启后生效。"""
        InfoBar.success(
            "设置成功",
            "界面缩放比例已修改，将在重启软件后生效。",
            parent=self.window(),
        )
