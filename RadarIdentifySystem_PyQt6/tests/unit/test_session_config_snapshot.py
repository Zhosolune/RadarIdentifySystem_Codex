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
    snapshot.recognition.min_confidence = 0.72

    restored = SessionConfigSnapshot.from_dict(snapshot.to_dict())

    assert restored.clustering.eps_cf == 3.5
    assert restored.recognition.min_confidence == 0.72
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
        }
    )

    assert restored.clustering.eps_cf == 4.0
    assert restored.clustering.min_pts_cf == ClusteringConfigSnapshot.default().min_pts_cf
    assert restored.recognition.max_candidates == RecognitionConfigSnapshot.default().max_candidates


def test_session_config_snapshot_falls_back_invalid_schema_version() -> None:
    """非法 schema_version 应回退为当前结构版本。"""
    for raw_version in (None, "invalid"):
        restored = SessionConfigSnapshot.from_dict({"schema_version": raw_version})

        assert restored.schema_version == SessionConfigSnapshot.SCHEMA_VERSION


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
