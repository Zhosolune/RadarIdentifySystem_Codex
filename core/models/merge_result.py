"""合并阶段结果数据模型。

本模块仅定义显式合并目标执行后的数据载体，不包含合并准则、绘图或推理逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.models.extraction_result import ExtractedClusterParams
from core.models.recognition_result import ClusterRecognition


@dataclass(frozen=True, slots=True)
class MergedClusterResult:
    """单个显式合并目标的执行结果。

    Attributes:
        merge_index [int]: 当前切片内从 1 开始的合并结果序号。
        slice_index [int]: 来源切片的 0-based 索引。
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
