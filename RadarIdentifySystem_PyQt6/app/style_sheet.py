"""应用样式表入口。"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QFile
from qfluentwidgets import StyleSheetBase, Theme, qconfig

from app import resource_rc  # noqa: F401  # 导入即注册 Qt 资源


class StyleSheet(StyleSheetBase, Enum):
    """项目页面样式枚举。"""

    HOME_INTERFACE = "home_interface"
    SETTING_INTERFACE = "setting_interface"

    def path(self, theme: Theme = Theme.AUTO) -> str:
        """返回样式文件路径。

        功能描述：
            优先返回已编译资源路径；若资源未编译，则回退到本地 `resources/qss` 文件，
            便于开发阶段热更新与调试。

        参数说明：
            theme (Theme): 主题模式，默认值为 `Theme.AUTO`。

        返回值说明：
            str: qss 路径，可能是 `:/RadarIdentifySystem/...` 资源路径或本地绝对路径。

        异常说明：
            无。
        """

        effective_theme = qconfig.theme if theme == Theme.AUTO else theme
        theme_name = effective_theme.value.lower()
        resource_path = f":/RadarIdentifySystem/qss/{theme_name}/{self.value}.qss"
        if QFile.exists(resource_path):
            return resource_path

        local_qss_path = Path(__file__).resolve().parent.parent / "resources" / "qss" / theme_name / f"{self.value}.qss"
        return str(local_qss_path).replace("\\", "/")
