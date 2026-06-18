"""Session 子配置快照测试。"""

from __future__ import annotations

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


def test_session_config_snapshot_instances_are_independent() -> None:
    """两个 session 的子配置修改不能互相影响。"""
    first = SessionConfigSnapshot.default()
    second = SessionConfigSnapshot.default()

    first.clustering.eps_pw = 0.9

    assert second.clustering.eps_pw != first.clustering.eps_pw
