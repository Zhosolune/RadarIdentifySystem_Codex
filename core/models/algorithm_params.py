"""核心算法参数数据模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClusteringParams:
    """聚类算法参数。

    功能描述：
        封装 CF/PW 级联聚类流程以及识别通过簇的 DOA 二次聚类参数。

    Attributes:
        eps_cf: CF 维度 DBSCAN 邻域半径。
        min_pts_cf: CF 维度 DBSCAN 核心点最小样本数。
        eps_pw: PW 维度 DBSCAN 邻域半径。
        min_pts_pw: PW 维度 DBSCAN 核心点最小样本数。
        eps_doa: DOA 维度 DBSCAN 邻域半径。
        min_pts_doa: DOA 维度 DBSCAN 核心点最小样本数。
        clip_threshold_doa: DOA 限幅阈值，当前仅作为参数契约保留。
        min_cluster_size: 聚类有效判定的最小点数。
    """

    eps_cf: float = 2.0
    min_pts_cf: int = 2
    eps_pw: float = 0.2
    min_pts_pw: int = 2
    eps_doa: float = 16.8
    min_pts_doa: int = 2
    clip_threshold_doa: float = 95.0
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
        eps_cf (float): CF 参数提取邻域半径。
        min_pts_cf (int): CF 参数提取最小邻居点数。
        threshold_ratio_cf (float): CF 参数提取门限率，单位为百分比。
        eps_pw (float): PW 参数提取邻域半径。
        min_pts_pw (int): PW 参数提取最小邻居点数。
        threshold_ratio_pw (float): PW 参数提取门限率，单位为百分比。
        eps_pri (float): PRI 参数提取邻域半径。
        min_pts_pri (int): PRI 参数提取最小邻居点数。
        threshold_ratio_pri (float): PRI 参数提取门限率，单位为百分比。
        filter_threshold_pri (float): PRI 过滤门限。
        harmonic_tolerance_pri (float): PRI 谐波抑制容差。
    """

    eps_cf: float = 2.0
    min_pts_cf: int = 4
    threshold_ratio_cf: float = 10.0
    eps_pw: float = 0.2
    min_pts_pw: int = 4
    threshold_ratio_pw: float = 10.0
    eps_pri: float = 0.2
    min_pts_pri: int = 3
    threshold_ratio_pri: float = 10.0
    filter_threshold_pri: float = 2.0
    harmonic_tolerance_pri: float = 0.1


@dataclass(frozen=True, slots=True)
class MergeParams:
    """合并算法参数占位值对象。

    功能描述：
        当前合并判别规则没有可配置参数，仅保留一个无业务含义的字段贯通
        ``全局配置 -> Session快照 -> runtime值对象``。未来接入真实参数时，
        应删除该占位字段，并在同一值对象中定义实际业务参数。

    Attributes:
        placeholder_value [float]: 配置链路占位值，当前合并算法不得读取。
    """

    placeholder_value: float = 0.0
