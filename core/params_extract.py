# -*- coding: utf-8 -*-
"""一维典型值提取与识别通过类参数提取算法。

本模块只提供不依赖业务字段、UI、Qt、线程的一维数值聚类工具，以及基于点云
矩阵为识别通过的簇提取 CF/PW/PRI/DOA 四类参数所需的纯算法函数。

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

from __future__ import annotations

from itertools import combinations
import logging

import numpy as np
from sklearn.cluster import DBSCAN

from core.models.algorithm_params import ExtractParams
from core.models.extraction_result import ExtractedClusterParams
from core.models.pulse_batch import COL_CF, COL_DOA, COL_PW, COL_TOA


LOGGER = logging.getLogger(__name__)


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


def extract_cluster_params(
    points: np.ndarray,
    extract_params: ExtractParams,
) -> ExtractedClusterParams:
    """从识别通过的簇点云矩阵中提取 CF、PW、PRI、DOA 典型参数。

    功能描述：
        面向识别通过的最终簇执行参数提取，返回统一的四类典型值容器。
        本函数不修改输入矩阵，且不依赖任何 UI/Qt/线程能力。

    Args:
        points [np.ndarray]: 单个识别通过类的点云矩阵，shape=(N, 6)；空矩阵时返回空结果。
        extract_params [ExtractParams]: 参数提取配置快照，控制 DBSCAN 邻域与门限。

    Returns:
        ExtractedClusterParams: 汇总 CF/PW/PRI/DOA 四类典型值的结果对象。

    Raises:
        无显式抛出异常；底层 DBSCAN 参数非法时向上透传。

    Example:
        >>> import numpy as np
        >>> pts = np.array([
        ...     [1000.0, 1.0, 20.0, 10.0, 10.0, 0.0],
        ...     [1000.0, 1.0, 20.0, 20.0, 20.0, 100.0],
        ...     [1000.0, 1.0, 20.0, 30.0, 30.0, 200.0],
        ... ])
        >>> params = ExtractParams(min_pts_cf=2, min_pts_pw=2, min_pts_pri=2)
        >>> result = extract_cluster_params(pts, params)
        >>> result.cf_values
        [1000.0]
    """
    # 空矩阵不参与任何提取，直接返回默认空容器。
    if points.size == 0:
        return ExtractedClusterParams()

    # CF 使用配置中的邻域半径、最小点数和门限率，底层仅负责一维数值聚类。
    cf_values = extract_grouped_values(
        points[:, COL_CF],
        eps=extract_params.eps_cf,
        min_samples=extract_params.min_pts_cf,
        threshold_ratio=extract_params.threshold_ratio_cf / 100.0,
    )
    # PW 与 CF 共享同一类典型值算法，但使用独立的 PW 参数配置。
    pw_values = extract_grouped_values(
        points[:, COL_PW],
        eps=extract_params.eps_pw,
        min_samples=extract_params.min_pts_pw,
        threshold_ratio=extract_params.threshold_ratio_pw / 100.0,
    )
    # PRI 是 TOA 的派生量，单位换算与业务过滤在此函数内完成。
    pri_values = extract_pri_values(points[:, COL_TOA], extract_params)
    # DOA 使用循环均值处理 0°/360° 边界，仍以列表返回以保持四类参数契约一致。
    doa_values = extract_doa_values(points[:, COL_DOA])
    return ExtractedClusterParams(
        cf_values=cf_values,
        pw_values=pw_values,
        pri_values=pri_values,
        doa_values=doa_values,
    )


def extract_pri_values(
    toa_values: np.ndarray,
    extract_params: ExtractParams,
) -> list[float]:
    """从 TOA 序列提取 PRI 典型值列表。

    功能描述：
        以相邻 TOA 差分得到 DTOA/PRI 序列，先执行一维典型值提取，
        再按谐波容差与最小值门限做业务过滤，避免输出组合周期或过短周期。

    Args:
        toa_values [np.ndarray]: 单簇 TOA 序列，单位为 0.1us；长度小于 2 时直接返回空列表。
        extract_params [ExtractParams]: 参数提取配置快照，提供 PRI 相关阈值。

    Returns:
        list[float]: PRI 典型值列表，单位为 us；未通过过滤时返回空列表。

    Raises:
        无显式抛出异常；底层 DBSCAN 参数非法时向上透传。

    Example:
        >>> import numpy as np
        >>> toa = np.array([0.0, 100.0, 200.0, 300.0])
        >>> extract_pri_values(toa, ExtractParams(eps_pri=0.5, min_pts_pri=2))
        [10.0]
    """
    if len(toa_values) < 2:
        return []

    # 保持当前类内脉冲顺序，按相邻 TOA 差分得到 DTOA/PRI 序列。
    toa_array = np.asarray(toa_values, dtype=float)
    # TOA 在项目内保持 0.1us 单位，PRI 对外展示与配置统一使用 us。
    pri_values = np.diff(toa_array) * 0.1
    # 补齐一个尾值，使 PRI 序列长度与原始脉冲数保持一致。
    pri_values = np.append(pri_values, 0.0)
    # 先对 PRI 序列执行一维典型值提取，后续再做业务过滤。
    grouped_values = extract_grouped_values(
        pri_values,
        eps=extract_params.eps_pri,
        min_samples=extract_params.min_pts_pri,
        threshold_ratio=extract_params.threshold_ratio_pri / 100.0,
    )
    if not grouped_values:
        return []

    # 多个典型 PRI 之间可能存在谐波或组合和值，需要按旧流程做关系过滤。
    if len(grouped_values) > 1:
        grouped_values = filter_related_pri_values(
            grouped_values,
            tolerance=extract_params.harmonic_tolerance_pri,
        )

    # 单个 PRI 低于门限时视为无效结果，避免输出异常短周期。
    if len(grouped_values) == 1 and grouped_values[0] < extract_params.filter_threshold_pri:
        return []
    return grouped_values


def extract_doa_values(doa_values: np.ndarray) -> list[float]:
    """从 DOA 序列提取循环均值列表。

    功能描述：
        先按数值排序并去掉两端极值以降低离群点影响，再执行循环均值算法
        处理 0°/360° 边界，最终固定到 4 位小数返回单元素列表。

    Args:
        doa_values [np.ndarray]: 单簇 DOA 序列，单位为度；空序列返回空列表。

    Returns:
        list[float]: 循环均值列表，长度为 0 或 1。

    Raises:
        无显式抛出异常。

    Example:
        >>> import numpy as np
        >>> extract_doa_values(np.array([1.0, 2.0, 358.0, 359.0]))
        [0.0]
    """
    if len(doa_values) == 0:
        return []

    # 先排序并去掉两端值，降低方位角离群点对最终均值的影响。
    sorted_doa = np.array(sorted(np.asarray(doa_values, dtype=float)))
    trimmed_doa = sorted_doa[1:-1] if len(sorted_doa) > 2 else sorted_doa
    if len(trimmed_doa) == 0:
        return []

    # 循环均值天然处理 0°/360° 边界，结果固定到 4 位用于稳定展示。
    return [float(np.round(circular_mean(trimmed_doa), 4))]


def circular_mean(angles: np.ndarray) -> float:
    """计算循环均值，正确处理跨越 0°/360° 边界的情况。

    功能描述：
        将每个角度转换为单位向量并求平均方向，再转回角度值。相比算术均值，
        循环均值可以正确处理如 [1°, 359°] 这类跨越边界的角度分布。

    Args:
        angles [np.ndarray]: 输入角度序列，单位为度；空序列直接返回 0.0。

    Returns:
        float: 循环均值（度），范围 [0.0, 360.0)。

    Raises:
        无显式抛出异常。

    Example:
        >>> import numpy as np
        >>> round(circular_mean(np.array([1.0, 359.0])), 4)
        0.0
    """
    if len(angles) == 0:
        return 0.0

    # 将每个角度转换为单位向量，求平均方向后再转换回角度。
    angles_rad = np.radians(angles, dtype=np.float64)
    sin_sum = np.sum(np.sin(angles_rad))
    cos_sum = np.sum(np.cos(angles_rad))
    mean_rad = np.arctan2(sin_sum, cos_sum)
    mean_deg = float(np.degrees(mean_rad))
    result = mean_deg % 360.0
    if np.isclose(result, 360.0):
        result = 0.0

    # 当算术均值和循环均值差异较大时，记录跨边界分布线索。
    arith_mean = float(np.mean(angles))
    diff = abs(result - arith_mean)
    if diff > 5.0:
        LOGGER.debug(
            "[circular_mean] 角度可能跨越0°/360°边界，n=%d, min=%.2f°, max=%.2f°, 算术均值=%.2f°, 循环均值=%.2f°, 偏差=%.2f°",
            len(angles),
            float(np.min(angles)),
            float(np.max(angles)),
            arith_mean,
            result,
            diff,
        )
    else:
        LOGGER.debug(
            "[circular_mean] n=%d, min=%.2f°, max=%.2f°, 算术均值=%.2f°, 循环均值=%.2f°",
            len(angles),
            float(np.min(angles)),
            float(np.max(angles)),
            arith_mean,
            result,
        )
    return result


def filter_related_pri_values(
    values: list[float],
    tolerance: float,
) -> list[float]:
    """按容差过滤整数倍、两数和、三数和相关的 PRI 值。

    功能描述：
        面向多个 PRI 典型值，先剔除较小基准的整数倍，再剔除近似等于两数和
        或三数和的组合周期，避免同一辐射源的谐波结果被当成独立 PRI 输出。

    Args:
        values [list[float]]: 已提取的 PRI 典型值列表；元素数少于 2 时直接返回原列表。
        tolerance [float]: 相关性判定的绝对容差，单位与 PRI 一致；小于等于 0 时不过滤。

    Returns:
        list[float]: 保留下来的独立 PRI 典型值列表，按数值升序返回。

    Raises:
        无显式抛出异常。

    Example:
        >>> filter_related_pri_values([10.0, 20.0, 30.0], tolerance=0.2)
        [10.0]
    """
    if tolerance <= 0 or len(values) <= 1:
        return values

    sorted_values = sorted(float(value) for value in values)
    removed_indices: set[int] = set()

    # 先过滤整数倍关系，较小值作为基准，较大相关值被移除。
    for base_index, base_value in enumerate(sorted_values):
        if base_index in removed_indices or base_value <= 0:
            continue
        for target_index in range(base_index + 1, len(sorted_values)):
            if target_index in removed_indices:
                continue
            target_value = sorted_values[target_index]
            multiple = round(target_value / base_value)
            if multiple >= 2 and abs(target_value - base_value * multiple) <= tolerance:
                removed_indices.add(target_index)

    # 再过滤两数和、三数和关系，避免组合周期作为独立 PRI 输出。
    for target_index, target_value in enumerate(sorted_values):
        if target_index in removed_indices:
            continue
        base_values = [
            value
            for index, value in enumerate(sorted_values[:target_index])
            if index not in removed_indices
        ]
        if _is_sum_of_related_values(
            target_value,
            base_values,
            tolerance,
        ):
            removed_indices.add(target_index)

    return [
        value
        for index, value in enumerate(sorted_values)
        if index not in removed_indices
    ]


def _is_sum_of_related_values(
    value: float,
    base_values: list[float],
    tolerance: float,
) -> bool:
    """判断当前 PRI 是否近似等于已有 PRI 的两数和或三数和。"""
    for combination_size in (2, 3):
        for candidate_values in combinations(base_values, combination_size):
            # 使用绝对容差判断组合和值，容差单位与 PRI 配置保持一致。
            if abs(value - sum(candidate_values)) <= tolerance:
                return True
    return False
