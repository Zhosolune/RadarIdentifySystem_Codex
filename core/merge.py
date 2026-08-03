"""切片级自动合并计划执行。

可插拔判别准则位于 ``core.merge_strategy``；本模块只负责执行已经确定的来源
分组、拼接点云并重新提取参数，不修改原聚类结果或识别结果。
"""

from __future__ import annotations

from dataclasses import asdict
import logging

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


LOGGER = logging.getLogger(__name__)


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
        LOGGER.debug(
            "初始化合并执行管线: 参数提取配置=%s",
            asdict(self.extract_params),
        )

    def _run_group(
        self,
        group: MergeGroup,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
        merge_index: int,
        strategy_id: str,
    ) -> MergedClusterResult:
        """执行自动策略计划中的一个来源分组。"""
        if merge_index < 1:
            raise ValueError("merge_index 必须大于等于1")
        if not strategy_id.strip():
            raise ValueError("strategy_id 不能为空")
        if slice_cluster_result.slice_idx != group.slice_index:
            raise ValueError("聚类结果与合并目标的切片索引不一致")
        if slice_recognition_result.slice_index != group.slice_index:
            raise ValueError("识别结果与合并目标的切片索引不一致")

        LOGGER.debug(
            "开始执行单个合并组: slice_index=%d, merge_index=%d, "
            "strategy_id=%s, source_cluster_indices=%s, 参数提取配置=%s",
            group.slice_index,
            merge_index,
            strategy_id,
            group.cluster_indices,
            asdict(self.extract_params),
        )
        # 先按策略分组顺序解析两类来源，确保点云、原索引和识别记录位置严格对应。
        source_clusters, source_recognitions = self._resolve_sources(
            group,
            slice_cluster_result,
            slice_recognition_result,
        )
        # 合并结果使用新数组承载拼接数据；来源簇和识别结果保持只读、继续独立存在。
        merged_points = self._concatenate_arrays(
            tuple(cluster.points for cluster in source_clusters),
            "点云",
        )
        merged_point_indices = self._concatenate_arrays(
            tuple(cluster.points_indices for cluster in source_clusters),
            "点索引",
        )
        LOGGER.debug(
            "来源数据拼接完成: slice_index=%d, merge_index=%d, "
            "source_cluster_indices=%s, 各来源点数=%s, 合并点云shape=%s, "
            "合并点索引shape=%s",
            group.slice_index,
            merge_index,
            group.cluster_indices,
            tuple(len(cluster.points) for cluster in source_clusters),
            merged_points.shape,
            merged_point_indices.shape,
        )
        # 仅对合并后的点云重新提取参数，当前功能不触发重新识别。
        extracted_params = extract_cluster_params(merged_points, self.extract_params)
        result = MergedClusterResult(
            merge_index=merge_index,
            slice_index=group.slice_index,
            strategy_id=strategy_id,
            source_cluster_indices=group.cluster_indices,
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
        LOGGER.debug(
            "单个合并组执行完成: slice_index=%d, merge_index=%d, "
            "source_cluster_indices=%s, time_range=%s, "
            "提取结果CF=%s, PW=%s, PRI=%s, DOA=%s",
            result.slice_index,
            result.merge_index,
            result.source_cluster_indices,
            result.time_range,
            tuple(result.extracted_params.cf_values),
            tuple(result.extracted_params.pw_values),
            tuple(result.extracted_params.pri_values),
            tuple(result.extracted_params.doa_values),
        )
        return result

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
        LOGGER.debug(
            "开始执行完整合并计划: slice_index=%d, strategy_id=%s, "
            "group_count=%d, groups=%s, start_merge_index=%d",
            plan.slice_index,
            plan.strategy_id,
            plan.group_count,
            tuple(group.cluster_indices for group in plan.groups),
            start_merge_index,
        )
        # 计划已保证组间互斥；执行层只保持计划顺序并连续分配结果序号。
        results = tuple(
            self._run_group(
                group=group,
                slice_cluster_result=slice_cluster_result,
                slice_recognition_result=slice_recognition_result,
                merge_index=start_merge_index + offset,
                strategy_id=plan.strategy_id,
            )
            for offset, group in enumerate(plan.groups)
        )
        LOGGER.debug(
            "完整合并计划执行完成: slice_index=%d, strategy_id=%s, "
            "result_count=%d, 结果来源=%s",
            plan.slice_index,
            plan.strategy_id,
            len(results),
            tuple(result.source_cluster_indices for result in results),
        )
        return results

    def _resolve_sources(
        self,
        group: MergeGroup,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> tuple[list[ClusterItem], list[ClusterRecognition]]:
        """按分组顺序解析已识别通过的来源簇和识别记录。"""
        # 映射仅用于查找，最终返回顺序仍以策略分组中的编号顺序为准。
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
        for cluster_index in group.cluster_indices:
            # 即使策略实现异常，执行层仍只接受最终有效且识别通过的簇。
            cluster = cluster_map.get(cluster_index)
            if cluster is None:
                raise ValueError(f"未找到来源簇 {cluster_index}")
            if cluster.state is not ClusterState.VALID:
                raise ValueError(f"来源簇 {cluster_index} 不是最终有效簇")
            recognition = recognition_map.get(cluster_index)
            if recognition is None:
                raise ValueError(f"来源簇 {cluster_index} 未识别通过")
            LOGGER.debug(
                "解析合并来源类别: slice_index=%d, cluster_index=%d, "
                "cluster_state=%s, dim_name=%s, point_count=%d, "
                "point_shape=%s, time_range=%s, pa_label=%d, dtoa_label=%d",
                group.slice_index,
                cluster_index,
                cluster.state,
                cluster.dim_name,
                len(cluster.points),
                cluster.points.shape,
                cluster.time_ranges,
                recognition.pa_label,
                recognition.dtoa_label,
            )
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
