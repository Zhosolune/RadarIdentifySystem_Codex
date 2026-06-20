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
from qfluentwidgets.common.router import qrouter

from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingSession
from runtime.session_config_factory import create_session_config_from_global
from runtime.session_registry import SessionRegistry
from ui.interfaces.home_interface import HomeInterface
from ui.interfaces.slice_interface import SliceInterface
from ui.interfaces.model_manager_interface import ModelManagerInterface
from ui.interfaces.setting_interface import SettingInterface
from ui.interfaces.params_interface import ParamsInterface

LOGGER = logging.getLogger(__name__)

class MainWindow(FluentWindow):
    """RadarIdentifySystem 主窗口。"""

    def __init__(self, session_registry: SessionRegistry | None = None) -> None:
        """初始化主窗口。

        Args:
            session_registry [SessionRegistry | None]: session 注册表；为 None 时使用默认持久化注册表。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当默认 SessionRegistry 初始化目录失败时抛出。
        """
        super().__init__()
        self.initWindow()

        # 创建子页面
        self.homeInterface = HomeInterface(self)
        self.sliceInterface = SliceInterface(self)
        self.modelManagerInterface = ModelManagerInterface(self)
        self.iconInterface = SettingInterface(self)
        self.paramsInterface = ParamsInterface(self)


        self.themeListener = SystemThemeListener(self)

        self.connectSignalToSlot()

        self._session_interfaces: dict[str, SliceInterface] = {}
        self.session_registry = session_registry or SessionRegistry()
        self.initNavigation()
        self.restore_session_interfaces()
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
            self.modelManagerInterface, FluentIcon.SETTING, "模型管理",
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.paramsInterface, FluentIcon.COMMAND_PROMPT, "参数配置",
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.iconInterface, FluentIcon.SETTING, "设置",
            position=NavigationItemPosition.BOTTOM,
        )

    def create_session_interface(self, session: ProcessingSession) -> SliceInterface:
        """创建或复用指定 session 对应的切片页面。

        Args:
            session [ProcessingSession]: 需要绑定到切片页面的处理会话。

        Returns:
            SliceInterface: 已创建或已存在的动态切片页面。

        Raises:
            无显式抛出异常。
        """
        existing_interface = self._session_interfaces.get(session.session_id)
        if existing_interface is not None:
            # 已有页面时直接激活，避免为同一 session 重复创建导航项。
            self.activate_session_interface(session.session_id)
            return existing_interface

        interface = SliceInterface(
            self,
            session=session,
            on_config_changed=lambda: self.session_registry.persist_session(
                session.session_id
            ),
        )
        interface.setObjectName(f"sessionSliceInterface_{session.session_id}")
        self.addSubInterface(
            interface,
            FluentIcon.PIE_SINGLE,
            session.display_name,
            position=NavigationItemPosition.TOP,
        )
        self._session_interfaces[session.session_id] = interface
        self.activate_session_interface(session.session_id)
        return interface

    def create_session_from_parsed(self, session: ProcessingSession) -> SliceInterface:
        """注册解析完成的 session 并创建对应动态页面。

        Args:
            session [ProcessingSession]: 主页解析完成后等待确认导入的 session。

        Returns:
            SliceInterface: 绑定该 session 的动态切片页面。

        Raises:
            OSError: 当 session 持久化写入失败时由注册表抛出。
            ValueError: 当 session_id 非法时由持久化层抛出。
        """
        session.config_snapshot = create_session_config_from_global()
        interface_existed = session.session_id in self._session_interfaces
        interface = self.create_session_interface(session)
        try:
            self.session_registry.register(session)
        except Exception:
            # 注册失败时只回滚本次创建的 UI 页面，避免留下未持久化的动态页。
            if not interface_existed:
                self.close_session_interface(session.session_id)
            raise
        self.refresh_session_manager_panel()
        signal_bus.session_registered.emit(session.session_id)
        signal_bus.session_activated.emit(session.session_id)
        return interface

    def session_interface(self, session_id: str) -> SliceInterface | None:
        """按 session_id 查找动态切片页面。

        Args:
            session_id [str]: 需要查询的 session 唯一标识。

        Returns:
            SliceInterface | None: 找到时返回页面实例，否则返回 None。

        Raises:
            无显式抛出异常。
        """
        return self._session_interfaces.get(session_id)

    def restore_session_interfaces(self) -> list[str]:
        """从注册表恢复动态 session 页面。

        Args:
            无。

        Returns:
            list[str]: 成功恢复为动态页面的 session id 列表。

        Raises:
            无显式抛出异常；损坏 session 由注册表和持久化层跳过。

        Example:
            >>> window = None
            >>> window is None
            True
        """
        restored_sessions = self.session_registry.restore()
        restored_ids: list[str] = []
        active_session_id = self.session_registry.active_session_id
        for session in restored_sessions:
            self.create_session_interface(session)
            restored_ids.append(session.session_id)

        if active_session_id:
            self.activate_session_interface(active_session_id)
        self.refresh_session_manager_panel()
        return restored_ids

    def refresh_session_manager_panel(self) -> None:
        """刷新主页 session 管理器列表。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> hasattr(object(), "session_manager_panel")
            False
        """
        if hasattr(self.homeInterface, "session_manager_panel"):
            self.homeInterface.session_manager_panel.set_sessions(
                self.session_registry.all_sessions()
            )

    def activate_session_interface(self, session_id: str) -> None:
        """激活指定 session 的动态切片页面。

        Args:
            session_id [str]: 需要激活的 session 唯一标识。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        interface = self._session_interfaces.get(session_id)
        if interface is None:
            return

        # 复用 FluentWindow 的导航切换逻辑，同步堆栈页与导航选中项。
        self.switchTo(interface)

    def close_session_interface(self, session_id: str) -> None:
        """关闭并移除指定 session 的动态切片页面。

        Args:
            session_id [str]: 需要关闭的 session 唯一标识。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        interface = self._session_interfaces.pop(session_id, None)
        if interface is None:
            return

        route_key = interface.objectName()
        # 先回到主页，再移除动态页，避免 QStackedWidget 自动切到无关页面并污染 qrouter 历史。
        if self.stackedWidget.currentWidget() is interface:
            self.switchTo(self.homeInterface)

        qrouter.remove(route_key)
        self.removeInterface(interface, isDelete=True)

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
        self.homeInterface.session_manager_panel.sessionActivated.connect(
            self.activate_session_interface
        )

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
