# Session Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build session isolation so each imported file creates an independent, persistent session with its own `SliceInterface`, controllers, configuration snapshot, and model selection.

**Architecture:** `core/models` defines pure session data contracts, `infra/session_store.py` persists session metadata/config files, `runtime/session_registry.py` owns runtime indexing and active session state, and `ui/main_window.py` hosts dynamic `SubInterface` pages. Existing global `AppConfig/QConfig` remains the default template for new sessions; session-specific settings use `SessionConfigSnapshot + SessionConfigItem` instead of the global `qconfig` singleton.

**Tech Stack:** Python 3.12, PyQt6, qfluentwidgets, pytest, JSON file persistence under `config/sessions`.

---

## File Structure

- Create `RadarIdentifySystem_PyQt6/core/models/session_config.py`
  - Session configuration dataclasses, validation, `SessionConfigItem`, and config JSON conversion.
- Create `RadarIdentifySystem_PyQt6/core/models/session_model.py`
  - Session-level model selection dataclass and validation helpers.
- Modify `RadarIdentifySystem_PyQt6/core/models/processing_session.py`
  - Add session metadata fields and safe defaults for restored sessions.
- Modify `RadarIdentifySystem_PyQt6/core/models/__init__.py`
  - Export new session data contracts.
- Modify `RadarIdentifySystem_PyQt6/utils/paths.py`
  - Add `get_session_config_dir()`.
- Create `RadarIdentifySystem_PyQt6/infra/session_store.py`
  - Persist `index.json`, `<session_id>/session.json`, and `<session_id>/config.json`.
- Create `RadarIdentifySystem_PyQt6/runtime/session_registry.py`
  - Runtime registry, active session state, registration, restore, close, metadata updates.
- Create `RadarIdentifySystem_PyQt6/runtime/session_config_factory.py`
  - Build `SessionConfigSnapshot` from global `appConfig` without importing app from core.
- Modify `RadarIdentifySystem_PyQt6/app/signal_bus.py`
  - Add `parse_completed`, `session_registered`, `session_activated`, `session_closed`, `session_metadata_changed`.
- Modify `RadarIdentifySystem_PyQt6/runtime/workflows/import_workflow.py`
  - Emit `parse_completed` instead of `import_completed` for parse completion.
- Modify `RadarIdentifySystem_PyQt6/ui/controllers/home_controller.py`
  - Render parse result only on `parse_completed`; create session through main window when import button is clicked.
- Modify `RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py`
  - Accept a bound session, set route-specific object name, pass session config to drawer panel.
- Modify `RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py`
  - Remove global import replacement, respond only to its session.
- Modify `RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py`
  - Validate/read session model selection.
- Modify `RadarIdentifySystem_PyQt6/runtime/workflows/identify_workflow.py`
  - Use session model selection and session config-derived params.
- Modify `RadarIdentifySystem_PyQt6/runtime/threading/identify_worker.py`
  - Use injected clustering/recognition params rather than global `runtime.algorithm_params`.
- Modify `RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py`
  - Bind auto-recognize and future session settings to session config items.
- Modify `RadarIdentifySystem_PyQt6/ui/components/spin_box_setting_card.py`
  - Support a config writer for global or session config items.
- Modify `RadarIdentifySystem_PyQt6/ui/components/double_spin_box_setting_card.py`
  - Support a config writer for global or session config items.
- Create `RadarIdentifySystem_PyQt6/ui/components/session_manager_panel.py`
  - Home-side session manager list for switch/close/rename commands.
- Modify `RadarIdentifySystem_PyQt6/ui/interfaces/home_interface.py`
  - Add session manager panel to the reserved right column.
- Modify `RadarIdentifySystem_PyQt6/ui/main_window.py`
  - Dynamic session page create/activate/close/restore methods.
- Tests:
  - `RadarIdentifySystem_PyQt6/tests/unit/test_session_config_snapshot.py`
  - `RadarIdentifySystem_PyQt6/tests/unit/test_session_store.py`
  - `RadarIdentifySystem_PyQt6/tests/unit/test_session_registry.py`
  - `RadarIdentifySystem_PyQt6/tests/unit/test_session_event_isolation.py`
  - `RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py`
  - `RadarIdentifySystem_PyQt6/tests/unit/test_session_config_item.py`
  - update `test_navigation_controls.py`, `test_slice_param_panel.py`, `test_model_selection_card.py`, `test_identify_worker_clustering_params.py`

---

### Task 1: Add Session Config Data Contracts

**Files:**
- Create: `RadarIdentifySystem_PyQt6/core/models/session_config.py`
- Modify: `RadarIdentifySystem_PyQt6/core/models/__init__.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_session_config_snapshot.py`

- [ ] **Step 1: Write failing tests for snapshot defaults, JSON recovery, and independent mutation**

Create `RadarIdentifySystem_PyQt6/tests/unit/test_session_config_snapshot.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_config_snapshot.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.models.session_config'`.

- [ ] **Step 3: Implement session config snapshots**

Create `RadarIdentifySystem_PyQt6/core/models/session_config.py`:

```python
"""Session 子配置数据契约。

该模块只定义可序列化的 session 级配置快照，不依赖 appConfig、Qt UI 或磁盘。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal
from qfluentwidgets import BoolValidator, RangeValidator


def _coerce_dataclass(cls, payload: dict[str, Any]) -> Any:
    """按 dataclass 默认值恢复字典。

    Args:
        cls: 目标 dataclass 类型，必须提供 ``default`` 类方法。
        payload: 外部读取的配置字典。

    Returns:
        Any: 恢复后的 dataclass 实例。

    Raises:
        无显式抛出异常。
    """
    default_obj = cls.default()
    values = asdict(default_obj)
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in values:
                values[key] = value
    return cls(**values)


@dataclass
class ClusteringConfigSnapshot:
    """聚类参数快照。"""

    eps_cf: float = 2.0
    min_pts_cf: int = 2
    eps_pw: float = 0.2
    min_pts_pw: int = 2
    eps_doa: float = 16.8
    min_pts_doa: int = 2
    clip_threshold_doa: float = 95.0

    @classmethod
    def default(cls) -> "ClusteringConfigSnapshot":
        """返回聚类配置默认值。"""
        return cls()


@dataclass
class RecognitionConfigSnapshot:
    """识别参数快照。"""

    tolerance: float = 0.5
    min_confidence: float = 0.8
    max_candidates: int = 5

    @classmethod
    def default(cls) -> "RecognitionConfigSnapshot":
        """返回识别配置默认值。"""
        return cls()


@dataclass
class ExtractConfigSnapshot:
    """参数提取配置快照。"""

    step: int = 1
    smooth_window: int = 5
    outlier_threshold: float = 3.0

    @classmethod
    def default(cls) -> "ExtractConfigSnapshot":
        """返回提取配置默认值。"""
        return cls()


@dataclass
class MergeConfigSnapshot:
    """合并配置快照。"""

    time_decay: float = 0.9
    sim_threshold: float = 0.8
    max_extrapolate: int = 3
    pri_equal_doa_tolerance: float = 20.0

    @classmethod
    def default(cls) -> "MergeConfigSnapshot":
        """返回合并配置默认值。"""
        return cls()


@dataclass
class BusinessConfigSnapshot:
    """Session 级业务配置快照。"""

    auto_recognize_next_slice: bool = True
    export_dir_path: str = ""
    auto_export: bool = False

    @classmethod
    def default(cls) -> "BusinessConfigSnapshot":
        """返回业务配置默认值。"""
        return cls()


@dataclass
class SessionConfigSnapshot:
    """Session 子配置总快照。"""

    SCHEMA_VERSION = 1

    schema_version: int = SCHEMA_VERSION
    clustering: ClusteringConfigSnapshot = field(default_factory=ClusteringConfigSnapshot.default)
    recognition: RecognitionConfigSnapshot = field(default_factory=RecognitionConfigSnapshot.default)
    extract: ExtractConfigSnapshot = field(default_factory=ExtractConfigSnapshot.default)
    merge: MergeConfigSnapshot = field(default_factory=MergeConfigSnapshot.default)
    business: BusinessConfigSnapshot = field(default_factory=BusinessConfigSnapshot.default)

    @classmethod
    def default(cls) -> "SessionConfigSnapshot":
        """返回完整 session 子配置默认值。"""
        return cls()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionConfigSnapshot":
        """从字典恢复配置快照。

        Args:
            payload: session 配置 JSON 字典。

        Returns:
            SessionConfigSnapshot: 恢复后的配置快照。

        Raises:
            无显式抛出异常。
        """
        data = payload if isinstance(payload, dict) else {}
        return cls(
            schema_version=int(data.get("schema_version", cls.SCHEMA_VERSION)),
            clustering=_coerce_dataclass(ClusteringConfigSnapshot, data.get("clustering", {})),
            recognition=_coerce_dataclass(RecognitionConfigSnapshot, data.get("recognition", {})),
            extract=_coerce_dataclass(ExtractConfigSnapshot, data.get("extract", {})),
            merge=_coerce_dataclass(MergeConfigSnapshot, data.get("merge", {})),
            business=_coerce_dataclass(BusinessConfigSnapshot, data.get("business", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 JSON 的字典。"""
        return asdict(self)


class SessionConfigItem(QObject):
    """绑定到 session 配置快照字段的轻量配置项。"""

    valueChanged = pyqtSignal(object)

    def __init__(
        self,
        snapshot: SessionConfigSnapshot,
        path: str,
        default: object,
        validator: object | None = None,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        """创建 session 配置项。

        Args:
            snapshot: 目标 session 配置快照。
            path: 点号分隔的字段路径，例如 ``clustering.eps_cf``。
            default: 默认值。
            validator: qfluentwidgets 校验器。
            on_changed: 值变化后的保存回调。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当字段路径不合法时抛出。
        """
        super().__init__()
        self.snapshot = snapshot
        self.group, self.name = path.rsplit(".", 1)
        self.path = path
        self.validator = validator
        self.defaultValue = default
        self._on_changed = on_changed
        self._read()

    @property
    def value(self) -> object:
        """返回当前字段值。"""
        return self._read()

    @value.setter
    def value(self, new_value: object) -> None:
        self.set(new_value)

    def set(self, new_value: object) -> None:
        """设置当前字段值并触发保存回调。"""
        corrected = self.validator.correct(new_value) if self.validator else new_value
        old_value = self._read()
        if old_value == corrected:
            return
        self._write(corrected)
        self.valueChanged.emit(corrected)
        if self._on_changed:
            self._on_changed()

    def _target(self) -> tuple[object, str]:
        """返回字段所属对象与字段名。"""
        target = self.snapshot
        parts = self.path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        return target, parts[-1]

    def _read(self) -> object:
        """读取绑定字段。"""
        target, field_name = self._target()
        return getattr(target, field_name)

    def _write(self, value: object) -> None:
        """写入绑定字段。"""
        target, field_name = self._target()
        setattr(target, field_name, value)
```

Modify `RadarIdentifySystem_PyQt6/core/models/__init__.py`:

```python
from .session_config import (
    BusinessConfigSnapshot,
    ClusteringConfigSnapshot,
    ExtractConfigSnapshot,
    MergeConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigItem,
    SessionConfigSnapshot,
)
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_config_snapshot.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/core/models/session_config.py RadarIdentifySystem_PyQt6/core/models/__init__.py RadarIdentifySystem_PyQt6/tests/unit/test_session_config_snapshot.py
git commit -m "feat(session): add session config snapshots"
```

---

### Task 2: Add Session Model Selection and ProcessingSession Metadata

**Files:**
- Create: `RadarIdentifySystem_PyQt6/core/models/session_model.py`
- Modify: `RadarIdentifySystem_PyQt6/core/models/processing_session.py`
- Modify: `RadarIdentifySystem_PyQt6/core/models/__init__.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_processing_session.py`

- [ ] **Step 1: Write failing tests for session metadata defaults**

Append to `RadarIdentifySystem_PyQt6/tests/unit/test_processing_session.py`:

```python
def test_processing_session_owns_metadata_and_snapshots() -> None:
    """ProcessingSession 应持有 session 级元数据与快照。"""
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")

    assert session.display_name == "a.xlsx"
    assert session.config_snapshot is not None
    assert session.model_selection.pa_model_path is None
    assert session.restored_from_store is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_processing_session.py::test_processing_session_owns_metadata_and_snapshots -q
```

Expected: FAIL with missing `display_name` or `config_snapshot`.

- [ ] **Step 3: Implement session model selection and metadata fields**

Create `RadarIdentifySystem_PyQt6/core/models/session_model.py`:

```python
"""Session 级模型选择数据契约。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SessionModelSelection:
    """单个 session 的模型选择。"""

    pa_model_path: str | None = None
    dtoa_model_path: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionModelSelection":
        """从 JSON 字典恢复模型选择。"""
        data = payload if isinstance(payload, dict) else {}
        return cls(
            pa_model_path=data.get("pa_model_path"),
            dtoa_model_path=data.get("dtoa_model_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON 字典。"""
        return asdict(self)


@dataclass(frozen=True)
class ActiveModelCandidate:
    """软件级激活模型候选项。"""

    model_type: str
    path: str
    display_name: str
```

Modify `ProcessingSession` imports and fields:

```python
from pathlib import Path
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
```

Add fields:

```python
display_name: str = ""
last_opened_at: datetime = field(default_factory=datetime.now)
restored_from_store: bool = False
config_snapshot: SessionConfigSnapshot = field(default_factory=SessionConfigSnapshot.default)
model_selection: SessionModelSelection = field(default_factory=SessionModelSelection)
```

Add `__post_init__`:

```python
def __post_init__(self) -> None:
    """补齐 session 展示名称。"""
    if not self.display_name and self.source_path:
        self.display_name = Path(self.source_path).name
    elif not self.display_name:
        self.display_name = f"Session {self.session_id}"
```

Modify `core/models/__init__.py` to export `SessionModelSelection` and `ActiveModelCandidate`.

- [ ] **Step 4: Run the focused test**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_processing_session.py::test_processing_session_owns_metadata_and_snapshots -q
```

Expected: PASS.

- [ ] **Step 5: Run existing processing session tests**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_processing_session.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/core/models/session_model.py RadarIdentifySystem_PyQt6/core/models/processing_session.py RadarIdentifySystem_PyQt6/core/models/__init__.py RadarIdentifySystem_PyQt6/tests/unit/test_processing_session.py
git commit -m "feat(session): add session metadata models"
```

---

### Task 3: Add Session Store Persistence

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/utils/paths.py`
- Create: `RadarIdentifySystem_PyQt6/infra/session_store.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_session_store.py`

- [ ] **Step 1: Write failing tests for JSON persistence**

Create `RadarIdentifySystem_PyQt6/tests/unit/test_session_store.py`:

```python
"""Session 持久化适配层测试。"""

from __future__ import annotations

from pathlib import Path

from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore


def test_session_store_writes_index_session_and_config(tmp_path: Path) -> None:
    """保存 session 时应写入索引、元数据和配置文件。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    session.config_snapshot.clustering.eps_cf = 8.0

    store.upsert_session(session)

    session_dir = tmp_path / session.session_id
    assert (tmp_path / "index.json").exists()
    assert (session_dir / "session.json").exists()
    assert (session_dir / "config.json").exists()

    restored = store.load_session(session.session_id)
    assert restored.source_path == "E:/data/a.xlsx"
    assert restored.config_snapshot.clustering.eps_cf == 8.0
    assert restored.raw_batch is None
    assert restored.restored_from_store is True


def test_session_store_delete_removes_session_dir(tmp_path: Path) -> None:
    """删除 session 时应删除目录并更新索引。"""
    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)

    store.delete_session(session.session_id)

    assert not (tmp_path / session.session_id).exists()
    assert store.load_index().sessions == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_store.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'infra.session_store'`.

- [ ] **Step 3: Add session config directory path helper**

Modify `RadarIdentifySystem_PyQt6/utils/paths.py`:

```python
def get_session_config_dir() -> Path:
    """获取 session 持久化目录。

    Args:
        无。

    Returns:
        Path: session 持久化目录路径。

    Raises:
        OSError: 当目录创建失败时抛出。

    Example:
        >>> get_session_config_dir().name
        'sessions'
    """
    session_dir = get_config_dir() / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir
```

- [ ] **Step 4: Implement `SessionStore`**

Create `RadarIdentifySystem_PyQt6/infra/session_store.py`:

```python
"""Session 文件式持久化适配层。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Any

from core.models.processing_session import ProcessingSession
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from utils.paths import get_session_config_dir


@dataclass
class SessionIndexEntry:
    """Session 索引条目。"""

    session_id: str
    display_name: str
    source_path: str
    source_type: str
    created_at: str
    last_opened_at: str


@dataclass
class SessionIndex:
    """Session 索引文件内容。"""

    schema_version: int = 1
    active_session_id: str | None = None
    sessions: list[SessionIndexEntry] = field(default_factory=list)


class SessionStore:
    """管理 session 元数据和子配置文件。"""

    def __init__(self, root_dir: Path | None = None) -> None:
        """初始化 store。

        Args:
            root_dir: session 持久化根目录，测试时可注入临时目录。
        """
        self.root_dir = root_dir or get_session_config_dir()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    @property
    def index_path(self) -> Path:
        """返回索引文件路径。"""
        return self.root_dir / "index.json"

    def load_index(self) -> SessionIndex:
        """读取 session 索引。"""
        payload = self._read_json(self.index_path, {})
        entries = [
            SessionIndexEntry(**entry)
            for entry in payload.get("sessions", [])
            if isinstance(entry, dict)
        ]
        return SessionIndex(
            schema_version=int(payload.get("schema_version", 1)),
            active_session_id=payload.get("active_session_id"),
            sessions=entries,
        )

    def save_index(self, index: SessionIndex) -> None:
        """保存 session 索引。"""
        self._write_json(
            self.index_path,
            {
                "schema_version": index.schema_version,
                "active_session_id": index.active_session_id,
                "sessions": [entry.__dict__ for entry in index.sessions],
            },
        )

    def upsert_session(self, session: ProcessingSession) -> None:
        """新增或更新 session 持久化文件。"""
        session_dir = self._session_dir(session.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(session_dir / "session.json", self._session_to_dict(session))
        self._write_json(session_dir / "config.json", session.config_snapshot.to_dict())
        index = self.load_index()
        entries = [entry for entry in index.sessions if entry.session_id != session.session_id]
        entries.append(self._index_entry(session))
        index.sessions = entries
        if index.active_session_id is None:
            index.active_session_id = session.session_id
        self.save_index(index)

    def load_session(self, session_id: str) -> ProcessingSession:
        """按 ID 恢复空产物 session。"""
        session_dir = self._session_dir(session_id)
        session_payload = self._read_json(session_dir / "session.json", {})
        config_payload = self._read_json(session_dir / "config.json", {})
        session = ProcessingSession(
            session_id=session_payload.get("session_id", session_id),
            source_path=session_payload.get("source_path", ""),
            source_type=session_payload.get("source_type", "unknown"),
            display_name=session_payload.get("display_name", ""),
            restored_from_store=True,
            config_snapshot=SessionConfigSnapshot.from_dict(config_payload),
            model_selection=SessionModelSelection.from_dict(session_payload.get("model_selection", {})),
        )
        return session

    def delete_session(self, session_id: str) -> None:
        """删除 session 文件和索引记录。"""
        session_dir = self._session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
        index = self.load_index()
        index.sessions = [entry for entry in index.sessions if entry.session_id != session_id]
        if index.active_session_id == session_id:
            index.active_session_id = index.sessions[-1].session_id if index.sessions else None
        self.save_index(index)

    def _session_dir(self, session_id: str) -> Path:
        """返回 session 目录。"""
        return self.root_dir / session_id

    def _index_entry(self, session: ProcessingSession) -> SessionIndexEntry:
        """从 session 生成索引条目。"""
        return SessionIndexEntry(
            session_id=session.session_id,
            display_name=session.display_name,
            source_path=session.source_path,
            source_type=session.source_type,
            created_at=session.created_at.isoformat(),
            last_opened_at=session.last_opened_at.isoformat(),
        )

    def _session_to_dict(self, session: ProcessingSession) -> dict[str, Any]:
        """从 session 生成元数据字典。"""
        return {
            "schema_version": 1,
            "session_id": session.session_id,
            "display_name": session.display_name,
            "source_path": session.source_path,
            "source_type": session.source_type,
            "created_at": session.created_at.isoformat(),
            "last_opened_at": session.last_opened_at.isoformat(),
            "model_selection": session.model_selection.to_dict(),
        }

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        """读取 JSON 文件。"""
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else default

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        """写入 JSON 文件。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=4)
```

- [ ] **Step 5: Run store tests**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_store.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/utils/paths.py RadarIdentifySystem_PyQt6/infra/session_store.py RadarIdentifySystem_PyQt6/tests/unit/test_session_store.py
git commit -m "feat(session): persist session metadata"
```

---

### Task 4: Add Session Registry and Config Factory

**Files:**
- Create: `RadarIdentifySystem_PyQt6/runtime/session_config_factory.py`
- Create: `RadarIdentifySystem_PyQt6/runtime/session_registry.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_session_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `RadarIdentifySystem_PyQt6/tests/unit/test_session_registry.py`:

```python
"""Session 运行态注册表测试。"""

from __future__ import annotations

from pathlib import Path

from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore
from runtime.session_registry import SessionRegistry


def test_session_registry_registers_and_activates(tmp_path: Path) -> None:
    """注册 session 后应能查询并激活。"""
    registry = SessionRegistry(SessionStore(tmp_path))
    first = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    second = ProcessingSession(source_path="E:/data/b.xlsx", source_type="excel")

    registry.register(first)
    registry.register(second)
    registry.activate(first.session_id)

    assert registry.get(first.session_id) is first
    assert registry.active_session_id == first.session_id
    assert registry.active_session is first


def test_session_registry_restores_from_store(tmp_path: Path) -> None:
    """注册表应能从 store 恢复空产物 session。"""
    store = SessionStore(tmp_path)
    original = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(original)

    registry = SessionRegistry(store)
    restored = registry.restore()

    assert len(restored) == 1
    assert restored[0].session_id == original.session_id
    assert restored[0].raw_batch is None
    assert restored[0].restored_from_store is True
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_registry.py -q
```

Expected: FAIL with missing `runtime.session_registry`.

- [ ] **Step 3: Implement config factory**

Create `RadarIdentifySystem_PyQt6/runtime/session_config_factory.py`:

```python
"""Session 子配置工厂。"""

from __future__ import annotations

from app.app_config import appConfig, qconfig
from core.models.session_config import (
    BusinessConfigSnapshot,
    ClusteringConfigSnapshot,
    ExtractConfigSnapshot,
    MergeConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigSnapshot,
)


def create_session_config_from_global() -> SessionConfigSnapshot:
    """从全局 appConfig 拷贝新 session 默认配置。"""
    return SessionConfigSnapshot(
        clustering=ClusteringConfigSnapshot(
            eps_cf=float(qconfig.get(appConfig.algorithmEpsilonCF)),
            min_pts_cf=int(qconfig.get(appConfig.algorithmMinPtsCF)),
            eps_pw=float(qconfig.get(appConfig.algorithmEpsilonPW)),
            min_pts_pw=int(qconfig.get(appConfig.algorithmMinPtsPW)),
            eps_doa=float(qconfig.get(appConfig.algorithmEpsilonDOA)),
            min_pts_doa=int(qconfig.get(appConfig.algorithmMinPtsDOA)),
            clip_threshold_doa=float(qconfig.get(appConfig.algorithmClipThresholdDOA)),
        ),
        recognition=RecognitionConfigSnapshot(
            tolerance=float(qconfig.get(appConfig.recognizeTolerance)),
            min_confidence=float(qconfig.get(appConfig.recognizeMinConfidence)),
            max_candidates=int(qconfig.get(appConfig.recognizeMaxCandidates)),
        ),
        extract=ExtractConfigSnapshot(
            step=int(qconfig.get(appConfig.extractStep)),
            smooth_window=int(qconfig.get(appConfig.extractSmoothWindow)),
            outlier_threshold=float(qconfig.get(appConfig.extractOutlierThreshold)),
        ),
        merge=MergeConfigSnapshot(
            time_decay=float(qconfig.get(appConfig.mergeTimeDecay)),
            sim_threshold=float(qconfig.get(appConfig.mergeSimThreshold)),
            max_extrapolate=int(qconfig.get(appConfig.mergeMaxExtrapolate)),
            pri_equal_doa_tolerance=float(qconfig.get(appConfig.mergePriEqualDoaTolerance)),
        ),
        business=BusinessConfigSnapshot(
            auto_recognize_next_slice=bool(qconfig.get(appConfig.autoRecognizeNextSlice)),
            export_dir_path=str(qconfig.get(appConfig.exportDirPath)),
            auto_export=bool(qconfig.get(appConfig.autoExport)),
        ),
    )
```

- [ ] **Step 4: Implement registry**

Create `RadarIdentifySystem_PyQt6/runtime/session_registry.py`:

```python
"""运行态 Session 注册表。"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime

from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore


class SessionRegistry:
    """维护运行态 session 索引和 active session。"""

    def __init__(self, store: SessionStore | None = None) -> None:
        """初始化注册表。"""
        self.store = store or SessionStore()
        self._sessions: OrderedDict[str, ProcessingSession] = OrderedDict()
        self.active_session_id: str | None = None

    @property
    def active_session(self) -> ProcessingSession | None:
        """返回当前 active session。"""
        if self.active_session_id is None:
            return None
        return self._sessions.get(self.active_session_id)

    def register(self, session: ProcessingSession, persist: bool = True) -> ProcessingSession:
        """注册 session。"""
        self._sessions[session.session_id] = session
        self.active_session_id = session.session_id
        session.last_opened_at = datetime.now()
        if persist:
            self.store.upsert_session(session)
        return session

    def restore(self) -> list[ProcessingSession]:
        """从 store 恢复 session 列表。"""
        index = self.store.load_index()
        restored: list[ProcessingSession] = []
        for entry in index.sessions:
            session = self.store.load_session(entry.session_id)
            self._sessions[session.session_id] = session
            restored.append(session)
        self.active_session_id = index.active_session_id if index.active_session_id in self._sessions else None
        return restored

    def get(self, session_id: str) -> ProcessingSession | None:
        """按 ID 查询 session。"""
        return self._sessions.get(session_id)

    def all_sessions(self) -> list[ProcessingSession]:
        """返回全部 session。"""
        return list(self._sessions.values())

    def activate(self, session_id: str) -> ProcessingSession:
        """激活指定 session。"""
        session = self._sessions[session_id]
        session.last_opened_at = datetime.now()
        self.active_session_id = session_id
        self.store.upsert_session(session)
        return session

    def close(self, session_id: str) -> None:
        """关闭并删除指定 session。"""
        self._sessions.pop(session_id, None)
        self.store.delete_session(session_id)
        if self.active_session_id == session_id:
            self.active_session_id = next(reversed(self._sessions), None) if self._sessions else None
```

- [ ] **Step 5: Run registry tests**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_registry.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/runtime/session_config_factory.py RadarIdentifySystem_PyQt6/runtime/session_registry.py RadarIdentifySystem_PyQt6/tests/unit/test_session_registry.py
git commit -m "feat(session): add runtime session registry"
```

---

### Task 5: Split Parse Completion from Session Registration

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/app/signal_bus.py`
- Modify: `RadarIdentifySystem_PyQt6/runtime/workflows/import_workflow.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/controllers/home_controller.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_session_event_isolation.py`

- [ ] **Step 1: Write failing event isolation tests**

Create `RadarIdentifySystem_PyQt6/tests/unit/test_session_event_isolation.py`:

```python
"""Session 事件隔离测试。"""

from __future__ import annotations

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingSession


class _Receiver(QObject):
    """记录信号接收次数。"""

    def __init__(self) -> None:
        super().__init__()
        self.parse_count = 0
        self.import_count = 0

    def on_parse(self, _session: ProcessingSession) -> None:
        """记录解析完成事件。"""
        self.parse_count += 1

    def on_import(self, _session: ProcessingSession) -> None:
        """记录旧导入事件。"""
        self.import_count += 1


def test_parse_completed_is_separate_from_import_completed() -> None:
    """解析完成事件不应复用旧 import_completed。"""
    receiver = _Receiver()
    signal_bus.parse_completed.connect(receiver.on_parse)
    signal_bus.import_completed.connect(receiver.on_import)
    try:
        signal_bus.parse_completed.emit(ProcessingSession())
        assert receiver.parse_count == 1
        assert receiver.import_count == 0
    finally:
        signal_bus.parse_completed.disconnect(receiver.on_parse)
        signal_bus.import_completed.disconnect(receiver.on_import)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_event_isolation.py -q
```

Expected: FAIL with missing `parse_completed`.

- [ ] **Step 3: Add new signal bus events**

Modify `_SignalBus` in `RadarIdentifySystem_PyQt6/app/signal_bus.py`:

```python
    parse_completed = pyqtSignal(ProcessingSession)
    session_registered = pyqtSignal(str)
    session_activated = pyqtSignal(str)
    session_closed = pyqtSignal(str)
    session_metadata_changed = pyqtSignal(str)
```

- [ ] **Step 4: Emit `parse_completed` from import workflow**

Modify `_on_worker_finished()` in `runtime/workflows/import_workflow.py`:

```python
        if success:
            signal_bus.stage_finished.emit(session_id, "importing", None)
            if self._worker is not None:
                signal_bus.parse_completed.emit(self._worker.session)
        else:
            signal_bus.stage_failed.emit(session_id, "importing", None, message)
```

- [ ] **Step 5: Update home controller to listen to parse completion**

Modify `_connect_signals()` in `ui/controllers/home_controller.py`:

```python
        signal_bus.parse_completed.connect(self.render_import_dashboard)
```

Remove the old `signal_bus.import_completed.connect(self.render_import_dashboard)` line.

- [ ] **Step 6: Run event test**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_event_isolation.py -q
```

Expected: PASS.

- [ ] **Step 7: Run home dashboard tests**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_home_dashboard_format.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/app/signal_bus.py RadarIdentifySystem_PyQt6/runtime/workflows/import_workflow.py RadarIdentifySystem_PyQt6/ui/controllers/home_controller.py RadarIdentifySystem_PyQt6/tests/unit/test_session_event_isolation.py
git commit -m "feat(session): split parse completion event"
```

---

### Task 6: Add Dynamic Session Pages to MainWindow

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/ui/main_window.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py`

- [ ] **Step 1: Write failing tests for dynamic page methods**

Create `RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py`:

```python
"""主窗口动态 session 页面测试。"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from core.models.processing_session import ProcessingSession
from ui.main_window import MainWindow


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享 Qt 应用。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication(sys.argv[:1])
        return _APP
    return app


def test_main_window_creates_independent_session_interfaces() -> None:
    """主窗口应为不同 session 创建不同切片页面。"""
    _app()
    window = MainWindow()
    first = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    second = ProcessingSession(source_path="E:/data/b.xlsx", source_type="excel")

    first_interface = window.create_session_interface(first)
    second_interface = window.create_session_interface(second)

    assert first_interface is not second_interface
    assert window.session_interface(first.session_id) is first_interface
    assert window.session_interface(second.session_id) is second_interface
    assert first_interface.objectName() == f"sessionSliceInterface_{first.session_id}"
    assert second_interface.objectName() == f"sessionSliceInterface_{second.session_id}"

    window.close()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py -q
```

Expected: FAIL with missing `create_session_interface`.

- [ ] **Step 3: Implement dynamic page methods**

Modify `ui/main_window.py` imports:

```python
from core.models.processing_session import ProcessingSession
```

Add fields in `__init__` before `initNavigation()`:

```python
        self._session_interfaces: dict[str, SliceInterface] = {}
```

Add methods:

```python
    def create_session_interface(self, session: ProcessingSession) -> SliceInterface:
        """创建或激活 session 对应的切片页面。"""
        if session.session_id in self._session_interfaces:
            self.activate_session_interface(session.session_id)
            return self._session_interfaces[session.session_id]

        interface = SliceInterface(self, session=session)
        interface.setObjectName(f"sessionSliceInterface_{session.session_id}")
        self.addSubInterface(
            interface,
            FluentIcon.PIE_SINGLE,
            session.display_name,
            position=NavigationItemPosition.TOP,
        )
        self._session_interfaces[session.session_id] = interface
        self.activate_session_interface(session.session_id)
        return interface

    def session_interface(self, session_id: str) -> SliceInterface | None:
        """按 session_id 返回切片页面。"""
        return self._session_interfaces.get(session_id)

    def activate_session_interface(self, session_id: str) -> None:
        """切换到指定 session 页面。"""
        interface = self._session_interfaces.get(session_id)
        if interface is not None:
            self.switchTo(interface)

    def close_session_interface(self, session_id: str) -> None:
        """关闭指定 session 页面。"""
        interface = self._session_interfaces.pop(session_id, None)
        if interface is None:
            return
        self.removeInterface(interface, isDelete=True)
        self.switchTo(self.homeInterface)
```

- [ ] **Step 4: Run test and note next expected failure**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py -q
```

Expected: FAIL because `SliceInterface.__init__()` does not accept `session`.

- [ ] **Step 5: Commit after SliceInterface task completes**

Do not commit this task alone until Task 7 updates `SliceInterface`; these two are coupled by constructor signature.

---

### Task 7: Bind SliceInterface and Controllers to Their Own Session

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py`
- Modify: `RadarIdentifySystem_PyQt6/tests/unit/test_navigation_controls.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py`

- [ ] **Step 1: Write failing test for controller session ownership**

Append to `test_navigation_controls.py`:

```python
def test_slice_controller_uses_constructor_session(qt_app) -> None:
    """切片控制器应使用页面构造时绑定的 session。"""
    from core.models.processing_session import ProcessingSession
    from ui.interfaces.slice_interface import SliceInterface

    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    view = SliceInterface(session=session)

    assert view._session is session
    assert view._slice_controller.view._session is session

    view.deleteLater()
```

- [ ] **Step 2: Run targeted tests and verify failure**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_navigation_controls.py::test_slice_controller_uses_constructor_session -q
```

Expected: FAIL with unexpected keyword argument `session`.

- [ ] **Step 3: Update SliceInterface constructor**

Modify `SliceInterface.__init__` signature:

```python
    def __init__(
        self,
        parent: QWidget | None = None,
        session: ProcessingSession | None = None,
    ) -> None:
```

Add import:

```python
from core.models.processing_session import ProcessingSession
```

Before `_init_layout()`:

```python
        self._session = session or ProcessingSession()
```

- [ ] **Step 4: Remove session replacement from SliceController**

In `SliceController.__init__`, remove:

```python
        self.view._session = ProcessingSession()
```

In `_connect_signals()`, remove:

```python
        signal_bus.import_completed.connect(self._on_import_completed)
```

Keep `_on_import_completed` temporarily unused or delete it if no tests reference it. If deleting it, remove its import-only need for `ProcessingSession` only if unused elsewhere.

- [ ] **Step 5: Run controller and main window tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_navigation_controls.py::test_slice_controller_uses_constructor_session RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py -q
```

Expected: PASS.

- [ ] **Step 6: Run existing navigation tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_navigation_controls.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 6 and 7 together**

```powershell
git add RadarIdentifySystem_PyQt6/ui/main_window.py RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py RadarIdentifySystem_PyQt6/tests/unit/test_navigation_controls.py
git commit -m "feat(session): create independent slice pages"
```

---

### Task 8: Register Sessions from Home Import Action

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/ui/controllers/home_controller.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/main_window.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_session_event_isolation.py`

- [ ] **Step 1: Add failing test for import button registration path**

Append to `test_session_event_isolation.py`:

```python
def test_home_import_action_delegates_to_window_session_creation(qt_app) -> None:
    """主页导入按钮应委托窗口创建 session 页面。"""
    from core.models.processing_session import ProcessingSession
    from ui.controllers.home_controller import HomeController

    class _Panel:
        def __init__(self) -> None:
            self.created: list[ProcessingSession] = []

        def create_session_from_parsed(self, session: ProcessingSession) -> None:
            self.created.append(session)

    class _View(QObject):
        def __init__(self) -> None:
            super().__init__()
            self._window = _Panel()

        def window(self):
            return self._window

    view = _View()
    controller = HomeController.__new__(HomeController)
    controller.view = view
    controller._last_import_session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    controller._show_top_warning = lambda title, content: None

    HomeController.import_current_session(controller)

    assert view.window().created == [controller._last_import_session]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_event_isolation.py::test_home_import_action_delegates_to_window_session_creation -q
```

Expected: FAIL because `HomeController.import_current_session()` emits `import_completed`.

- [ ] **Step 3: Add MainWindow session creation entry**

In `MainWindow.__init__`, after `_session_interfaces` initialization:

```python
        self.session_registry = SessionRegistry()
```

Add import:

```python
from runtime.session_registry import SessionRegistry
from runtime.session_config_factory import create_session_config_from_global
from app.signal_bus import signal_bus
```

Add method:

```python
    def create_session_from_parsed(self, session: ProcessingSession) -> SliceInterface:
        """将解析完成的 session 注册并创建动态页面。"""
        session.config_snapshot = create_session_config_from_global()
        self.session_registry.register(session)
        interface = self.create_session_interface(session)
        signal_bus.session_registered.emit(session.session_id)
        signal_bus.session_activated.emit(session.session_id)
        return interface
```

- [ ] **Step 4: Update HomeController import action**

Replace `signal_bus.import_completed.emit(self._last_import_session)` with:

```python
        window = self.view.window()
        if window is not None and hasattr(window, "create_session_from_parsed"):
            window.create_session_from_parsed(self._last_import_session)
        else:
            self._show_top_warning("导入失败", "当前窗口不支持创建 Session 页面。")
            return
```

Keep the success InfoBar after successful creation.

- [ ] **Step 5: Run focused test**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_event_isolation.py::test_home_import_action_delegates_to_window_session_creation -q
```

Expected: PASS.

- [ ] **Step 6: Run home/event tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_event_isolation.py RadarIdentifySystem_PyQt6\tests\unit\test_home_dashboard_format.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/ui/controllers/home_controller.py RadarIdentifySystem_PyQt6/ui/main_window.py RadarIdentifySystem_PyQt6/tests/unit/test_session_event_isolation.py
git commit -m "feat(session): register parsed sessions from home"
```

---

### Task 9: Add Session-Aware Config Item and Setting Cards

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/core/models/session_config.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/components/spin_box_setting_card.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/components/double_spin_box_setting_card.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_session_config_item.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py`

- [ ] **Step 1: Write failing tests for SessionConfigItem writer**

Create `RadarIdentifySystem_PyQt6/tests/unit/test_session_config_item.py`:

```python
"""Session 配置项适配测试。"""

from __future__ import annotations

from qfluentwidgets import RangeValidator

from core.models.session_config import SessionConfigItem, SessionConfigSnapshot


def test_session_config_item_updates_snapshot_and_calls_save() -> None:
    """SessionConfigItem 应写入快照并触发保存回调。"""
    snapshot = SessionConfigSnapshot.default()
    calls: list[str] = []
    item = SessionConfigItem(
        snapshot,
        "clustering.eps_cf",
        default=2.0,
        validator=RangeValidator(0.01, 50.0),
        on_changed=lambda: calls.append("saved"),
    )

    item.set(9.5)

    assert snapshot.clustering.eps_cf == 9.5
    assert calls == ["saved"]
```

- [ ] **Step 2: Run test**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_config_item.py -q
```

Expected: PASS if Task 1 implemented `SessionConfigItem` correctly.

- [ ] **Step 3: Add config writer support to custom cards**

Modify `SpinBoxSettingCard.__init__` signature:

```python
    def __init__(
        self,
        configItem,
        icon: FluentIconBase,
        title: str,
        content: str | None = None,
        unit: str | None = None,
        parent: QWidget | None = None,
        config_writer=None,
    ):
```

Inside `__init__`:

```python
        self.config_writer = config_writer or qconfig
```

Replace:

```python
        self.spinBox.setValue(qconfig.get(configItem))
```

with:

```python
        self.spinBox.setValue(self.config_writer.get(configItem))
```

Replace `_onValueChanged` body with:

```python
        self.config_writer.set(self.configItem, value)
```

Apply the same pattern to `DoubleSpinBoxSettingCard`, replacing `qconfig.get/set` with `self.config_writer.get/set`.

- [ ] **Step 4: Add SessionConfigWriter**

Append to `session_config.py`:

```python
class SessionConfigWriter:
    """为设置卡提供 get/set 接口的 session 配置写入器。"""

    def get(self, item: SessionConfigItem) -> object:
        """读取 session 配置项。"""
        return item.value

    def set(self, item: SessionConfigItem, value: object) -> None:
        """写入 session 配置项。"""
        item.set(value)
```

- [ ] **Step 5: Update SliceParamPanel constructor**

Change `SliceParamPanel.__init__` signature:

```python
    def __init__(
        self,
        session: ProcessingSession,
        on_config_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
```

Create session config item for auto-recognize:

```python
        self.auto_recognize_item = SessionConfigItem(
            session.config_snapshot,
            "business.auto_recognize_next_slice",
            default=True,
            validator=BoolValidator(),
            on_changed=on_config_changed,
        )
```

For `SwitchSettingCard`, do not use global qconfig. If built-in `SwitchSettingCard` cannot accept writer, replace it with a small local card or connect manually:

```python
        self.auto_recognize_card = SwitchSettingCard(
            icon=FluentIcon.PLAY,
            title="自动识别",
            content="切换下一片时自动执行识别工作流",
            configItem=None,
            parent=self,
        )
        self.auto_recognize_card.setChecked(bool(self.auto_recognize_item.value))
        self.auto_recognize_card.checkedChanged.connect(self.auto_recognize_item.set)
        self.auto_recognize_item.valueChanged.connect(self.auto_recognize_card.setChecked)
```

- [ ] **Step 6: Update SliceInterface drawer construction**

In `SliceInterface._create_right_column()`, replace:

```python
        self.slice_param_panel: SliceParamPanel = SliceParamPanel(
            self.slice_param_drawer
        )
```

with:

```python
        self.slice_param_panel: SliceParamPanel = SliceParamPanel(
            session=self._session,
            on_config_changed=lambda: None,
            parent=self.slice_param_drawer,
        )
```

The `lambda: None` will be replaced by store-backed save callback in Task 10.

- [ ] **Step 7: Update tests**

In `test_slice_param_panel.py`, instantiate with a session:

```python
from core.models.processing_session import ProcessingSession
panel = SliceParamPanel(session=ProcessingSession())
```

Assert:

```python
assert panel.auto_recognize_item.value is True
```

- [ ] **Step 8: Run tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_config_item.py RadarIdentifySystem_PyQt6\tests\unit\test_slice_param_panel.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/core/models/session_config.py RadarIdentifySystem_PyQt6/ui/components/spin_box_setting_card.py RadarIdentifySystem_PyQt6/ui/components/double_spin_box_setting_card.py RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py RadarIdentifySystem_PyQt6/tests/unit/test_session_config_item.py RadarIdentifySystem_PyQt6/tests/unit/test_slice_param_panel.py
git commit -m "feat(session): bind drawer settings to session config"
```

---

### Task 10: Use Session Config and Model Selection in Identify Workflow

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py`
- Modify: `RadarIdentifySystem_PyQt6/runtime/workflows/identify_workflow.py`
- Modify: `RadarIdentifySystem_PyQt6/runtime/threading/identify_worker.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_identify_worker_clustering_params.py`

- [ ] **Step 1: Write failing test for worker using injected params**

Append to `test_identify_worker_clustering_params.py`:

```python
def test_identify_worker_prefers_injected_session_params() -> None:
    """识别 worker 应使用注入的 session 参数。"""
    from core.models.algorithm_params import ClusteringParams, RecognitionParams
    from runtime.threading.identify_worker import IdentifyWorker

    assert "cluster_params" in IdentifyWorker.__init__.__code__.co_varnames
    assert isinstance(ClusteringParams(eps_cf=7.0), ClusteringParams)
    assert isinstance(RecognitionParams(tolerance=0.25), RecognitionParams)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_identify_worker_clustering_params.py::test_identify_worker_prefers_injected_session_params -q
```

Expected: FAIL because `IdentifyWorker.__init__` lacks `cluster_params`.

- [ ] **Step 3: Update IdentifyWorker constructor**

Modify imports:

```python
from core.models.algorithm_params import ClusteringParams, RecognitionParams
```

Update `__init__`:

```python
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
```

Set fields:

```python
        self._cluster_params = cluster_params
        self._recognize_params = recognize_params
```

In `run()`, replace:

```python
            clustering_params = get_clustering_params()
            recognition_params = get_recognition_params()
```

with:

```python
            clustering_params = self._cluster_params
            recognition_params = self._recognize_params
```

Remove unused import from `runtime.algorithm_params`.

- [ ] **Step 4: Update IdentifyWorkflow to assemble params from session**

Add helper functions in `identify_workflow.py`:

```python
def _cluster_params_from_session(session: ProcessingSession) -> ClusteringParams:
    """从 session 子配置组装聚类参数。"""
    cfg = session.config_snapshot.clustering
    return ClusteringParams(
        eps_cf=cfg.eps_cf,
        min_pts_cf=cfg.min_pts_cf,
        eps_pw=cfg.eps_pw,
        min_pts_pw=cfg.min_pts_pw,
        eps_doa=cfg.eps_doa,
        min_pts_doa=cfg.min_pts_doa,
        clip_threshold_doa=cfg.clip_threshold_doa,
    )


def _recognition_params_from_session(session: ProcessingSession) -> RecognitionParams:
    """从 session 子配置组装识别参数。"""
    cfg = session.config_snapshot.recognition
    return RecognitionParams(
        tolerance=cfg.tolerance,
        min_confidence=cfg.min_confidence,
        max_candidates=cfg.max_candidates,
    )
```

Replace global model reads:

```python
            pa_path = session.model_selection.pa_model_path
            dtoa_path = session.model_selection.dtoa_model_path
```

When creating worker:

```python
            self._worker = IdentifyWorker(
                session=session,
                slice_index=slice_index,
                inference_service=self._inference_service,
                cluster_params=_cluster_params_from_session(session),
                recognize_params=_recognition_params_from_session(session),
                parent=self,
            )
```

- [ ] **Step 5: Update IdentifyController validation**

Replace `_validate_enabled_models()` internals:

```python
        selection = self.view._session.model_selection
        pa_path = selection.pa_model_path
        dtoa_path = selection.dtoa_model_path
```

Keep the file existence checks.

- [ ] **Step 6: Run identify tests**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_identify_worker_clustering_params.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py RadarIdentifySystem_PyQt6/runtime/workflows/identify_workflow.py RadarIdentifySystem_PyQt6/runtime/threading/identify_worker.py RadarIdentifySystem_PyQt6/tests/unit/test_identify_worker_clustering_params.py
git commit -m "feat(session): use session params for identify workflow"
```

---

### Task 11: Restore Session Interfaces on Startup

**Files:**
- Modify: `RadarIdentifySystem_PyQt6/ui/main_window.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py`

- [ ] **Step 1: Add failing restore test**

Append to `test_main_window_sessions.py`:

```python
def test_main_window_restores_session_interfaces_from_registry(tmp_path) -> None:
    """主窗口应能从 registry 恢复动态 session 页面。"""
    _app()
    from infra.session_store import SessionStore
    from runtime.session_registry import SessionRegistry

    store = SessionStore(tmp_path)
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")
    store.upsert_session(session)

    window = MainWindow()
    window.session_registry = SessionRegistry(store)
    restored = window.restore_session_interfaces()

    assert restored == [session.session_id]
    assert window.session_interface(session.session_id) is not None
    window.close()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py::test_main_window_restores_session_interfaces_from_registry -q
```

Expected: FAIL with missing `restore_session_interfaces`.

- [ ] **Step 3: Implement restore method**

Add to `MainWindow`:

```python
    def restore_session_interfaces(self) -> list[str]:
        """从注册表恢复动态 session 页面。"""
        restored_sessions = self.session_registry.restore()
        restored_ids: list[str] = []
        for session in restored_sessions:
            self.create_session_interface(session)
            restored_ids.append(session.session_id)
        if self.session_registry.active_session_id:
            self.activate_session_interface(self.session_registry.active_session_id)
        return restored_ids
```

Call it at the end of `__init__` after `initNavigation()` only if this does not break tests:

```python
        self.restore_session_interfaces()
```

If tests need an empty store, inject default store that reads existing config. Unit tests that instantiate `MainWindow` may need to set an empty temp registry after construction.

- [ ] **Step 4: Run main window tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/ui/main_window.py RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py
git commit -m "feat(session): restore session pages on startup"
```

---

### Task 12: Add Minimal Home Session Manager Panel

**Files:**
- Create: `RadarIdentifySystem_PyQt6/ui/components/session_manager_panel.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/components/__init__.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/interfaces/home_interface.py`
- Modify: `RadarIdentifySystem_PyQt6/ui/main_window.py`
- Test: `RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py`

- [ ] **Step 1: Write failing test for session manager refresh**

Append to `test_main_window_sessions.py`:

```python
def test_home_session_manager_lists_created_session() -> None:
    """创建 session 后主页 session 管理器应能显示该 session。"""
    _app()
    window = MainWindow()
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")

    window.create_session_from_parsed(session)

    titles = window.homeInterface.session_manager_panel.session_titles()
    assert session.display_name in titles
    window.close()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py::test_home_session_manager_lists_created_session -q
```

Expected: FAIL with missing `session_manager_panel`.

- [ ] **Step 3: Create SessionManagerPanel**

Create `ui/components/session_manager_panel.py`:

```python
"""主页 session 管理面板。"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton, SimpleCardWidget

from core.models.processing_session import ProcessingSession


class SessionManagerPanel(SimpleCardWidget):
    """展示并管理当前 session 列表。"""

    sessionActivated = pyqtSignal(str)
    sessionCloseRequested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化 session 管理面板。"""
        super().__init__(parent)
        self.setObjectName("sessionManagerPanel")
        self._sessions: list[ProcessingSession] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        self._empty_label = BodyLabel("暂无 Session", self)
        self._layout.addWidget(self._empty_label)

    def set_sessions(self, sessions: list[ProcessingSession]) -> None:
        """刷新 session 列表。"""
        self._sessions = sessions
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not sessions:
            self._empty_label = BodyLabel("暂无 Session", self)
            self._layout.addWidget(self._empty_label)
            return
        for session in sessions:
            button = PushButton(session.display_name, self)
            button.clicked.connect(lambda _checked=False, sid=session.session_id: self.sessionActivated.emit(sid))
            self._layout.addWidget(button)

    def session_titles(self) -> list[str]:
        """返回当前显示的 session 标题。"""
        return [session.display_name for session in self._sessions]
```

- [ ] **Step 4: Export component and place it in HomeInterface right column**

Modify `ui/components/__init__.py`:

```python
from .session_manager_panel import SessionManagerPanel
```

Modify `home_interface.py` imports:

```python
    SessionManagerPanel,
```

In `_create_right_column()`, replace blank layout with:

```python
        self.session_manager_panel = SessionManagerPanel(column)
        layout.addWidget(self.session_manager_panel)
```

- [ ] **Step 5: Refresh panel after session changes**

Add to `MainWindow`:

```python
    def refresh_session_manager_panel(self) -> None:
        """刷新主页 session 管理器列表。"""
        if hasattr(self.homeInterface, "session_manager_panel"):
            self.homeInterface.session_manager_panel.set_sessions(
                self.session_registry.all_sessions()
            )
```

Call it after register, close, and restore:

```python
        self.refresh_session_manager_panel()
```

Connect panel activation in `connectSignalToSlot()` after home is created, or in `initNavigation()` after fixed pages exist:

```python
        self.homeInterface.session_manager_panel.sessionActivated.connect(
            self.activate_session_interface
        )
```

- [ ] **Step 6: Run session manager test**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py::test_home_session_manager_lists_created_session -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add RadarIdentifySystem_PyQt6/ui/components/session_manager_panel.py RadarIdentifySystem_PyQt6/ui/components/__init__.py RadarIdentifySystem_PyQt6/ui/interfaces/home_interface.py RadarIdentifySystem_PyQt6/ui/main_window.py RadarIdentifySystem_PyQt6/tests/unit/test_main_window_sessions.py
git commit -m "feat(session): add home session manager"
```

---

### Task 13: Final Verification and Cleanup

**Files:**
- Modify only files required by failing tests.
- Update: `RadarIdentifySystem_PyQt6/docs/operateLog.md`

- [ ] **Step 1: Run targeted new tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest `
  RadarIdentifySystem_PyQt6\tests\unit\test_session_config_snapshot.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_session_store.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_session_registry.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_session_event_isolation.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_session_config_item.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py -q
```

Expected: PASS.

- [ ] **Step 2: Run related existing tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; D:\Miniforge3\envs\pyqt6\python.exe -m pytest `
  RadarIdentifySystem_PyQt6\tests\unit\test_navigation_controls.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_slice_param_panel.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_model_selection_card.py `
  RadarIdentifySystem_PyQt6\tests\unit\test_identify_worker_clustering_params.py -q
```

Expected: PASS.

- [ ] **Step 3: Run compileall**

Run:

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m compileall RadarIdentifySystem_PyQt6\core RadarIdentifySystem_PyQt6\runtime RadarIdentifySystem_PyQt6\infra RadarIdentifySystem_PyQt6\ui
```

Expected: command exits with code 0.

- [ ] **Step 4: Run diff hygiene check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Update operation log**

Run:

```powershell
Get-Date -Format 'yyyy-MM-dd HH:mm'
```

Expected: PowerShell prints one timestamp such as `2026-06-18 15:19`.

Append an operation-log entry to `RadarIdentifySystem_PyQt6/docs/operateLog.md`. The first line must use the timestamp printed by the command above:

```markdown
- 时间：使用 Get-Date 命令输出的实际时间
- 操作类型：新增
- 影响文件：
  - `E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\core\models\session_config.py`
  - `E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\core\models\session_model.py`
  - `E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\infra\session_store.py`
  - `E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\runtime\session_registry.py`
  - `E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\main_window.py`
- 变更摘要：实现 session 独立化骨架、动态切片页面、session 子配置和持久化恢复。
- 原因：支持每个导入文件拥有独立 session、配置、模型选择和页面生命周期。
- 测试状态：已测试（记录实际通过的 pytest 与 compileall 命令）
```

- [ ] **Step 6: Commit final log update**

```powershell
git add RadarIdentifySystem_PyQt6/docs/operateLog.md
git commit -m "docs(session): record session isolation implementation"
```
