"""Session 子配置快照测试。"""

from __future__ import annotations

import core.models as core_models
import core.models.session_config as session_config_module
from core.models.session_config import (
    ClusteringConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigSnapshot,
)


def test_session_config_snapshot_round_trips_dict() -> None:
    """配置快照应能稳定序列化和反序列化。"""
    snapshot = SessionConfigSnapshot.default()
    snapshot.clustering.eps_cf = 3.5
    snapshot.recognition.greedy_strategy = False
    snapshot.recognition.pa_confidence_threshold = 0.72
    snapshot.recognition.dtoa_confidence_weight = 0.35
    snapshot.merge.placeholder_value = 0.36
    snapshot.plot.only_show_identified = "ALL"
    snapshot.plot.scale_mode = "STRETCH_BILINEAR"

    restored = SessionConfigSnapshot.from_dict(snapshot.to_dict())

    assert restored.clustering.eps_cf == 3.5
    assert restored.recognition.greedy_strategy is False
    assert restored.recognition.pa_confidence_threshold == 0.72
    assert restored.recognition.dtoa_confidence_weight == 0.35
    assert restored.merge.placeholder_value == 0.36
    assert restored.plot.only_show_identified == "ALL"
    assert restored.plot.scale_mode == "STRETCH_BILINEAR"
    assert restored.schema_version == SessionConfigSnapshot.SCHEMA_VERSION


def test_session_config_snapshot_fills_missing_fields() -> None:
    """旧配置缺字段时应使用当前默认值补齐。"""
    restored = SessionConfigSnapshot.from_dict(
        {
            "schema_version": 1,
            "clustering": {"eps_cf": 4.0},
            "recognition": {},
            "extract": {},
            "merge": {},
            "business": {},
            "plot": {},
        }
    )

    assert restored.clustering.eps_cf == 4.0
    assert restored.clustering.min_pts_cf == ClusteringConfigSnapshot.default().min_pts_cf
    assert (
        restored.recognition.joint_confidence_threshold
        == RecognitionConfigSnapshot.default().joint_confidence_threshold
    )
    assert restored.merge.placeholder_value == 0.0
    assert restored.plot.only_show_identified == "IDENTIFIED_ONLY"
    assert restored.plot.scale_mode == "STRETCH"
    assert restored.schema_version == SessionConfigSnapshot.SCHEMA_VERSION


def test_session_config_snapshot_discards_legacy_merge_placeholders() -> None:
    """旧版四个无意义合并字段应迁移为当前单一占位字段。"""
    restored = SessionConfigSnapshot.from_dict(
        {
            "schema_version": 1,
            "merge": {
                "time_decay": 0.7,
                "sim_threshold": 0.6,
                "max_extrapolate": 8,
                "pri_equal_doa_tolerance": 15.0,
            },
        }
    )

    assert restored.schema_version == SessionConfigSnapshot.SCHEMA_VERSION
    assert restored.merge.placeholder_value == 0.0
    assert not hasattr(restored.merge, "time_decay")


def test_session_config_snapshot_falls_back_invalid_schema_version() -> None:
    """非法 schema_version 应回退为当前结构版本。"""
    for raw_version in (None, "invalid"):
        restored = SessionConfigSnapshot.from_dict({"schema_version": raw_version})

    assert restored.schema_version == SessionConfigSnapshot.SCHEMA_VERSION


def test_session_config_snapshot_discards_legacy_recognition_placeholders() -> None:
    """旧识别占位字段应丢弃并迁移为当前识别参数默认值。"""
    restored = SessionConfigSnapshot.from_dict(
        {
            "schema_version": 2,
            "recognition": {
                "tolerance": 0.25,
                "min_confidence": 0.7,
                "max_candidates": 8,
            },
        }
    )

    assert restored.schema_version == SessionConfigSnapshot.SCHEMA_VERSION
    assert restored.recognition == RecognitionConfigSnapshot.default()
    assert not hasattr(restored.recognition, "tolerance")
    assert not hasattr(restored.recognition, "min_confidence")
    assert not hasattr(restored.recognition, "max_candidates")


def test_session_config_snapshot_instances_are_independent() -> None:
    """两个 session 的子配置修改不能互相影响。"""
    first = SessionConfigSnapshot.default()
    second = SessionConfigSnapshot.default()

    first.clustering.eps_pw = 0.9

    assert second.clustering.eps_pw != first.clustering.eps_pw


def test_core_session_config_exports_only_pure_snapshots() -> None:
    """core 配置模块不应导出 UI 设置适配项。"""
    assert not hasattr(session_config_module, "SessionConfigItem")
    assert not hasattr(core_models, "SessionConfigItem")
