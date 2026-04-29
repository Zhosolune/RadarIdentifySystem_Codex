# -*- coding: utf-8 -*-
"""core/clustering.py — 纯聚类算法模块。

本模块负责单维度的密度聚类算法实现及簇校验逻辑。
不包含跨维度编排、流程调度与结果组装，编排职责归 runtime 层。
"""

import numpy as np
from sklearn.cluster import DBSCAN
import logging

from core.models.pulse_batch import COL_TOA
from core.models.cluster_result import ClusterItem, ClusterState
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
