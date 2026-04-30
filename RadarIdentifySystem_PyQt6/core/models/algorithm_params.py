"""核心算法参数数据模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClusteringParams:
    """聚类算法参数。

    功能描述：
        封装 CF/PW 级联聚类流程使用的全部输入参数，作为聚类算法的稳定
        参数契约对象，避免在调用链上持续扩展长参数列表。

    Attributes:
        eps_cf (float): CF 维度 DBSCAN 邻域半径。
        eps_pw (float): PW 维度 DBSCAN 邻域半径。
        min_pts (int): DBSCAN 核心点最小样本数。
        min_cluster_size (int): 聚类有效判定的最小点数。
    """

    eps_cf: float = 2.0
    eps_pw: float = 0.2
    min_pts: int = 1
    min_cluster_size: int = 8


@dataclass(frozen=True, slots=True)
class RecognitionParams:
    """识别算法参数。

    功能描述：
        封装识别阶段使用的业务参数，供后续识别工作流与核心算法共享统一
        的参数契约。

    Attributes:
        tolerance (float): 识别匹配容差。
        min_confidence (float): 最低置信度阈值。
        max_candidates (int): 最大候选结果数量。
    """

    tolerance: float = 0.5
    min_confidence: float = 0.8
    max_candidates: int = 5


@dataclass(frozen=True, slots=True)
class ExtractParams:
    """参数提取算法参数。

    功能描述：
        封装参数提取阶段使用的控制参数，供后续提取逻辑统一消费。

    Attributes:
        step (int): 提取步长。
        smooth_window (int): 平滑窗口大小。
        outlier_threshold (float): 离群值判定阈值。
    """

    step: int = 1
    smooth_window: int = 5
    outlier_threshold: float = 3.0


@dataclass(frozen=True, slots=True)
class MergeParams:
    """合并算法参数。

    功能描述：
        封装聚类结果合并阶段的业务参数，供后续合并规则与工作流共享。

    Attributes:
        time_decay (float): 时间衰减系数。
        sim_threshold (float): 相似度阈值。
        max_extrapolate (int): 最大外推步数。
        pri_equal_doa_tolerance (float): 等 PRI 合并时的 DOA 容差。
    """

    time_decay: float = 0.9
    sim_threshold: float = 0.8
    max_extrapolate: int = 3
    pri_equal_doa_tolerance: float = 20.0
