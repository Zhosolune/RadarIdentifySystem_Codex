"""已识别类的合并准则与显式合并流程。

本模块通过 ``MergeStrategy`` 隔离可替换的合并准则，并由 ``MergePipeline`` 负责
执行已经确定的 ``MergeTarget``。默认准则只读取 core 数据模型，不依赖 runtime、UI
或推理服务。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.merge_result import MergedClusterResult
from core.models.pulse_batch import COL_DOA, COL_PDOA, COL_TOA, PULSE_COLUMN_COUNT
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import circular_mean, extract_cluster_params


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


class MergeStrategy(Protocol):
    """可插拔合并准则协议。

    新增合并准则时实现该协议，并由 runtime 注入具体实例即可切换算法，无需修改
    合并执行流程。

    Attributes:
        strategy_id [str]: 准则的稳定唯一标识，用于运行时切换和结果审计。

    Example:
        >>> strategy: MergeStrategy = HybridParameterMergeStrategy()
        >>> strategy.strategy_id
        'hybrid_parameter_v1'
    """

    strategy_id: str

    def build_targets(
        self,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> tuple[MergeTarget, ...]:
        """生成单个切片内的合并目标。

        Args:
            slice_cluster_result [SliceClusterResult]: 单切片聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 同切片识别结果。

        Returns:
            tuple[MergeTarget, ...]: 按确定性顺序生成的合并目标；无可合并类别时为空。

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
    """按TOA、PRI、CF、PA和方位信息生成合并目标。

    策略以最小未处理簇编号作为固定种子，种子CF在组扩展过程中不变化。候选类别
    只要与已合并组内至少一个类别满足完整规则即可加入，并持续扫描直至不能扩展。

    Attributes:
        strategy_id [str]: 供runtime选择和审计的稳定准则标识。
        pri_common_tolerance [float]: PRI共同值容差，单位 us。
        pdoa_invalid_value [float]: PDOA无效占位值。

    Example:
        >>> HybridParameterMergeStrategy().strategy_id
        'hybrid_parameter_v1'
    """

    strategy_id: str = "hybrid_parameter_v1"
    pri_common_tolerance: float = 0.2
    pdoa_invalid_value: float = 655.35

    def build_targets(
        self,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> tuple[MergeTarget, ...]:
        """按默认准则生成单切片合并目标。

        Args:
            slice_cluster_result [SliceClusterResult]: 单切片聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 同切片识别结果。

        Returns:
            tuple[MergeTarget, ...]: 每项至少包含两个来源簇，簇和分组均按编号排序。

        Raises:
            ValueError: 两类结果不属于同一切片时抛出。

        Example:
            输入模型包含NumPy点云，完整构造示例参见单元测试。
        """
        if slice_cluster_result.slice_idx != slice_recognition_result.slice_index:
            raise ValueError("聚类结果与识别结果的切片索引不一致")

        # 只为识别通过且最终状态有效的簇建立特征，避免无效类别进入合并候选集。
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

        # 采用固定种子、确定性贪婪扩展；已归组类别不会出现在后续合并目标中。
        remaining = features.copy()
        targets: list[MergeTarget] = []
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
                targets.append(
                    MergeTarget(
                        slice_index=slice_cluster_result.slice_idx,
                        cluster_indices=tuple(
                            sorted(feature.cluster_index for feature in merged_group)
                        ),
                    )
                )
        return tuple(targets)

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

        # CF和DOA使用识别阶段已经提取的代表值，保留当前参数提取口径。
        cf_values = self._finite_values(params.cf_values)
        doa_values = self._finite_values(params.doa_values)
        toa_values = self._finite_values(points[:, COL_TOA])
        if not cf_values or not doa_values or not toa_values:
            return None

        pri_values = tuple(self._finite_values(params.pri_values))
        direction_stats = self._extract_direction_stats(points)
        return _MergeFeatures(
            cluster_index=cluster.cluster_idx,
            cf_mean=float(np.mean(cf_values)),
            pri_values=pri_values,
            doa_mean=circular_mean(np.asarray(doa_values, dtype=np.float64)),
            pa_label=recognition.pa_label,
            toa_range=(min(toa_values), max(toa_values)),
            direction_stats=direction_stats,
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
        # TOA严格交叠是所有后续分支的大前提，端点相接不视为交叠。
        if max(member.toa_range[0], candidate.toa_range[0]) >= min(
            member.toa_range[1], candidate.toa_range[1]
        ):
            return False

        cf_difference = abs(candidate.cf_mean - seed.cf_mean)
        has_common_pri = self._has_common_pri(
            member.pri_values,
            candidate.pri_values,
        )
        if has_common_pri:
            # PRI均可提取且有共同值时，允许种子CF的10%并比较20°循环DOA差。
            return (
                cf_difference <= abs(seed.cf_mean) * 0.10
                and self._circular_angle_difference(
                    member.doa_mean,
                    candidate.doa_mean,
                )
                <= 20.0
            )

        # PRI不全可提取或没有共同值时，CF门限收紧为固定种子CF的5%。
        if cf_difference > abs(seed.cf_mean) * 0.05:
            return False

        if member.pa_label != candidate.pa_label:
            # PA类型不一致时，只要候选与组内任一成员满足2°即可加入。
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
            if (
                member_stats.pdoa_mean is None
                or candidate_stats.pdoa_mean is None
            ):
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

        # PDOA不是双方均有效时，回退到DOA均值或64格主方位邻近条件。
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

        # PDOA先过滤非数值和业务无效占位值，再计算主格与循环均值。
        raw_pdoa = np.asarray(points[:, COL_PDOA], dtype=np.float64)
        valid_pdoa = raw_pdoa[
            np.isfinite(raw_pdoa) & (raw_pdoa != self.pdoa_invalid_value)
        ]
        pdoa_bin, _ = self._dominant_direction(valid_pdoa, 2.0, 180)
        valid_ratio = len(valid_pdoa) / len(points)
        pdoa_valid = pdoa_bin >= 0 and valid_ratio > 0.4
        pdoa_mean = circular_mean(valid_pdoa) if len(valid_pdoa) else None
        return _DirectionStats(
            doa_bin=doa_bin,
            pdoa_bin=pdoa_bin,
            pdoa_mean=pdoa_mean,
            pdoa_valid=pdoa_valid,
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


# 保留语义清晰的默认入口，runtime无需绑定具体业务准则类名。
DefaultMergeStrategy = HybridParameterMergeStrategy


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
        strategy_id: str = "explicit",
    ) -> MergedClusterResult:
        """执行一个明确目标的合并流程。

        Args:
            target [MergeTarget]: 已由上层确定的来源簇集合。
            slice_cluster_result [SliceClusterResult]: 目标切片的聚类点云结果。
            slice_recognition_result [SliceRecognitionResult]: 目标切片的原识别结果。
            merge_index [int]: 当前切片内从 1 开始的合并结果序号。
            strategy_id [str]: 生成目标的准则标识，默认表示人工显式目标。

        Returns:
            MergedClusterResult: 点云拼接、来源识别保留和参数重提取后的结果。

        Raises:
            ValueError: 切片不匹配、序号非法、来源不存在或来源未识别通过时抛出。
        """
        if merge_index < 1:
            raise ValueError("merge_index 必须大于等于 1")
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
        # 合并后只重新执行参数提取，不调用 PA/DTOA 推理服务。
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
