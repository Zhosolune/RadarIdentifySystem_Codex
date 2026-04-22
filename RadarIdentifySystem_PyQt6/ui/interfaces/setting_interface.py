# -*- coding: utf-8 -*-
"""
ui/interfaces/setting_interface.py
设置界面。
"""
import logging

from PyQt6.QtWidgets import QWidget, QFileDialog
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from qfluentwidgets import (
    ScrollArea, SettingCardGroup, OptionsSettingCard, FluentIcon,
    ExpandGroupSettingCard, InfoBar, ExpandLayout, PushButton, CustomColorSettingCard, 

)
from qfluentwidgets import qconfig, setTheme, setThemeColor
from app.app_config import appConfig
from app.style_sheet import StyleSheet
from app.logger import clear_all_logs, get_current_log_file_path, get_log_dir_path

LOGGER = logging.getLogger(__name__)

class LogSettingCard(ExpandGroupSettingCard):
    """ 日志设置卡片 """

    def __init__(self, parent=None):
        # 头部内容显示当前生效日志目录，避免出现空文本。
        super().__init__(
            FluentIcon.DOCUMENT,
            "日志选项",
            str(get_log_dir_path()),
            parent
        )

        # 初始化按钮
        self.changePathBtn = PushButton("更改")
        self.openPathBtn = PushButton("打开")
        self.clearLogsBtn = PushButton("清理")
        
        self.changePathBtn.setFixedWidth(120)
        self.openPathBtn.setFixedWidth(120)
        self.clearLogsBtn.setFixedWidth(120)

        # 添加设置组
        self.logPathGroup = self.addGroup(
            FluentIcon.FOLDER,
            "自定义日志保存路径",
            "选择全量系统运行日志的统一落盘文件夹",
            self.changePathBtn
        )
        
        self.addGroup(
            FluentIcon.VIEW,
            "打开日志所在目录",
            "在文件管理器中浏览日志",
            self.openPathBtn
        )
        
        self.addGroup(
            FluentIcon.DELETE,
            "清理全部日志文件",
            "永久删除磁盘上所有当前配置目录下的日志",
            self.clearLogsBtn
        )

    def setLogPath(self, path: str) -> None:
        """更新日志路径显示。

        功能描述：
            同步更新日志设置卡头部内容，保持与当前配置目录一致。

        参数说明：
            path (str): 日志目录字符串。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        self.setContent(path)


class SettingInterface(ScrollArea):
    # 内容区最大宽度（px），超出后左右边距自动增大实现居中
    MAX_CONTENT_WIDTH = 860

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.settingScrollWidget = QWidget()
        self.cardGroupsLayout = ExpandLayout(self.settingScrollWidget)

        # 外观
        self._interfaceGroup = SettingCardGroup("外观", self.settingScrollWidget)
        # 主题设置卡
        self._themeCard = OptionsSettingCard(
            appConfig.themeMode,
            FluentIcon.BRUSH,
            "主题",
            "选择应用显示主题",
            texts=["浅色", "深色", "跟随系统"],
            parent=self._interfaceGroup,
        )
        # 主题色设置卡
        self._themeColorCard = CustomColorSettingCard(
            appConfig.themeColor,
            FluentIcon.PALETTE,
            "主题色",
            "改变应用显示的主题色",
            parent=self._interfaceGroup,
        )
        # 界面缩放设置卡
        self._zoomCard = OptionsSettingCard(
            appConfig.dpiScale,
            FluentIcon.ZOOM,
            "界面缩放",
            "改变应用显示的界面缩放比例",
            texts=[
                "100%", "125%", "150%", "175%", "200%",
                "使用系统设置"
            ],
            parent=self._interfaceGroup
        )

        # 高级
        self._advancedGroup = SettingCardGroup("高级", self.settingScrollWidget)
        self._logCard = LogSettingCard(self._advancedGroup)

        self._initWidget()

    def _initWidget(self):
        # self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 28, 0, 20)
        self.setWidget(self.settingScrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setObjectName("settingInterface")

        # 初始化样式
        self.settingScrollWidget.setObjectName('settingScrollWidget')
        # self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        # 初始化布局
        self._initLayout()
        self._connectSignalToSlot()

    def _initLayout(self):

        self._interfaceGroup.addSettingCard(self._themeCard)
        self._interfaceGroup.addSettingCard(self._themeColorCard)
        self._interfaceGroup.addSettingCard(self._zoomCard)

        self._advancedGroup.addSettingCard(self._logCard)

        # 添加设置卡片组到布局
        self.cardGroupsLayout.setSpacing(28)
        self.cardGroupsLayout.setContentsMargins(36, 10, 36, 0)
        self.cardGroupsLayout.addWidget(self._interfaceGroup)
        self.cardGroupsLayout.addWidget(self._advancedGroup)

    def resizeEvent(self, event):
        """动态调整左右边距，让卡片内容区不超过 MAX_CONTENT_WIDTH 并保持水平居中。"""
        super().resizeEvent(event)
        viewport_w = self.viewport().width()
        h_margin = max(36, (viewport_w - self.MAX_CONTENT_WIDTH) // 2)
        self.cardGroupsLayout.setContentsMargins(h_margin, 10, h_margin, 0)

    def _connectSignalToSlot(self):
        # 连接信号
        self._logCard.changePathBtn.clicked.connect(self._on_change_log_path)
        self._logCard.openPathBtn.clicked.connect(self._on_open_log_path)
        self._logCard.clearLogsBtn.clicked.connect(self._on_clear_logs)

        appConfig.themeChanged.connect(setTheme)
        self._themeColorCard.colorChanged.connect(lambda c: setThemeColor(c))
        
        # 缩放比例改变提示
        appConfig.dpiScale.valueChanged.connect(self._on_dpi_scale_changed)
        # self.micaCard.checkedChanged.connect(signalBus.micaEnableChanged)        

    def _on_dpi_scale_changed(self, scale) -> None:
        InfoBar.success("设置成功", "界面缩放比例已修改，将在重启软件后生效。", parent=self.window())

    def _on_change_log_path(self) -> None:
        # 获取当前日志目录路径
        current_path = str(get_log_dir_path())
        path = QFileDialog.getExistingDirectory(self, "选择日志保存目录", current_path)
        if path:
            # 将新路径写入配置
            qconfig.set(appConfig.logDir, path)
            self._logCard.setLogPath(path)
            LOGGER.info("日志目录已更新为：%s", path, extra={"session_id": "-"})
            InfoBar.success("设置成功", "新的日志路径已被保存，将在下次启动时生效。", parent=self.window())

    def _on_open_log_path(self) -> None:
        # 获取当前日志目录路径
        log_dir = get_log_dir_path()
        if log_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))
            LOGGER.info("已打开日志目录：%s", log_dir, extra={"session_id": "-"})
        else:
            LOGGER.warning("日志目录不存在：%s", log_dir, extra={"session_id": "-"})
            InfoBar.warning("未找到", f"路径不存在：{log_dir}", parent=self.window())

    def _on_clear_logs(self) -> None:
        try:
            LOGGER.info("开始清理日志，当前运行日志文件：%s", get_current_log_file_path(), extra={"session_id": "-"})
            count = clear_all_logs()
            if count == 0:
                LOGGER.info("日志清理完成，无历史日志文件需要删除", extra={"session_id": "-"})
                InfoBar.success("已清理", "当前没有需要清理的日志文件。", parent=self.window())
            else:
                LOGGER.info("日志清理完成，删除数量：%s", count, extra={"session_id": "-"})
                InfoBar.success("清理完毕", f"共清理了 {count} 个历史日志文件（当次运行日志可能因占用无法删除）。", parent=self.window())
        except Exception as e:
            LOGGER.exception("清理日志失败：%s", e, extra={"session_id": "-"})
            InfoBar.error("清理异常", str(e), parent=self.window())
