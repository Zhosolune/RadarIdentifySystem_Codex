"""合并计划与合并结果数据模型。

本模块仅定义合并判别及执行后的数据载体，不包含合并准则、绘图或推理逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.models.extraction_result import ExtractedClusterParams
from core.models.recognition_result import ClusterRecognition


@dataclass(frozen=True, slots=True)
class MergeGroup:
    """单个切片内需要合并的一组来源簇。

    Attributes:
        slice_index [int]: 目标切片的0-based索引。
        cluster_indices [tuple[int, ...]]: 至少两个、互不重复的来源簇编号。

    Raises:
        ValueError: 切片索引、来源数量或来源簇编号不合法时抛出。

    Example:
        >>> MergeGroup(slice_index=0, cluster_indices=(1, 3)).cluster_indices
        (1, 3)
    """

    slice_index: int
    cluster_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        """校验合并分组的结构约束。"""
        if self.slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        if len(self.cluster_indices) < 2:
            raise ValueError("合并分组至少需要两个来源簇")
        if any(cluster_index < 1 for cluster_index in self.cluster_indices):
            raise ValueError("来源簇编号必须大于等于 1")
        if len(set(self.cluster_indices)) != len(self.cluster_indices):
            raise ValueError("合并分组不能包含重复簇编号")


@dataclass(frozen=True, slots=True)
class SliceMergePlan:
    """一个切片经过某项准则判别后得到的完整合并计划。

    同一计划中的分组必须互不重叠，确保批量执行时每个来源簇最多进入一个结果。

    Attributes:
        slice_index [int]: 目标切片的0-based索引。
        strategy_id [str]: 生成计划的合并准则稳定标识。
        groups [tuple[MergeGroup, ...]]: 按确定性顺序排列的互斥合并分组。

    Raises:
        ValueError: 索引非法、准则标识为空、分组跨切片或组间重叠时抛出。

    Example:
        >>> plan = SliceMergePlan(0, "example", (MergeGroup(0, (1, 2)),))
        >>> plan.group_count
        1
    """

    slice_index: int
    strategy_id: str
    groups: tuple[MergeGroup, ...]

    def __post_init__(self) -> None:
        """校验切片计划及组间互斥约束。"""
        if self.slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        if not self.strategy_id.strip():
            raise ValueError("strategy_id 不能为空")
        seen_indices: set[int] = set()
        for group in self.groups:
            if group.slice_index != self.slice_index:
                raise ValueError("合并分组与计划的切片索引不一致")
            current_indices = set(group.cluster_indices)
            if seen_indices.intersection(current_indices):
                raise ValueError("同一合并计划中的分组不能包含重复来源簇")
            seen_indices.update(current_indices)

    @property
    def group_count(self) -> int:
        """返回计划包含的合并分组数量。

        Returns:
            int: 合并分组数量。

        Example:
            >>> SliceMergePlan(0, "example", ()).group_count
            0
        """
        return len(self.groups)


@dataclass(slots=True)
class MergePlan:
    """Session级切片合并计划集合。

    Attributes:
        slice_plans [dict[int, SliceMergePlan]]: 切片索引到完整合并计划的映射。
    """

    slice_plans: dict[int, SliceMergePlan] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MergedClusterResult:
    """单个显式合并目标的执行结果。

    Attributes:
        merge_index [int]: 当前切片内从 1 开始的合并结果序号。
        slice_index [int]: 来源切片的 0-based 索引。
        strategy_id [str]: 生成本次目标的准则标识；人工显式目标使用 ``explicit``。
        source_cluster_indices [tuple[int, ...]]: 按合并顺序保存的来源簇编号。
        source_dim_names [tuple[str, ...]]: 各来源簇原聚类维度。
        source_point_clouds [tuple[np.ndarray, ...]]: 保持独立的来源点云，供多颜色绘图。
        merged_points [np.ndarray]: 按来源顺序拼接后的完整点云。
        merged_point_indices [np.ndarray]: 拼接后的原切片点索引。
        time_range [tuple[float, float]]: 覆盖全部来源簇的时间范围。
        source_recognitions [tuple[ClusterRecognition, ...]]: 未重新推理的原识别记录。
        merged_recognition [ClusterRecognition | None]: 合并后识别结果；当前策略不重新识别，因此为 None。
        extracted_params [ExtractedClusterParams]: 对拼接点云重新提取的参数。
    """

    merge_index: int
    slice_index: int
    strategy_id: str
    source_cluster_indices: tuple[int, ...]
    source_dim_names: tuple[str, ...]
    source_point_clouds: tuple[np.ndarray, ...]
    merged_points: np.ndarray
    merged_point_indices: np.ndarray
    time_range: tuple[float, float]
    source_recognitions: tuple[ClusterRecognition, ...]
    merged_recognition: ClusterRecognition | None
    extracted_params: ExtractedClusterParams


@dataclass(slots=True)
class SliceMergeResult:
    """单个切片的全部人工或规则合并结果。

    Attributes:
        slice_index [int]: 当前切片的 0-based 索引。
        merged_clusters [list[MergedClusterResult]]: 按执行顺序保存的合并结果。
    """

    slice_index: int
    merged_clusters: list[MergedClusterResult] = field(default_factory=list)


@dataclass(slots=True)
class MergeResult:
    """Session 级合并结果集合。

    Attributes:
        slice_results [dict[int, SliceMergeResult]]: 切片索引到合并结果的映射。
    """

    slice_results: dict[int, SliceMergeResult] = field(default_factory=dict)
