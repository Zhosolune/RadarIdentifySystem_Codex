# -*- coding: utf-8 -*-
"""core/models — 核心数据模型包。"""

from .pulse_batch import (
    COL_CF,
    COL_DOA,
    COL_PA,
    COL_PDOA,
    COL_PW,
    COL_TOA,
    PULSE_COLUMN_COUNT,
    PulseBatch,
)
from .slice_result import PreprocessResult, SliceResult
from .dashboard_info import ExcelDashboardInfo, FileDashboardInfo
from .data_package import DataPackage
from .processing_session import ProcessingMode, ProcessingSession, ProcessingStage
from .algorithm_params import (
    ClusteringParams,
    RecognitionParams,
    ExtractParams,
    MergeParams,
)
from .extraction_result import ExtractedClusterParams
from .merge_result import (
    MergeGroup,
    MergePlan,
    MergeResult,
    MergedClusterResult,
    SliceMergePlan,
    SliceMergeResult,
)
from .recognition_result import (
    DTOA_LABEL_NAMES,
    NON_RADAR_LABEL,
    PA_LABEL_NAMES,
    RECOGNITION_CLASS_COUNT,
    ClusterRecognition,
    SliceRecognitionResult,
    RecognitionResult,
)
from .session_config import (
    BusinessConfigSnapshot,
    ClusteringConfigSnapshot,
    ExtractConfigSnapshot,
    MergeConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigSnapshot,
)
from .session_model import ActiveModelCandidate, SessionModelSelection

__all__ = [
    "PulseBatch",
    "COL_CF", "COL_PW", "COL_PA", "COL_DOA", "COL_PDOA", "COL_TOA",
    "PULSE_COLUMN_COUNT",
    "PreprocessResult",
    "SliceResult",
    "ExcelDashboardInfo",
    "FileDashboardInfo",
    "DataPackage",
    "ProcessingMode",
    "ProcessingSession",
    "ProcessingStage",
    "ClusteringParams",
    "RecognitionParams",
    "ExtractParams",
    "MergeParams",
    "ExtractedClusterParams",
    "MergeResult",
    "MergedClusterResult",
    "SliceMergeResult",
    "DTOA_LABEL_NAMES",
    "NON_RADAR_LABEL",
    "PA_LABEL_NAMES",
    "RECOGNITION_CLASS_COUNT",
    "ClusterRecognition",
    "SliceRecognitionResult",
    "RecognitionResult",
    "BusinessConfigSnapshot",
    "ClusteringConfigSnapshot",
    "ExtractConfigSnapshot",
    "MergeConfigSnapshot",
    "RecognitionConfigSnapshot",
    "SessionConfigSnapshot",
    "ActiveModelCandidate",
    "SessionModelSelection",
]
