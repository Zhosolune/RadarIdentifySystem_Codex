"""识别结果数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True, slots=True)
class ClusterRecognition:
    """单个簇的识别结果。

    功能描述：
        记录单个簇经过 PA 和 DTOA 维度推理后的预测标签、置信度以及综合判定结果。

    Attributes:
        slice_index (int): 所属切片索引。
        dim_name (str): 聚类维度名称 (如 "CF", "PW")。
        cluster_index (int): 簇的全局单调索引。
        valid_cluster_index (int | None): 仅当 is_valid 为 True 时存在，表示其在所有有效簇中的顺序索引。
        pa_label (int): PA 模型预测的类别标签。
        pa_confidence (float): PA 模型预测的置信度。
        dtoa_label (int): DTOA 模型预测的类别标签。
        dtoa_confidence (float): DTOA 模型预测的置信度。
        is_valid (bool): 综合判定该簇是否为有效目标。
        joint_prob (float): PA 和 DTOA 综合计算的联合概率。
        pa_conf_dict (Dict[int, float]): PA 预测各类别置信度字典。
        dtoa_conf_dict (Dict[int, float]): DTOA 预测各类别置信度字典。
    """

    slice_index: int
    dim_name: str
    cluster_index: int
    valid_cluster_index: int | None
    pa_label: int
    pa_confidence: float
    dtoa_label: int
    dtoa_confidence: float
    is_valid: bool
    joint_prob: float = 0.0
    pa_conf_dict: dict[int, float] = field(default_factory=dict)
    dtoa_conf_dict: dict[int, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SliceRecognitionResult:
    """单个切片的识别结果汇总。

    功能描述：
        包含一个切片内所有有效和无效簇的识别结果。

    Attributes:
        slice_index (int): 切片索引。
        valid_clusters (list[ClusterRecognition]): 判定为有效的簇集合。
        invalid_clusters (list[ClusterRecognition]): 判定为无效的簇集合。
    """

    slice_index: int
    valid_clusters: list[ClusterRecognition] = field(default_factory=list)
    invalid_clusters: list[ClusterRecognition] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """全局识别阶段产物。

    功能描述：
        包含所有切片的识别结果，作为 ProcessingSession.recognition_result 的具体类型。

    Attributes:
        slice_results (dict[int, SliceRecognitionResult]): 切片索引到其识别结果的映射。
    """

    slice_results: dict[int, SliceRecognitionResult] = field(default_factory=dict)
