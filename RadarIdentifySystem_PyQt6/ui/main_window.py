# -*- coding: utf-8 -*-
"""
ui/main_window.py
动态导航主窗口：
  - 欢迎页（固定首项）
  - 每个仓库对应一个侧边栏导航项（运行时动态添加/移除）
  - 设置页（固定末项）
"""
import logging

from PyQt6.QtCore import Qt, QSize, QTimer, QEvent, QObject
from PyQt6.QtWidgets import QWidget, QApplication, QAbstractButton
from PyQt6.QtGui import QIcon
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    InfoBar, InfoBarPosition, SystemThemeListener, SplashScreen
)

from ui.interfaces.home_interface import HomeInterface
from ui.interfaces.slice_interface import SliceInterface
from ui.interfaces.setting_interface import SettingInterface

LOGGER = logging.getLogger(__name__)

class MainWindow(FluentWindow):
    """RadarIdentifySystem 主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.initWindow()

        # 创建子页面
        self.homeInterface = HomeInterface(self)
        self.sliceInterface = SliceInterface(self)
        self.iconInterface = SettingInterface(self)


        self.themeListener = SystemThemeListener(self)

        self.connectSignalToSlot()

        self.initNavigation()
        self._enable_pointing_hand_cursor()

        timer = QTimer()
        timer.singleShot(1000, self.splashScreen.finish)
        # self.splashScreen.finish()

        self.themeListener.start()

    def _enable_pointing_hand_cursor(self) -> None:
        """为全局按钮统一设置手指光标。"""
        # 初始化已创建按钮的光标
        self._apply_pointing_cursor(self)
        # 监听后续动态创建按钮（组件库内部可能延迟创建）
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def _apply_pointing_cursor(self, root: QObject) -> None:
        """递归设置按钮光标。

        参数说明：
            root (QObject): 需要遍历的根对象。
        """
        # 扫描所有按钮子控件
        if isinstance(root, QWidget):
            for button in root.findChildren(QAbstractButton):
                # 设置手指光标
                button.setCursor(Qt.CursorShape.PointingHandCursor)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """事件过滤器。

        功能描述：
            处理组件库延迟创建按钮时的光标同步问题。
        """
        # 处理按钮显示事件
        if isinstance(obj, QAbstractButton) and event.type() in (QEvent.Type.Show, QEvent.Type.Polish):
            # 强制覆盖手指光标
            obj.setCursor(Qt.CursorShape.PointingHandCursor)
        # 处理动态子对象创建事件
        elif event.type() == QEvent.Type.ChildAdded and hasattr(event, "child"):
            child = event.child()
            if isinstance(child, QAbstractButton):
                # 同步新建按钮光标
                child.setCursor(Qt.CursorShape.PointingHandCursor)
            elif isinstance(child, QWidget):
                # 递归同步新建容器下的按钮光标
                self._apply_pointing_cursor(child)
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def initNavigation(self) -> None:
        # 主页
        self.addSubInterface(
            self.homeInterface, FluentIcon.HOME, "主页",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.sliceInterface, FluentIcon.PIE_SINGLE, "切片处理",
            position=NavigationItemPosition.TOP,
        )

        # 设置页
        self.addSubInterface(
            self.iconInterface, FluentIcon.SETTING, "设置",
            position=NavigationItemPosition.BOTTOM,
        )
    def initWindow(self) -> None:
        self.setWindowIcon(QIcon(':/RadarIdentifySystem/images/icon.png'))
        self.setWindowTitle("RadarIdentifySystem")
        self.resize(1500, 1000)
        self.setMinimumSize(1200, 800)
        
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
        # 解除事件过滤器
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        super().closeEvent(event)
