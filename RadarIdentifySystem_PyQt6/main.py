# -*- coding: utf-8 -*-
"""
v2/main.py  —  EasyVer v2 程序入口
将父目录加入 sys.path，以便复用 core/db/utils 后端。
"""

import sys
import os
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QLocale, qInstallMessageHandler, QtMsgType, QMessageLogContext
from qfluentwidgets import FluentTranslator
from app.app_config import appConfig
from ui.main_window import MainWindow
from app.logger import configure_logging, get_current_log_file_path
from app import resource_rc
import logging

LOGGER = logging.getLogger(__name__)

def qt_message_handler(mode: QtMsgType, context: QMessageLogContext, message: str):
    """
    拦截并处理 Qt 底层日志输出。
    主要用于屏蔽 qfluentwidgets 内部 ToolTip 读取 pixelSize 字体时导致的 -1 报错。
    """
    if "QFont::setPointSize: Point size <= 0" in message:
        return
        
    if mode == QtMsgType.QtDebugMsg:
        LOGGER.debug(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtInfoMsg:
        LOGGER.info(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtWarningMsg:
        LOGGER.warning(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtCriticalMsg:
        LOGGER.critical(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtFatalMsg:
        LOGGER.fatal(f"[Qt] {message}", extra={"session_id": "-"})

def exception_hook(exctype, value, tb):
    """
    Global exception hook to catch unhandled exceptions.
    Logs the full traceback and shows a critical error message box if on the main thread.
    """
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    LOGGER.critical("Uncaught exception:\n%s", error_msg, extra={"session_id": "-"})

    # Show error message to user only if we are in the main thread
    from PyQt6.QtCore import QThread
    if QThread.currentThread() is QApplication.instance().thread():
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Application Error")
            msg_box.setText("An unhandled exception occurred.")
            msg_box.setInformativeText(str(value))
            msg_box.setDetailedText(error_msg)
            msg_box.exec()
        except:
            pass  # If GUI fails, we at least have the log

    sys.__excepthook__(exctype, value, tb)


def main() -> None:
    configure_logging(appConfig.logDir.value)
    sys.excepthook = exception_hook
    qInstallMessageHandler(qt_message_handler)

    LOGGER.info("=========================================", extra={"session_id": "-"})
    LOGGER.info("RadarIdentifySystem Starting...", extra={"session_id": "-"})
    LOGGER.info("当前运行日志文件：%s", get_current_log_file_path(), extra={"session_id": "-"})

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    if appConfig.get(appConfig.dpiScale) != "Auto":
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(appConfig.get(appConfig.dpiScale))

    app = QApplication(sys.argv)
    app.setApplicationName("RadarIdentifySystem")
    app.setOrganizationName("RadarIdentifySystem")

    # 设置组件库中文
    translator = FluentTranslator(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
    app.installTranslator(translator)


    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
