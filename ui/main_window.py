# -*- coding: utf-8 -*-
"""应用主窗口与动态页面宿主。

主窗口仅负责窗口外观、固定导航、动态 Session 页面的挂载与切换，以及应用
关闭时的 UI 生命周期。Session 业务编排和全速任务交互分别由专用控制器承担。
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import QAbstractButton, QApplication, QWidget
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
    SplashScreen,
    SystemThemeListener,
)
from qfluentwidgets.common.router import qrouter

from app.application import ApplicationServices, create_application_services
from app.custom_icon import CustomIcon
from runtime.data_pool_registry import DataPoolRegistry
from runtime.full_speed_session_registry import FullSpeedSessionRegistry
from runtime.session_coordinator import ProcessingSession
from runtime.session_registry import SessionRegistry
from ui.controllers.full_speed_session_controller import (
    FullSpeedSessionController,
)
from ui.controllers.home_controller import HomeController
from ui.controllers.session_manager_controller import SessionManagerController
from ui.interfaces.home_interface import HomeInterface
from ui.interfaces.model_manager_interface import ModelManagerInterface
from ui.interfaces.params_interface import ParamsInterface
from ui.interfaces.setting_interface import SettingInterface
from ui.interfaces.slice_interface import SliceInterface

class MainWindow(FluentWindow):
    """承载固定导航和动态 Session 页面的应用主窗口。

    Attributes:
        services: 应用级共享运行期服务。
        home_controller: 主页交互控制器。
        session_manager_controller: 交互式 Session 管理控制器。
        full_speed_controller: 全速 Session 面板控制器。
    """

    def __init__(
        self,
        services: ApplicationServices | None = None,
        *,
        session_registry: SessionRegistry | None = None,
        data_pool_registry: DataPoolRegistry | None = None,
        full_speed_session_registry: FullSpeedSessionRegistry | None = None,
    ) -> None:
        """初始化主窗口。

        生产入口应显式传入 ``ApplicationServices``。保留独立注册器参数用于
        现有测试和嵌入场景，其目录装配仍统一委托给应用装配入口。

        Args:
            services [ApplicationServices | None]: 已完成装配的应用服务集合。
            session_registry [SessionRegistry | None]: 测试用交互式 Session 注册表。
            data_pool_registry [DataPoolRegistry | None]: 测试用数据池注册表。
            full_speed_session_registry [FullSpeedSessionRegistry | None]: 测试用全速注册表。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 同时传入服务集合和独立注册器时抛出。
            OSError: 默认持久化目录初始化失败时抛出。
        """
        if services is not None and any(
            registry is not None
            for registry in (
                session_registry,
                data_pool_registry,
                full_speed_session_registry,
            )
        ):
            raise ValueError("services 与独立注册器参数不能同时传入")

        super().__init__()
        self.initWindow()
        self.services = services or create_application_services(
            session_registry=session_registry,
            data_pool_registry=data_pool_registry,
            full_speed_session_registry=full_speed_session_registry,
        )

        # 保留只读别名，避免现有嵌入调用方在本次职责迁移中中断。
        self.session_registry = self.services.session_registry
        self.data_pool_registry = self.services.data_pool_registry
        self.full_speed_session_registry = (
            self.services.full_speed_session_registry
        )
        self.full_speed_workflow = self.services.full_speed_workflow

        self.homeInterface = HomeInterface(self)
        self.modelManagerInterface = ModelManagerInterface(self)
        self.iconInterface = SettingInterface(self)
        self.paramsInterface = ParamsInterface(self)
        self.themeListener = SystemThemeListener(self)
        self._session_interfaces: dict[str, SliceInterface] = {}
        self.modelManagerInterface.enabledModelsChanged.connect(
            self._refresh_session_model_candidates
        )

        self.session_manager_controller = SessionManagerController(
            self.homeInterface.session_manager_panel,
            self,
            self.services.session_coordinator,
        )
        self.home_controller = HomeController(
            self.homeInterface,
            self.services.data_pool_registry,
            self.services.session_coordinator,
            self.session_manager_controller.add_prepared_session,
        )
        self.full_speed_controller = FullSpeedSessionController(
            self.homeInterface.full_speed_session_panel,
            self.services.session_coordinator,
            self.services.full_speed_session_registry,
            self.services.full_speed_workflow,
            self,
        )

        self.initNavigation()
        self.session_manager_controller.restore_sessions()
        self.full_speed_controller.restore_sessions()
        self._enable_pointing_hand_cursor()

        QTimer.singleShot(1000, self.splashScreen.finish)
        self.themeListener.start()

    def _enable_pointing_hand_cursor(self) -> None:
        """为全局按钮统一设置手指光标。"""
        self._apply_pointing_cursor(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def _apply_pointing_cursor(self, root: QObject) -> None:
        """递归设置指定控件树中的按钮光标。

        Args:
            root [QObject]: 需要遍历的根对象。

        Returns:
            None: 无返回值。
        """
        if isinstance(root, QWidget):
            for button in root.findChildren(QAbstractButton):
                button.setCursor(Qt.CursorShape.PointingHandCursor)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """同步延迟创建按钮的手指光标。

        Args:
            obj [QObject]: 事件目标对象。
            event [QEvent]: Qt 事件对象。

        Returns:
            bool: 父类事件过滤器的处理结果。
        """
        if isinstance(obj, QAbstractButton) and event.type() in (
            QEvent.Type.Show,
            QEvent.Type.Polish,
        ):
            obj.setCursor(Qt.CursorShape.PointingHandCursor)
        elif event.type() == QEvent.Type.ChildAdded and hasattr(event, "child"):
            child = event.child()
            if isinstance(child, QAbstractButton):
                child.setCursor(Qt.CursorShape.PointingHandCursor)
            elif isinstance(child, QWidget):
                self._apply_pointing_cursor(child)
        return super().eventFilter(obj, event)

    def initNavigation(self) -> None:
        """注册主页和底部固定导航页面。

        Returns:
            None: 无返回值。
        """
        self.addSubInterface(
            self.homeInterface,
            FluentIcon.HOME,
            "主页",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.modelManagerInterface,
            CustomIcon.MODELS,
            "模型管理",
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.paramsInterface,
            FluentIcon.COMMAND_PROMPT,
            "参数配置",
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(
            self.iconInterface,
            FluentIcon.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM,
        )

    def create_session_interface(
        self,
        session: ProcessingSession,
        activate: bool = True,
    ) -> SliceInterface:
        """创建或复用指定 Session 对应的动态切片页面。

        Args:
            session [ProcessingSession]: 需要绑定的交互式 Session。
            activate [bool]: 创建后是否立即切换到该页面。

        Returns:
            SliceInterface: 已创建或已存在的动态切片页面。
        """
        existing_interface = self._session_interfaces.get(session.session_id)
        if existing_interface is not None:
            if activate:
                self.show_session_interface(session.session_id)
            return existing_interface

        interface = SliceInterface(
            self,
            session=session,
            on_config_changed=lambda: (
                self.services.session_coordinator.persist_interactive_session(
                    session.session_id
                )
            ),
        )
        interface.setObjectName(
            f"sessionSliceInterface_{session.session_id}"
        )
        self.addSubInterface(
            interface,
            FluentIcon.PIE_SINGLE,
            session.display_name,
            position=NavigationItemPosition.TOP,
        )
        self._session_interfaces[session.session_id] = interface
        if activate:
            self.show_session_interface(session.session_id)
        return interface

    def _refresh_session_model_candidates(self, model_type: str) -> None:
        """刷新全部已挂载 Session 抽屉中的指定模型候选列表。"""
        for interface in self._session_interfaces.values():
            interface.slice_param_panel.model_selection_card.refresh_enabled_models(
                model_type
            )

    def session_interface(self, session_id: str) -> SliceInterface | None:
        """按 ID 查找动态切片页面。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            SliceInterface | None: 找到的动态页面；不存在时返回 None。
        """
        return self._session_interfaces.get(session_id)

    def enabled_session_ids(self) -> set[str]:
        """返回当前已经挂载动态页面的 Session ID。

        Returns:
            set[str]: 已启用动态页面的 Session ID 集合。
        """
        return set(self._session_interfaces)

    def show_home_interface(self) -> None:
        """切换到主页。

        Returns:
            None: 无返回值。
        """
        self.switchTo(self.homeInterface)

    def show_session_interface(self, session_id: str) -> None:
        """仅切换到指定 Session 页面，不修改运行期活动状态。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            None: 无返回值。
        """
        interface = self._session_interfaces.get(session_id)
        if interface is not None:
            self.switchTo(interface)

    def set_session_navigation_text(self, session_id: str, text: str) -> None:
        """更新动态 Session 导航项文案。

        Args:
            session_id [str]: Session 唯一标识。
            text [str]: 新导航文案。

        Returns:
            None: 无返回值。
        """
        interface = self._session_interfaces.get(session_id)
        if interface is None:
            return
        navigation_item = self.navigationInterface.widget(
            interface.objectName()
        )
        navigation_item.setText(text)
        navigation_item.setToolTip(text)

    def close_session_interface(self, session_id: str) -> None:
        """关闭并移除指定 Session 的动态切片页面。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            None: 无返回值。
        """
        interface = self._session_interfaces.pop(session_id, None)
        if interface is None:
            return
        route_key = interface.objectName()
        if self.stackedWidget.currentWidget() is interface:
            self.show_home_interface()
        qrouter.remove(route_key)
        self.removeInterface(interface, isDelete=True)

    def initWindow(self) -> None:
        """初始化窗口外观、启动页和屏幕位置。

        Returns:
            None: 无返回值。
        """
        self.setWindowIcon(QIcon(":/RadarIdentifySystem/images/icon.png"))
        self.setWindowTitle("RadarIdentifySystem")
        self.resize(1440, 1000)
        self.setMinimumSize(1200, 800)
        self.splashScreen = SplashScreen(
            QIcon(":/RadarIdentifySystem/images/brand.png"),
            self,
        )
        self.splashScreen.setIconSize(QSize(400, 400))
        self.splashScreen.raise_()
        desktop = QApplication.screens()[0].availableGeometry()
        self.move(
            desktop.width() // 2 - self.width() // 2,
            desktop.height() // 2 - self.height() // 2,
        )
        self.show()
        QApplication.processEvents()

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭主窗口前停止任务并释放全局监听。

        Args:
            event [QCloseEvent]: Qt 关闭事件对象。

        Returns:
            None: 无返回值。
        """
        if not self.full_speed_controller.prepare_close():
            event.ignore()
            return
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        self.themeListener.terminate()
        self.themeListener.wait(3000)
        self.themeListener.deleteLater()
        super().closeEvent(event)
