"""Session 子配置数据契约。

该模块只定义可序列化的 session 级配置快照，不依赖 appConfig、Qt UI 或磁盘。

Example:
    >>> snapshot = SessionConfigSnapshot.default()
    >>> snapshot.clustering.eps_cf = 3.5
    >>> restored = SessionConfigSnapshot.from_dict(snapshot.to_dict())
    >>> restored.clustering.eps_cf
    3.5
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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


def _coerce_schema_version(value: object) -> int:
    """恢复旧配置后统一升级为当前配置结构版本号。"""
    try:
        int(value)
    except (TypeError, ValueError):
        pass
    return SessionConfigSnapshot.SCHEMA_VERSION


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
        greedy_strategy: 是否采用贪婪策略。
        pa_confidence_threshold: PA 预测置信度门限。
        pa_confidence_weight: PA 置信度相对权重。
        dtoa_confidence_threshold: DTOA 预测置信度门限。
        dtoa_confidence_weight: DTOA 置信度相对权重。
        joint_confidence_threshold: 严格策略联合概率门限。
    """

    greedy_strategy: bool = True
    pa_confidence_threshold: float = 0.5
    pa_confidence_weight: float = 0.6
    dtoa_confidence_threshold: float = 0.5
    dtoa_confidence_weight: float = 0.4
    joint_confidence_threshold: float = 0.8

    @classmethod
    def default(cls) -> "RecognitionConfigSnapshot":
        """返回识别配置默认值。

        Returns:
            RecognitionConfigSnapshot: 新建的识别配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> RecognitionConfigSnapshot.default().greedy_strategy
            True
        """
        return cls()


@dataclass
class ExtractConfigSnapshot:
    """参数提取配置快照。

    Attributes:
        eps_cf: CF 参数提取邻域半径。
        min_pts_cf: CF 参数提取最小邻居点数。
        threshold_ratio_cf: CF 参数提取门限率，单位为百分比。
        eps_pw: PW 参数提取邻域半径。
        min_pts_pw: PW 参数提取最小邻居点数。
        threshold_ratio_pw: PW 参数提取门限率，单位为百分比。
        eps_pri: PRI 参数提取邻域半径。
        min_pts_pri: PRI 参数提取最小邻居点数。
        threshold_ratio_pri: PRI 参数提取门限率，单位为百分比。
        filter_threshold_pri: PRI 过滤门限。
        harmonic_tolerance_pri: PRI 谐波抑制容差。
    """

    eps_cf: float = 2.0
    min_pts_cf: int = 4
    threshold_ratio_cf: float = 10.0
    eps_pw: float = 0.2
    min_pts_pw: int = 4
    threshold_ratio_pw: float = 10.0
    eps_pri: float = 0.2
    min_pts_pri: int = 3
    threshold_ratio_pri: float = 10.0
    filter_threshold_pri: float = 2.0
    harmonic_tolerance_pri: float = 0.1

    @classmethod
    def default(cls) -> "ExtractConfigSnapshot":
        """返回提取配置默认值。

        Returns:
            ExtractConfigSnapshot: 新建的提取配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> ExtractConfigSnapshot.default().min_pts_pri
            3
        """
        return cls()


@dataclass
class MergeConfigSnapshot:
    """当前Session的合并配置占位快照。

    当前合并准则仍使用硬编码规则，本模型只验证全局配置和Session独立配置
    的完整链路。未来出现真实合并参数时，应删除占位字段并在此定义实际字段；
    识别后的基准判别只读取本快照，合并面板临时参数不得写回本对象。

    Attributes:
        placeholder_value [float]: 配置链路占位值，当前合并算法不得读取。
    """

    placeholder_value: float = 0.0

    @classmethod
    def default(cls) -> "MergeConfigSnapshot":
        """返回合并配置默认值。

        Returns:
            MergeConfigSnapshot: 新建的合并配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> MergeConfigSnapshot.default().placeholder_value
            0.0
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
class PlotConfigSnapshot:
    """绘图配置快照。

    Attributes:
        only_show_identified: 绘图展示模式，`ALL` 表示展示全部聚类结果，
            `IDENTIFIED_ONLY` 表示仅展示识别后结果。
        scale_mode: 图像拉伸模式，控制切片图像如何缩放展示。
    """

    only_show_identified: str = "IDENTIFIED_ONLY"
    scale_mode: str = "STRETCH"

    @classmethod
    def default(cls) -> "PlotConfigSnapshot":
        """返回绘图配置默认值。

        Returns:
            PlotConfigSnapshot: 新建的绘图配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> PlotConfigSnapshot.default().only_show_identified
            'IDENTIFIED_ONLY'
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
        plot: 绘图配置快照。
    """

    SCHEMA_VERSION = 3

    schema_version: int = SCHEMA_VERSION
    clustering: ClusteringConfigSnapshot = field(default_factory=ClusteringConfigSnapshot.default)
    recognition: RecognitionConfigSnapshot = field(default_factory=RecognitionConfigSnapshot.default)
    extract: ExtractConfigSnapshot = field(default_factory=ExtractConfigSnapshot.default)
    merge: MergeConfigSnapshot = field(default_factory=MergeConfigSnapshot.default)
    business: BusinessConfigSnapshot = field(default_factory=BusinessConfigSnapshot.default)
    plot: PlotConfigSnapshot = field(default_factory=PlotConfigSnapshot.default)

    @classmethod
    def default(cls) -> "SessionConfigSnapshot":
        """返回完整 session 子配置默认值。

        Returns:
            SessionConfigSnapshot: 新建的完整配置默认快照。

        Raises:
            无显式抛出异常。

        Example:
            >>> SessionConfigSnapshot.default().schema_version
            3
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
            schema_version=_coerce_schema_version(data.get("schema_version", cls.SCHEMA_VERSION)),
            clustering=_coerce_dataclass(ClusteringConfigSnapshot, data.get("clustering", {})),
            recognition=_coerce_dataclass(RecognitionConfigSnapshot, data.get("recognition", {})),
            extract=_coerce_dataclass(ExtractConfigSnapshot, data.get("extract", {})),
            merge=_coerce_dataclass(MergeConfigSnapshot, data.get("merge", {})),
            business=_coerce_dataclass(BusinessConfigSnapshot, data.get("business", {})),
            plot=_coerce_dataclass(PlotConfigSnapshot, data.get("plot", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 JSON 的字典。

        Returns:
            dict[str, Any]: 包含 schema 版本和各子配置的纯字典。

        Raises:
            无显式抛出异常。

        Example:
            >>> SessionConfigSnapshot.default().to_dict()["schema_version"]
            3
        """
        return asdict(self)
