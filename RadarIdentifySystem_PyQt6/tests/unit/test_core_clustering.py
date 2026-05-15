import numpy as np
from core.clustering import cluster_single_slice
from core.models.algorithm_params import ClusteringParams
from core.params_extract import extract_grouped_values
from core.models.slice_result import SingleSlice

def test_extract_grouped_values():
    """测试提取组群均值功能。"""
    # 构造数据：有明显的三个分组
    # 组1：10.1, 10.2, 10.3, 10.1 (均值 ~10.175)
    # 组2：20.1, 20.2, 20.0, 20.1 (均值 ~20.1)
    # 噪声：50.0, 100.0
    data = [
        10.1, 10.2, 10.3, 10.1,
        20.1, 20.2, 20.0, 20.1,
        50.0, 100.0
    ]
    
    # min_samples=3 即可成簇
    grouped_values = extract_grouped_values(
        data, eps=0.5, min_samples=3, threshold_ratio=0.1
    )
    
    assert len(grouped_values) == 2
    assert 10.0 < grouped_values[0] < 11.0 or 10.0 < grouped_values[1] < 11.0
    assert 20.0 < grouped_values[0] < 21.0 or 20.0 < grouped_values[1] < 21.0

def test_cluster_single_slice():
    """测试单个切片级联聚类。"""
    # 构造数据，包含 CF 和 PW 两组明显的簇，以及一些噪声
    n = 20
    # CF 维度：前10个在 1000 左右，后10个散乱
    # PW 维度：后10个中，前5个在 5.0 左右，最后5个完全散乱
    
    cf = np.array([1000.0] * 10 + [2000.0 + i * 100 for i in range(10)])
    pw = np.array([1.0] * 10 + [5.0] * 5 + [10.0 + i for i in range(5)])
    doa = np.full(n, 90.0)
    pa = np.full(n, 100.0)
    toa = np.arange(n) * 10_000  # TOA 以 0.1us 递增，diff=10000(0.1us)×0.1=1000us，DTOA 具周期性
    
    data = np.column_stack([cf, pw, doa, pa, toa])
    slice_data = SingleSlice(index=0, data=data, time_range=(0.0, 200_000.0))
    
    # 执行级联聚类
    res = cluster_single_slice(
        slice_data,
        params=ClusteringParams(
            eps_cf=2.0,
            eps_pw=0.2,
            min_pts=3,
            min_cluster_size=4,
        ),
    )
    
    # 应该得到 2 个簇：1个 CF 簇 (前10个点)，1个 PW 簇 (第10~14个点)
    # 最后 5 个点是噪声
    assert len(res.clusters) == 2
    
    # 检查 CF 簇
    cf_cluster = next((c for c in res.clusters if c.dim_name == "CF"), None)
    assert cf_cluster is not None
    assert len(cf_cluster.points_indices) == 10
    
    # 检查 PW 簇
    pw_cluster = next((c for c in res.clusters if c.dim_name == "PW"), None)
    assert pw_cluster is not None
    assert len(pw_cluster.points_indices) == 5
    
    # 检查剩余点
    assert len(res.unprocessed_points) == 5
