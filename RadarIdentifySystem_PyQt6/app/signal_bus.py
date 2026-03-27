"""全局信号总线。"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class AppSignalBus(QObject):
    """应用级全局信号总线。

    功能描述：
        提供跨模块轻量事件通知，避免页面与业务模块直接耦合。

    参数说明：
        无。

    返回值说明：
        无。

    异常说明：
        无。
    """

    data_import_started = pyqtSignal(str)
    data_import_finished = pyqtSignal(object)
    data_import_failed = pyqtSignal(object)

    slice_started = pyqtSignal()
    slice_ready = pyqtSignal(object)
    slice_changed = pyqtSignal(int)

    identify_started = pyqtSignal()
    identify_progress = pyqtSignal(object)
    cluster_ready = pyqtSignal(object)
    identify_finished = pyqtSignal(bool, int)

    merge_started = pyqtSignal()
    merge_finished = pyqtSignal(object)

    export_started = pyqtSignal(str)
    export_progress = pyqtSignal(object)
    export_finished = pyqtSignal(str)
    export_failed = pyqtSignal(object)

    config_changed = pyqtSignal(str, object)
    theme_changed = pyqtSignal(str, str)

    toast_requested = pyqtSignal(str, str)
    error_reported = pyqtSignal(object)

    def __init__(self) -> None:
        """初始化信号总线。

        功能描述：
            构建应用全局信号对象。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        super().__init__()


signal_bus = AppSignalBus()
