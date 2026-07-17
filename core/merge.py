"""已识别类的显式合并流程。

合并准则不属于本模块。调用方只需提供明确的 ``MergeTarget``，本流程负责解析
已识别来源、拼接点云并重新提取参数；原识别输出只作为来源信息保留，不执行推理。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.merge_result import MergedClusterResult
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import extract_cluster_params


@dataclass(frozen=True, slots=True)
class MergeTarget:
    """调用方已经确定的单切片合并目标。

    Attributes:
        slice_index [int]: 目标切片的 0-based 索引。
        cluster_indices [tuple[int, ...]]: 需要合并的已识别有效簇编号，顺序决定绘图颜色。

    Raises:
        ValueError: 切片索引为负数、来源少于两个或包含重复簇编号时抛出。

    Example:
        >>> MergeTarget(slice_index=0, cluster_indices=(1, 3)).cluster_indices
        (1, 3)
    """

    slice_index: int
    cluster_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        """校验显式目标的最小结构约束。"""
        if self.slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        if len(self.cluster_indices) < 2:
            raise ValueError("合并目标至少需要两个来源簇")
        if any(cluster_index < 1 for cluster_index in self.cluster_indices):
            raise ValueError("来源簇编号必须大于等于 1")
        if len(set(self.cluster_indices)) != len(self.cluster_indices):
            raise ValueError("合并目标不能包含重复簇编号")


class MergePipeline:
    """编排已识别类的点云合并与参数重提取。

    本类刻意不依赖推理服务。若后续需要改变“是否重新识别”的规则，可在该编排层
    增加独立步骤，不影响合并准则生产者、session 写回或 UI 绘图。

    Attributes:
        extract_params [ExtractParams]: 当前 session 的参数提取快照。
    """

    def __init__(self, extract_params: ExtractParams | None = None) -> None:
        """初始化合并流程。

        Args:
            extract_params [ExtractParams | None]: 参数提取配置，默认使用内置参数。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.extract_params = extract_params or ExtractParams()

    def run(
        self,
        target: MergeTarget,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
        merge_index: int,
    ) -> MergedClusterResult:
        """执行一个明确目标的合并流程。

        Args:
            target [MergeTarget]: 已由上层确定的来源簇集合。
            slice_cluster_result [SliceClusterResult]: 目标切片的聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 目标切片的原识别结果。
            merge_index [int]: 当前切片内从 1 开始的合并结果序号。

        Returns:
            MergedClusterResult: 点云拼接、来源识别保留和参数重提取后的结果。

        Raises:
            ValueError: 切片不匹配、序号非法、来源不存在或来源未识别通过时抛出。
        """
        if merge_index < 1:
            raise ValueError("merge_index 必须大于等于 1")
        if slice_cluster_result.slice_idx != target.slice_index:
            raise ValueError("聚类结果与合并目标的切片索引不一致")
        if slice_recognition_result.slice_index != target.slice_index:
            raise ValueError("识别结果与合并目标的切片索引不一致")

        source_clusters, source_recognitions = self._resolve_sources(
            target,
            slice_cluster_result,
            slice_recognition_result,
        )
        merged_points = self._concatenate_arrays(
            tuple(cluster.points for cluster in source_clusters),
            "点云",
        )
        merged_point_indices = self._concatenate_arrays(
            tuple(cluster.points_indices for cluster in source_clusters),
            "点索引",
        )
        # 合并后只重新执行参数提取，不调用 PA/DTOA 推理服务。
        extracted_params = extract_cluster_params(merged_points, self.extract_params)
        return MergedClusterResult(
            merge_index=merge_index,
            slice_index=target.slice_index,
            source_cluster_indices=target.cluster_indices,
            source_dim_names=tuple(cluster.dim_name for cluster in source_clusters),
            source_point_clouds=tuple(cluster.points for cluster in source_clusters),
            merged_points=merged_points,
            merged_point_indices=merged_point_indices,
            time_range=(
                min(cluster.time_ranges[0] for cluster in source_clusters),
                max(cluster.time_ranges[1] for cluster in source_clusters),
            ),
            source_recognitions=tuple(source_recognitions),
            merged_recognition=None,
            extracted_params=extracted_params,
        )

    def _resolve_sources(
        self,
        target: MergeTarget,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> tuple[list[ClusterItem], list[ClusterRecognition]]:
        """按目标顺序解析已识别通过的来源簇和识别记录。"""
        cluster_map = {
            cluster.cluster_idx: cluster for cluster in slice_cluster_result.clusters
        }
        recognition_map = {
            recognition.cluster_index: recognition
            for recognition in slice_recognition_result.valid_clusters
            if recognition.is_valid
        }
        source_clusters: list[ClusterItem] = []
        source_recognitions: list[ClusterRecognition] = []
        for cluster_index in target.cluster_indices:
            cluster = cluster_map.get(cluster_index)
            if cluster is None:
                raise ValueError(f"未找到来源簇 {cluster_index}")
            if cluster.state is not ClusterState.VALID:
                raise ValueError(f"来源簇 {cluster_index} 不是最终有效簇")
            recognition = recognition_map.get(cluster_index)
            if recognition is None:
                raise ValueError(f"来源簇 {cluster_index} 未识别通过")
            source_clusters.append(cluster)
            source_recognitions.append(recognition)
        return source_clusters, source_recognitions

    @staticmethod
    def _concatenate_arrays(
        arrays: tuple[np.ndarray, ...],
        label: str,
    ) -> np.ndarray:
        """校验并按来源顺序拼接同构 NumPy 数组。"""
        if any(array.size == 0 for array in arrays):
            raise ValueError(f"来源{label}不能为空")
        try:
            return np.concatenate(arrays, axis=0)
        except ValueError as error:
            raise ValueError(f"来源{label}结构不一致，无法拼接") from error
