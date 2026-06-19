"""运行期 session 注册表测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.app_config import appConfig, qconfig
from core.models.processing_session import ProcessingSession
from infra.session_store import SessionIndex, SessionStore
from runtime.session_config_factory import create_session_config_from_global
from runtime.session_registry import SessionRegistry


class _FailingSessionStore(SessionStore):
    """测试用持久化失败注入存储。"""

    def __init__(self, root_dir: Path, failing_method: str) -> None:
        """初始化失败注入存储。"""
        super().__init__(root_dir)
        self.failing_method = failing_method
        self.deleted_session_ids: list[str] = []
        self._is_deleting_session = False

    def upsert_session(self, session: ProcessingSession) -> None:
        """按需在 upsert 时抛出异常。"""
        if self.failing_method == "upsert_session":
            raise OSError("注入 upsert_session 失败")
        super().upsert_session(session)

    def delete_session(self, session_id: str) -> None:
        """按需在 delete 时抛出异常。"""
        if self.failing_method == "delete_session":
            raise OSError("注入 delete_session 失败")
        self._is_deleting_session = True
        try:
            super().delete_session(session_id)
            self.deleted_session_ids.append(session_id)
        finally:
            self._is_deleting_session = False

    def set_active_session_id(self, session_id: str | None) -> None:
        """按需在设置 active id 时抛出异常。"""
        if self.failing_method == "set_active_session_id":
            raise OSError("注入 set_active_session_id 失败")
        if (
            self.failing_method == "set_active_session_id_after_delete"
            and self.deleted_session_ids
        ):
            raise OSError("注入 delete 后 set_active_session_id 失败")
        super().set_active_session_id(session_id)

    def save_index(self, index: SessionIndex) -> None:
        """按需在删除 session 后保存索引时抛出异常。"""
        if (
            self.failing_method == "save_index_after_delete"
            and self._is_deleting_session
        ):
            raise OSError("注入 delete 后 save_index 失败")
        super().save_index(index)


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


@pytest.mark.parametrize("failing_method", ["upsert_session", "set_active_session_id"])
def test_register_persistence_failure_keeps_memory_state(
    tmp_path: Path,
    failing_method: str,
) -> None:
    """注册持久化失败时不应提交内存 session、active id 或打开时间。"""
    store = _FailingSessionStore(tmp_path, failing_method)
    registry = SessionRegistry(store)
    session = _make_session("session-a", "a.xlsx")
    old_last_opened_at = session.last_opened_at

    with pytest.raises(OSError):
        registry.register(session)

    assert registry.get(session.session_id) is None
    assert registry.active_session_id is None
    assert registry.active_session is None
    assert session.last_opened_at == old_last_opened_at
    assert store.load_index().active_session_id != session.session_id
    assert all(
        entry.session_id != session.session_id
        for entry in store.load_index().sessions
    )
    with pytest.raises(FileNotFoundError):
        store.load_session(session.session_id)


def test_register_existing_session_rolls_back_disk_when_active_write_fails(
    tmp_path: Path,
) -> None:
    """重复注册已持久化 session 失败时应恢复原磁盘元数据。"""
    store = _FailingSessionStore(tmp_path, "")
    registry = SessionRegistry(store)
    original = registry.register(_make_session("session-a", "a.xlsx"))
    original_disk = store.load_session(original.session_id)
    replacement = _make_session("session-a", "b.xlsx")
    store.failing_method = "set_active_session_id"

    with pytest.raises(OSError):
        registry.register(replacement)

    restored_disk = store.load_session(original.session_id)
    assert registry.get(original.session_id) is original
    assert restored_disk.source_path == original_disk.source_path
    assert restored_disk.display_name == original_disk.display_name
    assert restored_disk.last_opened_at == original_disk.last_opened_at


def test_register_same_session_id_keeps_single_ordered_entry(tmp_path: Path) -> None:
    """重复注册相同 session id 时应按 upsert 语义保持单个内存条目。"""
    registry = SessionRegistry(SessionStore(tmp_path))
    first = _make_session("session-a", "a.xlsx")
    second = _make_session("session-a", "b.xlsx")

    registry.register(first)
    registry.register(second)

    assert registry.all_sessions() == [second]
    assert registry.active_session is second


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


def test_restore_clears_persisted_active_id_when_active_session_is_broken(
    tmp_path: Path,
) -> None:
    """active session 被跳过恢复时应同步清理持久化 active id。"""
    store = SessionStore(tmp_path)
    valid_session = _make_session("session-a", "a.xlsx")
    broken_session = _make_session("session-b", "b.xlsx")
    store.upsert_session(valid_session)
    store.upsert_session(broken_session)
    store.set_active_session_id(broken_session.session_id)
    (tmp_path / broken_session.session_id / "config.json").unlink()

    registry = SessionRegistry(store)
    restored_sessions = registry.restore()

    assert [session.session_id for session in restored_sessions] == ["session-a"]
    assert registry.active_session is None
    assert store.load_index().active_session_id is None


def test_activate_missing_session_raises_key_error(tmp_path: Path) -> None:
    """激活不存在的 session id 时应抛出 KeyError。"""
    registry = SessionRegistry(SessionStore(tmp_path))

    with pytest.raises(KeyError):
        registry.activate("missing")


@pytest.mark.parametrize("failing_method", ["upsert_session", "set_active_session_id"])
def test_activate_persistence_failure_keeps_memory_state(
    tmp_path: Path,
    failing_method: str,
) -> None:
    """激活持久化失败时不应改变 active id 或 session 打开时间。"""
    store = _FailingSessionStore(tmp_path, failing_method)
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"), persist=False)
    second = registry.register(_make_session("session-b", "b.xlsx"), persist=False)
    registry.active_session_id = first.session_id
    old_last_opened_at = second.last_opened_at

    with pytest.raises(OSError):
        registry.activate(second.session_id)

    assert registry.active_session is first
    assert registry.active_session_id == first.session_id
    assert second.last_opened_at == old_last_opened_at


def test_activate_active_write_failure_restores_disk_last_opened_at(
    tmp_path: Path,
) -> None:
    """激活 active id 写入失败时应恢复目标 session 的磁盘打开时间。"""
    store = _FailingSessionStore(tmp_path, "")
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"))
    second = registry.register(_make_session("session-b", "b.xlsx"))
    registry.activate(first.session_id)
    old_disk_last_opened_at = store.load_session(second.session_id).last_opened_at
    store.failing_method = "set_active_session_id"

    with pytest.raises(OSError):
        registry.activate(second.session_id)

    assert registry.active_session is first
    assert second.last_opened_at == old_disk_last_opened_at
    assert store.load_session(second.session_id).last_opened_at == old_disk_last_opened_at
    assert store.load_index().active_session_id == first.session_id


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


@pytest.mark.parametrize("failing_method", ["delete_session"])
def test_close_persistence_failure_keeps_memory_state(
    tmp_path: Path,
    failing_method: str,
) -> None:
    """关闭持久化失败时不应移除内存 session 或切换 active id。"""
    store = _FailingSessionStore(tmp_path, failing_method)
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"), persist=False)
    second = registry.register(_make_session("session-b", "b.xlsx"), persist=False)

    with pytest.raises(OSError):
        registry.close(second.session_id)

    assert registry.all_sessions() == [first, second]
    assert registry.active_session is second
    assert registry.active_session_id == second.session_id


def test_close_active_reconciles_memory_when_active_id_update_fails_after_delete(
    tmp_path: Path,
) -> None:
    """active session 已从磁盘删除后应同步内存状态再抛出 active id 写入异常。"""
    store = _FailingSessionStore(tmp_path, "set_active_session_id_after_delete")
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"))
    second = registry.register(_make_session("session-b", "b.xlsx"))

    with pytest.raises(OSError):
        registry.close(second.session_id)

    assert registry.get(second.session_id) is None
    assert registry.active_session_id != second.session_id
    assert registry.active_session is None
    assert first.session_id in {session.session_id for session in registry.all_sessions()}
    with pytest.raises(FileNotFoundError):
        store.load_session(second.session_id)


def test_close_reconciles_memory_when_delete_removes_dir_but_index_save_fails(
    tmp_path: Path,
) -> None:
    """删除目录成功但索引保存失败时应按磁盘事实移除内存 session。"""
    store = _FailingSessionStore(tmp_path, "")
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"))
    second = registry.register(_make_session("session-b", "b.xlsx"))
    store.failing_method = "save_index_after_delete"

    with pytest.raises(OSError):
        registry.close(second.session_id)

    assert registry.get(second.session_id) is None
    assert registry.active_session_id != second.session_id
    assert first.session_id in {session.session_id for session in registry.all_sessions()}
    with pytest.raises(FileNotFoundError):
        store.load_session(second.session_id)


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
