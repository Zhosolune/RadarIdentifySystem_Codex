"""项目内置组件库默认主题色回归测试。"""

from qfluentwidgets.common.config import QConfig


def test_qfluentwidgets_default_theme_color_uses_project_brand_color() -> None:
    """组件库应在没有持久化配置时使用项目指定的默认主题色。"""
    assert QConfig.themeColor.defaultValue.name() == "#4772c3"
