"""主页控制器。"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt, QTimer
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox, qconfig

from app.signal_bus import signal_bus
from app.app_config import appConfig
from core.models.data_package import DataPackage
from infra.import_file_list_manager import ImportFileListManager
from runtime.data_pool_registry import DataPoolRegistry
from runtime.session_coordinator import (
    ProcessingMode,
    ProcessingSession,
    SessionCoordinator,
)
from runtime.workflows.import_workflow import import_workflow
from ui.dialogs.create_session_dialog import CreateSessionDialog
from ui.dialogs.processing_dialog import ProcessingDialog

if TYPE_CHECKING:
    from ui.interfaces.home_interface import HomeInterface
    from ui.interfaces.slice_interface import SliceInterface


class HomeController(QObject):
    """主页业务控制器。

    负责将主页导入目录列表与导入数据面板连接起来：
    用户刷新、移除文件列表项或调整排序条件时，更新 Excel、Bin、MAT 标签页。

    Attributes:
        view: 绑定的主页视图实例。
        file_manager: 导入文件列表管理器。
    """

    def __init__(
        self,
        view: HomeInterface,
        data_pool_registry: DataPoolRegistry,
        session_coordinator: SessionCoordinator | None = None,
        interactive_session_registrar: (
            Callable[[ProcessingSession], SliceInterface] | None
        ) = None,
    ) -> None:
        """初始化主页控制器。

        Args:
            view: 主页视图实例，必须包含导入面板和数据池面板。
            data_pool_registry: 主窗口共享的数据池注册器。
            session_coordinator: Session 生命周期协调器；独立导入测试可不提供。
            interactive_session_registrar: 注册交互式 Session 并创建动态页面的回调。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(view)
        self.view = view
        self.data_pool_registry = data_pool_registry
        self.session_coordinator = session_coordinator
        self.interactive_session_registrar = interactive_session_registrar
        self.file_manager = ImportFileListManager()
        self._active_parse_package_id: str | None = None
        self._processing_dialog: ProcessingDialog | None = None
        self._connect_signals()

        # 延迟到事件循环空闲后渲染已持久化列表，启动时不自动扫描目录。
        QTimer.singleShot(0, self.render_saved_import_files)
        QTimer.singleShot(0, self.refresh_data_pool_panel)

    def render_saved_import_files(self) -> None:
        """渲染已持久化的导入文件列表。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.view.import_panel.set_files_by_type(self.file_manager.to_table_rows())

    def refresh_import_files(self) -> None:
        """刷新导入数据面板中的文件列表。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当导入文件列表状态保存失败时抛出。
        """
        directories = self._get_import_directories()
        files_by_type = self.file_manager.scan(directories)
        self.view.import_panel.set_files_by_type(files_by_type)

    def remove_selected_file(self) -> None:
        """从当前标签页列表中移除选中的文件行。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当导入文件列表状态保存失败时抛出。
        """
        format_key = self.view.import_panel.current_format_key()
        row_index = self.view.import_panel.current_selected_row()
        if not format_key or row_index < 0:
            return

        files_by_type = self.file_manager.remove_at(format_key, row_index)
        self.view.import_panel.set_files_by_type(files_by_type)

    def apply_sort(self) -> None:
        """按当前排序菜单选项重新排序文件列表。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当导入文件列表状态保存失败时抛出。
        """
        files_by_type = self.file_manager.sort(
            self.view.import_panel.current_sort_key(),
            ascending=self.view.import_panel.is_sort_ascending(),
        )
        self.view.import_panel.set_files_by_type(files_by_type)

    def _connect_signals(self) -> None:
        """连接主页相关控件信号。"""
        self.view.import_panel.refresh_action.triggered.connect(
            lambda _checked=False: self.refresh_import_files()
        )
        self.view.import_panel.remove_action.triggered.connect(
            lambda _checked=False: self.remove_selected_file()
        )
        self.view.import_panel.parseButton.clicked.connect(self.parse_selected_file)
        for action in (
            self.view.import_panel.nameAction,
            self.view.import_panel.sizeAction,
            self.view.import_panel.dateAction,
            self.view.import_panel.ascendAction,
            self.view.import_panel.descendAction,
        ):
            action.triggered.connect(lambda _checked=False: self.apply_sort())
        signal_bus.data_package_parsed.connect(self.register_parsed_package)
        signal_bus.stage_failed.connect(self._on_parse_stage_failed)
        self.view.data_pool_panel.createSessionRequested.connect(
            self.create_session_from_package
        )
        self.view.data_pool_panel.deletePackageRequested.connect(
            self.delete_data_package
        )

    def parse_selected_file(self) -> None:
        """解析当前文件列表中选中的文件。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常；启动失败会通过消息条提示用户。

        Example:
            >>> callable(HomeController.parse_selected_file)
            True
        """
        format_key = self.view.import_panel.current_format_key()
        row_index = self.view.import_panel.current_selected_row()
        entry = self.file_manager.get_entry_at(format_key, row_index)

        if entry is None:
            self._show_top_warning("未选择文件", "请先在当前标签页选择一个文件。")
            return
        if entry.format_key != "excel":
            self._show_top_warning("暂不支持", "当前仅支持解析 Excel 文件。")
            return
        if import_workflow.is_running():
            self._show_top_warning("正在解析", "已有文件正在解析，请等待完成后再试。")
            return

        self.view.import_panel.parseButton.setEnabled(False)
        self.view.import_panel.parseButton.setText("解析中")
        self._show_processing_dialog()

        try:
            # 点击解析时冻结格式选择，后台线程不再读取可变 UI 状态。
            data_format = self.view.import_panel.current_excel_data_format()
            self._active_parse_package_id = import_workflow.start_import(
                str(entry.path),
                data_format,
            )
        except Exception as exc:
            self._active_parse_package_id = None
            self.view.import_panel.parseButton.setEnabled(True)
            self.view.import_panel.parseButton.setText("解析")
            self._close_processing_dialog()
            self._show_top_warning("解析失败", str(exc))

    def register_parsed_package(self, package: DataPackage) -> None:
        """将解析完成的数据包持久化注册到数据池。

        Args:
            package: 已完成解析、预处理和输入冻结的数据包。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            无。
        """
        if package.package_id != self._active_parse_package_id:
            return

        self._active_parse_package_id = None
        self.view.import_panel.parseButton.setEnabled(True)
        self.view.import_panel.parseButton.setText("解析")
        self._close_processing_dialog()

        try:
            self.data_pool_registry.register(package)
        except Exception as exc:
            self._show_top_warning("数据池注册失败", str(exc))
            return
        self.refresh_data_pool_panel(package.package_id)
        InfoBar.success(
            title="已加入数据池",
            content=f"{package.display_name} 已完成解析，可创建处理 Session。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self.view.window() or self.view,
        )

    def refresh_data_pool_panel(
        self,
        selected_package_id: str | None = None,
    ) -> None:
        """刷新主页数据池列表。

        Args:
            selected_package_id [str | None]: 刷新后优先选中的数据包 ID。

        Returns:
            None: 无返回值。
        """
        self.view.data_pool_panel.set_packages(
            self.data_pool_registry.all_packages(),
            selected_package_id=selected_package_id,
        )

    def create_session_from_package(self, package_id: str) -> None:
        """从选中数据包创建交互式或全速 Session。

        Args:
            package_id: 数据池数据包 ID。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> callable(HomeController.create_session_from_package)
            True
        """
        package = self.data_pool_registry.get(package_id)
        if package is None:
            self._show_top_warning("数据包不存在", "请刷新数据池后重试。")
            return

        window = self.view.window()
        if self.session_coordinator is None:
            self._show_top_warning("创建失败", "当前窗口不支持数据池 Session。")
            return

        default_display_name = package.display_name
        dialog = CreateSessionDialog(default_display_name, window)
        if not dialog.exec():
            return

        session_name = dialog.get_session_name().strip() or default_display_name
        session_remark = dialog.get_session_remark().strip() or "无"
        processing_mode = dialog.get_processing_mode()
        try:
            session = self.create_session(
                package_id,
                processing_mode,
                session_name,
                session_remark,
            )
        except Exception as error:
            self._show_top_warning("创建失败", str(error))
            return
        mode_name = (
            "全速处理"
            if processing_mode.value == "full_speed"
            else "切片处理"
        )
        InfoBar.success(
            title="Session 已创建",
            content=f"{mode_name} Session {session.display_name} 已创建。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1800,
            parent=self.view.window() or self.view,
        )

    def create_session(
        self,
        package_id: str,
        processing_mode: ProcessingMode,
        display_name: str,
        remark: str,
    ) -> ProcessingSession:
        """从数据包创建并注册指定处理模式的 Session。

        Args:
            package_id [str]: 来源数据包 ID。
            processing_mode [ProcessingMode]: 交互式或全速处理模式。
            display_name [str]: Session 展示名称。
            remark [str]: Session 备注。

        Returns:
            ProcessingSession: 已注册到对应体系的 Session。

        Raises:
            RuntimeError: Session 协调器或交互式页面注册回调缺失时抛出。
            KeyError: 数据包不存在时抛出。
            OSError: Session 持久化失败时抛出。
        """
        if self.session_coordinator is None:
            raise RuntimeError("Session 协调器尚未配置")
        session = self.session_coordinator.build_session_from_data_package(
            package_id,
            processing_mode,
            display_name,
            remark,
        )
        if processing_mode is ProcessingMode.FULL_SPEED:
            self.session_coordinator.register_full_speed_session(session)
            signal_bus.session_registered.emit(session.session_id)
            return session
        if self.interactive_session_registrar is None:
            raise RuntimeError("交互式 Session 页面注册器尚未配置")
        self.interactive_session_registrar(session)
        return session

    def delete_data_package(self, package_id: str) -> None:
        """确认后删除未被任何 Session 引用的数据包。

        Args:
            package_id [str]: 目标数据包 ID。

        Returns:
            None: 无返回值。
        """
        package = self.data_pool_registry.get(package_id)
        if package is None:
            return
        dialog = MessageBox(
            "删除数据包",
            (
                f"确认删除“{package.display_name}”的解析缓存吗？"
                "原始文件不会删除，之后可重新解析。"
            ),
            self.view.window() or self.view,
        )
        if not dialog.exec():
            return
        referenced_ids = (
            self.session_coordinator.referenced_data_package_ids()
            if self.session_coordinator is not None
            else set()
        )
        try:
            deleted = self.data_pool_registry.delete(
                package_id,
                referenced_package_ids=referenced_ids,
            )
        except RuntimeError as exc:
            self._show_top_warning("无法删除数据包", str(exc))
            return
        except Exception as exc:
            self._show_top_warning("删除失败", str(exc))
            return
        if deleted:
            self.refresh_data_pool_panel()

    def _get_import_directories(self) -> list[str]:
        """读取当前持久化的导入目录列表。"""
        configured_dirs = qconfig.get(appConfig.importDataDirs)
        if not isinstance(configured_dirs, list):
            return []
        return [directory for directory in configured_dirs if isinstance(directory, str)]

    def _on_parse_stage_failed(
        self,
        session_id: str,
        stage: str,
        _slice_index: int | None,
        error_msg: str,
    ) -> None:
        """处理首页解析工作流失败事件。"""
        if session_id != self._active_parse_package_id or stage != "importing":
            return

        self._active_parse_package_id = None
        self.view.import_panel.parseButton.setEnabled(True)
        self.view.import_panel.parseButton.setText("解析")
        self._close_processing_dialog()
        self._show_top_warning("解析失败", error_msg)

    def _show_processing_dialog(self) -> None:
        """显示首页解析流程的蒙版动画。"""
        self._close_processing_dialog()
        self._processing_dialog = ProcessingDialog(
            self.view,
            title="解析数据",
            content="正在读取并预处理 Excel 文件，请稍候...",
        )
        self._processing_dialog.show()

    def _close_processing_dialog(self) -> None:
        """关闭首页解析流程的蒙版动画。"""
        if self._processing_dialog is not None:
            self._processing_dialog.close()
            self._processing_dialog = None

    def _show_top_warning(self, title: str, content: str) -> None:
        """在窗口顶部居中显示警告消息条。"""
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self.view.window() or self.view,
        )
