"""运行期 session 注册表测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.app_config import appConfig, qconfig
from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore
from runtime.session_config_factory import create_session_config_from_global
from runtime.session_registry import SessionRegistry


def _make_session(session_id: str, source_name: str) -> ProcessingSession:
    """创建带稳定 id 的测试 session。"""
    return ProcessingSession(
        session_id=session_id,
        source_path=f"E:/data/{source_name}",
        source_type="excel",
    )


def test_register_sets_active_and_persists_active_id(tmp_path: Path) -> None:
    """注册 session 后应可查询、自动激活并持久化 active id。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    session = _make_session("session-a", "a.xlsx")
    old_last_opened_at = session.last_opened_at

    registered = registry.register(session)

    assert registered is session
    assert registry.get("session-a") is session
    assert registry.active_session is session
    assert session.last_opened_at >= old_last_opened_at
    assert store.load_index().active_session_id == "session-a"
    assert store.load_session("session-a").session_id == "session-a"


def test_restore_uses_store_sessions_and_restores_active_id(
    tmp_path: Path,
) -> None:
    """恢复时应复用 store 的批量恢复结果和索引 active id。"""
    store = SessionStore(tmp_path)
    first = _make_session("session-a", "a.xlsx")
    second = _make_session("session-b", "b.xlsx")
    first.raw_batch = object()
    first.cluster_result = object()
    store.upsert_session(first)
    store.upsert_session(second)
    store.set_active_session_id(second.session_id)

    registry = SessionRegistry(store)
    restored_sessions = registry.restore()

    assert [session.session_id for session in restored_sessions] == [
        "session-a",
        "session-b",
    ]
    assert registry.active_session is registry.get("session-b")
    restored_first = registry.get("session-a")
    assert restored_first is not None
    assert restored_first.restored_from_store is True
    assert restored_first.raw_batch is None
    assert restored_first.slice_result is None
    assert restored_first.cluster_result is None
    assert restored_first.recognition_result is None
    assert restored_first.merge_result is None


def test_activate_missing_session_raises_key_error(tmp_path: Path) -> None:
    """激活不存在的 session id 时应抛出 KeyError。"""
    registry = SessionRegistry(SessionStore(tmp_path))

    with pytest.raises(KeyError):
        registry.activate("missing")


def test_close_active_switches_to_last_remaining_and_syncs_index(
    tmp_path: Path,
) -> None:
    """关闭 active session 后应切换到剩余列表的最后一个并同步索引。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"))
    second = registry.register(_make_session("session-b", "b.xlsx"))

    registry.close(second.session_id)

    assert registry.active_session is first
    assert registry.all_sessions() == [first]
    assert store.load_index().active_session_id == first.session_id
    with pytest.raises(FileNotFoundError):
        store.load_session(second.session_id)


def test_close_non_active_keeps_active_session(tmp_path: Path) -> None:
    """关闭非 active session 时不应改变当前 active session。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"))
    second = registry.register(_make_session("session-b", "b.xlsx"))

    registry.close(first.session_id)

    assert registry.active_session is second
    assert store.load_index().active_session_id == second.session_id


def test_close_without_deleting_persisted_session_keeps_disk_files(
    tmp_path: Path,
) -> None:
    """delete_persisted=False 时应只关闭内存 session，不删除磁盘内容。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    session = registry.register(_make_session("session-a", "a.xlsx"))

    registry.close(session.session_id, delete_persisted=False)

    assert registry.get(session.session_id) is None
    assert registry.active_session is None
    assert store.load_index().active_session_id is None
    assert store.load_session(session.session_id).session_id == session.session_id


def test_create_session_config_from_global_returns_independent_snapshot() -> None:
    """全局配置工厂应返回与当前 qconfig 等值但互不引用的快照。"""
    original_eps_cf = qconfig.get(appConfig.algorithmEpsilonCF)
    changed_eps_cf = (
        original_eps_cf + 1.0
        if original_eps_cf < 49.0
        else original_eps_cf - 1.0
    )
    qconfig.set(appConfig.algorithmEpsilonCF, changed_eps_cf, save=False)
    try:
        snapshot = create_session_config_from_global()

        assert snapshot.clustering.eps_cf == qconfig.get(appConfig.algorithmEpsilonCF)
        assert snapshot.clustering.min_pts_cf == qconfig.get(appConfig.algorithmMinPtsCF)
        assert snapshot.clustering.eps_pw == qconfig.get(appConfig.algorithmEpsilonPW)
        assert snapshot.clustering.min_pts_pw == qconfig.get(appConfig.algorithmMinPtsPW)
        assert snapshot.clustering.eps_doa == qconfig.get(appConfig.algorithmEpsilonDOA)
        assert snapshot.clustering.min_pts_doa == qconfig.get(appConfig.algorithmMinPtsDOA)
        assert snapshot.clustering.clip_threshold_doa == qconfig.get(
            appConfig.algorithmClipThresholdDOA
        )
        assert snapshot.recognition.tolerance == qconfig.get(appConfig.recognizeTolerance)
        assert snapshot.recognition.min_confidence == qconfig.get(
            appConfig.recognizeMinConfidence
        )
        assert snapshot.recognition.max_candidates == qconfig.get(
            appConfig.recognizeMaxCandidates
        )
        assert snapshot.extract.step == qconfig.get(appConfig.extractStep)
        assert snapshot.extract.smooth_window == qconfig.get(appConfig.extractSmoothWindow)
        assert snapshot.extract.outlier_threshold == qconfig.get(
            appConfig.extractOutlierThreshold
        )
        assert snapshot.merge.time_decay == qconfig.get(appConfig.mergeTimeDecay)
        assert snapshot.merge.sim_threshold == qconfig.get(appConfig.mergeSimThreshold)
        assert snapshot.merge.max_extrapolate == qconfig.get(appConfig.mergeMaxExtrapolate)
        assert snapshot.merge.pri_equal_doa_tolerance == qconfig.get(
            appConfig.mergePriEqualDoaTolerance
        )
        assert snapshot.business.auto_recognize_next_slice == qconfig.get(
            appConfig.autoRecognizeNextSlice
        )
        assert snapshot.business.export_dir_path == qconfig.get(appConfig.exportDirPath)
        assert snapshot.business.auto_export == qconfig.get(appConfig.autoExport)

        snapshot.clustering.eps_cf = original_eps_cf + 2.0

        assert qconfig.get(appConfig.algorithmEpsilonCF) == changed_eps_cf
    finally:
        qconfig.set(appConfig.algorithmEpsilonCF, original_eps_cf, save=False)
