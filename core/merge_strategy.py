"""可插拔合并准则及其纯算法辅助逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.merge_result import MergeGroup, SliceMergePlan
from core.models.pulse_batch import COL_DOA, COL_PDOA, COL_TOA, PULSE_COLUMN_COUNT
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import circular_mean


class MergeStrategy(Protocol):
    """可插拔合并准则协议。

    Attributes:
        strategy_id [str]: 准则的稳定唯一标识。
    """

    strategy_id: str

    def build_plan(
        self,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """生成单切片完整合并计划。

        Args:
            slice_cluster_result [SliceClusterResult]: 单切片聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 同切片识别结果。

        Returns:
            SliceMergePlan: 包含全部互斥合并分组的切片计划。

        Raises:
            ValueError: 聚类结果与识别结果的切片索引不一致时抛出。
        """
        ...


@dataclass(frozen=True, slots=True)
class _DirectionStats:
    """单簇DOA/PDOA主方位统计。"""

    doa_bin: int
    pdoa_bin: int
    pdoa_mean: float | None
    pdoa_valid: bool


@dataclass(frozen=True, slots=True)
class _MergeFeatures:
    """默认合并准则所需的单簇不可变特征快照。"""

    cluster_index: int
    cf_mean: float
    pri_values: tuple[float, ...]
    doa_mean: float
    pa_label: int
    toa_range: tuple[float, float]
    direction_stats: _DirectionStats


class HybridParameterMergeStrategy:
    """按TOA、PRI、CF、PA和方位信息生成完整合并计划。

    策略以最小未处理簇编号作为固定种子，种子CF在组扩展过程中不变化。候选类别
    只要与已合并组内至少一个类别满足完整规则即可加入，并持续扫描直至不能扩展。

    Attributes:
        strategy_id [str]: 供runtime选择和审计的稳定准则标识。
        pri_common_tolerance [float]: PRI共同值容差，单位us。
        pdoa_invalid_value [float]: PDOA无效占位值。

    Example:
        >>> HybridParameterMergeStrategy().strategy_id
        'hybrid_parameter_v1'
    """

    strategy_id: str = "hybrid_parameter_v1"
    pri_common_tolerance: float = 0.2
    pdoa_invalid_value: float = 655.35

    def build_plan(
        self,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """按默认准则生成单切片完整合并计划。

        Args:
            slice_cluster_result [SliceClusterResult]: 单切片聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 同切片识别结果。

        Returns:
            SliceMergePlan: 分组和簇编号均按确定性顺序排列的计划。

        Raises:
            ValueError: 两类结果不属于同一切片时抛出。
        """
        if slice_cluster_result.slice_idx != slice_recognition_result.slice_index:
            raise ValueError("聚类结果与识别结果的切片索引不一致")

        # 只为识别通过且最终状态有效的簇建立特征，识别结果本身保持只读。
        recognition_map = {
            recognition.cluster_index: recognition
            for recognition in slice_recognition_result.valid_clusters
            if recognition.is_valid
        }
        features: list[_MergeFeatures] = []
        for cluster in sorted(
            slice_cluster_result.clusters,
            key=lambda item: item.cluster_idx,
        ):
            recognition = recognition_map.get(cluster.cluster_idx)
            if cluster.state is not ClusterState.VALID or recognition is None:
                continue
            feature = self._build_features(cluster, recognition)
            if feature is not None:
                features.append(feature)

        # 固定种子贪婪扩展形成互斥分组，每个来源簇最多进入一个合并结果。
        remaining = features.copy()
        groups: list[MergeGroup] = []
        while remaining:
            seed = remaining.pop(0)
            merged_group = [seed]
            changed = True
            while changed:
                changed = False
                for candidate in remaining.copy():
                    if self._can_join_group(seed, merged_group, candidate):
                        merged_group.append(candidate)
                        remaining.remove(candidate)
                        changed = True
            if len(merged_group) >= 2:
                groups.append(
                    MergeGroup(
                        slice_index=slice_cluster_result.slice_idx,
                        cluster_indices=tuple(
                            sorted(feature.cluster_index for feature in merged_group)
                        ),
                    )
                )
        return SliceMergePlan(
            slice_index=slice_cluster_result.slice_idx,
            strategy_id=self.strategy_id,
            groups=tuple(groups),
        )

    def build_targets(
        self,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> tuple[MergeGroup, ...]:
        """兼容旧调用方并返回完整计划中的互斥分组。

        Args:
            slice_cluster_result [SliceClusterResult]: 单切片聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 同切片识别结果。

        Returns:
            tuple[MergeGroup, ...]: 完整计划中的互斥合并分组。

        Raises:
            ValueError: 两类结果不属于同一切片时抛出。
        """
        return self.build_plan(slice_cluster_result, slice_recognition_result).groups

    def _build_features(
        self,
        cluster: ClusterItem,
        recognition: ClusterRecognition,
    ) -> _MergeFeatures | None:
        """从core模型构造单簇策略特征，关键数据缺失时返回空。"""
        points = cluster.points
        params = recognition.extracted_params
        if (
            not isinstance(points, np.ndarray)
            or points.ndim != 2
            or points.shape[0] == 0
            or points.shape[1] < PULSE_COLUMN_COUNT
            or params is None
        ):
            return None

        cf_values = self._finite_values(params.cf_values)
        doa_values = self._finite_values(params.doa_values)
        toa_values = self._finite_values(points[:, COL_TOA])
        if not cf_values or not doa_values or not toa_values:
            return None

        pri_values = tuple(self._finite_values(params.pri_values))
        return _MergeFeatures(
            cluster_index=cluster.cluster_idx,
            cf_mean=float(np.mean(cf_values)),
            pri_values=pri_values,
            doa_mean=circular_mean(np.asarray(doa_values, dtype=np.float64)),
            pa_label=recognition.pa_label,
            toa_range=(min(toa_values), max(toa_values)),
            direction_stats=self._extract_direction_stats(points),
        )

    def _can_join_group(
        self,
        seed: _MergeFeatures,
        merged_group: list[_MergeFeatures],
        candidate: _MergeFeatures,
    ) -> bool:
        """判断候选类别是否与组内至少一个类别满足完整规则。"""
        return any(
            self._matches_member(seed, member, candidate)
            for member in merged_group
        )

    def _matches_member(
        self,
        seed: _MergeFeatures,
        member: _MergeFeatures,
        candidate: _MergeFeatures,
    ) -> bool:
        """使用固定种子CF评估候选与一个已合并类别。"""
        if max(member.toa_range[0], candidate.toa_range[0]) >= min(
            member.toa_range[1],
            candidate.toa_range[1],
        ):
            return False

        cf_difference = abs(candidate.cf_mean - seed.cf_mean)
        has_common_pri = self._has_common_pri(
            member.pri_values,
            candidate.pri_values,
        )
        if has_common_pri:
            return (
                cf_difference <= abs(seed.cf_mean) * 0.10
                and self._circular_angle_difference(
                    member.doa_mean,
                    candidate.doa_mean,
                )
                <= 20.0
            )

        if cf_difference > abs(seed.cf_mean) * 0.05:
            return False

        if member.pa_label != candidate.pa_label:
            return (
                self._circular_angle_difference(
                    member.doa_mean,
                    candidate.doa_mean,
                )
                <= 2.0
            )

        member_stats = member.direction_stats
        candidate_stats = candidate.direction_stats
        if member_stats.pdoa_valid and candidate_stats.pdoa_valid:
            if member_stats.pdoa_mean is None or candidate_stats.pdoa_mean is None:
                return False
            return (
                self._circular_angle_difference(
                    member_stats.pdoa_mean,
                    candidate_stats.pdoa_mean,
                )
                <= 6.0
                or self._circular_bin_difference(
                    member_stats.pdoa_bin,
                    candidate_stats.pdoa_bin,
                    180,
                )
                <= 2
            )

        return (
            self._circular_angle_difference(
                member.doa_mean,
                candidate.doa_mean,
            )
            <= 16.8
            or self._circular_bin_difference(
                member_stats.doa_bin,
                candidate_stats.doa_bin,
                64,
            )
            <= 2
        )

    def _extract_direction_stats(self, points: np.ndarray) -> _DirectionStats:
        """从六列点云计算DOA/PDOA主格及PDOA有效性。"""
        doa_values = np.asarray(points[:, COL_DOA], dtype=np.float64)
        doa_values = doa_values[np.isfinite(doa_values)]
        doa_bin, _ = self._dominant_direction(doa_values, 5.625, 64)

        raw_pdoa = np.asarray(points[:, COL_PDOA], dtype=np.float64)
        valid_pdoa = raw_pdoa[
            np.isfinite(raw_pdoa) & (raw_pdoa != self.pdoa_invalid_value)
        ]
        pdoa_bin, _ = self._dominant_direction(valid_pdoa, 2.0, 180)
        valid_ratio = len(valid_pdoa) / len(points)
        return _DirectionStats(
            doa_bin=doa_bin,
            pdoa_bin=pdoa_bin,
            pdoa_mean=circular_mean(valid_pdoa) if len(valid_pdoa) else None,
            pdoa_valid=pdoa_bin >= 0 and valid_ratio > 0.4,
        )

    @staticmethod
    def _dominant_direction(
        angle_values: np.ndarray,
        step_degree: float,
        bin_count: int,
    ) -> tuple[int, float]:
        """计算角度序列的主格子索引和格子中心角。"""
        if angle_values.size == 0:
            return -1, 0.0
        normalized = np.mod(angle_values, 360.0)
        bin_indices = np.floor(normalized / step_degree).astype(int)
        bin_indices = np.clip(bin_indices, 0, bin_count - 1)
        counts = np.bincount(bin_indices, minlength=bin_count)
        dominant_bin = int(np.argmax(counts))
        dominant_angle = ((dominant_bin + 0.5) * step_degree) % 360.0
        return dominant_bin, float(dominant_angle)

    def _has_common_pri(
        self,
        first_values: tuple[float, ...],
        second_values: tuple[float, ...],
    ) -> bool:
        """判断双方PRI是否均可提取且存在容差内共同值。"""
        return bool(first_values) and bool(second_values) and any(
            abs(first - second) <= self.pri_common_tolerance
            for first in first_values
            for second in second_values
        )

    @staticmethod
    def _finite_values(values: object) -> list[float]:
        """将可迭代数值过滤为有限浮点列表。"""
        try:
            array = np.asarray(values, dtype=np.float64).reshape(-1)
        except (TypeError, ValueError):
            return []
        return [float(value) for value in array[np.isfinite(array)]]

    @staticmethod
    def _circular_angle_difference(first: float, second: float) -> float:
        """计算两个角度在360°圆周上的最短差值。"""
        difference = abs((float(first) - float(second)) % 360.0)
        return min(difference, 360.0 - difference)

    @staticmethod
    def _circular_bin_difference(first: int, second: int, bin_count: int) -> int:
        """计算两个格子索引在循环分箱上的最短距离。"""
        if first < 0 or second < 0:
            return bin_count
        difference = abs(first - second)
        return min(difference, bin_count - difference)


DefaultMergeStrategy = HybridParameterMergeStrategy
