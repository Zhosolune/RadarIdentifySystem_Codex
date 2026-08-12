# -*- coding: utf-8 -*-
"""首页仪表盘展示格式测试。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.components.import_dashboard_panel import (
    format_dashboard_band,
    format_dashboard_duration,
)


def test_format_dashboard_duration_uses_ms_until_1000ms() -> None:
    """持续时间不超过 1000ms 时使用 ms。"""
    assert format_dashboard_duration(10_000) == "1.00 ms"
    assert format_dashboard_duration(10_000_000) == "1000.00 ms"


def test_format_dashboard_duration_uses_seconds_above_1000ms() -> None:
    """持续时间超过 1000ms 且不超过 60s 时使用 s。"""
    assert format_dashboard_duration(10_010_000) == "1.00 s"
    assert format_dashboard_duration(600_000_000) == "60.00 s"


def test_format_dashboard_duration_uses_minutes_above_60s() -> None:
    """持续时间超过 60s 时使用 min。"""
    assert format_dashboard_duration(610_000_000) == "1.02 min"


def test_format_dashboard_band_removes_band_suffix() -> None:
    """波段指标应只展示波段名，并为未知值保留占位符。"""
    assert format_dashboard_band("S波段") == "S"
    assert format_dashboard_band("X") == "X"
    assert format_dashboard_band(None) == "--"


if __name__ == "__main__":
    tests = [
        test_format_dashboard_duration_uses_ms_until_1000ms,
        test_format_dashboard_duration_uses_seconds_above_1000ms,
        test_format_dashboard_duration_uses_minutes_above_60s,
        test_format_dashboard_band_removes_band_suffix,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
