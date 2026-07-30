"""设置页面日志操作控制器。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFileDialog
from qfluentwidgets import InfoBar, qconfig

from app.app_config import appConfig
from app.logger import (
    clear_all_logs,
    get_current_log_file_path,
    get_log_dir_path,
)

if TYPE_CHECKING:
    from ui.interfaces.setting_interface import SettingInterface


LOGGER = logging.getLogger(__name__)


class SettingController(QObject):
    """编排日志目录修改、打开和清理操作。

    Attributes:
        view [SettingInterface]: 当前绑定的设置页面。
    """

    def __init__(self, view: SettingInterface) -> None:
        """初始化设置控制器并绑定日志操作。

        Args:
            view [SettingInterface]: 设置页面视图。

        Returns:
            None: 无返回值。
        """
        super().__init__(view)
        self.view = view
        view.log_card.change_path_button.clicked.connect(
            self.handle_change_log_path
        )
        view.log_card.open_path_button.clicked.connect(
            self.handle_open_log_path
        )
        view.log_card.clear_logs_button.clicked.connect(
            self.handle_clear_logs
        )
        view.log_card.set_log_path(str(self._configured_log_dir()))

    def _configured_log_dir(self) -> Path:
        """返回当前配置对应的规范化日志目录。"""
        return get_log_dir_path(qconfig.get(appConfig.logDir))

    def handle_change_log_path(self) -> None:
        """选择并保存新的日志目录。

        Returns:
            None: 无返回值。
        """
        current_path = str(self._configured_log_dir())
        path = QFileDialog.getExistingDirectory(
            self.view,
            "选择日志保存目录",
            current_path,
        )
        if not path:
            return

        normalized_path = str(get_log_dir_path(path))
        qconfig.set(appConfig.logDir, normalized_path)
        self.view.log_card.set_log_path(normalized_path)
        LOGGER.info(
            "日志目录已更新为：%s",
            normalized_path,
            extra={"session_id": "-"},
        )
        InfoBar.success(
            "设置成功",
            "新的日志路径已被保存，将在下次启动时生效。",
            parent=self.view.window(),
        )

    def handle_open_log_path(self) -> None:
        """使用系统文件管理器打开当前日志目录。

        Returns:
            None: 无返回值。
        """
        log_dir = self._configured_log_dir()
        if not log_dir.exists():
            LOGGER.warning(
                "日志目录不存在：%s",
                log_dir,
                extra={"session_id": "-"},
            )
            InfoBar.warning(
                "未找到",
                f"路径不存在：{log_dir}",
                parent=self.view.window(),
            )
            return

        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir))):
            LOGGER.info(
                "已打开日志目录：%s",
                log_dir,
                extra={"session_id": "-"},
            )
            return

        LOGGER.warning(
            "系统未能打开日志目录：%s",
            log_dir,
            extra={"session_id": "-"},
        )
        InfoBar.warning(
            "打开失败",
            f"系统未能打开路径：{log_dir}",
            parent=self.view.window(),
        )

    def handle_clear_logs(self) -> None:
        """清理当前配置目录中的历史日志文件。

        Returns:
            None: 无返回值。
        """
        try:
            LOGGER.info(
                "开始清理日志，当前运行日志文件：%s",
                get_current_log_file_path(),
                extra={"session_id": "-"},
            )
            count = clear_all_logs(self._configured_log_dir())
            if count == 0:
                LOGGER.info(
                    "日志清理完成，无历史日志文件需要删除",
                    extra={"session_id": "-"},
                )
                InfoBar.success(
                    "已清理",
                    "当前没有需要清理的日志文件。",
                    parent=self.view.window(),
                )
                return

            LOGGER.info(
                "日志清理完成，删除数量：%s",
                count,
                extra={"session_id": "-"},
            )
            InfoBar.success(
                "清理完毕",
                f"共清理了 {count} 个历史日志文件"
                "（当次运行日志可能因占用无法删除）。",
                parent=self.view.window(),
            )
        except Exception as error:
            LOGGER.exception(
                "清理日志失败：%s",
                error,
                extra={"session_id": "-"},
            )
            InfoBar.error(
                "清理异常",
                str(error),
                parent=self.view.window(),
            )
