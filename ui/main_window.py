# -*- coding: utf-8 -*-
"""
ui/main_window.py
动态导航主窗口：
  - 欢迎页（固定首项）
  - 每个仓库对应一个侧边栏导航项（运行时动态添加/移除）
  - 设置页（固定末项）
"""
from PyQt6.QtCore import Qt, QSize, QTimer, QEvent, QObject, QUrl
from PyQt6.QtWidgets import (
    QWidget,
    QApplication,
    QAbstractButton,
    QFileDialog,
)
from PyQt6.QtGui import QDesktopServices, QIcon
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon,
    SystemThemeListener, SplashScreen, InfoBar, InfoBarPosition, MessageBox,
)
from qfluentwidgets.common.router import qrouter

from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingMode, ProcessingSession, ProcessingStage
from core.models.session_config import SessionConfigSnapshot
from runtime.data_pool_registry import DataPoolRegistry
from runtime.full_speed_session_registry import FullSpeedSessionRegistry
from runtime.session_config_factory import (
    create_session_config_from_global,
    create_session_model_selection_from_global,
)
from runtime.session_registry import SessionRegistry
from runtime.workflows.full_speed_workflow import FullSpeedWorkflow
from ui.controllers.session_manager_controller import SessionManagerController
from ui.components.full_speed_params_window import FullSpeedParamsWindow
from ui.interfaces.home_interface import HomeInterface
from ui.interfaces.slice_interface import SliceInterface
from ui.interfaces.model_manager_interface import ModelManagerInterface
from ui.interfaces.setting_interface import SettingInterface
from ui.interfaces.params_interface import ParamsInterface

class MainWindow(FluentWindow):
    """RadarIdentifySystem 主窗口。"""

    def __init__(
        self,
        session_registry: SessionRegistry | None = None,
        data_pool_registry: DataPoolRegistry | None = None,
        full_speed_session_registry: FullSpeedSessionRegistry | None = None,
    ) -> None:
        """初始化主窗口。

        Args:
            session_registry [SessionRegistry | None]: session 注册表；为 None 时使用默认持久化注册表。
            data_pool_registry [DataPoolRegistry | None]: 数据池注册器。
            full_speed_session_registry [FullSpeedSessionRegistry | None]: 全速 Session 注册器。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当默认 SessionRegistry 初始化目录失败时抛出。
        """
        super().__init__()
        self.initWindow()

        # 两类 Session 默认与交互式 Session 使用同一配置根目录，测试或嵌入场景
        # 注入自定义 SessionStore 时不会意外写入项目级配置目录。
        self.session_registry = session_registry or SessionRegistry()
        session_root = self.session_registry.store.root_dir
        data_pool_root = (
            session_root.parent / "data_pool"
            if session_root.name == "sessions"
            else session_root / "data_pool"
        )
        self.data_pool_registry = data_pool_registry or (
            DataPoolRegistry.from_root_dir(data_pool_root)
        )
        if not self.data_pool_registry.all_packages():
            self.data_pool_registry.restore()
        self.full_speed_session_registry = (
            full_speed_session_registry
            or FullSpeedSessionRegistry(session_root / "full_speed")
        )
        self.full_speed_workflow = FullSpeedWorkflow(
            self.full_speed_session_registry,
            self,
        )

        # 创建子页面
        self.homeInterface = HomeInterface(self, self.data_pool_registry)
        self.sliceInterface = SliceInterface(self)
        self.modelManagerInterface = ModelManagerInterface(self)
        self.iconInterface = SettingInterface(self)
        self.paramsInterface = ParamsInterface(self)


        self.themeListener = SystemThemeListener(self)

        self._session_interfaces: dict[str, SliceInterface] = {}
        self._full_speed_param_windows: dict[
            str,
            FullSpeedParamsWindow,
        ] = {}
        self._session_manager_controller = SessionManagerController(
            self.homeInterface.session_manager_panel,
            self,
        )
        self._connect_full_speed_controls()
        self.initNavigation()
        self.restore_session_interfaces()
        self.restore_full_speed_sessions()
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
        # self.addSubInterface(
        #     self.sliceInterface, FluentIcon.PIE_SINGLE, "切片处理",
        #     position=NavigationItemPosition.TOP,
        # )

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

    def create_session_interface(
        self,
        session: ProcessingSession,
        activate: bool = True,
    ) -> SliceInterface:
        """创建或复用指定 session 对应的切片页面。

        Args:
            session [ProcessingSession]: 需要绑定到切片页面的处理会话。
            activate [bool]: 是否在创建后立即切换到该页面，默认为 True。

        Returns:
            SliceInterface: 已创建或已存在的动态切片页面。

        Raises:
            无显式抛出异常。
        """
        existing_interface = self._session_interfaces.get(session.session_id)
        if existing_interface is not None:
            # 已有页面时直接激活，避免为同一 session 重复创建导航项。
            if activate:
                self._switch_to_session_interface(session.session_id)
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
        if activate:
            self._switch_to_session_interface(session.session_id)
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
        interface = self.add_session_from_import(session)
        self.activate_session_interface(session.session_id)
        return interface

    def add_session_from_import(self, session: ProcessingSession) -> SliceInterface:
        """注册解析完成的 session 并在主页中选中。

        Args:
            session [ProcessingSession]: 主页解析完成后等待确认导入的处理会话。

        Returns:
            SliceInterface: 绑定该 session 的动态切片页面。

        Raises:
            OSError: 当 session 持久化写入失败时由注册表抛出。
            ValueError: 当 session_id 非法时由持久化层抛出。
        """
        session.config_snapshot = create_session_config_from_global()
        interface_existed = session.session_id in self._session_interfaces
        interface = self.create_session_interface(session, activate=False)
        try:
            # 后台准备动态页面，但保持主页停留和原 active session 不变。
            self.session_registry.register(session, activate=False)
        except Exception:
            # 注册失败时只回滚本次创建的 UI 页面，避免留下未持久化的动态页。
            if not interface_existed:
                self.close_session_interface(session.session_id)
            raise
        # 保持停留主页，仅在管理器中选中新建 session。
        self.switchTo(self.homeInterface)
        self.refresh_session_manager_panel(selected_session_id=session.session_id)
        signal_bus.session_registered.emit(session.session_id)
        return interface

    def create_session_from_data_package(
        self,
        package_id: str,
        processing_mode: ProcessingMode,
        display_name: str,
        remark: str,
    ) -> ProcessingSession:
        """从数据池创建指定处理模式的独立 Session。

        Args:
            package_id [str]: 来源数据包 ID。
            processing_mode [ProcessingMode]: 交互式或全速处理模式。
            display_name [str]: Session 展示名称。
            remark [str]: Session 备注。

        Returns:
            ProcessingSession: 已注册到对应同级体系的 Session。

        Raises:
            KeyError: 数据包不存在时抛出。
            OSError: Session 持久化失败时抛出。
        """
        package = self.data_pool_registry.get(package_id)
        if package is None:
            raise KeyError(f"数据包不存在: {package_id}")
        session = ProcessingSession.from_data_package(
            package,
            processing_mode=processing_mode,
            display_name=display_name,
            remark=remark,
        )
        session.config_snapshot = create_session_config_from_global()
        session.model_selection = create_session_model_selection_from_global()

        if processing_mode is ProcessingMode.FULL_SPEED:
            # 全速任务必然在流水线末尾导出 Excel，快照应如实记录该行为。
            session.config_snapshot.business.auto_export = True
            self.full_speed_session_registry.register(session)
            self.switchTo(self.homeInterface)
            self.refresh_full_speed_session_panel(session.session_id)
            signal_bus.session_registered.emit(session.session_id)
        else:
            self.add_session_from_import(session)
        return session

    def restore_full_speed_sessions(self) -> list[str]:
        """恢复全速 Session 卡片并重新挂接数据池输入。

        Returns:
            list[str]: 成功恢复的全速 Session ID。
        """
        restored_ids: list[str] = []
        sessions = self.full_speed_session_registry.all_sessions()
        if not sessions:
            sessions = self.full_speed_session_registry.restore()
        for session in sessions:
            if not self._attach_data_package_input(session):
                continue
            restored_ids.append(session.session_id)
        self.refresh_full_speed_session_panel()
        return restored_ids

    def refresh_full_speed_session_panel(
        self,
        selected_session_id: str | None = None,
    ) -> None:
        """刷新主页全速 Session 卡片列表。"""
        sessions = self.full_speed_session_registry.all_sessions()
        states = {
            session.session_id: state
            for session in sessions
            if (
                state := self.full_speed_session_registry.state(
                    session.session_id
                )
            )
            is not None
        }
        if not hasattr(self.homeInterface, "full_speed_session_panel"):
            return
        self.homeInterface.full_speed_session_panel.set_sessions(
            sessions,
            states,
            selected_session_id=selected_session_id,
        )

    def _connect_full_speed_controls(self) -> None:
        """连接主页全速 Session 卡片与运行期工作流。"""
        panel = self.homeInterface.full_speed_session_panel
        panel.outputDirectoryRequested.connect(
            self.select_full_speed_output_dir
        )
        panel.parametersRequested.connect(
            self.open_full_speed_params
        )
        panel.startRequested.connect(self.start_full_speed_session)
        panel.cancelRequested.connect(self.cancel_full_speed_session)
        panel.deleteRequested.connect(self.delete_full_speed_session)
        panel.openOutputRequested.connect(self.open_full_speed_output)
        signal_bus.full_speed_session_changed.connect(
            self.refresh_full_speed_session_panel
        )

    def select_full_speed_output_dir(self, session_id: str) -> None:
        """为尚未启动的全速 Session 选择独立保存目录。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.full_speed_session_registry.get(session_id)
        if session is None:
            self._show_full_speed_warning("设置失败", "全速 Session 不存在")
            return
        current_dir = session.config_snapshot.business.export_dir_path
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "选择全速处理 Excel 保存目录",
            current_dir,
        )
        if not output_dir:
            return
        try:
            self.full_speed_session_registry.set_output_dir(
                session_id,
                output_dir,
            )
        except Exception as error:
            self._show_full_speed_warning("设置失败", str(error))
            return
        self.refresh_full_speed_session_panel(session_id)

    def open_full_speed_params(self, session_id: str) -> None:
        """打开未冻结全速 Session 的两栏参数编辑窗口。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.full_speed_session_registry.get(session_id)
        if session is None:
            self._show_full_speed_warning("设置失败", "全速 Session 不存在")
            return
        if session.full_speed_locked:
            self._show_full_speed_warning(
                "参数已冻结",
                "全速任务首次开始后不能再修改参数",
            )
            return

        existing = self._full_speed_param_windows.get(session_id)
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return

        window = FullSpeedParamsWindow(
            session_id,
            session.display_name,
            session.config_snapshot,
        )
        window.configSaved.connect(
            lambda snapshot, target_id=session_id: (
                self.save_full_speed_params(target_id, snapshot)
            )
        )
        window.destroyed.connect(
            lambda _object=None, target_id=session_id, target=window: (
                self._release_full_speed_params_window(target_id, target)
            )
        )
        self._full_speed_param_windows[session_id] = window
        window.show()
        window.raise_()
        window.activateWindow()

    def save_full_speed_params(
        self,
        session_id: str,
        snapshot: SessionConfigSnapshot,
    ) -> None:
        """保存参数窗口提交的 Session 快照并关闭对应窗口。

        Args:
            session_id [str]: 目标全速 Session ID。
            snapshot [SessionConfigSnapshot]: 参数窗口提交的配置快照。

        Returns:
            None: 无返回值。
        """
        try:
            self.full_speed_session_registry.set_config_snapshot(
                session_id,
                snapshot,
            )
        except Exception as error:
            self._show_full_speed_warning("参数保存失败", str(error))
            return

        window = self._full_speed_param_windows.get(session_id)
        if window is not None:
            window.close()
        self.refresh_full_speed_session_panel(session_id)
        InfoBar.success(
            title="参数已保存",
            content="当前全速 Session 将使用这组参数执行。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1800,
            parent=self,
        )

    def _release_full_speed_params_window(
        self,
        session_id: str,
        window: FullSpeedParamsWindow,
    ) -> None:
        """释放已关闭的全速参数窗口引用。"""
        if self._full_speed_param_windows.get(session_id) is window:
            self._full_speed_param_windows.pop(session_id, None)

    def start_full_speed_session(self, session_id: str) -> None:
        """冻结当前 Session 参数与模型并启动独立全速线程。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.full_speed_session_registry.get(session_id)
        if session is None:
            self._show_full_speed_warning("启动失败", "全速 Session 不存在")
            return
        try:
            if not session.config_snapshot.business.export_dir_path.strip():
                self.select_full_speed_output_dir(session_id)
                if not session.config_snapshot.business.export_dir_path.strip():
                    return
            self.full_speed_workflow.start(session_id)
            # 工作流成功进入运行态后关闭可能残留的参数窗口。
            params_window = self._full_speed_param_windows.get(session_id)
            if params_window is not None:
                params_window.close()
        except Exception as error:
            self._show_full_speed_warning("启动失败", str(error))
            self.refresh_full_speed_session_panel(session_id)

    def cancel_full_speed_session(self, session_id: str) -> None:
        """请求正在运行的全速 Session 安全取消。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        if not self.full_speed_workflow.cancel(session_id):
            self._show_full_speed_warning(
                "无法取消",
                "当前任务不在可取消的执行阶段",
            )

    def delete_full_speed_session(self, session_id: str) -> None:
        """确认后删除非运行中的全速 Session。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.full_speed_session_registry.get(session_id)
        if session is None:
            return
        dialog = MessageBox(
            "删除全速 Session",
            f"确认删除“{session.display_name}”吗？已生成的 Excel 文件不会删除。",
            self,
        )
        if not dialog.exec():
            return
        try:
            self.full_speed_session_registry.delete(session_id)
        except Exception as error:
            self._show_full_speed_warning("删除失败", str(error))
            return
        params_window = self._full_speed_param_windows.get(session_id)
        if params_window is not None:
            params_window.close()
        self.refresh_full_speed_session_panel()

    def open_full_speed_output(self, session_id: str) -> None:
        """使用系统默认程序打开全速任务 Excel 结果。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        state = self.full_speed_session_registry.state(session_id)
        if state is None or not state.output_file:
            self._show_full_speed_warning("无法打开", "当前任务还没有结果文件")
            return
        if not QDesktopServices.openUrl(
            QUrl.fromLocalFile(state.output_file)
        ):
            self._show_full_speed_warning(
                "无法打开",
                f"请手动访问：{state.output_file}",
            )

    def _show_full_speed_warning(self, title: str, content: str) -> None:
        """在主窗口顶部显示全速任务提示。"""
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def referenced_data_package_ids(self) -> set[str]:
        """返回两类 Session 当前引用的全部数据包 ID。"""
        interactive_ids = {
            session.data_package_id
            for session in self.session_registry.all_sessions()
            if session.data_package_id is not None
        }
        return (
            interactive_ids
            | self.full_speed_session_registry.referenced_package_ids()
        )

    def _attach_data_package_input(self, session: ProcessingSession) -> bool:
        """把恢复 Session 重新挂接到数据池中的只读输入。"""
        if session.data_package_id is None:
            return False
        package = self.data_pool_registry.get(session.data_package_id)
        if package is None:
            return False
        session.raw_batch = package.raw_batch
        session.preprocess_result = package.preprocess_result
        session.dashboard_info = package.dashboard_info
        # 全速成功记录只恢复审计状态和 Excel 路径，不恢复大体量中间结果；
        # 交互式 Session 则从可重新切片的预处理阶段继续。
        if (
            session.processing_mode is not ProcessingMode.FULL_SPEED
            or session.stage is not ProcessingStage.EXPORTED
        ):
            session.stage = ProcessingStage.PREPROCESSED
        return True

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
        for session in restored_sessions:
            if session.data_package_id is not None:
                if not self._attach_data_package_input(session):
                    continue
            self.create_session_interface(session, activate=False)
            restored_ids.append(session.session_id)

        # 启动后始终进入主页，历史界面状态不再参与路由恢复。
        self.switchTo(self.homeInterface)
        self.refresh_session_manager_panel(selected_session_id=None)
        return restored_ids

    def refresh_session_manager_panel(
        self,
        selected_session_id: str | None = None,
    ) -> None:
        """刷新主页 session 管理器列表。

        Args:
            selected_session_id [str | None]: 刷新后优先选中的 session id。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> hasattr(object(), "session_manager_panel")
            False
        """
        if hasattr(self.homeInterface, "session_manager_panel"):
            preferred_session_id = (
                selected_session_id
                or self.homeInterface.session_manager_panel.current_session_id()
                or self.session_registry.active_session_id
            )
            self.homeInterface.session_manager_panel.set_sessions(
                self.session_registry.all_sessions(),
                selected_session_id=preferred_session_id,
                enabled_session_ids=set(self._session_interfaces),
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

        if self.session_registry.get(session_id) is not None:
            # 同步持久化活跃会话并刷新主页详情选中项。
            self.session_registry.activate(session_id)
            self.refresh_session_manager_panel(selected_session_id=session_id)
            signal_bus.session_activated.emit(session_id)

        self._switch_to_session_interface(session_id)

    def _switch_to_session_interface(self, session_id: str) -> None:
        """仅切换到指定 session 页面，不修改注册表状态。"""
        interface = self._session_interfaces.get(session_id)
        if interface is None:
            return

        # 复用 FluentWindow 的导航切换逻辑，同步堆栈页与导航选中项。
        self.switchTo(interface)

    def set_session_navigation_text(self, session_id: str, text: str) -> None:
        """同步更新动态导航项文案。"""
        interface = self._session_interfaces.get(session_id)
        if interface is None:
            return

        navigation_item = self.navigationInterface.widget(interface.objectName())
        navigation_item.setText(text)
        navigation_item.setToolTip(text)

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
        self.resize(1440, 1000)
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

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        """关闭主窗口前释放全局监听。

        Args:
            event [object]: Qt 关闭事件对象。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        if self.full_speed_workflow.is_running():
            if not self.full_speed_workflow.shutdown():
                event.ignore()
                self._show_full_speed_warning(
                    "正在停止任务",
                    "仍有全速任务处于单片计算中，请稍后再次关闭。",
                )
                return

        for window in list(self._full_speed_param_windows.values()):
            window.close()

        # 解除事件过滤器
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        self.themeListener.terminate()
        self.themeListener.wait(3000)
        self.themeListener.deleteLater()
        super().closeEvent(event)
