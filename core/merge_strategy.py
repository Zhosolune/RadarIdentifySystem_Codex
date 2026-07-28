"""可插拔合并准则及其纯算法辅助逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

import numpy as np

from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.merge_result import MergeGroup, SliceMergePlan
from core.models.pulse_batch import COL_DOA, COL_PDOA, COL_TOA, PULSE_COLUMN_COUNT
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import circular_mean


LOGGER = logging.getLogger(__name__)


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
    doa_bin_center: float
    pdoa_bin: int
    pdoa_bin_center: float
    pdoa_mean: float | None
    pdoa_valid: bool
    pdoa_valid_count: int
    point_count: int
    pdoa_valid_ratio: float


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
        common_pri_cf_ratio [float]: 共同PRI分支的种子CF相对容差。
        common_pri_doa_tolerance [float]: 共同PRI分支的DOA容差，单位度。
        fallback_cf_ratio [float]: 无共同PRI分支的种子CF相对容差。
        pa_mismatch_doa_tolerance [float]: PA类型不一致分支的DOA容差，单位度。
        pdoa_valid_ratio_threshold [float]: PDOA有效比例严格下限。
        pdoa_mean_tolerance [float]: PDOA有效分支的均值角度容差，单位度。
        doa_fallback_tolerance [float]: PDOA无效分支的DOA均值容差，单位度。
        direction_bin_tolerance [int]: DOA/PDOA循环主格距离容差。
        doa_bin_step [float]: DOA循环分箱步长，单位度。
        doa_bin_count [int]: DOA循环分箱总数。
        pdoa_bin_step [float]: PDOA循环分箱步长，单位度。
        pdoa_bin_count [int]: PDOA循环分箱总数。

    Example:
        >>> HybridParameterMergeStrategy().strategy_id
        'hybrid_parameter_v1'
    """

    strategy_id: str = "hybrid_parameter_v1"
    pri_common_tolerance: float = 0.2
    pdoa_invalid_value: float = 655.35
    common_pri_cf_ratio: float = 0.10
    common_pri_doa_tolerance: float = 20.0
    fallback_cf_ratio: float = 0.05
    pa_mismatch_doa_tolerance: float = 2.0
    pdoa_valid_ratio_threshold: float = 0.4
    pdoa_mean_tolerance: float = 6.0
    doa_fallback_tolerance: float = 16.8
    direction_bin_tolerance: int = 2
    doa_bin_step: float = 5.625
    doa_bin_count: int = 64
    pdoa_bin_step: float = 2.0
    pdoa_bin_count: int = 180

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

        LOGGER.info(
            "开始合并判别: strategy_id=%s, slice_index=%d, "
            "聚类簇总数=%d, 识别通过记录数=%d",
            self.strategy_id,
            slice_cluster_result.slice_idx,
            len(slice_cluster_result.clusters),
            len(slice_recognition_result.valid_clusters),
        )
        LOGGER.info(
            "合并策略硬编码参数: TOA要求=严格交叠(端点相接不算), "
            "PRI共同值容差=%.6gus, 共同PRI分支CF容差=种子CF绝对值*%.2f, "
            "共同PRI分支DOA容差=%.6g°, 无共同PRI分支CF容差=种子CF绝对值*%.2f, "
            "PA不一致DOA容差=%.6g°, PDOA无效值=%.6g, "
            "PDOA有效比例要求=>%.2f, PDOA有效分支均值容差=%.6g°, "
            "PDOA无效回退DOA均值容差=%.6g°, 循环主格距离容差=%d, "
            "DOA分箱=%.6g°/%d格, PDOA分箱=%.6g°/%d格",
            self.pri_common_tolerance,
            self.common_pri_cf_ratio,
            self.common_pri_doa_tolerance,
            self.fallback_cf_ratio,
            self.pa_mismatch_doa_tolerance,
            self.pdoa_invalid_value,
            self.pdoa_valid_ratio_threshold,
            self.pdoa_mean_tolerance,
            self.doa_fallback_tolerance,
            self.direction_bin_tolerance,
            self.doa_bin_step,
            self.doa_bin_count,
            self.pdoa_bin_step,
            self.pdoa_bin_count,
        )

        # 合并判别只消费“聚类有效且识别通过”的交集，避免把无效簇带入计划。
        # 此处构造新映射和特征快照，不修改识别结果与聚类结果。
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
            if cluster.state is not ClusterState.VALID:
                LOGGER.info(
                    "类别跳过合并判别: slice_index=%d, cluster_index=%d, "
                    "原因=聚类状态不是VALID, state=%s",
                    slice_cluster_result.slice_idx,
                    cluster.cluster_idx,
                    cluster.state,
                )
                continue
            if recognition is None:
                LOGGER.info(
                    "类别跳过合并判别: slice_index=%d, cluster_index=%d, "
                    "原因=不存在识别通过记录",
                    slice_cluster_result.slice_idx,
                    cluster.cluster_idx,
                )
                continue
            feature = self._build_features(cluster, recognition)
            if feature is not None:
                features.append(feature)

        LOGGER.info(
            "合并判别有效输入准备完成: slice_index=%d, 有效类别数=%d, 类别编号=%s",
            slice_cluster_result.slice_idx,
            len(features),
            tuple(feature.cluster_index for feature in features),
        )

        # 每轮取最小未处理簇作为合并种子；组内后续CF阈值始终以该种子为基准。
        remaining = features.copy()
        groups: list[MergeGroup] = []
        while remaining:
            seed = remaining.pop(0)
            merged_group = [seed]
            LOGGER.info(
                "开始构建合并组: slice_index=%d, seed_cluster=%d, "
                "seed_cf_mean=%.12g, 待判别类别=%s",
                slice_cluster_result.slice_idx,
                seed.cluster_index,
                seed.cf_mean,
                tuple(feature.cluster_index for feature in remaining),
            )

            # 新成员可能成为其它候选的“至少一个已合并类别”，因此需要持续扫描
            # 到本轮不再扩展，才能完整实现2°等“与组内任一类满足即可”的规则。
            changed = True
            scan_round = 0
            while changed:
                changed = False
                scan_round += 1
                LOGGER.info(
                    "合并组扩展扫描: slice_index=%d, seed_cluster=%d, "
                    "scan_round=%d, 当前组=%s, 候选=%s",
                    slice_cluster_result.slice_idx,
                    seed.cluster_index,
                    scan_round,
                    tuple(feature.cluster_index for feature in merged_group),
                    tuple(feature.cluster_index for feature in remaining),
                )
                for candidate in remaining.copy():
                    if self._can_join_group(seed, merged_group, candidate):
                        merged_group.append(candidate)
                        remaining.remove(candidate)
                        changed = True
                        LOGGER.info(
                            "候选类别加入合并组: slice_index=%d, seed_cluster=%d, "
                            "candidate_cluster=%d, 更新后组=%s",
                            slice_cluster_result.slice_idx,
                            seed.cluster_index,
                            candidate.cluster_index,
                            tuple(
                                feature.cluster_index for feature in merged_group
                            ),
                        )
            # 单个簇不构成合并结果；已入组簇已从remaining移除，最终各组合并互斥。
            if len(merged_group) >= 2:
                group = MergeGroup(
                    slice_index=slice_cluster_result.slice_idx,
                    cluster_indices=tuple(
                        sorted(feature.cluster_index for feature in merged_group)
                    ),
                )
                groups.append(group)
                LOGGER.info(
                    "形成合并组: slice_index=%d, seed_cluster=%d, "
                    "cluster_indices=%s",
                    slice_cluster_result.slice_idx,
                    seed.cluster_index,
                    group.cluster_indices,
                )
            else:
                LOGGER.info(
                    "种子类别未形成合并组: slice_index=%d, seed_cluster=%d, "
                    "原因=没有任何候选通过全部判别",
                    slice_cluster_result.slice_idx,
                    seed.cluster_index,
                )
        LOGGER.info(
            "合并判别完成: strategy_id=%s, slice_index=%d, 合并组数量=%d, "
            "合并组=%s",
            self.strategy_id,
            slice_cluster_result.slice_idx,
            len(groups),
            tuple(group.cluster_indices for group in groups),
        )
        return SliceMergePlan(
            slice_index=slice_cluster_result.slice_idx,
            strategy_id=self.strategy_id,
            groups=tuple(groups),
        )

    def _build_features(
        self,
        cluster: ClusterItem,
        recognition: ClusterRecognition,
    ) -> _MergeFeatures | None:
        """从core模型构造单簇策略特征，关键数据缺失时返回空。"""
        points = cluster.points
        params = recognition.extracted_params
        if not isinstance(points, np.ndarray):
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=点云不是NumPy数组, "
                "实际类型=%s",
                cluster.cluster_idx,
                type(points).__name__,
            )
            return None
        if points.ndim != 2:
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=点云不是二维数组, "
                "shape=%s",
                cluster.cluster_idx,
                points.shape,
            )
            return None
        if points.shape[0] == 0:
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=点云没有数据行",
                cluster.cluster_idx,
            )
            return None
        if points.shape[1] < PULSE_COLUMN_COUNT:
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=点云列数不足, "
                "实际列数=%d, 最低列数=%d",
                cluster.cluster_idx,
                points.shape[1],
                PULSE_COLUMN_COUNT,
            )
            return None
        if params is None:
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=识别记录缺少提取参数",
                cluster.cluster_idx,
            )
            return None

        cf_values = self._finite_values(params.cf_values)
        doa_values = self._finite_values(params.doa_values)
        toa_values = self._finite_values(points[:, COL_TOA])
        if not cf_values:
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=CF没有有限数值, 原值=%s",
                cluster.cluster_idx,
                params.cf_values,
            )
            return None
        if not doa_values:
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=DOA没有有限数值, 原值=%s",
                cluster.cluster_idx,
                params.doa_values,
            )
            return None
        if not toa_values:
            LOGGER.info(
                "类别特征构建失败: cluster_index=%d, 原因=TOA没有有限数值",
                cluster.cluster_idx,
            )
            return None

        # PRI允许提取失败，空元组本身就是后续规则第2分支的有效输入。
        pri_values = tuple(self._finite_values(params.pri_values))
        direction_stats = self._extract_direction_stats(points)
        feature = _MergeFeatures(
            cluster_index=cluster.cluster_idx,
            cf_mean=float(np.mean(cf_values)),
            pri_values=pri_values,
            doa_mean=circular_mean(np.asarray(doa_values, dtype=np.float64)),
            pa_label=recognition.pa_label,
            toa_range=(min(toa_values), max(toa_values)),
            direction_stats=direction_stats,
        )
        LOGGER.info(
            "类别合并特征: cluster_index=%d, point_count=%d, cf_values=%s, "
            "cf_mean=%.12g, pri_values=%s, doa_values=%s, doa_mean=%.12g°, "
            "pa_label=%d, toa_range=[%.12g, %.12g], doa_main_bin=%d, "
            "doa_main_bin_center=%.12g°, pdoa_valid_count=%d/%d, "
            "pdoa_valid_ratio=%.6f, pdoa_valid=%s, pdoa_mean=%s, "
            "pdoa_main_bin=%d, pdoa_main_bin_center=%.12g°",
            feature.cluster_index,
            direction_stats.point_count,
            tuple(cf_values),
            feature.cf_mean,
            feature.pri_values,
            tuple(doa_values),
            feature.doa_mean,
            feature.pa_label,
            feature.toa_range[0],
            feature.toa_range[1],
            direction_stats.doa_bin,
            direction_stats.doa_bin_center,
            direction_stats.pdoa_valid_count,
            direction_stats.point_count,
            direction_stats.pdoa_valid_ratio,
            direction_stats.pdoa_valid,
            (
                "None"
                if direction_stats.pdoa_mean is None
                else f"{direction_stats.pdoa_mean:.12g}°"
            ),
            direction_stats.pdoa_bin,
            direction_stats.pdoa_bin_center,
        )
        return feature

    def _can_join_group(
        self,
        seed: _MergeFeatures,
        merged_group: list[_MergeFeatures],
        candidate: _MergeFeatures,
    ) -> bool:
        """判断候选类别是否与组内至少一个类别满足完整规则。"""
        # “至少一个”是组扩展规则的关键，尤其适用于PA类型不一致时的2°比较。
        LOGGER.info(
            "开始候选入组判别: seed_cluster=%d, candidate_cluster=%d, "
            "依次比较组内类别=%s",
            seed.cluster_index,
            candidate.cluster_index,
            tuple(member.cluster_index for member in merged_group),
        )
        for member in merged_group:
            if self._matches_member(seed, member, candidate):
                LOGGER.info(
                    "候选入组判别通过: seed_cluster=%d, member_cluster=%d, "
                    "candidate_cluster=%d, 规则=与组内至少一个类别匹配",
                    seed.cluster_index,
                    member.cluster_index,
                    candidate.cluster_index,
                )
                return True
        LOGGER.info(
            "候选入组判别拒绝: seed_cluster=%d, candidate_cluster=%d, "
            "原因=与当前组内所有类别均不匹配",
            seed.cluster_index,
            candidate.cluster_index,
        )
        return False

    def _matches_member(
        self,
        seed: _MergeFeatures,
        member: _MergeFeatures,
        candidate: _MergeFeatures,
    ) -> bool:
        """使用固定种子CF评估候选与一个已合并类别。"""
        LOGGER.info(
            "类别两两合并判别开始: seed_cluster=%d, member_cluster=%d, "
            "candidate_cluster=%d",
            seed.cluster_index,
            member.cluster_index,
            candidate.cluster_index,
        )
        # TOA存在严格交叠是所有后续规则成立的大前提；端点相接不视为交叠。
        overlap_start = max(member.toa_range[0], candidate.toa_range[0])
        overlap_end = min(member.toa_range[1], candidate.toa_range[1])
        if overlap_start >= overlap_end:
            LOGGER.info(
                "类别两两合并判别拒绝: member_cluster=%d, candidate_cluster=%d, "
                "分支=TOA严格交叠前置条件, member_toa=[%.12g, %.12g], "
                "candidate_toa=[%.12g, %.12g], overlap_start=%.12g, "
                "overlap_end=%.12g, 条件=overlap_start < overlap_end, 结果=False",
                member.cluster_index,
                candidate.cluster_index,
                member.toa_range[0],
                member.toa_range[1],
                candidate.toa_range[0],
                candidate.toa_range[1],
                overlap_start,
                overlap_end,
            )
            return False
        LOGGER.info(
            "TOA严格交叠前置条件通过: member_cluster=%d, candidate_cluster=%d, "
            "member_toa=[%.12g, %.12g], candidate_toa=[%.12g, %.12g], "
            "overlap=[%.12g, %.12g]",
            member.cluster_index,
            candidate.cluster_index,
            member.toa_range[0],
            member.toa_range[1],
            candidate.toa_range[0],
            candidate.toa_range[1],
            overlap_start,
            overlap_end,
        )

        # CF差距只和本组合并种子比较，不能在组扩展时改用新成员重新定基准。
        cf_difference = abs(candidate.cf_mean - seed.cf_mean)
        has_common_pri = self._has_common_pri(
            member.pri_values,
            candidate.pri_values,
        )
        LOGGER.info(
            "PRI共同值判别: member_cluster=%d, candidate_cluster=%d, "
            "member_pri=%s, candidate_pri=%s, 容差=%.6gus, has_common_pri=%s",
            member.cluster_index,
            candidate.cluster_index,
            member.pri_values,
            candidate.pri_values,
            self.pri_common_tolerance,
            has_common_pri,
        )

        # 规则1：双方PRI均可提取且存在共同值时，使用10% CF与20° DOA门限。
        if has_common_pri:
            cf_limit = abs(seed.cf_mean) * self.common_pri_cf_ratio
            doa_difference = self._circular_angle_difference(
                member.doa_mean,
                candidate.doa_mean,
            )
            cf_passed = cf_difference <= cf_limit
            doa_passed = doa_difference <= self.common_pri_doa_tolerance
            result = cf_passed and doa_passed
            LOGGER.info(
                "类别两两合并判别%s: member_cluster=%d, candidate_cluster=%d, "
                "分支=规则1_存在共同PRI, seed_cf=%.12g, candidate_cf=%.12g, "
                "cf_difference=%.12g, cf_limit=%.12g, cf_passed=%s, "
                "member_doa=%.12g°, candidate_doa=%.12g°, "
                "doa_difference=%.12g°, doa_limit=%.12g°, doa_passed=%s, "
                "result=%s",
                "通过" if result else "拒绝",
                member.cluster_index,
                candidate.cluster_index,
                seed.cf_mean,
                candidate.cf_mean,
                cf_difference,
                cf_limit,
                cf_passed,
                member.doa_mean,
                candidate.doa_mean,
                doa_difference,
                self.common_pri_doa_tolerance,
                doa_passed,
                result,
            )
            return result

        # 规则2：PRI不能全提取或没有共同值时，CF门限收紧为种子CF的5%。
        cf_limit = abs(seed.cf_mean) * self.fallback_cf_ratio
        if cf_difference > cf_limit:
            LOGGER.info(
                "类别两两合并判别拒绝: member_cluster=%d, candidate_cluster=%d, "
                "分支=规则2_无共同PRI_CF前置条件, seed_cf=%.12g, "
                "candidate_cf=%.12g, cf_difference=%.12g, cf_limit=%.12g, "
                "条件=cf_difference <= cf_limit, result=False",
                member.cluster_index,
                candidate.cluster_index,
                seed.cf_mean,
                candidate.cf_mean,
                cf_difference,
                cf_limit,
            )
            return False
        LOGGER.info(
            "规则2无共同PRI的CF前置条件通过: member_cluster=%d, "
            "candidate_cluster=%d, seed_cf=%.12g, candidate_cf=%.12g, "
            "cf_difference=%.12g, cf_limit=%.12g",
            member.cluster_index,
            candidate.cluster_index,
            seed.cf_mean,
            candidate.cf_mean,
            cf_difference,
            cf_limit,
        )

        # 规则2.1.1：PA类型不一致时，只按双方DOA均值的2°门限判定。
        # 上层_can_join_group会将候选与全部已合并类别逐一比较。
        if member.pa_label != candidate.pa_label:
            doa_difference = self._circular_angle_difference(
                member.doa_mean,
                candidate.doa_mean,
            )
            result = doa_difference <= self.pa_mismatch_doa_tolerance
            LOGGER.info(
                "类别两两合并判别%s: member_cluster=%d, candidate_cluster=%d, "
                "分支=规则2.1.1_PA类型不一致, member_pa=%d, candidate_pa=%d, "
                "member_doa=%.12g°, candidate_doa=%.12g°, "
                "doa_difference=%.12g°, doa_limit=%.12g°, result=%s",
                "通过" if result else "拒绝",
                member.cluster_index,
                candidate.cluster_index,
                member.pa_label,
                candidate.pa_label,
                member.doa_mean,
                candidate.doa_mean,
                doa_difference,
                self.pa_mismatch_doa_tolerance,
                result,
            )
            return result

        member_stats = member.direction_stats
        candidate_stats = candidate.direction_stats

        # 规则2.1.2.1：PA类型一致且双方PDOA均有效时，
        # PDOA均值差不大于6°或循环格子距离不大于2即可合并。
        if member_stats.pdoa_valid and candidate_stats.pdoa_valid:
            if member_stats.pdoa_mean is None or candidate_stats.pdoa_mean is None:
                LOGGER.info(
                    "类别两两合并判别拒绝: member_cluster=%d, "
                    "candidate_cluster=%d, 分支=规则2.1.2.1_PDOA有效, "
                    "原因=有效标记与均值数据不一致, member_pdoa_mean=%s, "
                    "candidate_pdoa_mean=%s",
                    member.cluster_index,
                    candidate.cluster_index,
                    member_stats.pdoa_mean,
                    candidate_stats.pdoa_mean,
                )
                return False
            pdoa_difference = self._circular_angle_difference(
                member_stats.pdoa_mean,
                candidate_stats.pdoa_mean,
            )
            bin_difference = self._circular_bin_difference(
                member_stats.pdoa_bin,
                candidate_stats.pdoa_bin,
                self.pdoa_bin_count,
            )
            mean_passed = pdoa_difference <= self.pdoa_mean_tolerance
            bin_passed = bin_difference <= self.direction_bin_tolerance
            result = mean_passed or bin_passed
            LOGGER.info(
                "类别两两合并判别%s: member_cluster=%d, candidate_cluster=%d, "
                "分支=规则2.1.2.1_PA一致且双方PDOA有效, pa_label=%d, "
                "member_pdoa_mean=%.12g°, candidate_pdoa_mean=%.12g°, "
                "pdoa_difference=%.12g°, mean_limit=%.12g°, mean_passed=%s, "
                "member_pdoa_bin=%d, candidate_pdoa_bin=%d, "
                "bin_difference=%d, bin_limit=%d, bin_passed=%s, "
                "组合条件=mean_passed OR bin_passed, result=%s",
                "通过" if result else "拒绝",
                member.cluster_index,
                candidate.cluster_index,
                member.pa_label,
                member_stats.pdoa_mean,
                candidate_stats.pdoa_mean,
                pdoa_difference,
                self.pdoa_mean_tolerance,
                mean_passed,
                member_stats.pdoa_bin,
                candidate_stats.pdoa_bin,
                bin_difference,
                self.direction_bin_tolerance,
                bin_passed,
                result,
            )
            return result

        # 规则2.1.2.2：至少一方PDOA无效时，回退到DOA；
        # DOA均值差不大于16.8°或循环格子距离不大于2即可合并。
        doa_difference = self._circular_angle_difference(
            member.doa_mean,
            candidate.doa_mean,
        )
        bin_difference = self._circular_bin_difference(
            member_stats.doa_bin,
            candidate_stats.doa_bin,
            self.doa_bin_count,
        )
        mean_passed = doa_difference <= self.doa_fallback_tolerance
        bin_passed = bin_difference <= self.direction_bin_tolerance
        result = mean_passed or bin_passed
        LOGGER.info(
            "类别两两合并判别%s: member_cluster=%d, candidate_cluster=%d, "
            "分支=规则2.1.2.2_PA一致且至少一方PDOA无效_回退DOA, pa_label=%d, "
            "member_pdoa_valid=%s(%.6f), candidate_pdoa_valid=%s(%.6f), "
            "member_doa=%.12g°, candidate_doa=%.12g°, "
            "doa_difference=%.12g°, mean_limit=%.12g°, mean_passed=%s, "
            "member_doa_bin=%d, candidate_doa_bin=%d, bin_difference=%d, "
            "bin_limit=%d, bin_passed=%s, "
            "组合条件=mean_passed OR bin_passed, result=%s",
            "通过" if result else "拒绝",
            member.cluster_index,
            candidate.cluster_index,
            member.pa_label,
            member_stats.pdoa_valid,
            member_stats.pdoa_valid_ratio,
            candidate_stats.pdoa_valid,
            candidate_stats.pdoa_valid_ratio,
            member.doa_mean,
            candidate.doa_mean,
            doa_difference,
            self.doa_fallback_tolerance,
            mean_passed,
            member_stats.doa_bin,
            candidate_stats.doa_bin,
            bin_difference,
            self.direction_bin_tolerance,
            bin_passed,
            result,
        )
        return result

    def _extract_direction_stats(self, points: np.ndarray) -> _DirectionStats:
        """从六列点云计算DOA/PDOA主格及PDOA有效性。"""
        # DOA按5.625°划分64个循环格，保留出现次数最多的主格。
        doa_values = np.asarray(points[:, COL_DOA], dtype=np.float64)
        doa_values = doa_values[np.isfinite(doa_values)]
        doa_bin, doa_bin_center = self._dominant_direction(
            doa_values,
            self.doa_bin_step,
            self.doa_bin_count,
        )

        # PDOA占位值655.35不参与均值、主格和有效比例计算。
        raw_pdoa = np.asarray(points[:, COL_PDOA], dtype=np.float64)
        valid_pdoa = raw_pdoa[
            np.isfinite(raw_pdoa) & (raw_pdoa != self.pdoa_invalid_value)
        ]
        pdoa_bin, pdoa_bin_center = self._dominant_direction(
            valid_pdoa,
            self.pdoa_bin_step,
            self.pdoa_bin_count,
        )
        # 延续辅助算法的有效性定义：存在主格且有效PDOA占总点数比例严格大于40%。
        valid_ratio = len(valid_pdoa) / len(points)
        return _DirectionStats(
            doa_bin=doa_bin,
            doa_bin_center=doa_bin_center,
            pdoa_bin=pdoa_bin,
            pdoa_bin_center=pdoa_bin_center,
            pdoa_mean=circular_mean(valid_pdoa) if len(valid_pdoa) else None,
            pdoa_valid=(
                pdoa_bin >= 0
                and valid_ratio > self.pdoa_valid_ratio_threshold
            ),
            pdoa_valid_count=len(valid_pdoa),
            point_count=len(points),
            pdoa_valid_ratio=valid_ratio,
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
        # 先归一化到[0, 360)，再映射到循环格，保证负角度也能正确分箱。
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
        # 任一侧为空即属于“PRI不能全都提取”；非空时逐项寻找容差内共同值。
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
