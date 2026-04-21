# -*- coding: utf-8 -*-
"""tests/unit/test_core_slicing.py — core/data/slicing.py 单元测试。

覆盖场景：
    - slice_by_toa: 空数据、单切片、多切片、空切片跳过、
      slices/time_ranges 索引一致性
    - slice_from_preprocess: 便捷包装正确性

运行方式（在 RadarIdentifySystem_PyQt6 根目录下）：
    python -m pytest tests/unit/test_core_slicing.py -v
    或:
    python tests/unit/test_core_slicing.py
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from core.data.slicing import slice_by_toa, slice_from_preprocess
from core.data.preprocess import preprocess
from core.models.pulse_batch import COL_TOA
from core.models.slice_result import SliceResult, SingleSlice


# -------------------------------------------------------------------
# 辅助函数
# -------------------------------------------------------------------

def _make_data_with_toa(toa_values: list[float], cf: float = 5000.0) -> np.ndarray:
    """构造 shape=(N, 5) 的测试数据，TOA 由参数指定。"""
    n = len(toa_values)
    return np.column_stack([
        np.full(n, cf),         # CF
        np.full(n, 1.0),        # PW
        np.full(n, 90.0),       # DOA
        np.full(n, 100.0),      # PA
        np.array(toa_values, dtype=float),  # TOA
    ])


# -------------------------------------------------------------------
# slice_by_toa 测试
# -------------------------------------------------------------------

def test_slice_empty_data():
    """空数据返回 slice_count=0 的 SliceResult。"""
    data = np.empty((0, 5))
    result = slice_by_toa(data)
    assert result.slice_count == 0
    assert len(result.slices) == 0


def test_slice_single_pulse():
    """单条脉冲 → 1 个切片。"""
    data = _make_data_with_toa([0.0])
    result = slice_by_toa(data, slice_length_ms=250.0)
    assert result.slice_count == 1


def test_slice_all_in_one_window():
    """所有脉冲在同一窗口内 → 1 个切片。"""
    toa = [0.0, 50.0, 100.0, 200.0, 249.0]
    data = _make_data_with_toa(toa)
    result = slice_by_toa(data, slice_length_ms=250.0)
    assert result.slice_count == 1
    assert len(result.slices[0].data) == 5
    assert result.slices[0].time_range == (0.0, 250.0)
    assert result.slices[0].index == 0


def test_slice_two_windows():
    """脉冲分布在两个不同窗口 → 2 个切片。"""
    toa = [0.0, 100.0, 260.0, 400.0]  # 前两个在 [0,250)，后两个在 [250,500)
    data = _make_data_with_toa(toa)
    result = slice_by_toa(data, slice_length_ms=250.0)
    assert result.slice_count == 2
    assert len(result.slices[0].data) == 2, "第1片应有2条脉冲"
    assert len(result.slices[1].data) == 2, "第2片应有2条脉冲"
    assert result.slices[0].time_range == (0.0, 250.0)
    assert result.slices[1].time_range == (250.0, 500.0)
    assert result.slices[0].index == 0
    assert result.slices[1].index == 1


def test_slice_skip_empty_window():
    """中间窗口无脉冲时应被跳过，不出现在结果中。"""
    # [0,250) 有数据，[250,500) 无数据，[500,750) 有数据
    toa = [0.0, 100.0, 550.0, 600.0]
    data = _make_data_with_toa(toa)
    result = slice_by_toa(data, slice_length_ms=250.0)
    assert result.slice_count == 2, f"中间空窗口应被跳过，期望 2 片，实际 {result.slice_count}"
    assert result.slices[0].time_range == (0.0, 250.0)
    assert result.slices[1].time_range == (500.0, 750.0)
    assert result.slices[0].index == 0
    assert result.slices[1].index == 1


def test_slice_time_ranges_align_with_slices():
    """time_ranges 与 slices 长度完全对应。"""
    toa = list(range(0, 1000, 10))  # 100 条脉冲，TOA 0~990 ms
    data = _make_data_with_toa(toa)
    result = slice_by_toa(data, slice_length_ms=250.0)
    assert len(result.slices) == len(result.time_ranges), (
        "slices 与 time_ranges 长度必须一致"
    )


def test_slice_time_range_boundaries():
    """每个切片的时间范围左端点 <= 切片内 TOA 最小值，右端点 > TOA 最大值。"""
    toa = [10.0, 50.0, 200.0, 280.0, 450.0]
    data = _make_data_with_toa(toa)
    result = slice_by_toa(data, slice_length_ms=250.0)
    for i, (s, (t_start, t_end)) in enumerate(zip(result.slices, result.time_ranges)):
        slice_toa = s[:, COL_TOA]
        assert t_start <= float(np.min(slice_toa)), (
            f"切片{i}: t_start={t_start} 应 <= 切片内最小 TOA={np.min(slice_toa)}"
        )
        assert t_end > float(np.max(slice_toa)), (
            f"切片{i}: t_end={t_end} 应 > 切片内最大 TOA={np.max(slice_toa)}"
        )


def test_slice_no_data_modification():
    """slice_by_toa 不修改传入数组。"""
    toa = [0.0, 100.0, 300.0]
    data = _make_data_with_toa(toa)
    original_copy = data.copy()
    slice_by_toa(data, slice_length_ms=250.0)
    np.testing.assert_array_equal(data, original_copy, "传入数组不应被修改")


def test_slice_total_pulses_preserved():
    """切片后各子数组总行数等于原始数据行数（因为无空切片跳过的极端情况）。"""
    toa = list(np.linspace(0, 999, 200))   # 200 条横跨 1000ms
    data = _make_data_with_toa(toa)
    result = slice_by_toa(data, slice_length_ms=250.0)
    total_in_slices = sum(len(s) for s in result.slices)
    assert total_in_slices == 200, f"期望 200 条脉冲，实际 {total_in_slices}"





# -------------------------------------------------------------------
# slice_from_preprocess 测试
# -------------------------------------------------------------------

def test_slice_from_preprocess_convenience():
    """slice_from_preprocess 与直接调用 slice_by_toa 等价。"""
    import numpy as np
    n = 100
    toa = np.linspace(0, 500, n)
    data = np.column_stack([
        np.full(n, 5000.0),
        np.full(n, 1.0),
        np.full(n, 90.0),
        np.full(n, 100.0),
        toa,
    ])
    prep_result = preprocess(data)
    result_via_helper = slice_from_preprocess(prep_result, slice_length_ms=250.0)
    result_direct = slice_by_toa(prep_result.data, slice_length_ms=250.0)

    assert result_via_helper.slice_count == result_direct.slice_count, (
        "便捷函数与直接调用 slice_by_toa 结果应一致"
    )


# -------------------------------------------------------------------
# 内联运行入口（不依赖 pytest）
# -------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_slice_empty_data,
        test_slice_single_pulse,
        test_slice_all_in_one_window,
        test_slice_two_windows,
        test_slice_skip_empty_window,
        test_slice_time_ranges_align_with_slices,
        test_slice_time_range_boundaries,
        test_slice_no_data_modification,
        test_slice_total_pulses_preserved,
        test_slice_result_post_init_consistency,
        test_slice_from_preprocess_convenience,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
    print(f"\n结果: {passed} 通过 / {failed} 失败 / {len(tests)} 总计")
    sys.exit(0 if failed == 0 else 1)
