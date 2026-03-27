"""signal_bus 单元测试。"""

from __future__ import annotations

from app.events import ErrorEvent, IdentifyProgressEvent
from app.signal_bus import AppSignalBus


def test_signal_bus_contains_p02_signals() -> None:
    """校验 P02 事件全集已在总线上声明。

    功能描述：
        验证 P02 文档定义的关键信号名称在 `AppSignalBus` 中存在，防止后续迁移遗漏。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        AssertionError: 当任一关键信号缺失时抛出。
    """

    signal_names = [
        "data_import_started",
        "data_import_finished",
        "data_import_failed",
        "slice_started",
        "slice_ready",
        "slice_changed",
        "identify_started",
        "identify_progress",
        "cluster_ready",
        "identify_finished",
        "merge_started",
        "merge_finished",
        "export_started",
        "export_progress",
        "export_finished",
        "export_failed",
        "config_changed",
        "theme_changed",
        "toast_requested",
        "error_reported",
    ]

    for name in signal_names:
        assert hasattr(AppSignalBus, name), f"缺少信号: {name}"


def test_signal_emits_event_payload() -> None:
    """校验信号可正确传递事件载荷。

    功能描述：
        对典型对象型信号和基础类型信号做最小发射校验，确保后续模块可据此对接。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        AssertionError: 当发射结果与预期不一致时抛出。
    """

    bus = AppSignalBus()

    progress_payloads: list[IdentifyProgressEvent] = []
    error_payloads: list[ErrorEvent] = []
    config_payloads: list[tuple[str, object]] = []

    bus.identify_progress.connect(lambda event: progress_payloads.append(event))
    bus.error_reported.connect(lambda event: error_payloads.append(event))
    bus.config_changed.connect(lambda key, value: config_payloads.append((key, value)))

    progress_event = IdentifyProgressEvent(current_slice_idx=2, total_slices=10, progress=0.2)
    error_event = ErrorEvent(code="E001", message="示例错误", detail="detail", trace_id="trace-001")

    bus.identify_progress.emit(progress_event)
    bus.error_reported.emit(error_event)
    bus.config_changed.emit("plot.scaleMode", "STRETCH")

    assert progress_payloads == [progress_event]
    assert error_payloads == [error_event]
    assert config_payloads == [("plot.scaleMode", "STRETCH")]
