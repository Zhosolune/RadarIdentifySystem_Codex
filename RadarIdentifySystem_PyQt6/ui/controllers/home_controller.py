"""主页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer
from qfluentwidgets import qconfig

from app.app_config import appConfig
from infra.import_file_scanner import ImportFileScanner

if TYPE_CHECKING:
    from ui.interfaces.home_interface import HomeInterface


class HomeController(QObject):
    """主页业务控制器。

    负责将主页导入目录列表与导入数据面板连接起来：
    目录配置变化或用户点击刷新时，扫描导入目录并更新 Excel、Bin、MAT 标签页。

    Attributes:
        view: 绑定的主页视图实例。
        scanner: 导入文件扫描器。
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
        self.scanner = ImportFileScanner()
        self._connect_signals()

        # 延迟到事件循环空闲后执行首次扫描，确保标签页控件已完成装配。
        QTimer.singleShot(0, self.refresh_import_files)

    def refresh_import_files(self) -> None:
        """刷新导入数据面板中的文件列表。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常；不可访问目录由扫描适配器跳过。
        """
        directories = self._get_import_directories()
        files_by_type = self.scanner.scan(directories)
        self.view.import_panel.set_files_by_type(files_by_type)

    def _connect_signals(self) -> None:
        """连接主页相关控件信号。"""
        self.view.import_panel.refresh_action.triggered.connect(
            lambda _checked=False: self.refresh_import_files()
        )

    def _get_import_directories(self) -> list[str]:
        """读取当前持久化的导入目录列表。"""
        configured_dirs = qconfig.get(appConfig.importDataDirs)
        if not isinstance(configured_dirs, list):
            return []
        return [directory for directory in configured_dirs if isinstance(directory, str)]
