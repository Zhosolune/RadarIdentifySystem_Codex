"""UI 专属适配策略入口。"""

from .hover_scrollbar import HoverScrollBarAdapter
from .responsive_content_width import ResponsiveContentWidthAdapter

__all__ = [
    "HoverScrollBarAdapter",
    "ResponsiveContentWidthAdapter",
]
