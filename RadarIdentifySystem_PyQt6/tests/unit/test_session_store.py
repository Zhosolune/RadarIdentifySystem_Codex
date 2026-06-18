"""Session 持久化适配层测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore


def test_session_store_writes_index_session_and_config(tmp_path: Path) -> None:
    """保存 session 时应写入索引、元数据和配置文件。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    session.config_snapshot.clustering.eps_cf = 8.0
    session.model_selection.pa_model_path = "E:/models/pa.pt"

    store.upsert_session(session)

    session_dir = tmp_path / session.session_id
    assert (tmp_path / "index.json").exists()
    assert (session_dir / "session.json").exists()
    assert (session_dir / "config.json").exists()

    restored = store.load_session(session.session_id)
    assert restored.source_path == "E:/data/a.xlsx"
    assert restored.display_name == "a.xlsx"
    assert restored.config_snapshot.clustering.eps_cf == 8.0
    assert restored.model_selection.pa_model_path == "E:/models/pa.pt"
    assert restored.raw_batch is None
    assert restored.slice_result is None
    assert restored.cluster_result is None
    assert restored.recognition_result is None
    assert restored.merge_result is None
    assert restored.restored_from_store is True


def test_session_store_delete_removes_session_dir(tmp_path: Path) -> None:
    """删除 session 时应删除目录并更新索引。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)

    store.delete_session(session.session_id)

    assert not (tmp_path / session.session_id).exists()
    assert store.load_index().sessions == []


def test_session_store_delete_clears_active_session_id(tmp_path: Path) -> None:
    """删除活动 session 时应同步清空 active session id。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)
    store.set_active_session_id(session.session_id)

    store.delete_session(session.session_id)

    assert store.load_index().active_session_id is None


def test_session_store_persists_active_session_id(tmp_path: Path) -> None:
    """设置 active session id 时应写入索引文件。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)

    store.set_active_session_id(session.session_id)

    reloaded_store = SessionStore(tmp_path)
    assert reloaded_store.load_index().active_session_id == session.session_id


@pytest.mark.parametrize("session_id", ["", "..", "a/b"])
def test_session_store_rejects_invalid_active_session_id(
    tmp_path: Path,
    session_id: str,
) -> None:
    """设置 active session id 时应拒绝非法 session id。"""
    store = SessionStore(tmp_path)

    with pytest.raises(ValueError):
        store.set_active_session_id(session_id)


def test_session_store_loads_sessions_in_index_order(tmp_path: Path) -> None:
    """加载 session 列表时应保持索引中的顺序。"""
    store = SessionStore(tmp_path)
    first = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    second = ProcessingSession(source_path="E:/data/b.xlsx", source_type="excel")
    store.upsert_session(first)
    store.upsert_session(second)

    index = store.load_index()
    index.sessions = list(reversed(index.sessions))
    store.save_index(index)

    assert [entry.session_id for entry in store.list_sessions()] == [
        second.session_id,
        first.session_id,
    ]
    assert [session.session_id for session in store.load_all_sessions()] == [
        second.session_id,
        first.session_id,
    ]


def test_session_store_rejects_empty_session_id(tmp_path: Path) -> None:
    """空 session id 不应解析为持久化根目录。"""
    store = SessionStore(tmp_path)

    with pytest.raises(ValueError):
        store.delete_session("")

    assert tmp_path.exists()


@pytest.mark.parametrize(
    "session_id",
    ["..", ".", "a/b", "a\\b", "a/../b"],
)
def test_session_store_rejects_unsafe_session_dir_names(
    tmp_path: Path,
    session_id: str,
) -> None:
    """session id 必须是单段安全目录名。"""
    store = SessionStore(tmp_path)

    with pytest.raises(ValueError):
        store.delete_session(session_id)


def test_session_store_rejects_absolute_session_dir_name(tmp_path: Path) -> None:
    """session id 不允许是绝对路径。"""
    store = SessionStore(tmp_path)

    with pytest.raises(ValueError):
        store.delete_session(str(tmp_path / "x"))


def test_session_store_load_index_returns_empty_for_broken_json(
    tmp_path: Path,
) -> None:
    """索引 JSON 损坏时应回退为空索引。"""
    (tmp_path / "index.json").write_text("{broken", encoding="utf-8")
    store = SessionStore(tmp_path)

    index = store.load_index()

    assert index.active_session_id is None
    assert index.sessions == []


def test_session_store_load_index_returns_empty_for_invalid_fields(
    tmp_path: Path,
) -> None:
    """索引字段非法时应回退为空索引。"""
    (tmp_path / "index.json").write_text(
        '{"schema_version": "bad", "sessions": []}',
        encoding="utf-8",
    )
    store = SessionStore(tmp_path)

    index = store.load_index()

    assert index.active_session_id is None
    assert index.sessions == []


def test_session_store_load_index_returns_empty_for_invalid_active_id(
    tmp_path: Path,
) -> None:
    """索引 active session id 非法时应回退为空索引。"""
    (tmp_path / "index.json").write_text(
        '{"schema_version": 1, "active_session_id": "", "sessions": []}',
        encoding="utf-8",
    )
    store = SessionStore(tmp_path)

    index = store.load_index()

    assert index.active_session_id is None
    assert index.sessions == []


def test_session_store_load_all_sessions_skips_broken_entries(
    tmp_path: Path,
) -> None:
    """批量恢复时应跳过损坏条目并继续恢复有效 session。"""
    store = SessionStore(tmp_path)
    valid_session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    missing_config = ProcessingSession(source_path="E:/data/b.xlsx", source_type="excel")
    broken_metadata = ProcessingSession(source_path="E:/data/c.xlsx", source_type="excel")
    store.upsert_session(valid_session)
    store.upsert_session(missing_config)
    store.upsert_session(broken_metadata)
    (tmp_path / missing_config.session_id / "config.json").unlink()
    (tmp_path / broken_metadata.session_id / "session.json").write_text(
        "{broken",
        encoding="utf-8",
    )

    restored_sessions = store.load_all_sessions()

    assert [session.session_id for session in restored_sessions] == [
        valid_session.session_id,
    ]
