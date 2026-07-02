"""参数提取核心算法边界测试。"""

from __future__ import annotations

import inspect

import core.params_extract as params_extract
from core.params_extract import extract_grouped_values


def test_extract_grouped_values_returns_cluster_means() -> None:
    """核心提取工具应只对一维输入返回典型值均值。"""
    grouped_values = extract_grouped_values(
        [10.1, 10.2, 10.3, 20.0, 20.1, 20.2, 90.0],
        eps=0.5,
        min_samples=3,
        threshold_ratio=0.1,
    )

    assert sorted(grouped_values) == [10.2, 20.1]


def test_params_extract_does_not_own_dimension_business_logic() -> None:
    """core 参数提取模块不应依赖簇模型、参数对象或雷达列索引。"""
    source = inspect.getsource(params_extract)

    assert not hasattr(params_extract, "extract_cluster_params")
    assert "ClusterItem" not in source
    assert "ExtractParams" not in source
    assert "COL_CF" not in source
    assert "COL_PW" not in source
    assert "COL_DOA" not in source
    assert "COL_TOA" not in source
