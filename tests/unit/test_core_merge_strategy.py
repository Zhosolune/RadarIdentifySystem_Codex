"""默认可插拔合并准则单元测试。"""

from __future__ import annotations

import numpy as np
import pytest

from core.merge import DefaultMergeStrategy, MergeStrategy
from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.extraction_result import ExtractedClusterParams
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult


def _points(
    doa_values: list[float],
    pdoa_values: list[float],
    toa_values: list[float],
) -> np.ndarray:
    """构造遵循六列契约的测试点云。"""
    row_count = len(toa_values)
    assert len(doa_values) == row_count
    assert len(pdoa_values) == row_count
    return np.column_stack(
        (
            np.full(row_count, 100.0),
            np.full(row_count, 1.0),
            np.full(row_count, 20.0),
            np.asarray(doa_values, dtype=np.float64),
            np.asarray(pdoa_values, dtype=np.float64),
            np.asarray(toa_values, dtype=np.float64),
        )
    )


def _cluster(cluster_index: int, points: np.ndarray) -> ClusterItem:
    """构造已识别通过状态的测试簇。"""
    return ClusterItem(
        cluster_idx=cluster_index,
        dim_name="CF",
        points=points,
        points_indices=np.arange(len(points), dtype=np.int64),
        slice_idx=0,
        time_ranges=(0.0, 9999.0),
        state=ClusterState.VALID,
        valid_cluster_idx=cluster_index - 1,
    )


def _recognition(
    cluster_index: int,
    *,
    cf_values: list[float],
    pri_values: list[float],
    doa_values: list[float],
    pa_label: int,
) -> ClusterRecognition:
    """构造带合并特征的有效识别结果。"""
    return ClusterRecognition(
        slice_index=0,
        dim_name="CF",
        cluster_index=cluster_index,
        valid_cluster_index=cluster_index - 1,
        pa_label=pa_label,
        pa_confidence=0.9,
        dtoa_label=0,
        dtoa_confidence=0.9,
        is_valid=True,
        extracted_params=ExtractedClusterParams(
            cf_values=cf_values,
            pri_values=pri_values,
            doa_values=doa_values,
        ),
    )


def _results(
    specs: list[
        tuple[
            np.ndarray,
            list[float],
            list[float],
            list[float],
            int,
        ]
    ],
) -> tuple[SliceClusterResult, SliceRecognitionResult]:
    """按给定点云和提取特征构造同切片输入。"""
    clusters: list[ClusterItem] = []
    recognitions: list[ClusterRecognition] = []
    for cluster_index, (points, cf, pri, doa, pa_label) in enumerate(specs, start=1):
        clusters.append(_cluster(cluster_index, points))
        recognitions.append(
            _recognition(
                cluster_index,
                cf_values=cf,
                pri_values=pri,
                doa_values=doa,
                pa_label=pa_label,
            )
        )
    return (
        SliceClusterResult(slice_idx=0, clusters=clusters),
        SliceRecognitionResult(slice_index=0, valid_clusters=recognitions),
    )


def _default_points(
    *,
    doa: float = 0.0,
    pdoa: float = 0.0,
    toa_start: float = 0.0,
) -> np.ndarray:
    """构造五点、PDOA完全有效且TOA跨度为40的默认点云。"""
    return _points(
        [doa] * 5,
        [pdoa] * 5,
        [toa_start + offset for offset in (0.0, 10.0, 20.0, 30.0, 40.0)],
    )


def test_strategy_protocol_supports_replaceable_implementation() -> None:
    """默认实现应满足只依赖build_targets的可替换策略协议。"""
    strategy: MergeStrategy = DefaultMergeStrategy()

    assert strategy.strategy_id == "hybrid_parameter_v1"
    assert callable(strategy.build_targets)


def test_common_pri_branch_includes_all_threshold_boundaries() -> None:
    """共同PRI分支应包含0.2us、种子CF 10%和20°DOA边界。"""
    cluster_result, recognition_result = _results(
        [
            (_default_points(doa=359.0), [100.0], [10.0], [359.0], 1),
            (_default_points(doa=19.0, toa_start=5.0), [110.0], [10.2], [19.0], 2),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert [target.cluster_indices for target in targets] == [(1, 2)]


@pytest.mark.parametrize(
    ("candidate_cf", "candidate_doa"),
    [
        (110.01, 0.0),
        (100.0, 20.01),
    ],
)
def test_common_pri_branch_rejects_values_beyond_limits(
    candidate_cf: float,
    candidate_doa: float,
) -> None:
    """共同PRI分支任一阈值超限时均不得合并。"""
    cluster_result, recognition_result = _results(
        [
            (_default_points(), [100.0], [10.0], [0.0], 1),
            (
                _default_points(doa=candidate_doa),
                [candidate_cf],
                [10.0],
                [candidate_doa],
                2,
            ),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert targets == ()


def test_toa_endpoint_contact_is_not_an_intersection() -> None:
    """TOA只有端点接触时不得进入任何合并分支。"""
    cluster_result, recognition_result = _results(
        [
            (_default_points(), [100.0], [10.0], [0.0], 1),
            (_default_points(toa_start=40.0), [100.0], [10.0], [0.0], 1),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert targets == ()


def test_pa_mismatch_uses_any_merged_member_for_two_degree_rule() -> None:
    """PA不一致候选只需与组内任一成员的DOA均值相差不超过2°。"""
    cluster_result, recognition_result = _results(
        [
            (_default_points(doa=0.0, pdoa=100.0), [100.0], [], [0.0], 1),
            (_default_points(doa=30.0, pdoa=100.0), [102.0], [], [30.0], 1),
            (_default_points(doa=31.0, pdoa=200.0), [104.0], [], [31.0], 2),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert [target.cluster_indices for target in targets] == [(1, 2, 3)]


def test_greedy_expansion_rescans_candidates_after_group_growth() -> None:
    """候选初次失败后，应在新成员加入时重新扫描并允许传递扩展。"""
    cluster_result, recognition_result = _results(
        [
            (_default_points(doa=0.0, pdoa=100.0), [100.0], [], [0.0], 1),
            (_default_points(doa=11.0, pdoa=200.0), [102.0], [], [11.0], 2),
            (_default_points(doa=10.0, pdoa=100.0), [104.0], [], [10.0], 1),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert [target.cluster_indices for target in targets] == [(1, 2, 3)]


def test_pdoa_validity_requires_strictly_more_than_forty_percent() -> None:
    """PDOA有效率40%应回退DOA分支，60%才允许PDOA分支合并。"""
    seed_points = _points(
        [0.0] * 5,
        [0.0] * 5,
        [0.0, 10.0, 20.0, 30.0, 40.0],
    )
    forty_percent_points = _points(
        [40.0] * 5,
        [2.0, 2.0, 655.35, 655.35, 655.35],
        [5.0, 15.0, 25.0, 35.0, 45.0],
    )
    sixty_percent_points = _points(
        [40.0] * 5,
        [2.0, 2.0, 2.0, 655.35, 655.35],
        [5.0, 15.0, 25.0, 35.0, 45.0],
    )

    forty_inputs = _results(
        [
            (seed_points, [100.0], [], [0.0], 1),
            (forty_percent_points, [100.0], [], [40.0], 1),
        ]
    )
    sixty_inputs = _results(
        [
            (seed_points, [100.0], [], [0.0], 1),
            (sixty_percent_points, [100.0], [], [40.0], 1),
        ]
    )

    strategy = DefaultMergeStrategy()
    assert strategy.build_targets(*forty_inputs) == ()
    assert [
        target.cluster_indices for target in strategy.build_targets(*sixty_inputs)
    ] == [(1, 2)]


def test_pdoa_branch_accepts_circular_grid_distance() -> None:
    """PDOA均值差超限时，循环主格距离不超过2仍应合并。"""
    seed_points = _points(
        [0.0] * 5,
        [0.0, 0.0, 0.0, 100.0, 100.0],
        [0.0, 10.0, 20.0, 30.0, 40.0],
    )
    candidate_points = _points(
        [40.0] * 5,
        [4.1, 4.1, 4.1, 260.0, 260.0],
        [5.0, 15.0, 25.0, 35.0, 45.0],
    )
    cluster_result, recognition_result = _results(
        [
            (seed_points, [100.0], [], [0.0], 1),
            (candidate_points, [100.0], [], [40.0], 1),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert [target.cluster_indices for target in targets] == [(1, 2)]


def test_pdoa_branch_rejects_when_angle_and_grid_both_exceed_limits() -> None:
    """PDOA均值差与主格距离同时超限时不得合并。"""
    cluster_result, recognition_result = _results(
        [
            (_default_points(pdoa=0.0), [100.0], [], [0.0], 1),
            (_default_points(doa=40.0, pdoa=20.0), [100.0], [], [40.0], 1),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert targets == ()


def test_invalid_pdoa_branch_accepts_circular_doa_grid_distance() -> None:
    """PDOA无效且DOA均值差超限时，循环DOA主格邻近仍应合并。"""
    seed_points = _points(
        [359.0] * 5,
        [655.35] * 5,
        [0.0, 10.0, 20.0, 30.0, 40.0],
    )
    candidate_points = _points(
        [1.0] * 5,
        [655.35] * 5,
        [5.0, 15.0, 25.0, 35.0, 45.0],
    )
    cluster_result, recognition_result = _results(
        [
            (seed_points, [100.0], [], [100.0], 1),
            (candidate_points, [100.0], [], [150.0], 1),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert [target.cluster_indices for target in targets] == [(1, 2)]


def test_seed_cf_remains_fixed_during_group_expansion() -> None:
    """后加入成员不得替代种子作为5% CF门限基准。"""
    cluster_result, recognition_result = _results(
        [
            (_default_points(), [100.0], [], [0.0], 1),
            (_default_points(), [104.0], [], [0.0], 1),
            (_default_points(), [108.0], [], [0.0], 1),
        ]
    )

    targets = DefaultMergeStrategy().build_targets(
        cluster_result,
        recognition_result,
    )

    assert [target.cluster_indices for target in targets] == [(1, 2)]


def test_strategy_rejects_mismatched_slice_results() -> None:
    """策略应拒绝不同切片的聚类结果与识别结果。"""
    cluster_result, recognition_result = _results(
        [(_default_points(), [100.0], [], [0.0], 1)]
    )
    wrong_recognition_result = SliceRecognitionResult(
        slice_index=1,
        valid_clusters=recognition_result.valid_clusters,
    )

    with pytest.raises(ValueError, match="切片索引不一致"):
        DefaultMergeStrategy().build_targets(
            cluster_result,
            wrong_recognition_result,
        )
