# -*- coding: utf-8 -*-
"""
ui/main_window.py
动态导航主窗口：
  - 欢迎页（固定首项）
  - 每个仓库对应一个侧边栏导航项（运行时动态添加/移除）
  - 设置页（固定末项）
"""
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QIcon
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    InfoBar, InfoBarPosition, SystemThemeListener, SplashScreen
)
from app.logger import get_logger

from ui.interfaces.home_interface import HomeInterface
from ui.interfaces.setting_interface import SettingInterface

LOGGER = get_logger("ui.mainWindow")

class MainWindow(FluentWindow):
    """RadarIdentifySystem 主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.initWindow()

        # 创建子页面
        self.homeInterface = HomeInterface(self)
        self.iconInterface = SettingInterface(self)


        self.themeListener = SystemThemeListener(self)

        self.connectSignalToSlot()

        self.initNavigation()

        timer = QTimer()
        timer.singleShot(1000, self.splashScreen.finish)
        # self.splashScreen.finish()

        self.themeListener.start()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def initNavigation(self) -> None:
        # 主页
        self.addSubInterface(
            self.homeInterface, FluentIcon.HOME, "主页",
            position=NavigationItemPosition.TOP,
        )

        # 设置页
        self.addSubInterface(
            self.iconInterface, FluentIcon.SETTING, "设置",
            position=NavigationItemPosition.BOTTOM,
        )
    def initWindow(self) -> None:
        self.setWindowIcon(QIcon(':/RadarIdentifySystem/images/logo.png'))
        self.setWindowTitle("RadarIdentifySystem")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)
        
        # 启动页
        self.splashScreen = SplashScreen(QIcon(':/RadarIdentifySystem/images/brand.png'), self)
        self.splashScreen.setIconSize(QSize(400, 400))
        self.splashScreen.raise_()
        
        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
        self.show()
        QApplication.processEvents()


    def connectSignalToSlot(self) -> None:
        """连接信号到槽函数。"""
        pass

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        super().closeEvent(event)