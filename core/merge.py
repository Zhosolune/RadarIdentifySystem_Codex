"""显式合并与切片级批量计划执行。

可插拔判别准则位于 ``core.merge_strategy``；本模块只负责执行已经确定的来源
分组、拼接点云并重新提取参数，不修改原聚类结果或识别结果。
"""

from __future__ import annotations

import numpy as np

from core.merge_strategy import (
    DefaultMergeStrategy,
    HybridParameterMergeStrategy,
    MergeStrategy,
)
from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.merge_result import MergeGroup, MergedClusterResult, SliceMergePlan
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import extract_cluster_params


# 兼容既有runtime和测试；计划模型中的正式名称为MergeGroup。
MergeTarget = MergeGroup


class MergePipeline:
    """编排已识别类的点云合并与参数重提取。

    本类不依赖推理服务，所有方法只创建派生合并结果，不修改传入的聚类、识别
    或合并计划对象。

    Attributes:
        extract_params [ExtractParams]: 当前session的参数提取快照。
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
        target: MergeGroup,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
        merge_index: int,
        strategy_id: str = "explicit",
    ) -> MergedClusterResult:
        """执行一个明确来源分组的合并流程。

        Args:
            target [MergeGroup]: 已由上层确定的来源簇集合。
            slice_cluster_result [SliceClusterResult]: 目标切片的聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 目标切片的原识别结果。
            merge_index [int]: 当前切片内从1开始的合并结果序号。
            strategy_id [str]: 生成分组的准则标识，默认表示人工显式目标。

        Returns:
            MergedClusterResult: 点云拼接、来源识别保留和参数重提取后的结果。

        Raises:
            ValueError: 切片不匹配、序号非法、来源不存在或来源未识别通过时抛出。
        """
        if merge_index < 1:
            raise ValueError("merge_index 必须大于等于1")
        if not strategy_id.strip():
            raise ValueError("strategy_id 不能为空")
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
        extracted_params = extract_cluster_params(merged_points, self.extract_params)
        return MergedClusterResult(
            merge_index=merge_index,
            slice_index=target.slice_index,
            strategy_id=strategy_id,
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

    def run_plan(
        self,
        plan: SliceMergePlan,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
        start_merge_index: int = 1,
    ) -> tuple[MergedClusterResult, ...]:
        """一次执行切片计划中的全部互斥合并分组。

        Args:
            plan [SliceMergePlan]: 合并准则生成的完整切片计划。
            slice_cluster_result [SliceClusterResult]: 目标切片的聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 目标切片的原识别结果。
            start_merge_index [int]: 首个结果的1-based序号，默认从1开始。

        Returns:
            tuple[MergedClusterResult, ...]: 与计划分组顺序一致的独立合并结果。

        Raises:
            ValueError: 起始序号非法、切片不匹配或任一来源簇不可用时抛出。

        Example:
            >>> hasattr(MergePipeline, "run_plan")
            True
        """
        if start_merge_index < 1:
            raise ValueError("start_merge_index 必须大于等于1")
        if slice_cluster_result.slice_idx != plan.slice_index:
            raise ValueError("聚类结果与合并计划的切片索引不一致")
        if slice_recognition_result.slice_index != plan.slice_index:
            raise ValueError("识别结果与合并计划的切片索引不一致")
        return tuple(
            self.run(
                target=group,
                slice_cluster_result=slice_cluster_result,
                slice_recognition_result=slice_recognition_result,
                merge_index=start_merge_index + offset,
                strategy_id=plan.strategy_id,
            )
            for offset, group in enumerate(plan.groups)
        )

    def _resolve_sources(
        self,
        target: MergeGroup,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> tuple[list[ClusterItem], list[ClusterRecognition]]:
        """按分组顺序解析已识别通过的来源簇和识别记录。"""
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
        """校验并按来源顺序拼接同构NumPy数组。"""
        if any(array.size == 0 for array in arrays):
            raise ValueError(f"来源{label}不能为空")
        try:
            return np.concatenate(arrays, axis=0)
        except ValueError as error:
            raise ValueError(f"来源{label}结构不一致，无法拼接") from error
