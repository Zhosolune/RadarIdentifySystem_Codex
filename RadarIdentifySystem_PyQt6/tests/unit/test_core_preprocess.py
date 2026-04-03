# -*- coding: utf-8 -*-
"""tests/unit/test_core_preprocess.py — core/data/preprocess.py 单元测试。

覆盖场景：
    - clean_pa: 正常过滤、全部无效、全部有效、空数组
    - fix_toa_flip: 无翻折、单翻折、多翻折、空数组
    - detect_band: 各频段边界、空数组
    - preprocess: 组合流程正确性

运行方式（在 RadarIdentifySystem_PyQt6 根目录下）：
    python -m pytest tests/unit/test_core_preprocess.py -v
    或（不依赖 pytest）:
    python tests/unit/test_core_preprocess.py
"""

from __future__ import annotations

import sys
import os

# 将项目根目录加入路径，以便 import core.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from core.data.preprocess import clean_pa, fix_toa_flip, detect_band, preprocess
from core.models.pulse_batch import COL_PA, COL_TOA, COL_CF


# -------------------------------------------------------------------
# 辅助函数
# -------------------------------------------------------------------

def _make_data(rows: list[list[float]]) -> np.ndarray:
    """快速构造 shape=(N, 5) 测试数组。"""
    return np.array(rows, dtype=float)


def _make_uniform(n: int, cf=5000.0, pw=1.0, doa=90.0, pa=100.0, toa_start=0.0, toa_step=0.1) -> np.ndarray:
    """生成 N 行均匀 TOA 的测试数据（PA 均为 100，CF 默认 C 波段）。"""
    toa = np.arange(n, dtype=float) * toa_step + toa_start
    cf_arr = np.full(n, cf)
    pw_arr = np.full(n, pw)
    doa_arr = np.full(n, doa)
    pa_arr = np.full(n, pa)
    return np.column_stack([cf_arr, pw_arr, doa_arr, pa_arr, toa])


# -------------------------------------------------------------------
# clean_pa 测试
# -------------------------------------------------------------------

def test_clean_pa_removes_invalid():
    """剔除 PA=255 行，保留其余行。"""
    data = _make_data([
        [5000, 1, 90, 100, 0.0],
        [5000, 1, 90, 255, 0.1],  # 无效
        [5000, 1, 90, 80,  0.2],
    ])
    result = clean_pa(data)
    assert result.shape == (2, 5), f"期望2行，实际{result.shape}"
    assert 255 not in result[:, COL_PA], "结果中不应有 PA=255"


def test_clean_pa_all_invalid():
    """全部为 PA=255 时返回空数组。"""
    data = _make_data([
        [5000, 1, 90, 255, 0.0],
        [5000, 1, 90, 255, 0.1],
    ])
    result = clean_pa(data)
    assert result.shape[0] == 0, "全部无效应返回空数组"


def test_clean_pa_all_valid():
    """全部有效时原样返回。"""
    data = _make_uniform(5)
    result = clean_pa(data)
    assert result.shape == data.shape, "全部有效时 shape 不应改变"


def test_clean_pa_empty():
    """空数组（0行5列）正常处理，不抛异常。"""
    data = np.empty((0, 5))
    result = clean_pa(data)
    assert result.shape == (0, 5)


# -------------------------------------------------------------------
# fix_toa_flip 测试
# -------------------------------------------------------------------

def test_fix_toa_flip_no_flip():
    """无翻折时 toa_flip_count=0，数据不变（仅可能归零）。"""
    data = _make_uniform(10, toa_start=0.0, toa_step=1.0)
    fixed, count = fix_toa_flip(data)
    assert count == 0, "无翻折场景 flip_count 应为 0"
    # 无翻折时函数不修改 TOA，原始数据保持不变
    np.testing.assert_array_equal(fixed[:, COL_TOA], data[:, COL_TOA])


def test_fix_toa_flip_single_flip():
    """单翻折点：修正后 TOA 应单调不减。"""
    # 构造：0, 1, 2, 3（翻折）, -1e5, 0, 1 → 翻折后需平移
    toa = np.array([0.0, 10.0, 20.0, 30.0, -100000.0, -99990.0, -99980.0])
    n = len(toa)
    data = np.column_stack([
        np.full(n, 5000.0),  # CF
        np.full(n, 1.0),     # PW
        np.full(n, 90.0),    # DOA
        np.full(n, 100.0),   # PA
        toa,                 # TOA
    ])
    fixed, count = fix_toa_flip(data)
    assert count == 1, f"应检测到 1 个翻折点，实际 {count}"
    fixed_toa = fixed[:, COL_TOA]
    diffs = np.diff(fixed_toa)
    assert np.all(diffs >= 0), f"修正后 TOA 应单调不减，diff={diffs}"


def test_fix_toa_flip_multiple_flips():
    """多翻折点：修正后 TOA 仍单调不减。"""
    # 第一段 0~30, 翻折到 -1e5, 再从 -1e5 到 -1e5+30, 再翻折
    seg1 = np.arange(4) * 10.0               # 0, 10, 20, 30
    flip1 = -100000.0
    seg2 = flip1 + np.arange(4) * 10.0       # -1e5, -99990, -99980, -99970
    flip2 = -200000.0
    seg3 = flip2 + np.arange(3) * 10.0       # -2e5, -199990, -199980
    toa = np.concatenate([seg1, seg2, seg3])
    n = len(toa)
    data = np.column_stack([
        np.full(n, 5000.0),
        np.full(n, 1.0),
        np.full(n, 90.0),
        np.full(n, 100.0),
        toa,
    ])
    fixed, count = fix_toa_flip(data)
    assert count == 2, f"应检测到 2 个翻折点，实际 {count}"
    fixed_toa = fixed[:, COL_TOA]
    diffs = np.diff(fixed_toa)
    assert np.all(diffs >= 0), f"多翻折修正后 TOA 应单调不减"


def test_fix_toa_flip_empty():
    """空数组不抛异常，flip_count=0。"""
    data = np.empty((0, 5))
    fixed, count = fix_toa_flip(data)
    assert count == 0
    assert fixed.shape == (0, 5)


def test_fix_toa_original_not_modified():
    """fix_toa_flip 不修改传入的原始数组。"""
    data = _make_uniform(5, toa_start=0.0, toa_step=1.0)
    original_toa = data[:, COL_TOA].copy()
    fix_toa_flip(data)
    np.testing.assert_array_equal(data[:, COL_TOA], original_toa, "原始数组 TOA 不应被修改")


# -------------------------------------------------------------------
# detect_band 测试
# -------------------------------------------------------------------

def test_detect_band_L():
    data = _make_uniform(5, cf=1500.0)
    assert detect_band(data) == "L波段"


def test_detect_band_S():
    data = _make_uniform(5, cf=3000.0)
    assert detect_band(data) == "S波段"


def test_detect_band_C():
    data = _make_uniform(5, cf=6000.0)
    assert detect_band(data) == "C波段"


def test_detect_band_X():
    data = _make_uniform(5, cf=10000.0)
    assert detect_band(data) == "X波段"


def test_detect_band_below_1000():
    """CF < 1000 MHz 时返回 None（不纳入处理）。"""
    data = _make_uniform(5, cf=800.0)
    assert detect_band(data) is None


def test_detect_band_empty():
    """空数组时返回 None。"""
    data = np.empty((0, 5))
    assert detect_band(data) is None


# -------------------------------------------------------------------
# preprocess 组合测试
# -------------------------------------------------------------------

def test_preprocess_basic_flow():
    """正常流程：有效数据 → preprocess → 统计字段正确。"""
    data = _make_uniform(100, cf=5000.0, toa_step=2.0)  # TOA 范围 0~198 ms
    result = preprocess(data)

    assert result.total_pulses == 100
    assert result.filtered_pulses == 0
    assert result.toa_flip_count == 0
    assert result.time_range_ms > 0
    assert result.band == "C波段"
    assert result.remaining_pulses == 100


def test_preprocess_with_pa_filter():
    """包含 PA=255 的数据 — 过滤数量统计正确。"""
    valid = _make_uniform(90, cf=5000.0)
    invalid_rows = np.copy(_make_uniform(10, cf=5000.0))
    invalid_rows[:, COL_PA] = 255
    data = np.vstack([valid, invalid_rows])

    result = preprocess(data)
    assert result.total_pulses == 100
    assert result.filtered_pulses == 10
    assert result.remaining_pulses == 90


def test_preprocess_estimated_slice_count():
    """切片估算：时间跨度 500 ms / 250 ms = 2 片。"""
    n = 100
    toa = np.linspace(0, 500, n)  # 0~500 ms，跨度 500 ms
    data = np.column_stack([
        np.full(n, 5000.0),
        np.full(n, 1.0),
        np.full(n, 90.0),
        np.full(n, 100.0),
        toa,
    ])
    result = preprocess(data, slice_length_ms=250.0)
    assert result.estimated_slice_count == 2, (
        f"500ms / 250ms=2片，实际={result.estimated_slice_count}"
    )


def test_preprocess_empty_data():
    """空数据不抛异常，统计均为 0。"""
    data = np.empty((0, 5))
    result = preprocess(data)
    assert result.total_pulses == 0
    assert result.filtered_pulses == 0
    assert result.remaining_pulses == 0
    assert result.band is None
    assert result.time_range_ms == 0.0


# -------------------------------------------------------------------
# 内联运行入口（不依赖 pytest）
# -------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_clean_pa_removes_invalid,
        test_clean_pa_all_invalid,
        test_clean_pa_all_valid,
        test_clean_pa_empty,
        test_fix_toa_flip_no_flip,
        test_fix_toa_flip_single_flip,
        test_fix_toa_flip_multiple_flips,
        test_fix_toa_flip_empty,
        test_fix_toa_original_not_modified,
        test_detect_band_L,
        test_detect_band_S,
        test_detect_band_C,
        test_detect_band_X,
        test_detect_band_below_1000,
        test_detect_band_empty,
        test_preprocess_basic_flow,
        test_preprocess_with_pa_filter,
        test_preprocess_estimated_slice_count,
        test_preprocess_empty_data,
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
