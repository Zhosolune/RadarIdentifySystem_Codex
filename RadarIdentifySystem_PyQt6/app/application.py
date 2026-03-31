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



