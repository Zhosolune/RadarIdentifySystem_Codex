import numpy as np
from core.slicing import slice_by_toa
from core.models.pulse_batch import COL_TOA

def test_slice_by_toa_basic():
    """测试基本切片逻辑。"""
    # 构造测试数据，3个切片，每个切片1个脉冲
    # 0, 100 -> 切片0 [0, 250)
    # 260 -> 切片1 [250, 500)
    # 600 -> 切片2 [500, 750)
    toa = np.array([0.0, 100.0, 260.0, 600.0])
    n = len(toa)
    data = np.column_stack([
        np.full(n, 5000.0),  # CF
        np.full(n, 1.0),     # PW
        np.full(n, 90.0),    # DOA
        np.full(n, 100.0),   # PA
        toa,                 # TOA
    ])
    
    res = slice_by_toa(data, slice_length_ms=250.0)
    
    assert res.slice_length_ms == 250.0
    assert res.slice_count == 3
    assert len(res.slices[0].data) == 2
    assert len(res.slices[1].data) == 1
    assert len(res.slices[2].data) == 1
    
    assert res.slices[0].time_range == (0.0, 250.0)
    assert res.slices[1].time_range == (250.0, 500.0)
    assert res.slices[2].time_range == (500.0, 750.0)

def test_slice_by_toa_empty_skip():
    """测试跳过空切片。"""
    # 0.0 -> 切片0
    # 800.0 -> 切片3 (跳过 250, 500)
    toa = np.array([0.0, 800.0])
    n = len(toa)
    data = np.column_stack([
        np.full(n, 5000.0),
        np.full(n, 1.0),
        np.full(n, 90.0),
        np.full(n, 100.0),
        toa,
    ])
    
    res = slice_by_toa(data, slice_length_ms=250.0)
    assert res.slice_count == 2
    assert res.slices[0].time_range == (0.0, 250.0)
    assert res.slices[1].time_range == (750.0, 1000.0)

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
    
    res = slice_by_toa(data, slice_length_ms=250.0)
    assert res.slice_count == 1
    assert res.slices[0].time_range == (0.0, 250.0)
