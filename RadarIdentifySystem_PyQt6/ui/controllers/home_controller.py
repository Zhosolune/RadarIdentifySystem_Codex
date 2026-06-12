"""主页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer
from qfluentwidgets import qconfig

from app.signal_bus import signal_bus
from app.app_config import appConfig
from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from infra.import_file_list_manager import ImportFileListManager
from ui.components import DashboardMetric, DashboardPage

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
        for action in (
            self.view.import_panel.nameAction,
            self.view.import_panel.sizeAction,
            self.view.import_panel.dateAction,
            self.view.import_panel.ascendAction,
            self.view.import_panel.descendAction,
        ):
            action.triggered.connect(lambda _checked=False: self.apply_sort())
        signal_bus.import_completed.connect(self.render_import_dashboard)

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
        dashboard_info = session.dashboard_info
        if not isinstance(dashboard_info, ExcelDashboardInfo):
            return

        metrics = [
            DashboardMetric("总脉冲", str(dashboard_info.total_pulses)),
            DashboardMetric("剔除脉冲", str(dashboard_info.removed_pulses)),
            DashboardMetric("幅度丢弃", str(dashboard_info.amplitude_dropped_pulses)),
            DashboardMetric("持续时间", self._format_duration(dashboard_info.duration)),
            DashboardMetric("波段", dashboard_info.band or "--"),
            DashboardMetric("预计切片数", str(dashboard_info.estimated_slice_count)),
        ]
        self.view.dashboard_panel.set_dashboard_pages(
            [
                DashboardPage(
                    route_key="excel_info",
                    title="文件信息",
                    metrics=metrics,
                )
            ]
        )

    def _get_import_directories(self) -> list[str]:
        """读取当前持久化的导入目录列表。"""
        configured_dirs = qconfig.get(appConfig.importDataDirs)
        if not isinstance(configured_dirs, list):
            return []
        return [directory for directory in configured_dirs if isinstance(directory, str)]

    def _format_duration(self, duration: float) -> str:
        """将 0.1us 持续时间格式化为仪表盘显示文本。"""
        return f"{duration / 10_000:.2f} ms"
