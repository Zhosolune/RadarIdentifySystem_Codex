"""Session 持久化适配层测试。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from core.models.dashboard_info import PulseDashboardInfo
from core.models.processing_session import ProcessingMode, ProcessingSession
from core.models.processing_session import ProcessingStage
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
from infra.session_store import SessionStore


class _RecordingRLock:
    """测试用可重入锁记录器。"""

    def __init__(self) -> None:
        """初始化锁状态记录。"""
        self.depth = 0
        self.enter_calls = 0
        self.max_depth = 0

    def __enter__(self) -> "_RecordingRLock":
        """进入锁上下文并记录嵌套层级。"""
        self.depth += 1
        self.enter_calls += 1
        self.max_depth = max(self.max_depth, self.depth)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """退出锁上下文并回退层级计数。"""
        self.depth -= 1


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


def test_session_store_index_omits_startup_restore_state(tmp_path: Path) -> None:
    """索引文件不应保存启动恢复弹窗所需的界面状态。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")

    store.upsert_session(session)
    payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))

    assert "active_session_id" not in payload
    assert "last_exit_view" not in payload


def test_session_store_upsert_uses_reentrant_lock_for_index_update(
    tmp_path: Path,
) -> None:
    """保存 session 时应通过同一把可重入锁包裹索引更新。"""
    store = SessionStore(tmp_path)
    recording_lock = _RecordingRLock()
    store._lock = recording_lock
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")

    store.upsert_session(session)

    assert recording_lock.enter_calls >= 3
    assert recording_lock.max_depth >= 2


def test_session_store_round_trips_import_cache(tmp_path: Path) -> None:
    """session 导入缓存应能恢复到导入/预处理完成态。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    raw_data = np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]])
    preprocess_data = np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 0.0]])
    dashboard_info = PulseDashboardInfo(
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


def test_session_store_migrates_legacy_five_column_import_cache(
    tmp_path: Path,
) -> None:
    """旧版五列缓存恢复时应重排列并使用 DOA 补齐 PDOA。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(
        session_id="legacy-cache",
        source_path="E:/data/legacy.xlsx",
        source_type="excel",
    )
    legacy_data = np.array([[1000.0, 2.0, 30.0, 40.0, 50.0]])
    metadata = {
        "schema_version": 1,
        "raw_batch": {
            "source_path": session.source_path,
            "source_type": session.source_type,
            "total_pulses": 1,
        },
        "preprocess_result": {
            "total_pulses": 1,
            "filtered_pulses": 0,
            "toa_flip_count": 0,
            "time_range": 0.0,
            "estimated_slice_count": 0,
            "band": "L波段",
        },
        "dashboard_info": {
            "total_pulses": 1,
            "removed_pulses": 0,
            "amplitude_dropped_pulses": 0,
            "duration": 0.0,
            "band": "L波段",
            "estimated_slice_count": 0,
        },
    }
    cache_path = store._import_cache_path(session.session_id)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        raw_data=legacy_data,
        preprocess_data=legacy_data,
        metadata=np.array(json.dumps(metadata, ensure_ascii=False)),
    )

    assert store.load_import_cache(session) is True
    assert session.raw_batch is not None
    assert session.preprocess_result is not None
    expected = np.array([[1000.0, 2.0, 40.0, 30.0, 30.0, 50.0]])
    np.testing.assert_array_equal(session.raw_batch.data, expected)
    np.testing.assert_array_equal(session.preprocess_result.data, expected)


def test_session_store_delete_removes_session_dir(tmp_path: Path) -> None:
    """删除 session 时应删除目录并更新索引。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)

    store.delete_session(session.session_id)

    assert not (tmp_path / session.session_id).exists()
    assert store.load_index().sessions == []


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

    assert index.sessions == []


def test_session_store_load_index_ignores_legacy_invalid_active_id(
    tmp_path: Path,
) -> None:
    """旧索引 active session id 非法时应被忽略。"""
    (tmp_path / "index.json").write_text(
        '{"schema_version": 1, "active_session_id": "", "sessions": []}',
        encoding="utf-8",
    )
    store = SessionStore(tmp_path)

    index = store.load_index()

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


def test_session_store_updates_remark_metadata(tmp_path: Path) -> None:
    """更新备注时应只改写 session 元数据并保留索引顺序。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)

    updated = store.update_session_remark(session.session_id, "新的备注")

    assert updated.remark == "新的备注"
    restored = store.load_session(session.session_id)
    assert restored.remark == "新的备注"
    assert [entry.session_id for entry in store.load_index().sessions] == [session.session_id]


def test_session_store_round_trips_full_speed_reference_and_lock(
    tmp_path: Path,
) -> None:
    """全速 Session 应持久化数据包引用、冻结状态和结果文件路径。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(
        session_id="full_speed_store",
        data_package_id="package1",
        data_format="old",
        processing_mode=ProcessingMode.FULL_SPEED,
        full_speed_locked=True,
        exported_file_path="E:/output/result.xlsx",
        stage=ProcessingStage.EXPORTED,
    )
    store.upsert_session(session)

    restored = store.load_session(session.session_id)

    assert restored.data_package_id == "package1"
    assert restored.data_format == "old"
    assert restored.processing_mode is ProcessingMode.FULL_SPEED
    assert restored.full_speed_locked
    assert restored.exported_file_path == "E:/output/result.xlsx"
    assert restored.stage is ProcessingStage.EXPORTED
