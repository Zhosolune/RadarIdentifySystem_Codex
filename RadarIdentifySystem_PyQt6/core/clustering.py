# -*- coding: utf-8 -*-
"""core/clustering.py — 纯聚类算法模块。

本模块负责雷达信号点云在载频（CF）和脉宽（PW）维度的密度聚类。
提供级联聚类的算法实现，输入切片数据，输出聚类结果集。
"""

import numpy as np
from sklearn.cluster import DBSCAN
import logging

from core.models.pulse_batch import COL_TOA
from core.models.slice_result import SingleSlice
from core.models.cluster_result import ClusterItem, SliceClusterResult, ClusterState
from core.models.algorithm_params import ClusteringParams, RecognitionParams
from core.models.recognition_result import SliceRecognitionResult, ClusterRecognition
from core.recognition import InferenceService, recognize_clusters
from core.params_extract import extract_grouped_values


logger = logging.getLogger(__name__)


def run_1d_dbscan(data: np.ndarray, dim_idx: int, epsilon: float, min_pts: int) -> np.ndarray:
    """使用 DBSCAN 算法对指定维度进行一维聚类。

    Args:
        data (np.ndarray): 待聚类的数据矩阵，shape=(N, 5)。
        dim_idx (int): 用于聚类的特征列索引（0=CF, 1=PW 等）。
        epsilon (float): DBSCAN 邻域半径。
        min_pts (int): DBSCAN 核心点最小样本数。

    Returns:
        np.ndarray: 聚类标签数组，-1 表示噪声点。
    """
    if len(data) == 0:
        return np.array([])
        
    dim_data = data[:, dim_idx].reshape(-1, 1)
    
    try:
        dbscan = DBSCAN(eps=epsilon, min_samples=min_pts, metric='euclidean', n_jobs=1)
        labels = dbscan.fit_predict(dim_data)
        return labels
    except Exception as e:
        logger.error(f"DBSCAN聚类异常 (dim_idx={dim_idx}): {e}")
        return np.full(len(data), -1)


def process_dimension_clustering(
    points: np.ndarray,
    dim_name: str,
    dim_idx: int,
    epsilon: float,
    min_pts: int,
    min_cluster_size: int,
    slice_idx: int,
    time_range: tuple[float, float],
    start_cluster_id: int
) -> tuple[list[ClusterItem], np.ndarray]:
    """处理单一维度的聚类与校验逻辑。

    功能描述：
        对输入点云执行 1D DBSCAN，并通过 DTOA 周期性校验与最小点数校验，
        过滤出有效的簇，其余标记为离散点（噪声）。

    Args:
        points (np.ndarray): 待聚类点云，shape=(N, 5)。
        dim_name (str): 维度名称 ('CF' 或 'PW')。
        dim_idx (int): 维度索引（CF为0，PW为1）。
        epsilon (float): DBSCAN 半径。
        min_pts (int): DBSCAN 最小核心点数。
        min_cluster_size (int): 单个簇允许的最小样本数。
        slice_idx (int): 当前切片索引，用于填充结果。
        time_range (tuple[float, float]): 当前切片的时间范围。
        start_cluster_id (int): 簇编号起始值，用于连续编号。

    Returns:
        tuple[list[ClusterItem], np.ndarray]:
            - list[ClusterItem]: 聚类成功并通过初步校验的簇列表。
            - np.ndarray: 未被聚类（或被判定为无效簇）的离散点在 points 中的索引。
    """
    clusters = []
    processed_indices = set()
    
    # 1. 运行一维 DBSCAN
    labels = run_1d_dbscan(points, dim_idx, epsilon, min_pts)
    unique_labels = np.unique(labels)
    
    current_cluster_id = start_cluster_id
    
    # 2. 遍历簇并校验
    for label in unique_labels:
        if label == -1:  # 噪声跳过
            continue
            
        mask = labels == label
        cluster_points = points[mask]
        
        # 计算 DTOA (us)
        # points 的第 4 列是 TOA (ms)，这里转为 us
        if len(cluster_points) > 1:
            dtoa = np.diff(cluster_points[:, COL_TOA]) * 1000
            dtoa = np.append(dtoa, dtoa[-1])  # 补齐长度，使用最后一个 DTOA 值
        else:
            dtoa = np.array([0.0])
        
        # 校验 DTOA 周期性
        valid_dtoa_groups = extract_grouped_values(
            dtoa, eps=0.2, min_samples=4, threshold_ratio=0.1
        )
        is_valid_dtoa = len(valid_dtoa_groups) > 0
        
        # 综合判定：点数够 或 DTOA 有明显周期
        if len(cluster_points) > min_cluster_size or is_valid_dtoa:
            indices = np.where(mask)[0]
            processed_indices.update(indices)
            
            # 构建簇对象
            item = ClusterItem(
                cluster_idx=current_cluster_id,
                dim_name=dim_name,
                points=cluster_points,
                points_indices=indices,  # 注意：这是相对于输入 points 的局部索引
                slice_idx=slice_idx,
                time_ranges=time_range,
                state=ClusterState.PENDING
            )
            clusters.append(item)
            current_cluster_id += 1
            
    # 3. 收集所有未被处理的点（真实噪声 + 未过校验的簇）
    all_indices = set(range(len(points)))
    unprocessed_indices = list(all_indices - processed_indices)
    
    return clusters, np.array(unprocessed_indices)


def cluster_and_recognize_slice(
    slice_data: SingleSlice,
    inference_service: InferenceService,
    cluster_params: ClusteringParams | None = None,
    recognize_params: RecognitionParams | None = None,
) -> tuple[SliceClusterResult, SliceRecognitionResult]:
    """对单个切片执行级联聚类与识别。

    功能描述：
        1. CF 维度聚类 -> 产出 CF 簇。
        2. CF 簇识别 -> 成功簇保留；失败簇打散。
        3. CF 未聚类点 + CF 失败簇散点 -> PW 维度聚类 -> 产出 PW 簇。
        4. PW 簇识别 -> 成功簇保留；失败簇打散。
        5. 最终组装聚类结果和识别结果。

    Args:
        slice_data: 单个切片数据。
        inference_service: 推理服务实现。
        cluster_params: 聚类参数。
        recognize_params: 识别参数。

    Returns:
        包含聚类结果与识别结果的元组。
    """
    cluster_params = cluster_params or ClusteringParams()
    recognize_params = recognize_params or RecognitionParams()
    
    all_valid_clusters: list[ClusterItem] = []
    all_recognitions: list[ClusterRecognition] = []
    recycled_indices = set()
    
    points = slice_data.data
    if len(points) == 0:
        return (
            SliceClusterResult(slice_data.index, [], np.array([]), np.array([])),
            SliceRecognitionResult(slice_data.index, [], [])
        )

    current_cluster_id = 1
    current_valid_idx = 0

    # ── 1. CF 维度聚类 ──
    cf_clusters, cf_unprocessed_idx = process_dimension_clustering(
        points=points,
        dim_name="CF",
        dim_idx=0,
        epsilon=cluster_params.eps_cf,
        min_pts=cluster_params.min_pts,
        min_cluster_size=cluster_params.min_cluster_size,
        slice_idx=slice_data.index,
        time_range=slice_data.time_range,
        start_cluster_id=current_cluster_id
    )
    current_cluster_id += len(cf_clusters)

    # ── 2. CF 维度识别 ──
    cf_valid, cf_invalid, cf_recs, current_valid_idx = recognize_clusters(
        cf_clusters, inference_service, recognize_params, current_valid_idx
    )
    all_valid_clusters.extend(cf_valid)
    all_recognitions.extend(cf_recs)

    # 收集 CF 识别失败的点，准备汇入 PW
    for c in cf_invalid:
        recycled_indices.update(c.points_indices)

    # ── 3. 准备 PW 维度的点云 ──
    # PW 聚类的输入点 = CF 未能聚类的点 + CF 识别失败被拆散的点
    pw_input_indices = list(set(cf_unprocessed_idx) | recycled_indices)
    
    if len(pw_input_indices) > 0:
        pw_input_indices = np.array(pw_input_indices)
        pw_points = points[pw_input_indices]
        
        # ── 4. PW 维度聚类 ──
        pw_clusters, pw_unprocessed_local_idx = process_dimension_clustering(
            points=pw_points,
            dim_name="PW",
            dim_idx=1,
            epsilon=cluster_params.eps_pw,
            min_pts=cluster_params.min_pts,
            min_cluster_size=cluster_params.min_cluster_size,
            slice_idx=slice_data.index,
            time_range=slice_data.time_range,
            start_cluster_id=current_cluster_id
        )
        current_cluster_id += len(pw_clusters)

        # 映射回原始 points 的全局索引
        for cluster in pw_clusters:
            cluster.points_indices = pw_input_indices[cluster.points_indices]
            
        # ── 5. PW 维度识别 ──
        pw_valid, pw_invalid, pw_recs, current_valid_idx = recognize_clusters(
            pw_clusters, inference_service, recognize_params, current_valid_idx
        )
        all_valid_clusters.extend(pw_valid)
        all_recognitions.extend(pw_recs)

        for c in pw_invalid:
            recycled_indices.update(c.points_indices)

        # 计算最终无用点 = (PW 输入点中未被 PW 聚类覆盖的) + (PW 聚类了但识别失败的)
        # 或者可以直接用全集减去所有有效簇的点
        valid_indices = set()
        for c in all_valid_clusters:
            valid_indices.update(c.points_indices)
            
        final_unprocessed_idx = list(set(range(len(points))) - valid_indices - recycled_indices)
    else:
        final_unprocessed_idx = list(cf_unprocessed_idx)

    # 组装结果
    cluster_result = SliceClusterResult(
        slice_idx=slice_data.index,
        clusters=all_valid_clusters + cf_invalid + (pw_invalid if 'pw_invalid' in locals() else []),
        unprocessed_points=points[final_unprocessed_idx] if len(final_unprocessed_idx) > 0 else np.array([]),
        recycled_points=points[list(recycled_indices)] if len(recycled_indices) > 0 else np.array([])
    )

    valid_recs = [r for r in all_recognitions if r.is_valid]
    invalid_recs = [r for r in all_recognitions if not r.is_valid]

    recognition_result = SliceRecognitionResult(
        slice_index=slice_data.index,
        valid_clusters=valid_recs,
        invalid_clusters=invalid_recs
    )

    return cluster_result, recognition_result
