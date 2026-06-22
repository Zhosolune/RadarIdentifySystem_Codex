# -*- coding: utf-8 -*-
"""core/models/cluster_result.py — 聚类输出数据结构。

本模块定义了聚类算法的输出结果数据模型。
支持三种状态：PENDING（待识别）、VALID（有效雷达信号）、INVALID（噪声/被回收）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np


class ClusterState(Enum):
    """聚类结果状态枚举。
    
    功能描述：
        定义单个簇在识别流程中的生命周期状态。
    """
    PENDING = auto()  # 待识别（刚完成聚类）
    VALID = auto()    # 有效（经过识别判定为真实雷达信号）
    INVALID = auto()  # 无效/噪声（识别失败，将被回收为离散点）


@dataclass
class ClusterItem:
    """单个聚类簇的数据模型。
    
    功能描述：
        存储单个雷达信号簇的点云数据及相关特征。
    """
    cluster_idx: int                 # 簇的唯一序号
    dim_name: str                    # 聚类维度名称 ('CF' 或 'PW')
    points: np.ndarray               # 簇内点云数据，shape=(N, 5)
    points_indices: np.ndarray       # 簇内点在当前维度处理前的数据数组中的索引
    slice_idx: int                   # 所属切片索引
    time_ranges: tuple[float, float] # 该簇所处的时间范围 (start, end)，单位 0.1us
    state: ClusterState = ClusterState.PENDING  # 簇当前状态
    
    # 以下为特征与识别产物，识别前可为空
    valid_cluster_idx: int | None = None  # 仅在 state=VALID 时分配，标记其在所有有效簇中的顺序索引
    pa_label: int | None = None
    dtoa_label: int | None = None
    joint_prob: float | None = None
    image_paths: dict[str, str] | None = None
    
    @property
    def cluster_size(self) -> int:
        """获取簇内包含的点云数量。"""
        return len(self.points)


@dataclass
class SliceClusterResult:
    """单一切片的聚类结果总览。
    
    功能描述：
        汇总单个切片经过 CF 和 PW 两轮聚类后的最终状态，
        包含所有产生的簇，以及未被聚类或被判定无效回收的离散点。
    """
    slice_idx: int
    clusters: list[ClusterItem] = field(default_factory=list)
    unprocessed_points: np.ndarray | None = None  # 历经所有维度仍未被聚类的离散点
    recycled_points: np.ndarray | None = None     # 被识别为无效（INVALID）后回收的点


@dataclass
class ClusteringResult:
    """全量会话的聚类结果。
    
    功能描述：
        汇总所有切片的聚类与识别结果，写入 ProcessingSession 中。
    """
    slice_results: dict[int, SliceClusterResult] = field(default_factory=dict)
    
    @property
    def total_clusters(self) -> int:
        """所有切片中聚类簇的总数。"""
        return sum(len(res.clusters) for res in self.slice_results.values())
