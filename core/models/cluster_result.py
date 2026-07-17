# -*- coding: utf-8 -*-
"""core/models/cluster_result.py — 聚类输出数据结构。

本模块定义了聚类算法的输出结果数据模型，是 core 层与 runtime/识别链路之间的
数据载体。单个簇支持三种状态：PENDING（待识别）、VALID（有效雷达信号）、
INVALID（噪声/被回收）。

Example:
    构造一个簇并标记为有效：

    >>> import numpy as np
    >>> from core.models.cluster_result import ClusterItem, ClusterState
    >>> pts = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]])
    >>> item = ClusterItem(
    ...     cluster_idx=0,
    ...     dim_name='CF',
    ...     points=pts,
    ...     points_indices=np.array([0]),
    ...     slice_idx=0,
    ...     time_ranges=(10.0, 20.0),
    ... )
    >>> item.cluster_size
    1
    >>> item.state = ClusterState.VALID
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np


class ClusterState(Enum):
    """聚类结果状态枚举。

    定义单个簇在识别流程中的生命周期状态，贯穿「聚类完成 -> 识别判定 -> 回收/确认」
    全过程。

    Attributes:
        PENDING [ClusterState]: 待识别，簇刚完成聚类尚未进入识别流程。
        VALID [ClusterState]: 有效，经识别判定为真实雷达信号。
        INVALID [ClusterState]: 无效/噪声，识别失败，将被回收为离散点。
    """
    # 待识别（刚完成聚类）
    PENDING = auto()
    # 有效（经过识别判定为真实雷达信号）
    VALID = auto()
    # 无效/噪声（识别失败，将被回收为离散点）
    INVALID = auto()


@dataclass
class ClusterItem:
    """单个聚类簇的数据模型。

    存储单个雷达信号簇的点云数据及相关特征，并在识别流程中逐步补充识别产物
    （标签、联合概率、图像路径等）。该结构本身不参与任何计算逻辑，仅作为数据载体
    在 core -> runtime -> ui 之间传递。

    Attributes:
        cluster_idx [int]: 簇的唯一序号，在其所属切片与维度内唯一。
        dim_name [str]: 聚类维度名称，取值 'CF'（载频）或 'PW'（脉宽）。
        points [np.ndarray]: 簇内点云数据，shape=(N, 6)，列含义由上游统一约定。
        points_indices [np.ndarray]: 簇内点在当前维度处理前的数据数组中的索引，shape=(N,)。
        slice_idx [int]: 所属切片索引，用于定位其归属的 SliceClusterResult。
        time_ranges [tuple[float, float]]: 该簇所处的时间范围 (start, end)，单位 0.1us。
        state [ClusterState]: 簇当前生命周期状态，默认 PENDING。
        valid_cluster_idx [int | None]: 仅在 state=VALID 时分配，标记其在所有有效簇中的顺序索引。
        pa_label [int | None]: 脉内到达角（PA）识别标签，识别前为 None。
        dtoa_label [int | None]: 到达时间差（DTOA）识别标签，识别前为 None。
        joint_prob [float | None]: PA 与 DTOA 联合识别置信概率，识别前为 None。
        image_paths [dict[str, str] | None]: 识别过程中生成的图像路径映射，键为图像类型，识别前为 None。
    """
    
    cluster_idx: int                            # 簇的唯一序号
    dim_name: str                               # 聚类维度名称 ('CF' 或 'PW')
    points: np.ndarray                          # 簇内点云数据，shape=(N, 6)
    points_indices: np.ndarray                  # 簇内点在当前维度处理前的数据数组中的索引
    slice_idx: int                              # 所属切片索引
    time_ranges: tuple[float, float]            # 该簇所处的时间范围 (start, end)，单位 0.1us
    state: ClusterState = ClusterState.PENDING  # 簇当前状态

    # 以下为特征与识别产物，识别前可为空
    valid_cluster_idx: int | None = None        # 仅在 state=VALID 时分配，标记其在所有有效簇中的顺序索引
    pa_label: int | None = None                 # 脉内到达角（PA）识别标签
    dtoa_label: int | None = None               # 到达时间差（DTOA）识别标签
    joint_prob: float | None = None             # PA 与 DTOA 联合识别置信概率
    image_paths: dict[str, str] | None = None   # 识别过程中生成的图像路径映射，键为图像类型

    @property
    def cluster_size(self) -> int:
        """获取簇内包含的点云数量。

        Returns:
            簇内点云数量，等价于 points 数组的行数。
        """
        return len(self.points)


@dataclass
class SliceClusterResult:
    """单一切片的聚类结果总览。

    汇总单个切片经过 CF 和 PW 两轮聚类后的最终状态，包含所有产生的簇，
    以及未被聚类或被判定无效回收的离散点。该结构作为 ClusteringResult 的子项，
    由 Workflow 在聚类阶段写回 Session。

    Attributes:
        slice_idx [int]: 切片索引，与原始切片一一对应。
        clusters [list[ClusterItem]]: 该切片产生的全部簇，包含各维度与各状态。
        unprocessed_points [np.ndarray | None]: 历经所有维度仍未被聚类的离散点，shape=(M, 6)。
        recycled_points [np.ndarray | None]: 被识别为无效（INVALID）后回收的点，shape=(K, 6)。
    """
    
    slice_idx: int                                              # 切片索引，与原始切片一一对应
    clusters: list[ClusterItem] = field(default_factory=list)   # 该切片产生的全部簇
    unprocessed_points: np.ndarray | None = None                # 历经所有维度仍未被聚类的离散点
    recycled_points: np.ndarray | None = None                   # 被识别为无效（INVALID）后回收的点


@dataclass
class ClusteringResult:
    """全量会话的聚类结果。

    汇总所有切片的聚类与识别结果，作为 ProcessingSession 中聚类阶段的唯一产物，
    供后续识别、合并阶段读取。该结构以 slice_idx 为键组织各切片结果。

    Attributes:
        slice_results [dict[int, SliceClusterResult]]: 切片索引到切片聚类结果的映射。
    """
    # 切片索引到切片聚类结果的映射
    slice_results: dict[int, SliceClusterResult] = field(default_factory=dict)

    @property
    def total_clusters(self) -> int:
        """获取所有切片中聚类簇的总数。

        Returns:
            所有切片中聚类簇的总数。
        """
        # 遍历各切片结果，累加其簇数量
        return sum(len(res.clusters) for res in self.slice_results.values())
