"""应用级事件模型定义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ImportFinishedEvent:
    """数据导入完成事件。"""

    file_path: str
    source_type: str
    total_pulses: int
    filtered_pulses: int
    band: str


@dataclass(slots=True)
class SliceReadyEvent:
    """切片结果就绪事件。"""

    slice_count: int
    time_ranges: list[tuple[float, float]]


@dataclass(slots=True)
class IdentifyProgressEvent:
    """识别进度事件。"""

    current_slice_idx: int
    total_slices: int
    progress: float


@dataclass(slots=True)
class ClusterReadyEvent:
    """聚类结果就绪事件。"""

    slice_idx: int
    cluster_idx: int
    dim_name: str
    is_valid: bool


@dataclass(slots=True)
class MergeFinishedEvent:
    """合并流程完成事件。"""

    slice_idx: int
    merged_count: int


@dataclass(slots=True)
class ExportProgressEvent:
    """导出进度事件。"""

    progress: float
    message: str


@dataclass(slots=True)
class ErrorEvent:
    """统一错误事件。"""

    code: str
    message: str
    detail: str
    trace_id: str
