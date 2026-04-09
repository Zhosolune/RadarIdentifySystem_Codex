"""自定义图标管理模块。

提供继承自 FluentIconBase 的自定义图标枚举，自动适配深浅色主题。
"""

from __future__ import annotations

import os
from enum import Enum
from qfluentwidgets import Theme, FluentIconBase, getIconColor

# 资源目录下存放 SVG 图标的根目录绝对路径（由于可能打包，考虑使用相对运行时的绝对路径，或配置路径）
# 这里通过相对路径定位到 e:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\resources\images\icons
_ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "images", "icons")


class CustomIcon(FluentIconBase, Enum):
    """自定义图标枚举。
    
    枚举值对应图标文件名的基础名称。
    例如：ChevronLeft 会根据主题映射到 ChevronLeft_black.svg 或 ChevronLeft_white.svg
    """
    
    CHEVRON_LEFT = "ChevronLeft"
    CHEVRON_RIGHT = "ChevronRight"
    CHEVRONS_LEFT = "ChevronsLeft"
    CHEVRONS_RIGHT = "ChevronsRight"
    RESET = "Reset"

    def path(self, theme=Theme.AUTO) -> str:
        """获取图标路径。
        
        功能描述：
            根据当前主题（Theme.LIGHT 或 Theme.DARK），返回对应的黑色或白色图标文件路径。
            
        参数说明：
            theme: qfluentwidgets.Theme 枚举，表示当前应用的主题模式。
            
        返回值说明：
            str: 对应的 .svg 文件绝对路径。
        """
        # getIconColor(theme) 根据 theme 返回 "black" 或 "white"
        color_suffix = getIconColor(theme)
        return os.path.join(_ICON_DIR, f"{self.value}_{color_suffix}.svg")
