"""运行期 session 注册表测试。"""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pytest

from app.app_config import appConfig, qconfig
from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
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


def _attach_import_cache_payload(
    session: ProcessingSession,
    raw_data: np.ndarray,
    preprocess_data: np.ndarray,
    band: str,
) -> None:
    """为测试 session 填充可写入导入缓存的最小运行态数据。"""
    dashboard_info = ExcelDashboardInfo(
        total_pulses=len(raw_data),
        removed_pulses=0,
        amplitude_dropped_pulses=0,
        duration=0.0,
        band=band,
        estimated_slice_count=0,
    )
    session.raw_batch = PulseBatch(
        data=raw_data,
        source_path=session.source_path,
        source_type=session.source_type,
        total_pulses=len(raw_data),
    )
    session.preprocess_result = PreprocessResult(
        data=preprocess_data,
        total_pulses=len(preprocess_data),
        filtered_pulses=0,
        toa_flip_count=0,
        time_range=0.0,
        estimated_slice_count=0,
        band=band,
        dashboard_info=dashboard_info,
    )
    session.dashboard_info = dashboard_info

def test_register_sets_runtime_active_without_persisting_active_id(tmp_path: Path) -> None:
    """注册 session 后应可查询、自动激活且不持久化 active id。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    session = _make_session("session-a", "a.xlsx")
    old_last_opened_at = session.last_opened_at

    registered = registry.register(session)

    assert registered is session
    assert registry.get("session-a") is session
    assert registry.active_session is session
    assert session.last_opened_at >= old_last_opened_at
    index_payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert "active_session_id" not in index_payload
    persisted_session = store.load_session("session-a")
    assert persisted_session.session_id == "session-a"
    assert persisted_session.last_opened_at == session.last_opened_at


def test_persist_session_writes_current_config_without_changing_active(
    tmp_path: Path,
) -> None:
    """显式持久化 session 时应写入当前子配置且不改变 active id。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    first_session = _make_session("session-a", "a.xlsx")
    second_session = _make_session("session-b", "b.xlsx")
    registry.register(first_session)
    registry.register(second_session)

    first_session.config_snapshot.business.auto_recognize_next_slice = False
    persisted = registry.persist_session("session-a")

    assert persisted is first_session
    assert registry.active_session_id == "session-b"
    index_payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert "active_session_id" not in index_payload
    assert (
        store.load_session("session-a")
        .config_snapshot
        .business
        .auto_recognize_next_slice
        is False
    )


def test_persist_session_overwrites_existing_import_cache(
    tmp_path: Path,
) -> None:
    """显式持久化已存在 session 时应覆盖旧的导入缓存。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    session = _make_session("session-cache", "cache.xlsx")
    old_raw_data = np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]])
    old_preprocess_data = np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]])
    _attach_import_cache_payload(
        session,
        raw_data=old_raw_data,
        preprocess_data=old_preprocess_data,
        band="旧缓存",
    )
    registry.register(session)

    new_raw_data = np.array([[2000.0, 4.0, 80.0, 60.0, 60.0, 10.0]])
    new_preprocess_data = np.array([[2100.0, 4.0, 80.0, 60.0, 60.0, 10.0]])
    _attach_import_cache_payload(
        session,
        raw_data=new_raw_data,
        preprocess_data=new_preprocess_data,
        band="新缓存",
    )
    registry.persist_session(session.session_id)

    restored = store.load_session(session.session_id)
    assert store.load_import_cache(restored) is True
    assert restored.raw_batch is not None
    assert restored.preprocess_result is not None
    assert restored.dashboard_info is not None
    assert restored.dashboard_info.band == "新缓存"
    np.testing.assert_array_equal(restored.raw_batch.data, new_raw_data)
    np.testing.assert_array_equal(
        restored.preprocess_result.data,
        new_preprocess_data,
    )

def test_persist_session_rejects_unknown_session(tmp_path: Path) -> None:
    """显式持久化未知 session 时应抛出 KeyError。"""
    registry = SessionRegistry(SessionStore(tmp_path))

    with pytest.raises(KeyError, match="missing"):
        registry.persist_session("missing")


@pytest.mark.parametrize(
    "failing_method",
    ["upsert_session"],
)
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
    assert all(
        entry.session_id != session.session_id
        for entry in store.load_index().sessions
    )
    with pytest.raises(FileNotFoundError):
        store.load_session(session.session_id)


def test_register_same_session_id_keeps_single_ordered_entry(tmp_path: Path) -> None:
    """重复注册相同 session id 时应按 upsert 语义保持单个内存条目。"""
    registry = SessionRegistry(SessionStore(tmp_path))
    first = _make_session("session-a", "a.xlsx")
    second = _make_session("session-a", "b.xlsx")

    registry.register(first)
    registry.register(second)

    assert registry.all_sessions() == [second]
    assert registry.active_session is second


def test_restore_uses_store_sessions_without_restoring_active_id(
    tmp_path: Path,
) -> None:
    """恢复时应复用 store 的批量恢复结果，但不恢复历史 active id。"""
    store = SessionStore(tmp_path)
    first = _make_session("session-a", "a.xlsx")
    second = _make_session("session-b", "b.xlsx")
    first.raw_batch = object()
    first.cluster_result = object()
    store.upsert_session(first)
    store.upsert_session(second)
    index_payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    index_payload["active_session_id"] = second.session_id
    (tmp_path / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    registry = SessionRegistry(store)
    restored_sessions = registry.restore()

    assert [session.session_id for session in restored_sessions] == [
        "session-a",
        "session-b",
    ]
    assert registry.active_session is None
    assert registry.active_session_id is None
    restored_first = registry.get("session-a")
    assert restored_first is not None
    assert restored_first.restored_from_store is True
    assert restored_first.raw_batch is None
    assert restored_first.slice_result is None
    assert restored_first.cluster_result is None
    assert restored_first.recognition_result is None
    assert restored_first.merge_result is None


def test_restore_ignores_persisted_active_id_when_active_session_is_broken(
    tmp_path: Path,
) -> None:
    """active session 被跳过恢复时不应再处理历史 active id 状态。"""
    store = SessionStore(tmp_path)
    valid_session = _make_session("session-a", "a.xlsx")
    broken_session = _make_session("session-b", "b.xlsx")
    store.upsert_session(valid_session)
    store.upsert_session(broken_session)
    index_payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    index_payload["active_session_id"] = broken_session.session_id
    (tmp_path / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / broken_session.session_id / "config.json").unlink()

    registry = SessionRegistry(store)
    restored_sessions = registry.restore()

    assert [session.session_id for session in restored_sessions] == ["session-a"]
    assert registry.active_session is None
    assert registry.active_session_id is None


def test_activate_missing_session_raises_key_error(tmp_path: Path) -> None:
    """激活不存在的 session id 时应抛出 KeyError。"""
    registry = SessionRegistry(SessionStore(tmp_path))

    with pytest.raises(KeyError):
        registry.activate("missing")


@pytest.mark.parametrize("failing_method", ["upsert_session"])
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


def test_close_active_switches_to_last_remaining_runtime_only(
    tmp_path: Path,
) -> None:
    """关闭 active session 后应在运行期切换到剩余列表的最后一个。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    first = registry.register(_make_session("session-a", "a.xlsx"))
    second = registry.register(_make_session("session-b", "b.xlsx"))

    registry.close(second.session_id)

    assert registry.active_session is first
    assert registry.all_sessions() == [first]
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
        assert snapshot.recognition.greedy_strategy == qconfig.get(
            appConfig.recognizeGreedyStrategy
        )
        assert snapshot.recognition.pa_confidence_threshold == qconfig.get(
            appConfig.recognizePaConfidenceThreshold
        )
        assert snapshot.recognition.pa_confidence_weight == qconfig.get(
            appConfig.recognizePaConfidenceWeight
        )
        assert snapshot.recognition.dtoa_confidence_threshold == qconfig.get(
            appConfig.recognizeDtoaConfidenceThreshold
        )
        assert snapshot.recognition.dtoa_confidence_weight == qconfig.get(
            appConfig.recognizeDtoaConfidenceWeight
        )
        assert snapshot.recognition.joint_confidence_threshold == qconfig.get(
            appConfig.recognizeJointConfidenceThreshold
        )
        assert snapshot.extract.eps_cf == qconfig.get(appConfig.extractEpsilonCF)
        assert snapshot.extract.min_pts_cf == qconfig.get(appConfig.extractMinPtsCF)
        assert snapshot.extract.threshold_ratio_cf == qconfig.get(
            appConfig.extractThresholdRatioCF
        )
        assert snapshot.extract.eps_pw == qconfig.get(appConfig.extractEpsilonPW)
        assert snapshot.extract.min_pts_pw == qconfig.get(appConfig.extractMinPtsPW)
        assert snapshot.extract.threshold_ratio_pw == qconfig.get(
            appConfig.extractThresholdRatioPW
        )
        assert snapshot.extract.eps_pri == qconfig.get(appConfig.extractEpsilonPRI)
        assert snapshot.extract.min_pts_pri == qconfig.get(appConfig.extractMinPtsPRI)
        assert snapshot.extract.threshold_ratio_pri == qconfig.get(
            appConfig.extractThresholdRatioPRI
        )
        assert snapshot.extract.filter_threshold_pri == qconfig.get(
            appConfig.extractFilterThresholdPRI
        )
        assert snapshot.extract.harmonic_tolerance_pri == qconfig.get(
            appConfig.extractHarmonicTolerancePRI
        )
        assert snapshot.merge.placeholder_value == qconfig.get(
            appConfig.mergePlaceholderValue
        )
        assert snapshot.business.auto_recognize_next_slice == qconfig.get(
            appConfig.autoRecognizeNextSlice
        )
        assert snapshot.business.export_dir_path == qconfig.get(appConfig.exportDirPath)
        assert snapshot.business.auto_export == qconfig.get(appConfig.autoExport)
        assert snapshot.plot.only_show_identified == qconfig.get(
            appConfig.plotOnlyShowIdentified
        )
        assert snapshot.plot.scale_mode == qconfig.get(appConfig.plotScaleMode)

        snapshot.clustering.eps_cf = original_eps_cf + 2.0

        assert qconfig.get(appConfig.algorithmEpsilonCF) == changed_eps_cf
    finally:
        qconfig.set(appConfig.algorithmEpsilonCF, original_eps_cf, save=False)


def test_update_remark_persists_and_refreshes_memory(tmp_path: Path) -> None:
    """更新备注时应同步内存 session 与持久化元数据。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    session = registry.register(_make_session("session-a", "a.xlsx"))

    updated = registry.update_remark(session.session_id, "  新备注  ")

    assert updated is session
    assert session.remark == "新备注"
    assert store.load_session(session.session_id).remark == "新备注"


def test_update_remark_rejects_unknown_session(tmp_path: Path) -> None:
    """更新不存在的 session 备注时应抛出 KeyError。"""
    registry = SessionRegistry(SessionStore(tmp_path))

    with pytest.raises(KeyError, match="missing"):
        registry.update_remark("missing", "备注")


def test_update_metadata_persists_name_and_remark_together(tmp_path: Path) -> None:
    """更新 session 元数据时应一次同步名称、备注和持久化内容。"""
    store = SessionStore(tmp_path)
    registry = SessionRegistry(store)
    session = registry.register(_make_session("session-a", "a.xlsx"))

    updated = registry.update_metadata(session.session_id, "???", " ??? ")

    assert updated is session
    assert session.display_name == "???"
    assert session.remark == "???"
    restored = store.load_session(session.session_id)
    assert restored.display_name == "???"
    assert restored.remark == "???"
