"""Session 文件式持久化适配层。

该模块负责保存和恢复 session 元数据、模型选择、配置快照，并额外维护每个 session 的
导入/预处理缓存。缓存只覆盖 P03 导入完成态，不保存切片、聚类、识别、合并等下游结果。

Example:
    >>> from pathlib import Path
    >>> store = SessionStore(Path("config/sessions"))
    >>> isinstance(store.load_index(), SessionIndex)
    True
"""

from __future__ import annotations

import json
import shutil
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from core.models.dashboard_info import ExcelDashboardInfo
from core.models.processing_session import ProcessingSession
from core.models.processing_session import ProcessingStage
from core.models.pulse_batch import PulseBatch
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.slice_result import PreprocessResult
from utils.paths import get_session_config_dir


_WINDOWS_INVALID_FILENAME_CHARS = set('<>:"|?*')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _require_string_session_id(value: object) -> str:
    """要求持久化读取到的 session id 原本就是字符串。"""
    if not isinstance(value, str):
        raise ValueError("session_id 必须是字符串")
    return value


@dataclass
class SessionIndexEntry:
    """Session 索引条目。

    Attributes:
        session_id: session 唯一标识。
        display_name: 面向界面展示的 session 名称。
        source_path: 原始数据源路径。
        source_type: 原始数据源类型。
        created_at: session 创建时间。
        last_opened_at: session 最近打开时间。
    """

    session_id: str
    display_name: str
    source_path: str
    source_type: str
    created_at: datetime
    last_opened_at: datetime

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionIndexEntry":
        """从字典恢复索引条目。

        Args:
            payload [dict[str, Any]]: 从索引 JSON 读取的单条 session 元数据。

        Returns:
            SessionIndexEntry: 恢复后的索引条目。

        Raises:
            KeyError: 当必要字段缺失时抛出。
            ValueError: 当 session_id 不是字符串或时间字段不是合法 ISO 格式时抛出。

        Example:
            >>> entry = SessionIndexEntry.from_dict({
            ...     "session_id": "s1",
            ...     "display_name": "a.xlsx",
            ...     "source_path": "E:/data/a.xlsx",
            ...     "source_type": "excel",
            ...     "created_at": "2026-06-18T20:00:00",
            ...     "last_opened_at": "2026-06-18T20:01:00",
            ... })
            >>> entry.session_id
            's1'
        """

        return cls(
            session_id=_require_string_session_id(payload["session_id"]),
            display_name=str(payload["display_name"]),
            source_path=str(payload["source_path"]),
            source_type=str(payload["source_type"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            last_opened_at=datetime.fromisoformat(str(payload["last_opened_at"])),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 JSON 的字典。

        Args:
            无。

        Returns:
            dict[str, Any]: 包含 ISO 时间字符串的索引条目字典。

        Raises:
            无显式抛出异常。

        Example:
            >>> entry = SessionIndexEntry(
            ...     session_id="s1",
            ...     display_name="a.xlsx",
            ...     source_path="E:/data/a.xlsx",
            ...     source_type="excel",
            ...     created_at=datetime(2026, 6, 18, 20, 0),
            ...     last_opened_at=datetime(2026, 6, 18, 20, 1),
            ... )
            >>> entry.to_dict()["session_id"]
            's1'
        """

        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["last_opened_at"] = self.last_opened_at.isoformat()
        return data


@dataclass
class SessionIndex:
    """Session 持久化索引。

    Attributes:
        schema_version: 索引结构版本号。
        active_session_id: 当前活动 session id；未设置时为 None。
        sessions: 按展示和恢复顺序排列的 session 索引条目。
    """

    schema_version: int = 1
    active_session_id: str | None = None
    sessions: list[SessionIndexEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionIndex":
        """从字典恢复 session 索引。

        Args:
            payload [dict[str, Any]]: 从 index.json 读取的索引字典。

        Returns:
            SessionIndex: 恢复后的索引对象。

        Raises:
            ValueError: 当 schema_version、sessions 或时间字段无法解析时抛出。

        Example:
            >>> index = SessionIndex.from_dict({"schema_version": 1, "sessions": []})
            >>> index.schema_version
            1
        """

        sessions = payload.get("sessions", [])
        if not isinstance(sessions, list):
            raise ValueError("sessions 必须是列表")
        if not all(isinstance(entry, dict) for entry in sessions):
            raise ValueError("sessions 条目必须是字典")
        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            active_session_id=payload.get("active_session_id"),
            sessions=[
                SessionIndexEntry.from_dict(entry)
                for entry in sessions
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 index.json 的字典。

        Args:
            无。

        Returns:
            dict[str, Any]: 包含 schema、active id 和 session 条目的索引字典。

        Raises:
            无显式抛出异常。

        Example:
            >>> SessionIndex().to_dict()["sessions"]
            []
        """

        return {
            "schema_version": self.schema_version,
            "active_session_id": self.active_session_id,
            "sessions": [entry.to_dict() for entry in self.sessions],
        }


class SessionStore:
    """Session 文件式持久化存储。

    目录结构固定为 ``index.json``、``<session_id>/session.json`` 和
    ``<session_id>/config.json``，仅保存恢复 session 所需的轻量状态。

    Attributes:
        root_dir: session 持久化根目录。
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        """初始化 session 存储。

        Args:
            root_dir [Path | None]: 持久化根目录；为 None 时使用项目配置目录下的 sessions 目录。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当根目录创建失败时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> store.root_dir.name
            'sessions'
        """

        self.root_dir = root_dir or get_session_config_dir()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        # 串行化索引与 session 文件读写，避免并发读改写互相覆盖。
        self._lock = threading.RLock()

    def load_index(self) -> SessionIndex:
        """读取 session 索引。

        Args:
            无。

        Returns:
            SessionIndex: 当前索引；索引文件不存在、损坏或 id 字段非法时返回空索引。

        Raises:
            无显式抛出异常；索引读取失败时回退为空索引。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> isinstance(store.load_index(), SessionIndex)
            True
        """

        with self._lock:
            index_path = self.root_dir / "index.json"
            if not index_path.exists():
                return SessionIndex()

            try:
                with index_path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)
                if not isinstance(payload, dict):
                    return SessionIndex()
                index = SessionIndex.from_dict(payload)
                if index.active_session_id is not None:
                    index.active_session_id = self._validate_session_id(
                        index.active_session_id,
                    )
                for entry in index.sessions:
                    entry.session_id = self._validate_session_id(entry.session_id)
                return index
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                return SessionIndex()

    def save_index(self, index: SessionIndex) -> None:
        """保存 session 索引。

        Args:
            index [SessionIndex]: 待写入的索引对象。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当目录创建或文件写入失败时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> store.save_index(SessionIndex())
        """

        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            self._write_json(self.root_dir / "index.json", index.to_dict())

    def upsert_session(self, session: ProcessingSession) -> None:
        """新增或更新 session 持久化内容。

        Args:
            session [ProcessingSession]: 需要保存的 session 对象。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当目录创建或文件写入失败时抛出。
            ValueError: 当 session_id 指向 root_dir 外部路径时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
            >>> isinstance(session.session_id, str)
            True
        """

        with self._lock:
            session_dir = self._session_dir(session.session_id)
            session_dir.mkdir(parents=True, exist_ok=True)

            # 保存 session 元数据与配置快照。
            self._write_json(
                session_dir / "session.json",
                self._session_to_metadata(session),
            )
            self._write_json(
                session_dir / "config.json",
                session.config_snapshot.to_dict(),
            )

            # 在同一把锁内完成索引更新，避免并发 upsert 丢失条目。
            index = self.load_index()
            entry = self._session_to_index_entry(session)
            for index_pos, existing_entry in enumerate(index.sessions):
                if existing_entry.session_id == session.session_id:
                    index.sessions[index_pos] = entry
                    break
            else:
                index.sessions.append(entry)
            self.save_index(index)

    def load_session(self, session_id: str) -> ProcessingSession:
        """按 id 恢复单个 session。

        Args:
            session_id [str]: 需要恢复的 session 唯一标识。

        Returns:
            ProcessingSession: 恢复后的 session，计算产物字段保持为空。

        Raises:
            FileNotFoundError: 当 session.json 或 config.json 不存在时抛出。
            OSError: 当文件读取失败时抛出。
            json.JSONDecodeError: 当 JSON 格式非法时抛出。
            ValueError: 当 session_id 非法、元数据 id 不一致或时间字段无法解析时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> isinstance(store, SessionStore)
            True
        """

        with self._lock:
            requested_session_id = self._validate_session_id(session_id)
            session_dir = self._session_dir(requested_session_id)
            metadata = self._read_json(session_dir / "session.json")
            config_payload = self._read_json(session_dir / "config.json")
            model_payload = metadata.get("model_selection")
            metadata_session_id = self._validate_session_id(
                _require_string_session_id(metadata["session_id"]),
            )
            if metadata_session_id != requested_session_id:
                raise ValueError("session 元数据 id 与请求 id 不一致")

            session = ProcessingSession(
                session_id=requested_session_id,
                source_path=str(metadata["source_path"]),
                source_type=str(metadata["source_type"]),
                created_at=datetime.fromisoformat(str(metadata["created_at"])),
                display_name=str(metadata["display_name"]),
                last_opened_at=datetime.fromisoformat(str(metadata["last_opened_at"])),
                restored_from_store=True,
                config_snapshot=SessionConfigSnapshot.from_dict(config_payload),
                model_selection=SessionModelSelection.from_dict(model_payload),
            )

            # 明确保持计算产物为空，避免把持久化层扩展为结果保存系统。
            session.raw_batch = None
            session.slice_result = None
            session.cluster_result = None
            session.recognition_result = None
            session.merge_result = None
            return session

    def save_import_cache(self, session: ProcessingSession) -> None:
        """保存 session 的导入与预处理缓存。

        Args:
            session [ProcessingSession]: 已完成导入与预处理的 session。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当 session 缺少导入或预处理产物时抛出。
            OSError: 当缓存文件写入失败时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> isinstance(store, SessionStore)
            True
        """

        with self._lock:
            if session.raw_batch is None or session.preprocess_result is None:
                raise ValueError("保存导入缓存前必须完成导入与预处理")
            if session.dashboard_info is None:
                raise ValueError("保存导入缓存前必须存在仪表盘信息")

            cache_path = self._import_cache_path(session.session_id)
            metadata = {
                "schema_version": 1,
                "raw_batch": {
                    "source_path": session.raw_batch.source_path,
                    "source_type": session.raw_batch.source_type,
                    "total_pulses": session.raw_batch.total_pulses,
                },
                "preprocess_result": {
                    "total_pulses": session.preprocess_result.total_pulses,
                    "filtered_pulses": session.preprocess_result.filtered_pulses,
                    "toa_flip_count": session.preprocess_result.toa_flip_count,
                    "time_range": session.preprocess_result.time_range,
                    "estimated_slice_count": (
                        session.preprocess_result.estimated_slice_count
                    ),
                    "band": session.preprocess_result.band,
                },
                "dashboard_info": asdict(session.dashboard_info),
            }

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            # 数组交给 npz 存储，结构化元信息以 JSON 字符串随包写入。
            np.savez_compressed(
                cache_path,
                raw_data=session.raw_batch.data,
                preprocess_data=session.preprocess_result.data,
                metadata=np.array(json.dumps(metadata, ensure_ascii=False)),
            )

    def load_import_cache(self, session: ProcessingSession) -> bool:
        """读取 session 的导入缓存并恢复运行态数据。

        Args:
            session [ProcessingSession]: 需要填充缓存数据的 session。

        Returns:
            bool: 成功恢复缓存时返回 True，缓存缺失或损坏时返回 False。

        Raises:
            ValueError: 当 session_id 非法时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> session = ProcessingSession(session_id="missing")
            >>> store.load_import_cache(session)
            False
        """

        with self._lock:
            cache_path = self._import_cache_path(session.session_id)
            if not cache_path.exists():
                return False

            try:
                with np.load(cache_path, allow_pickle=False) as cache:
                    metadata = json.loads(str(cache["metadata"].item()))
                    if int(metadata.get("schema_version", 0)) != 1:
                        return False
                    raw_data = np.array(cache["raw_data"])
                    preprocess_data = np.array(cache["preprocess_data"])

                raw_payload = metadata["raw_batch"]
                preprocess_payload = metadata["preprocess_result"]
                dashboard_payload = metadata["dashboard_info"]
                dashboard_info = ExcelDashboardInfo(
                    total_pulses=int(dashboard_payload["total_pulses"]),
                    removed_pulses=int(dashboard_payload["removed_pulses"]),
                    amplitude_dropped_pulses=int(
                        dashboard_payload["amplitude_dropped_pulses"]
                    ),
                    duration=float(dashboard_payload["duration"]),
                    band=dashboard_payload["band"],
                    estimated_slice_count=int(
                        dashboard_payload["estimated_slice_count"]
                    ),
                )
                preprocess_result = PreprocessResult(
                    data=preprocess_data,
                    total_pulses=int(preprocess_payload["total_pulses"]),
                    filtered_pulses=int(preprocess_payload["filtered_pulses"]),
                    toa_flip_count=int(preprocess_payload["toa_flip_count"]),
                    time_range=float(preprocess_payload["time_range"]),
                    estimated_slice_count=int(
                        preprocess_payload["estimated_slice_count"]
                    ),
                    band=preprocess_payload["band"],
                    dashboard_info=dashboard_info,
                )

                with session.lock:
                    # 只恢复导入/预处理产物，下游结果仍由对应流程重新产生。
                    session.raw_batch = PulseBatch(
                        data=raw_data,
                        source_path=str(raw_payload["source_path"]),
                        source_type=str(raw_payload["source_type"]),
                        total_pulses=int(raw_payload["total_pulses"]),
                    )
                    session.preprocess_result = preprocess_result
                    session.dashboard_info = dashboard_info
                    session.stage = ProcessingStage.PREPROCESSED
                return True
            except (
                OSError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ):
                return False

    def list_sessions(self) -> list[SessionIndexEntry]:
        """按索引顺序列出 session 条目。

        Args:
            无。

        Returns:
            list[SessionIndexEntry]: 当前索引中的 session 条目列表。

        Raises:
            OSError: 当索引读取失败时抛出。
            json.JSONDecodeError: 当索引 JSON 格式非法时抛出。
            ValueError: 当索引字段无法解析时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> isinstance(store.list_sessions(), list)
            True
        """

        return list(self.load_index().sessions)

    def load_all_sessions(self) -> list[ProcessingSession]:
        """按索引顺序恢复全部 session。

        Args:
            无。

        Returns:
            list[ProcessingSession]: 已恢复的 session 列表；单个损坏条目会被跳过。

        Raises:
            无显式抛出异常；单个 session 文件缺失或损坏时跳过对应条目。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> isinstance(store.load_all_sessions(), list)
            True
        """

        with self._lock:
            sessions: list[ProcessingSession] = []
            for entry in self.load_index().sessions:
                try:
                    sessions.append(self.load_session(entry.session_id))
                except (
                    FileNotFoundError,
                    OSError,
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue
            return sessions

    def delete_session(self, session_id: str) -> None:
        """删除 session 目录并更新索引。

        Args:
            session_id [str]: 需要删除的 session 唯一标识。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当目录删除或索引写入失败时抛出。
            ValueError: 当 session_id 指向 root_dir 外部路径时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> store.delete_session("missing")
        """

        with self._lock:
            session_dir = self._session_dir(session_id)
            if session_dir.exists():
                shutil.rmtree(session_dir)

            index = self.load_index()
            index.sessions = [
                entry for entry in index.sessions if entry.session_id != session_id
            ]
            if index.active_session_id == session_id:
                index.active_session_id = None
            self.save_index(index)

    def set_active_session_id(self, session_id: str | None) -> None:
        """持久化当前活动 session id。

        Args:
            session_id [str | None]: 当前活动 session id；传入 None 表示清空。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当索引读取或写入失败时抛出。
            json.JSONDecodeError: 当索引 JSON 格式非法时抛出。
            ValueError: 当索引字段无法解析时抛出。

        Example:
            >>> store = SessionStore(Path("config/sessions"))
            >>> store.set_active_session_id(None)
        """

        with self._lock:
            index = self.load_index()
            index.active_session_id = (
                None if session_id is None else self._validate_session_id(session_id)
            )
            self.save_index(index)

    def _validate_session_id(self, session_id: str) -> str:
        """校验 session id 是否为单段安全目录名。"""
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id 不能为空")
        if session_id in {".", ".."}:
            raise ValueError("session_id 不能是当前目录或上级目录")
        if "/" in session_id or "\\" in session_id:
            raise ValueError("session_id 不能包含路径分隔符")
        if session_id.rstrip(" .") != session_id:
            raise ValueError("session_id 不能以空格或点结尾")
        if any(ord(char) < 32 for char in session_id):
            raise ValueError("session_id 不能包含控制字符")
        if any(char in _WINDOWS_INVALID_FILENAME_CHARS for char in session_id):
            raise ValueError("session_id 不能包含 Windows 文件名非法字符")
        if session_id.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise ValueError("session_id 不能使用 Windows 保留设备名")

        session_path = Path(session_id)
        if session_path.is_absolute() or session_path.drive or session_path.root:
            raise ValueError("session_id 不能是绝对路径")
        if session_path.name != session_id:
            raise ValueError("session_id 必须是单段目录名")
        return session_id

    def _session_dir(self, session_id: str) -> Path:
        """生成并校验 session 目录路径。"""
        safe_session_id = self._validate_session_id(session_id)
        root = self.root_dir.resolve()
        session_dir = (self.root_dir / safe_session_id).resolve()
        if session_dir == root:
            raise ValueError("session 目录不能等于持久化根目录")
        try:
            session_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError("session 目录不能位于持久化根目录之外") from exc
        return session_dir

    def _import_cache_path(self, session_id: str) -> Path:
        """返回指定 session 的导入缓存文件路径。"""
        return self._session_dir(session_id) / "import_cache.npz"

    def _session_to_index_entry(self, session: ProcessingSession) -> SessionIndexEntry:
        """从 session 构造索引条目。"""
        return SessionIndexEntry(
            session_id=session.session_id,
            display_name=session.display_name,
            source_path=session.source_path,
            source_type=session.source_type,
            created_at=session.created_at,
            last_opened_at=session.last_opened_at,
        )

    def _session_to_metadata(self, session: ProcessingSession) -> dict[str, Any]:
        """从 session 构造元数据 JSON 字典。"""
        return {
            "session_id": session.session_id,
            "source_path": session.source_path,
            "source_type": session.source_type,
            "created_at": session.created_at.isoformat(),
            "display_name": session.display_name,
            "last_opened_at": session.last_opened_at.isoformat(),
            "model_selection": session.model_selection.to_dict(),
        }

    def _read_json(self, file_path: Path) -> dict[str, Any]:
        """读取 JSON 字典文件。"""
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            return {}
        return payload

    def _write_json(self, file_path: Path, payload: dict[str, Any]) -> None:
        """写入 JSON 字典文件。"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
