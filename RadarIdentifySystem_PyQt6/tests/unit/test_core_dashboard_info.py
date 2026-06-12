# -*- coding: utf-8 -*-
"""core/dashboard_info.py 的单元测试。

覆盖 Excel 文件仪表盘信息从预处理结果中派生的规则，确保 UI 层只需要读取
已经归一化的摘要数据。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.dashboard_info import DashboardInfoManager
from core.models.pulse_batch import COL_TOA
from core.preprocess import preprocess


def test_builds_excel_dashboard_info_from_preprocess_result() -> None:
    """从 Excel 预处理结果生成六项仪表盘指标。"""
    data = np.array(
        [
            [5000.0, 1.0, 90.0, 100.0, 1000.0],
            [5000.0, 1.0, 91.0, 255.0, 2000.0],
            [5000.0, 1.0, 92.0, 80.0, 2_501_000.0],
        ],
        dtype=float,
    )
    preprocess_result = preprocess(data, source_type="excel", slice_length=2_500_000)

    info = DashboardInfoManager().build_excel_info(preprocess_result, slice_length=2_500_000)

    assert info.total_pulses == 3
    assert info.removed_pulses == 1
    assert info.amplitude_dropped_pulses == 1
    assert info.duration == 2_500_000.0
    assert info.band == "C波段"
    assert info.estimated_slice_count == 1


def test_excel_dashboard_duration_uses_fixed_toa_last_minus_first() -> None:
    """持续时间来自翻折修正后的最后一个 TOA 减第一个 TOA。"""
    data = np.array(
        [
            [5000.0, 1.0, 90.0, 100.0, 10_000.0],
            [5000.0, 1.0, 91.0, 100.0, 20_000.0],
            [5000.0, 1.0, 92.0, 100.0, -1_000_000_000.0],
            [5000.0, 1.0, 93.0, 100.0, -999_990_000.0],
        ],
        dtype=float,
    )
    preprocess_result = preprocess(data, source_type="excel", slice_length=2_500_000)
    fixed_toa = preprocess_result.data[:, COL_TOA]

    info = DashboardInfoManager().build("excel", preprocess_result, slice_length=2_500_000)

    assert info is not None
    assert info.duration == float(fixed_toa[-1] - fixed_toa[0])
    assert info.duration > 0


def test_build_returns_none_for_unimplemented_source_type() -> None:
    """尚未实现的文件类型返回 None，预留 bin/mat 后续扩展。"""
    preprocess_result = preprocess(np.empty((0, 5)), source_type="excel")

    info = DashboardInfoManager().build("bin", preprocess_result)

    assert info is None


if __name__ == "__main__":
    tests = [
        test_builds_excel_dashboard_info_from_preprocess_result,
        test_excel_dashboard_duration_uses_fixed_toa_last_minus_first,
        test_build_returns_none_for_unimplemented_source_type,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
