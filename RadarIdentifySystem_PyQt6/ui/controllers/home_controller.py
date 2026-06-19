"""主页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt, QTimer
from qfluentwidgets import InfoBar, InfoBarPosition, qconfig

from app.signal_bus import signal_bus
from app.app_config import appConfig
from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from infra.import_file_list_manager import ImportFileListManager
from runtime.workflows.import_workflow import import_workflow
from ui.components import DashboardMetric, DashboardPage
from ui.components.import_dashboard_panel import format_dashboard_duration
from ui.dialogs.processing_dialog import ProcessingDialog

if TYPE_CHECKING:
    from ui.interfaces.home_interface import HomeInterface


class HomeController(QObject):
    """主页业务控制器。

    负责将主页导入目录列表与导入数据面板连接起来：
    用户刷新、移除文件列表项或调整排序条件时，更新 Excel、Bin、MAT 标签页。

    Attributes:
        view: 绑定的主页视图实例。
        file_manager: 导入文件列表管理器。
    """

    def __init__(self, view: HomeInterface) -> None:
        """初始化主页控制器。

        Args:
            view: 主页视图实例，必须包含 ``import_dir_card`` 与 ``import_panel``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(view)
        self.view = view
        self.file_manager = ImportFileListManager()
        self._active_parse_session_id: str | None = None
        self._last_import_session: ProcessingSession | None = None
        self._processing_dialog: ProcessingDialog | None = None
        self._connect_signals()

        # 延迟到事件循环空闲后渲染已持久化列表，启动时不自动扫描目录。
        QTimer.singleShot(0, self.render_saved_import_files)

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
        signal_bus.parse_completed.connect(self.render_import_dashboard)
        signal_bus.stage_failed.connect(self._on_parse_stage_failed)
        self.view.dashboard_panel.importSessionRequested.connect(
            self.import_current_session
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

        session = ProcessingSession(source_path=str(entry.path), source_type="excel")
        self._active_parse_session_id = session.session_id
        self._last_import_session = None
        self.view.import_panel.parseButton.setEnabled(False)
        self.view.import_panel.parseButton.setText("解析中")
        self.view.dashboard_panel.clear_dashboard_pages()
        self._show_processing_dialog()

        try:
            import_workflow.start_import(session, str(entry.path))
        except Exception as exc:
            self._active_parse_session_id = None
            self.view.import_panel.parseButton.setEnabled(True)
            self.view.import_panel.parseButton.setText("解析")
            self._close_processing_dialog()
            self._show_top_warning("解析失败", str(exc))

    def render_import_dashboard(self, session: ProcessingSession) -> None:
        """根据导入会话刷新仪表盘摘要。

        Args:
            session: 已完成导入和预处理的处理会话。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from core.models.processing_session import ProcessingSession
            >>> isinstance(ProcessingSession(), ProcessingSession)
            True
        """
        if session.session_id != self._active_parse_session_id:
            return

        self._active_parse_session_id = None
        self.view.import_panel.parseButton.setEnabled(True)
        self.view.import_panel.parseButton.setText("解析")
        self._close_processing_dialog()

        dashboard_info = session.dashboard_info
        if not isinstance(dashboard_info, ExcelDashboardInfo):
            return
        self._last_import_session = session

        metrics = [
            DashboardMetric("总脉冲", str(dashboard_info.total_pulses)),
            DashboardMetric("剔除脉冲", str(dashboard_info.removed_pulses)),
            DashboardMetric("幅度丢弃", str(dashboard_info.amplitude_dropped_pulses)),
            DashboardMetric("持续时间", format_dashboard_duration(dashboard_info.duration)),
            DashboardMetric("波段", dashboard_info.band or "--"),
            DashboardMetric("预计切片数", str(dashboard_info.estimated_slice_count)),
        ]
        self.view.dashboard_panel.set_dashboard_pages(
            [
                DashboardPage(
                    route_key="excel_info",
                    title=dashboard_info.band or "未知波段",
                    metrics=metrics,
                )
            ]
        )

    def import_current_session(self) -> None:
        """将最近解析完成的会话重新广播给下游页面。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> callable(HomeController.import_current_session)
            True
        """
        if self._last_import_session is None:
            self._show_top_warning("暂无可导入数据", "请先解析文件后再导入 Session。")
            return

        signal_bus.import_completed.emit(self._last_import_session)
        InfoBar.success(
            title="已导入",
            content=f"Session {self._last_import_session.session_id} 已发送到处理流程。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1800,
            parent=self.view.window() or self.view,
        )

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
        if session_id != self._active_parse_session_id or stage != "importing":
            return

        self._active_parse_session_id = None
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
