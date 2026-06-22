"""Session 持久化适配层测试。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from core.models.processing_session import ProcessingStage
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
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


def test_session_store_round_trips_import_cache(tmp_path: Path) -> None:
    """session 导入缓存应能恢复到导入/预处理完成态。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    raw_data = np.array([[1000.0, 2.0, 30.0, 40.0, 0.0]])
    preprocess_data = np.array([[1000.0, 2.0, 30.0, 40.0, 0.0]])
    dashboard_info = ExcelDashboardInfo(
        total_pulses=1,
        removed_pulses=0,
        amplitude_dropped_pulses=0,
        duration=0.0,
        band="C波段",
        estimated_slice_count=0,
    )
    session.raw_batch = PulseBatch(
        data=raw_data,
        source_path="E:/data/a.xlsx",
        source_type="excel",
        total_pulses=1,
    )
    session.preprocess_result = PreprocessResult(
        data=preprocess_data,
        total_pulses=1,
        filtered_pulses=0,
        toa_flip_count=0,
        time_range=0.0,
        estimated_slice_count=0,
        band="C波段",
        dashboard_info=dashboard_info,
    )
    session.dashboard_info = dashboard_info

    store.upsert_session(session)
    store.save_import_cache(session)
    restored = store.load_session(session.session_id)
    assert store.load_import_cache(restored) is True

    assert restored.raw_batch is not None
    assert restored.preprocess_result is not None
    assert restored.dashboard_info == dashboard_info
    assert restored.stage is ProcessingStage.PREPROCESSED
    np.testing.assert_array_equal(restored.raw_batch.data, raw_data)
    np.testing.assert_array_equal(restored.preprocess_result.data, preprocess_data)


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


def test_session_store_load_index_returns_empty_for_invalid_entry_id(
    tmp_path: Path,
) -> None:
    """索引条目的 session id 非法时应回退为空索引。"""
    (tmp_path / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_session_id": None,
                "sessions": [
                    {
                        "session_id": "a/b",
                        "display_name": "a.xlsx",
                        "source_path": "E:/data/a.xlsx",
                        "source_type": "excel",
                        "created_at": "2026-06-18T20:00:00",
                        "last_opened_at": "2026-06-18T20:01:00",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = SessionStore(tmp_path)

    index = store.load_index()

    assert index.active_session_id is None
    assert index.sessions == []


def test_session_store_load_index_returns_empty_for_numeric_entry_id(
    tmp_path: Path,
) -> None:
    """索引条目的 session id 为非字符串时应回退为空索引。"""
    (tmp_path / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_session_id": None,
                "sessions": [
                    {
                        "session_id": 123,
                        "display_name": "a.xlsx",
                        "source_path": "E:/data/a.xlsx",
                        "source_type": "excel",
                        "created_at": "2026-06-18T20:00:00",
                        "last_opened_at": "2026-06-18T20:01:00",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = SessionStore(tmp_path)

    index = store.load_index()

    assert index.active_session_id is None
    assert index.sessions == []


def test_session_store_load_index_returns_empty_when_sessions_is_not_list(
    tmp_path: Path,
) -> None:
    """索引 sessions 字段不是列表时应回退为空索引。"""
    (tmp_path / "index.json").write_text(
        '{"schema_version": 1, "active_session_id": null, "sessions": {}}',
        encoding="utf-8",
    )
    store = SessionStore(tmp_path)

    index = store.load_index()

    assert index.active_session_id is None
    assert index.sessions == []


def test_session_store_load_index_returns_empty_for_non_dict_entry(
    tmp_path: Path,
) -> None:
    """索引包含非字典条目时应回退为空索引。"""
    (tmp_path / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_session_id": None,
                "sessions": [
                    123,
                    {
                        "session_id": "valid",
                        "display_name": "a.xlsx",
                        "source_path": "E:/data/a.xlsx",
                        "source_type": "excel",
                        "created_at": "2026-06-18T20:00:00",
                        "last_opened_at": "2026-06-18T20:01:00",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = SessionStore(tmp_path)

    index = store.load_index()

    assert index.active_session_id is None
    assert index.sessions == []


def test_session_store_load_session_rejects_invalid_metadata_id(
    tmp_path: Path,
) -> None:
    """session 元数据中的非法 id 应阻止单 session 恢复。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)
    session_json_path = tmp_path / session.session_id / "session.json"
    payload = json.loads(session_json_path.read_text(encoding="utf-8"))
    payload["session_id"] = "a/b"
    session_json_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        store.load_session(session.session_id)


def test_session_store_load_session_rejects_numeric_metadata_id(
    tmp_path: Path,
) -> None:
    """session 元数据 id 为非字符串时应阻止单 session 恢复。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)
    session_json_path = tmp_path / session.session_id / "session.json"
    payload = json.loads(session_json_path.read_text(encoding="utf-8"))
    payload["session_id"] = 123
    session_json_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        store.load_session(session.session_id)


def test_session_store_load_session_rejects_mismatched_metadata_id(
    tmp_path: Path,
) -> None:
    """session 元数据 id 与请求 id 不一致时应抛出异常。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    other_session = ProcessingSession(source_path="E:/data/b.xlsx", source_type="excel")
    store.upsert_session(session)
    session_json_path = tmp_path / session.session_id / "session.json"
    payload = json.loads(session_json_path.read_text(encoding="utf-8"))
    payload["session_id"] = other_session.session_id
    session_json_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        store.load_session(session.session_id)


def test_session_store_load_all_sessions_skips_metadata_id_pollution(
    tmp_path: Path,
) -> None:
    """批量恢复时应跳过元数据 id 被污染或不一致的坏 session。"""
    store = SessionStore(tmp_path)
    valid_session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    polluted_session = ProcessingSession(source_path="E:/data/b.xlsx", source_type="excel")
    mismatched_session = ProcessingSession(source_path="E:/data/c.xlsx", source_type="excel")
    other_session = ProcessingSession(source_path="E:/data/d.xlsx", source_type="excel")
    store.upsert_session(valid_session)
    store.upsert_session(polluted_session)
    store.upsert_session(mismatched_session)

    polluted_json_path = tmp_path / polluted_session.session_id / "session.json"
    polluted_payload = json.loads(polluted_json_path.read_text(encoding="utf-8"))
    polluted_payload["session_id"] = "a/b"
    polluted_json_path.write_text(
        json.dumps(polluted_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    mismatched_json_path = tmp_path / mismatched_session.session_id / "session.json"
    mismatched_payload = json.loads(mismatched_json_path.read_text(encoding="utf-8"))
    mismatched_payload["session_id"] = other_session.session_id
    mismatched_json_path.write_text(
        json.dumps(mismatched_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    restored_sessions = store.load_all_sessions()

    assert [session.session_id for session in restored_sessions] == [
        valid_session.session_id,
    ]


def test_session_store_load_all_sessions_skips_numeric_metadata_id(
    tmp_path: Path,
) -> None:
    """批量恢复时应跳过元数据 id 为非字符串的坏 session。"""
    store = SessionStore(tmp_path)
    valid_session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    broken_session = ProcessingSession(source_path="E:/data/b.xlsx", source_type="excel")
    store.upsert_session(valid_session)
    store.upsert_session(broken_session)
    broken_json_path = tmp_path / broken_session.session_id / "session.json"
    payload = json.loads(broken_json_path.read_text(encoding="utf-8"))
    payload["session_id"] = 123
    broken_json_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    restored_sessions = store.load_all_sessions()

    assert [session.session_id for session in restored_sessions] == [
        valid_session.session_id,
    ]


@pytest.mark.parametrize(
    "session_id",
    [
        "CON",
        "NUL",
        "COM1",
        "con.txt",
        "bad:name",
        "bad*",
        "bad?",
        'bad"',
        "bad<",
        "bad>",
        "bad|",
        "trail.",
        "trail ",
        "bad\x01",
    ],
)
def test_session_store_rejects_windows_invalid_file_names(
    tmp_path: Path,
    session_id: str,
) -> None:
    """session id 不允许使用 Windows 非法文件名或保留设备名。"""
    store = SessionStore(tmp_path)

    with pytest.raises(ValueError):
        store.delete_session(session_id)


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
