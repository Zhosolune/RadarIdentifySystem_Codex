"""自定义图标管理模块。

提供继承自 FluentIconBase 的自定义图标枚举，自动适配深浅色主题。
"""

from __future__ import annotations

from enum import Enum
from qfluentwidgets import Theme, FluentIconBase, getIconColor

class CustomIcon(FluentIconBase, Enum):
    """自定义图标枚举。
    
    枚举值对应图标文件名的基础名称。
    例如：ChevronLeft 会根据主题映射到 :/RadarIdentifySystem/images/icons/ChevronLeft_black.svg
    """
    
    CHEVRON_LEFT = "ChevronLeft"
    CHEVRON_RIGHT = "ChevronRight"
    CHEVRONS_LEFT = "ChevronsLeft"
    CHEVRONS_RIGHT = "ChevronsRight"

    def path(self, theme=Theme.AUTO) -> str:
        """获取图标的 QRC 资源路径。
        
        功能描述：
            根据当前主题（Theme.LIGHT 或 Theme.DARK），返回资源系统中的图标路径。
            
        参数说明：
            theme: qfluentwidgets.Theme 枚举，表示当前应用的主题模式。
            
        返回值说明：
            str: 对应的 qrc 资源路径（如 :/RadarIdentifySystem/images/icons/...）。
        """
        color_suffix = getIconColor(theme)
        return f":/RadarIdentifySystem/images/icons/{self.value}_{color_suffix}.svg"
