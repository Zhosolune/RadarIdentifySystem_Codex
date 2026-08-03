"""日志设置卡组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from qfluentwidgets import (
    ComboBox,
    ExpandGroupSettingCard,
    FluentIcon,
    PushButton,
    qconfig,
)

from app.app_config import appConfig


class LogSettingCard(ExpandGroupSettingCard):
    """展示日志等级、目录修改、打开和清理操作。

    Attributes:
        change_path_button [PushButton]: 请求修改日志目录的按钮。
        open_path_button [PushButton]: 请求打开日志目录的按钮。
        clear_logs_button [PushButton]: 请求清理历史日志的按钮。
        log_level_combo [ComboBox]: 修改全局日志记录等级的下拉框。
    """

    def __init__(
        self,
        current_path: str,
        parent: QWidget | None = None,
    ) -> None:
        """初始化日志设置卡。

        Args:
            current_path [str]: 卡片头部初始展示的日志目录。
            parent [QWidget | None]: 父组件。

        Returns:
            None: 无返回值。
        """
        super().__init__(
            FluentIcon.DOCUMENT,
            "日志选项",
            current_path,
            parent,
        )
        self.change_path_button = PushButton("更改")
        self.open_path_button = PushButton("打开")
        self.clear_logs_button = PushButton("清理")
        self.log_level_combo = ComboBox()
        self._log_level_options = tuple(
            str(option) for option in appConfig.logLevel.validator.options
        )
        self.log_level_combo.addItems(list(self._log_level_options))
        self._sync_log_level_combo(qconfig.get(appConfig.logLevel))
        self.log_level_combo.currentIndexChanged.connect(
            self._on_log_level_changed
        )
        appConfig.logLevel.valueChanged.connect(self._sync_log_level_combo)

        for button in (
            self.change_path_button,
            self.open_path_button,
            self.clear_logs_button,
        ):
            button.setFixedWidth(120)
        self.log_level_combo.setFixedWidth(120)

        self.addGroup(
            FluentIcon.DEVELOPER_TOOLS,
            "日志记录等级",
            "DEBUG记录全部信息；INFO、WARN、ERROR依次减少记录内容",
            self.log_level_combo,
        )

        self.addGroup(
            FluentIcon.FOLDER,
            "自定义日志保存路径",
            "选择系统运行日志的统一落盘文件夹",
            self.change_path_button,
        )
        self.addGroup(
            FluentIcon.VIEW,
            "打开日志所在目录",
            "在文件管理器中浏览日志",
            self.open_path_button,
        )
        self.addGroup(
            FluentIcon.DELETE,
            "清理全部日志文件",
            "永久删除磁盘上所有当前配置目录下的日志",
            self.clear_logs_button,
        )

    def _on_log_level_changed(self, index: int) -> None:
        """把下拉框选择写入全局日志等级配置。"""
        if not 0 <= index < len(self._log_level_options):
            return
        qconfig.set(appConfig.logLevel, self._log_level_options[index])

    def _sync_log_level_combo(self, value: object) -> None:
        """在配置从其它入口变化时同步下拉框。"""
        rendered_value = str(value)
        index = (
            self._log_level_options.index(rendered_value)
            if rendered_value in self._log_level_options
            else 0
        )
        if self.log_level_combo.currentIndex() != index:
            self.log_level_combo.setCurrentIndex(index)

    def set_log_path(self, path: str) -> None:
        """更新卡片头部展示的日志目录。

        Args:
            path [str]: 最新日志目录。

        Returns:
            None: 无返回值。
        """
        self.card.setContent(path)
