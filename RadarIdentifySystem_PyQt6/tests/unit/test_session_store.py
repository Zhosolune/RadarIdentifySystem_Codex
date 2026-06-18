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


def test_session_store_persists_active_session_id(tmp_path: Path) -> None:
    """设置 active session id 时应写入索引文件。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)

    store.set_active_session_id(session.session_id)

    reloaded_store = SessionStore(tmp_path)
    assert reloaded_store.load_index().active_session_id == session.session_id


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
