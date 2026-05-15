import numpy as np
from core.slicing import slice_by_toa
from core.models.pulse_batch import COL_TOA

def test_slice_by_toa_basic():
    """测试基本切片逻辑。"""
    # 构造测试数据，3个切片，每个切片1个脉冲
    # TOA 以 0.1us 为单位存储
    # 0, 1_000_000(100ms) -> 切片0 [0, 2_500_000)
    # 2_600_000(260ms) -> 切片1 [2_500_000, 5_000_000)
    # 6_000_000(600ms) -> 切片2 [5_000_000, 7_500_000)
    toa = np.array([0.0, 1_000_000.0, 2_600_000.0, 6_000_000.0])
    n = len(toa)
    data = np.column_stack([
        np.full(n, 5000.0),  # CF
        np.full(n, 1.0),     # PW
        np.full(n, 90.0),    # DOA
        np.full(n, 100.0),   # PA
        toa,                 # TOA
    ])
    
    res = slice_by_toa(data, slice_length=2_500_000)
    
    assert res.slice_length == 2_500_000
    assert res.slice_count == 3
    assert len(res.slices[0].data) == 2
    assert len(res.slices[1].data) == 1
    assert len(res.slices[2].data) == 1
    
    assert res.slices[0].time_range == (0.0, 2_500_000.0)
    assert res.slices[1].time_range == (2_500_000.0, 5_000_000.0)
    assert res.slices[2].time_range == (5_000_000.0, 7_500_000.0)

def test_slice_by_toa_empty_skip():
    """测试跳过空切片。"""
    # 0 -> 切片0
    # 8_000_000(800ms) -> 切片3 (跳过 250, 500)
    toa = np.array([0.0, 8_000_000.0])
    n = len(toa)
    data = np.column_stack([
        np.full(n, 5000.0),
        np.full(n, 1.0),
        np.full(n, 90.0),
        np.full(n, 100.0),
        toa,
    ])
    
    res = slice_by_toa(data, slice_length=2_500_000)
    assert res.slice_count == 2
    assert res.slices[0].time_range == (0.0, 2_500_000.0)
    assert res.slices[1].time_range == (7_500_000.0, 10_000_000.0)

def test_slice_by_toa_single_point():
    """测试单个点切片。"""
    toa = np.array([0.0])
    n = len(toa)
    data = np.column_stack([
        np.full(n, 5000.0),
        np.full(n, 1.0),
        np.full(n, 90.0),
        np.full(n, 100.0),
        toa,
    ])
    
    res = slice_by_toa(data, slice_length=2_500_000)
    assert res.slice_count == 1
    assert res.slices[0].time_range == (0.0, 2_500_000.0)
