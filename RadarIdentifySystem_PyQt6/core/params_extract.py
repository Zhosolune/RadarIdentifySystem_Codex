# -*- coding: utf-8 -*-
"""core/params_extract.py — 参数提取与信号有效性验证。

本模块提供雷达信号的特征提取、DTOA（到达时间差）聚类验证等功能。
不依赖 UI / Qt / 线程。
"""

import numpy as np
from sklearn.cluster import DBSCAN


def extract_grouped_values(data: list | np.ndarray, eps: float = 0.5, min_samples: int = 3, threshold_ratio: float = 0.1) -> list[float]:
    """使用 DBSCAN 算法对一维数据（如 DTOA）进行聚类分析并提取组群均值。

    功能描述：
        主要用于验证雷达信号的到达时间差 (DTOA) 是否具有稳定的周期性。
        通过对 DTOA 进行一维聚类，若能找到显著的簇，则认为信号 PRI 稳定。

    Args:
        data (list | np.ndarray): 需要进行聚类分析的数据列表（通常是 DTOA 数组）。
        eps (float): DBSCAN 的邻域半径参数，默认 0.5。
        min_samples (int): DBSCAN 的最小样本数参数，默认 3。
        threshold_ratio (float): 用于过滤簇大小的阈值比例，默认 0.1。

    Returns:
        list[float]: 包含各个有效簇的均值的列表。若为空则说明未找到稳定周期。
    """
    if len(data) == 0:
        return []

    # 将数据转换为二维数组 (N, 1)
    data_reshaped = np.array(data).reshape(-1, 1)
    
    # 使用 DBSCAN 进行聚类
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(data_reshaped)
    labels = db.labels_
    
    grouped_values = []
    
    # 计算有效簇（非噪声且点数 >= 3）的数量
    unique_labels = set(labels)
    clusters_with_multiple_samples = sum(
        1 for label in unique_labels 
        if label != -1 and np.sum(labels == label) >= 3
    )
    
    # 计算当前簇成立的最小样本数阈值
    expected_min_size = len(data) / max(clusters_with_multiple_samples, 1) * threshold_ratio
    
    for label in unique_labels:
        if label == -1:
            continue
            
        current_cluster_size = np.sum(labels == label)
        if current_cluster_size >= expected_min_size:
            # 提取当前簇的所有值并计算均值
            cluster_values = data_reshaped[labels == label]
            cluster_mean = np.round(np.mean(cluster_values), 4)
            grouped_values.append(float(cluster_mean))
            
    return grouped_values
