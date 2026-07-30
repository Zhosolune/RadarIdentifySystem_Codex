"""日志设置卡组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from qfluentwidgets import ExpandGroupSettingCard, FluentIcon, PushButton


class LogSettingCard(ExpandGroupSettingCard):
    """展示日志目录修改、打开和清理操作。

    Attributes:
        change_path_button [PushButton]: 请求修改日志目录的按钮。
        open_path_button [PushButton]: 请求打开日志目录的按钮。
        clear_logs_button [PushButton]: 请求清理历史日志的按钮。
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

        for button in (
            self.change_path_button,
            self.open_path_button,
            self.clear_logs_button,
        ):
            button.setFixedWidth(120)

        self.addGroup(
            FluentIcon.FOLDER,
            "自定义日志保存路径",
            "选择全量系统运行日志的统一落盘文件夹",
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

    def set_log_path(self, path: str) -> None:
        """更新卡片头部展示的日志目录。

        Args:
            path [str]: 最新日志目录。

        Returns:
            None: 无返回值。
        """
        self.card.setContent(path)
