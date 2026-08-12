# -*- coding: utf-8 -*-
"""统一脉冲仪表盘与波段拆分规则单元测试。

覆盖 Excel 文件仪表盘信息从预处理结果中派生的规则，确保 UI 层只需要读取
已经归一化的摘要数据。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.banding import split_pulse_indices_by_band
from core.dashboard import DashboardInfoManager
from core.models.pulse_batch import COL_TOA
from core.preprocess import preprocess


def test_builds_pulse_dashboard_info_from_preprocess_result() -> None:
    """从统一预处理结果生成六项仪表盘指标。"""
    data = np.array(
        [
            [5000.0, 1.0, 100.0, 90.0, 90.0, 1000.0],
            [5000.0, 1.0, 255.0, 91.0, 91.0, 2000.0],
            [5000.0, 1.0, 80.0, 92.0, 92.0, 2_501_000.0],
        ],
        dtype=float,
    )
    preprocess_result = preprocess(data, source_type="excel", slice_length=2_500_000)

    info = DashboardInfoManager().build_pulse_info(
        preprocess_result,
        slice_length=2_500_000,
    )

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
            [5000.0, 1.0, 100.0, 90.0, 90.0, 10_000.0],
            [5000.0, 1.0, 100.0, 91.0, 91.0, 20_000.0],
            [5000.0, 1.0, 100.0, 92.0, 92.0, 30_000.0],
            [5000.0, 1.0, 100.0, 93.0, 93.0, -1_000_000_000.0],
            [5000.0, 1.0, 100.0, 94.0, 94.0, -999_990_000.0],
        ],
        dtype=float,
    )
    preprocess_result = preprocess(data, source_type="excel", slice_length=2_500_000)
    fixed_toa = preprocess_result.data[:, COL_TOA]

    info = DashboardInfoManager().build("excel", preprocess_result, slice_length=2_500_000)

    assert info is not None
    assert info.duration == float(fixed_toa[-1] - fixed_toa[0])
    assert info.duration > 0


def test_build_returns_common_info_for_bin() -> None:
    """BIN 与 Excel 共用统一摘要契约。"""
    preprocess_result = preprocess(np.empty((0, 6)), source_type="bin")

    info = DashboardInfoManager().build("bin", preprocess_result)

    assert info.total_pulses == 0


def test_preprocess_counts_source_filter_and_pa_drop_separately() -> None:
    """来源过滤计入总剔除数，但不冒充 PA 丢弃数量。"""
    data = np.array([[1500, 1, 255, 1, 1, 10]], dtype=float)

    result = preprocess(
        data,
        source_type="bin",
        source_total_pulses=3,
        band_name="L波段",
    )

    assert result.total_pulses == 3
    assert result.filtered_pulses == 3
    assert result.amplitude_dropped_pulses == 1
    assert result.dashboard_info is not None
    assert result.dashboard_info.removed_pulses == 3
    assert result.dashboard_info.amplitude_dropped_pulses == 1
    assert result.dashboard_info.band == "L波段"


def test_splits_mixed_source_rows_into_stable_lsc_groups() -> None:
    """Excel 与 BIN 可复用同一组逐行 CF 波段边界。"""
    data = np.array(
        [
            [999, 1, 1, 1, 1, 0],
            [1500, 1, 1, 1, 1, 1],
            [3999, 1, 1, 1, 1, 2],
            [4000, 1, 1, 1, 1, 3],
            [8000, 1, 1, 1, 1, 4],
            [1501, 1, 1, 1, 1, 5],
        ],
        dtype=float,
    )

    groups = split_pulse_indices_by_band(data)

    assert groups["L"].tolist() == [1, 5]
    assert groups["S"].tolist() == [2]
    assert groups["C"].tolist() == [3]


if __name__ == "__main__":
    tests = [
        test_builds_pulse_dashboard_info_from_preprocess_result,
        test_excel_dashboard_duration_uses_fixed_toa_last_minus_first,
        test_build_returns_common_info_for_bin,
        test_preprocess_counts_source_filter_and_pa_drop_separately,
        test_splits_mixed_source_rows_into_stable_lsc_groups,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
