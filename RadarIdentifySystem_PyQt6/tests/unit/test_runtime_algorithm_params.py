"""运行时算法参数组装测试。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.algorithm_params import get_clustering_params


def test_get_clustering_params_reads_split_cf_pw_and_doa_config() -> None:
    """聚类参数组装器应读取拆分后的 CF/PW 与 DOA 配置项。"""
    params = get_clustering_params()

    assert params.eps_cf == 2.0
    assert params.min_pts_cf == 2
    assert params.eps_pw == 0.2
    assert params.min_pts_pw == 2
    assert params.eps_doa == 16.8
    assert params.min_pts_doa == 2
    assert params.clip_threshold_doa == 95.0
