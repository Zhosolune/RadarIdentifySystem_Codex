"""主窗口定义。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import FluentWindow, NavigationItemPosition

from app.config import apply_theme_preferences
from app.style_sheet import StyleSheet


class PlaceholderInterface(QWidget):
    """占位页面组件。

    功能描述：
        在 P01 阶段提供最小页面，用于验证导航与窗口壳可运行。

    参数说明：
        route_key (str): 页面路由键。
        title (str): 页面标题。
        description (str): 页面说明。
        style_sheet (StyleSheet | None): 页面样式枚举，默认值为 None。

    返回值说明：
        无。

    异常说明：
        ValueError: 当 `route_key` 为空时抛出。
    """

    def __init__(self, route_key: str, title: str, description: str, style_sheet: StyleSheet | None = None) -> None:
        """初始化占位页面。

        功能描述：
            创建标题与说明布局并设置对象名称，必要时应用页面 qss。

        参数说明：
            route_key (str): 页面路由键。
            title (str): 页面标题。
            description (str): 页面说明。
            style_sheet (StyleSheet | None): 页面样式枚举，默认值为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            ValueError: 当 `route_key` 为空时抛出。
        """

        super().__init__()
        if route_key.strip() == "":
            raise ValueError("route_key 不能为空")

        self.setObjectName(route_key)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_label.setStyleSheet("font-size: 22px; font-weight: 600;")

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 14px; color: #6c6c6c;")

        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch(1)

        if style_sheet is not None:
            style_sheet.apply(self)


class MainWindow(FluentWindow):
    """Fluent 主窗口。

    功能描述：
        构建 FluentWindow 最小壳，完成主题应用与主页/设置导航注册。

    参数说明：
        无。

    返回值说明：
        无。

    异常说明：
        RuntimeError: 当导航初始化失败时抛出。
    """

    def __init__(self) -> None:
        """初始化主窗口。

        功能描述：
            创建最小页面、应用主题，并注册导航入口。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            RuntimeError: 当页面注册失败时抛出。
        """

        super().__init__()
        self.home_page = PlaceholderInterface("home", "主页", "P01 骨架已启动。", StyleSheet.WELCOME_PAGE)
        self.setting_page = PlaceholderInterface(
            "settings",
            "设置",
            "P10 阶段迁入完整 SettingCard 配置页。",
            StyleSheet.SETTING_PAGE,
        )

        self._init_window()
        self._apply_theme()
        self._init_navigation()

    def _init_window(self) -> None:
        """初始化窗口参数。

        功能描述：
            设置窗口标题、尺寸与最小宽高。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        self.setWindowTitle("RadarIdentifySystem PyQt6")
        self.resize(1200, 800)
        self.setMinimumSize(960, 640)

    def _apply_theme(self) -> None:
        """应用主题配置。

        功能描述：
            根据 `app/config.py` 中配置应用主题模式与主题色。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            RuntimeError: 当主题应用失败时抛出。
        """

        apply_theme_preferences()

    def _init_navigation(self) -> None:
        """初始化导航菜单。

        功能描述：
            添加主页和设置页导航项，并默认切换到主页。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            RuntimeError: 当导航添加失败时抛出。
        """

        self.addSubInterface(self.home_page, FIF.HOME, "主页", NavigationItemPosition.TOP)
        self.addSubInterface(self.setting_page, FIF.SETTING, "设置", NavigationItemPosition.BOTTOM)
        self.switchTo(self.home_page)
