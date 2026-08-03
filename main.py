# -*- coding: utf-8 -*-
"""
RadarIdentifySystem_PyQt6 程序入口
将父目录加入 sys.path，以便复用 core/db/utils 后端。
"""

import sys
import os
from pathlib import Path
import traceback

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QLocale, qInstallMessageHandler, QtMsgType, QMessageLogContext
from qfluentwidgets import FluentTranslator
from app.app_config import appConfig, qconfig
from app.application import create_application_services
from app.model_bootstrap import initialize_model_runtime
from ui.main_window import MainWindow
from app.logger import (
    configure_logging,
    get_current_log_file_path,
    set_log_level,
    shutdown_logging,
)
from app import resource_rc
import logging

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

LOGGER = logging.getLogger(__name__)

def qt_message_handler(mode: QtMsgType, context: QMessageLogContext, message: str) -> None:
    """拦截并处理 Qt 底层日志输出。

    主要用于屏蔽 qfluentwidgets 内部 ToolTip 读取 pixelSize 字体时导致的 -1 报错，
    并把其余 Qt 日志按级别转发到项目统一日志系统。

    Args:
        mode [QtMsgType]: Qt 消息级别。
        context [QMessageLogContext]: Qt 消息上下文，当前未使用。
        message [str]: Qt 原始消息内容。

    Returns:
        None: 无返回值。
    """
    # 屏蔽 qfluentwidgets 内部字体 pixelSize 为 -1 时的无意义警告
    if "QFont::setPointSize: Point size <= 0" in message:
        return

    # 按 Qt 消息级别映射到 Python logging 级别，统一带 session_id 占位
    if mode == QtMsgType.QtDebugMsg:
        LOGGER.debug(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtInfoMsg:
        LOGGER.info(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtWarningMsg:
        LOGGER.warning(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtCriticalMsg:
        LOGGER.error(f"[Qt] {message}", extra={"session_id": "-"})
    elif mode == QtMsgType.QtFatalMsg:
        LOGGER.error(f"[Qt] {message}", extra={"session_id": "-"})


def exception_hook(exctype: type, value: BaseException, tb: object) -> None:
    """全局未捕获异常钩子。

    记录完整异常堆栈到日志系统，并在主线程中弹出错误对话框提示用户；
    若 GUI 弹窗本身失败则仅保留日志，最后回退到系统默认异常钩子。

    Args:
        exctype [type]: 异常类型。
        value [BaseException]: 异常实例。
        tb [object]: 异常回溯对象。

    Returns:
        None: 无返回值。
    """
    # 拼接完整异常堆栈文本，便于日志定位
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    LOGGER.error("Uncaught exception:\n%s", error_msg, extra={"session_id": "-"})

    # 仅在主线程弹出错误对话框，避免子线程触发 GUI 崩溃
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
        except Exception:
            # GUI 弹窗失败时仅保留日志，避免二次异常
            pass

    # 回退到系统默认异常钩子，保证解释器行为一致
    sys.__excepthook__(exctype, value, tb)


def main() -> None:
    configure_logging(
        qconfig.get(appConfig.logDir),
        qconfig.get(appConfig.logLevel),
    )
    # 设置页修改配置后立即更新所有全局及 Session Handler，无需重启。
    appConfig.logLevel.valueChanged.connect(set_log_level)
    sys.excepthook = exception_hook
    qInstallMessageHandler(qt_message_handler)

    LOGGER.info("=========================================", extra={"session_id": "-"})
    LOGGER.info("RadarIdentifySystem Starting...", extra={"session_id": "-"})
    LOGGER.info(
        "日志记录等级：%s",
        qconfig.get(appConfig.logLevel),
        extra={"session_id": "-"},
    )
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

    # 对于PyQt6 6.8+ 版本
    # 强制使用 Fusion 风格，避免 Windows 11 原生 QStyle 给 qfluentwidgets 弹出层组件（ToolTip/ComboBox/Menu）套上灰色粗边框
    app.setStyle("Fusion")

    # 设置组件库中文
    translator = FluentTranslator(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
    app.installTranslator(translator)

    # 初始化模型启用配置（内部完成 ONNX 模型预加载）
    initialize_model_runtime(write_log=True)

    # 在应用入口完成运行期依赖装配，主窗口只接收已构造的共享服务。
    window = MainWindow(create_application_services())
    window.show()

    exit_code = 0
    try:
        exit_code = app.exec()
    finally:
        # 主事件循环结束后显式关闭全局和各 Session 文件，避免残留句柄。
        shutdown_logging()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
