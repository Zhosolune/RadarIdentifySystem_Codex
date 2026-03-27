"""应用生命周期管理。"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PyQt6.QtWidgets import QApplication

from app import resource_rc  # noqa: F401  # 导入即注册 Qt 资源
from app.config import load_app_config
from app.logger import get_logger
from ui.main_window import MainWindow


LOGGER = get_logger("app.application")


def create_qapplication(argv: Sequence[str] | None = None) -> QApplication:
    """创建 Qt 应用实例。

    功能描述：
        统一创建 `QApplication`，并写入应用基础元信息。

    参数说明：
        argv (Sequence[str] | None): 启动参数，默认值为 None。
            当参数为 None 时将使用 `sys.argv`。

    返回值说明：
        QApplication: 已初始化的 Qt 应用实例。

    异常说明：
        RuntimeError: 当 Qt 运行环境初始化失败时抛出。
    """

    args = list(argv) if argv is not None else list(sys.argv)
    app = QApplication(args)
    app.setApplicationName("RadarIdentifySystem_PyQt6")
    app.setOrganizationName("RadarIdentifySystem")
    return app


def create_main_window() -> MainWindow:
    """创建主窗口实例。

    功能描述：
        统一创建并返回主窗口对象。

    参数说明：
        无。

    返回值说明：
        MainWindow: 主窗口实例。

    异常说明：
        RuntimeError: 当主窗口初始化失败时抛出。
    """

    return MainWindow()


def run(argv: Sequence[str] | None = None) -> int:
    """运行应用主流程。

    功能描述：
        加载配置、创建应用与主窗口，并启动事件循环。

    参数说明：
        argv (Sequence[str] | None): 启动参数，默认值为 None。

    返回值说明：
        int: Qt 事件循环退出码。

    异常说明：
        OSError: 当配置文件目录不可读写时抛出。
        RuntimeError: 当应用或窗口初始化失败时抛出。
    """

    config_path = load_app_config()
    qt_app = create_qapplication(argv)
    window = create_main_window()
    window.show()

    LOGGER.info("应用启动完成，配置文件：%s", str(config_path))
    return qt_app.exec()


