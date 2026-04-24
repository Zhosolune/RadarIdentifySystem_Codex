"""识别与特征预测算法。

功能描述：
    对聚类结果进行 PA 与 DTOA 维度的特征预测，计算联合概率，
    并判定簇的有效性。本模块为纯业务逻辑，不直接依赖 ONNX 或绘图库，
    通过依赖注入（回调或接口）调用外部推理能力。
"""

from __future__ import annotations

from typing import Protocol
from core.models.algorithm_params import RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState
from core.models.recognition_result import ClusterRecognition


class InferenceService(Protocol):
    """推理服务协议。
    
    由 infra 层实现此协议，封装 ONNX 模型调用和绘图过程。
    """
    def predict_pa(self, cluster: ClusterItem) -> tuple[int, float, dict[int, float]]:
        """预测 PA 特征，返回 (类别标签, 置信度, 各类别置信度字典)"""
        ...

    def predict_dtoa(self, cluster: ClusterItem) -> tuple[int, float, dict[int, float]]:
        """预测 DTOA 特征，返回 (类别标签, 置信度, 各类别置信度字典)"""
        ...


def recognize_clusters(
    clusters: list[ClusterItem],
    inference_service: InferenceService,
    params: RecognitionParams,
    start_valid_idx: int
) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
    """对一组簇执行识别。
    
    功能描述：
        调用推理服务获取预测结果，根据配置参数进行判定。
        为通过判定的有效簇分配全局递增的 valid_cluster_idx。

    Args:
        clusters: 待识别的簇列表。
        inference_service: 注入的推理服务。
        params: 识别判定参数。
        start_valid_idx: 当前有效簇的起始索引。

    Returns:
        (有效簇列表, 无效簇列表, 识别记录列表, 下一个可用的有效簇索引)
    """
    valid_clusters = []
    invalid_clusters = []
    recognitions = []

    pa_weight = 0.6
    dtoa_weight = 0.4
    current_valid_idx = start_valid_idx

    for cluster in clusters:
        # 调用防腐层进行推理
        pa_label, pa_conf, pa_conf_dict = inference_service.predict_pa(cluster)
        dtoa_label, dtoa_conf, dtoa_conf_dict = inference_service.predict_dtoa(cluster)

        joint_prob = pa_conf * pa_weight + dtoa_conf * dtoa_weight

        is_valid = False
        if (
            pa_conf >= params.tolerance and 
            dtoa_conf >= params.tolerance and 
            joint_prob >= params.min_confidence
        ):
            if pa_label != 5 and dtoa_label != 5:
                is_valid = True

        valid_cluster_idx = None
        if is_valid:
            valid_cluster_idx = current_valid_idx
            current_valid_idx += 1

        rec_info = ClusterRecognition(
            slice_index=cluster.slice_idx,
            dim_name=cluster.dim_name,
            cluster_index=cluster.cluster_idx,
            valid_cluster_index=valid_cluster_idx,
            pa_label=pa_label,
            pa_confidence=pa_conf,
            dtoa_label=dtoa_label,
            dtoa_confidence=dtoa_conf,
            is_valid=is_valid,
            joint_prob=joint_prob,
            pa_conf_dict=pa_conf_dict,
            dtoa_conf_dict=dtoa_conf_dict
        )
        recognitions.append(rec_info)

        if is_valid:
            cluster.state = ClusterState.VALID
            cluster.pa_label = pa_label
            cluster.dtoa_label = dtoa_label
            cluster.joint_prob = joint_prob
            cluster.valid_cluster_idx = valid_cluster_idx
            valid_clusters.append(cluster)
        else:
            cluster.state = ClusterState.INVALID
            invalid_clusters.append(cluster)

    return valid_clusters, invalid_clusters, recognitions, current_valid_idx