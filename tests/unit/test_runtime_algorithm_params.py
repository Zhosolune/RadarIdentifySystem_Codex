"""Session 快照到运行时算法参数的统一转换测试。"""

from __future__ import annotations

from dataclasses import fields

from core.models.algorithm_params import ClusteringParams
from core.models.session_config import (
    ClusteringConfigSnapshot,
    ExtractConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigSnapshot,
)
from runtime.algorithm_params import (
    IdentifyPipelineParams,
    build_extract_params,
    build_identify_pipeline_params,
)


def _different_value(value: object) -> object:
    """根据默认值类型生成确定的非默认测试值。"""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 7
    if isinstance(value, float):
        return value + 1.25
    raise TypeError(f"暂不支持的配置字段类型: {type(value).__name__}")


def _replace_all_config_values(
    config: (
        ClusteringConfigSnapshot
        | RecognitionConfigSnapshot
        | ExtractConfigSnapshot
    ),
) -> dict[str, object]:
    """替换配置对象全部字段并返回字段期望值。"""
    expected: dict[str, object] = {}
    for field in fields(config):
        value = _different_value(getattr(config, field.name))
        setattr(config, field.name, value)
        expected[field.name] = value
    return expected


def test_build_identify_pipeline_params_maps_every_snapshot_field() -> None:
    """统一转换器应显式保留三个配置分组中的每个字段。"""
    snapshot = SessionConfigSnapshot.default()
    expected_groups = {
        "clustering": _replace_all_config_values(snapshot.clustering),
        "recognition": _replace_all_config_values(snapshot.recognition),
        "extract": _replace_all_config_values(snapshot.extract),
    }

    params = build_identify_pipeline_params(snapshot)

    assert isinstance(params, IdentifyPipelineParams)
    for group_name, expected in expected_groups.items():
        actual_group = getattr(params, group_name)
        for field_name, expected_value in expected.items():
            assert getattr(actual_group, field_name) == expected_value
    # 该字段当前是固定算法默认值，并非 Session 可配置项。
    assert (
        params.clustering.min_cluster_size
        == ClusteringParams().min_cluster_size
    )


def test_build_identify_pipeline_params_keeps_sessions_independent() -> None:
    """不同 Session 快照应生成互不共享且不受后续修改影响的参数。"""
    interactive_snapshot = SessionConfigSnapshot.default()
    full_speed_snapshot = SessionConfigSnapshot.default()
    interactive_snapshot.clustering.eps_cf = 3.25
    interactive_snapshot.recognition.greedy_strategy = False
    full_speed_snapshot.clustering.eps_cf = 8.5
    full_speed_snapshot.extract.eps_pri = 0.75

    interactive_params = build_identify_pipeline_params(
        interactive_snapshot
    )
    full_speed_params = build_identify_pipeline_params(full_speed_snapshot)
    interactive_snapshot.clustering.eps_cf = 99.0
    full_speed_snapshot.extract.eps_pri = 9.0

    assert interactive_params is not full_speed_params
    assert interactive_params.clustering is not full_speed_params.clustering
    assert interactive_params.recognition is not full_speed_params.recognition
    assert interactive_params.extract is not full_speed_params.extract
    assert interactive_params.clustering.eps_cf == 3.25
    assert interactive_params.recognition.greedy_strategy is False
    assert full_speed_params.clustering.eps_cf == 8.5
    assert full_speed_params.extract.eps_pri == 0.75


def test_build_extract_params_returns_a_new_frozen_value_object() -> None:
    """合并重提取应复用转换规则但获得独立提取参数对象。"""
    snapshot = SessionConfigSnapshot.default()
    snapshot.extract.eps_cf = 4.5

    first = build_extract_params(snapshot.extract)
    second = build_extract_params(snapshot.extract)
    snapshot.extract.eps_cf = 7.5

    assert first is not second
    assert first.eps_cf == 4.5
    assert second.eps_cf == 4.5
