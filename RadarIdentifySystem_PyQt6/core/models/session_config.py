"""Session 子配置数据契约。

该模块定义可序列化的 session 级配置快照，以及用于绑定快照字段的轻量配置项。
快照对象不依赖 appConfig、Qt UI 或磁盘持久化。

Example:
    >>> snapshot = SessionConfigSnapshot.default()
    >>> snapshot.clustering.eps_cf = 3.5
    >>> restored = SessionConfigSnapshot.from_dict(snapshot.to_dict())
    >>> restored.clustering.eps_cf
    3.5
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal
from qfluentwidgets import BoolValidator, RangeValidator


ValidatorType = BoolValidator | RangeValidator


def _coerce_dataclass(cls: type[Any], payload: dict[str, Any]) -> Any:
    """按 dataclass 默认值恢复字典。

    Args:
        cls [type[Any]]: 目标 dataclass 类型，必须提供 ``default`` 类方法。
        payload [dict[str, Any]]: 外部读取的配置字典，仅已知字段会被写入。

    Returns:
        Any: 恢复后的 dataclass 实例，缺失字段使用当前默认值。

    Raises:
        无显式抛出异常。

    Example:
        >>> _coerce_dataclass(ClusteringConfigSnapshot, {"eps_cf": 4.0}).eps_cf
        4.0
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
    """聚类参数快照。

    Attributes:
        eps_cf: 载频聚类半径。
        min_pts_cf: 载频聚类最小点数。
        eps_pw: 脉宽聚类半径。
        min_pts_pw: 脉宽聚类最小点数。
        eps_doa: 方位聚类半径。
        min_pts_doa: 方位聚类最小点数。
        clip_threshold_doa: 方位裁剪阈值。
    """

    eps_cf: float = 2.0
    min_pts_cf: int = 2
    eps_pw: float = 0.2
    min_pts_pw: int = 2
    eps_doa: float = 16.8
    min_pts_doa: int = 2
    clip_threshold_doa: float = 95.0

    @classmethod
    def default(cls) -> "ClusteringConfigSnapshot":
        """返回聚类配置默认值。

        Returns:
            ClusteringConfigSnapshot: 新建的聚类配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> ClusteringConfigSnapshot.default().min_pts_cf
            2
        """
        return cls()


@dataclass
class RecognitionConfigSnapshot:
    """识别参数快照。

    Attributes:
        tolerance: 识别容差。
        min_confidence: 最小置信度。
        max_candidates: 最大候选数量。
    """

    tolerance: float = 0.5
    min_confidence: float = 0.8
    max_candidates: int = 5

    @classmethod
    def default(cls) -> "RecognitionConfigSnapshot":
        """返回识别配置默认值。

        Returns:
            RecognitionConfigSnapshot: 新建的识别配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> RecognitionConfigSnapshot.default().max_candidates
            5
        """
        return cls()


@dataclass
class ExtractConfigSnapshot:
    """参数提取配置快照。

    Attributes:
        step: 提取步长。
        smooth_window: 平滑窗口大小。
        outlier_threshold: 异常值阈值。
    """

    step: int = 1
    smooth_window: int = 5
    outlier_threshold: float = 3.0

    @classmethod
    def default(cls) -> "ExtractConfigSnapshot":
        """返回提取配置默认值。

        Returns:
            ExtractConfigSnapshot: 新建的提取配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> ExtractConfigSnapshot.default().smooth_window
            5
        """
        return cls()


@dataclass
class MergeConfigSnapshot:
    """合并配置快照。

    Attributes:
        time_decay: 时间衰减系数。
        sim_threshold: 相似度阈值。
        max_extrapolate: 最大外推次数。
        pri_equal_doa_tolerance: PRI 相同时的方位容差。
    """

    time_decay: float = 0.9
    sim_threshold: float = 0.8
    max_extrapolate: int = 3
    pri_equal_doa_tolerance: float = 20.0

    @classmethod
    def default(cls) -> "MergeConfigSnapshot":
        """返回合并配置默认值。

        Returns:
            MergeConfigSnapshot: 新建的合并配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> MergeConfigSnapshot.default().max_extrapolate
            3
        """
        return cls()


@dataclass
class BusinessConfigSnapshot:
    """Session 级业务配置快照。

    Attributes:
        auto_recognize_next_slice: 是否自动识别下一切片。
        export_dir_path: 导出目录路径。
        auto_export: 是否自动导出。
    """

    auto_recognize_next_slice: bool = True
    export_dir_path: str = ""
    auto_export: bool = False

    @classmethod
    def default(cls) -> "BusinessConfigSnapshot":
        """返回业务配置默认值。

        Returns:
            BusinessConfigSnapshot: 新建的业务配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> BusinessConfigSnapshot.default().auto_export
            False
        """
        return cls()


@dataclass
class SessionConfigSnapshot:
    """Session 子配置总快照。

    Attributes:
        schema_version: 配置结构版本号。
        clustering: 聚类配置快照。
        recognition: 识别配置快照。
        extract: 参数提取配置快照。
        merge: 合并配置快照。
        business: session 级业务配置快照。
    """

    SCHEMA_VERSION = 1

    schema_version: int = SCHEMA_VERSION
    clustering: ClusteringConfigSnapshot = field(default_factory=ClusteringConfigSnapshot.default)
    recognition: RecognitionConfigSnapshot = field(default_factory=RecognitionConfigSnapshot.default)
    extract: ExtractConfigSnapshot = field(default_factory=ExtractConfigSnapshot.default)
    merge: MergeConfigSnapshot = field(default_factory=MergeConfigSnapshot.default)
    business: BusinessConfigSnapshot = field(default_factory=BusinessConfigSnapshot.default)

    @classmethod
    def default(cls) -> "SessionConfigSnapshot":
        """返回完整 session 子配置默认值。

        Returns:
            SessionConfigSnapshot: 新建的完整配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> SessionConfigSnapshot.default().schema_version
            1
        """
        return cls()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionConfigSnapshot":
        """从字典恢复配置快照。

        Args:
            payload [dict[str, Any]]: session 配置 JSON 字典，缺失字段会补默认值。

        Returns:
            SessionConfigSnapshot: 恢复后的配置快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> restored = SessionConfigSnapshot.from_dict({"clustering": {"eps_cf": 4.0}})
            >>> restored.clustering.eps_cf
            4.0
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
        """转换为可写入 JSON 的字典。

        Returns:
            dict[str, Any]: 包含 schema 版本和各子配置的纯字典。

        Raises:
            无显式抛出异常。

        Example:
            >>> SessionConfigSnapshot.default().to_dict()["schema_version"]
            1
        """
        return asdict(self)


class SessionConfigItem(QObject):
    """绑定到 session 配置快照字段的轻量配置项。

    Attributes:
        valueChanged: 字段值变更信号。
        snapshot: 目标 session 配置快照。
        group: 字段路径所属分组。
        name: 字段名称。
        path: 点号分隔字段路径。
        validator: 可选 qfluentwidgets 校验器。
        defaultValue: 配置项默认值。
        value: 当前字段值。
    """

    valueChanged = pyqtSignal(object)

    def __init__(
        self,
        snapshot: SessionConfigSnapshot,
        path: str,
        default: object,
        validator: ValidatorType | None = None,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        """创建 session 配置项。

        Args:
            snapshot [SessionConfigSnapshot]: 目标 session 配置快照。
            path [str]: 点号分隔的字段路径，例如 ``clustering.eps_cf``。
            default [object]: 默认值。
            validator [ValidatorType | None]: qfluentwidgets 校验器，默认不校验。
            on_changed [Callable[[], None] | None]: 值变化后的保存回调，默认不回调。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当字段路径不合法时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> item = SessionConfigItem(snapshot, "clustering.eps_cf", 2.0)
            >>> item.set(3.5)
            >>> snapshot.clustering.eps_cf
            3.5
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
        """返回当前字段值。

        Returns:
            object: 当前绑定字段的值。

        Raises:
            ValueError: 当字段路径不合法时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> SessionConfigItem(snapshot, "recognition.max_candidates", 5).value
            5
        """
        return self._read()

    @value.setter
    def value(self, new_value: object) -> None:
        self.set(new_value)

    def set(self, new_value: object) -> None:
        """设置当前字段值并触发保存回调。

        Args:
            new_value [object]: 需要写入的新值，会先经过可选校验器修正。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当字段路径不合法时抛出。

        Example:
            >>> snapshot = SessionConfigSnapshot.default()
            >>> item = SessionConfigItem(snapshot, "business.auto_export", False)
            >>> item.set(True)
            >>> item.value
            True
        """
        corrected = self.validator.correct(new_value) if self.validator else new_value
        old_value = self._read()
        if old_value == corrected:
            return

        # 写入快照后再发出信号，确保订阅方读取到最新值。
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
