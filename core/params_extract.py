# -*- coding: utf-8 -*-
"""一维典型值提取算法。

本模块只提供不依赖业务字段、UI、Qt、线程的一维数值聚类工具。

Example:
    对一维数值序列提取两个典型值：
    >>> extract_grouped_values(
    ...     [10.0, 10.1, 10.2, 20.0, 20.1, 20.2],
    ...     eps=0.3,
    ...     min_samples=3,
    ...     threshold_ratio=0.1,
    ... )
    [10.1, 20.1]
"""

import numpy as np
from sklearn.cluster import DBSCAN


def extract_grouped_values(
    data: list | np.ndarray,
    eps: float = 0.5,
    min_samples: int = 3,
    threshold_ratio: float = 0.1,
) -> list[float]:
    """使用 DBSCAN 算法对一维数据进行聚类分析并提取组群均值。

    对任意一维数值序列执行 DBSCAN 聚类，并返回通过点数门限过滤后的
    有效簇均值。调用方负责决定输入序列的业务含义和单位，本函数只处理
    一维数值聚类和均值提取。

    Args:
        data [list | np.ndarray]: 需要进行聚类分析的一维数值列表；为空时直接返回空列表。
        eps [float]: DBSCAN 的邻域半径参数，必须大于 0。
        min_samples [int]: DBSCAN 的最小样本数参数，必须大于 0。
        threshold_ratio [float]: 用于过滤簇大小的阈值比例，取值建议为 0 到 1。

    Returns:
        list[float]: 包含各个有效簇的均值的列表。若为空则说明未找到稳定周期。

    Raises:
        ValueError: 当 scikit-learn DBSCAN 参数非法时由底层实现抛出。

    Example:
        >>> extract_grouped_values(
        ...     [10.0, 10.1, 10.2, 20.0, 20.1, 20.2],
        ...     eps=0.3,
        ...     min_samples=3,
        ...     threshold_ratio=0.1,
        ... )
        [10.1, 20.1]
    """
    if len(data) == 0:
        return []

    # DBSCAN 接收二维特征矩阵，这里把一维序列转换为单列矩阵。
    data_reshaped = np.array(data).reshape(-1, 1)

    # 使用固定的欧氏距离对单列数值执行密度聚类。
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(data_reshaped)
    labels = db.labels_

    grouped_values: list[float] = []

    # 统计包含至少 3 个样本的非噪声簇数量，用于估算每个有效簇的规模门限。
    unique_labels = set(labels)
    clusters_with_multiple_samples = sum(
        1 for label in unique_labels
        if label != -1 and np.sum(labels == label) >= 3
    )

    # 根据样本总量、有效簇数量和比例门限计算当前簇最小规模。
    expected_min_size = (
        len(data) / max(clusters_with_multiple_samples, 1) * threshold_ratio
    )

    for label in unique_labels:
        if label == -1:
            continue

        # 跳过样本数不足的簇，避免噪声或偶发近邻影响典型值。
        current_cluster_size = np.sum(labels == label)
        if current_cluster_size >= expected_min_size:
            # 对当前簇内所有原始值求均值，并固定到 4 位小数，保证结果稳定展示。
            cluster_values = data_reshaped[labels == label]
            cluster_mean = np.round(np.mean(cluster_values), 4)
            grouped_values.append(float(cluster_mean))

    return grouped_values
