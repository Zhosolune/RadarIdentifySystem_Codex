# -*- coding: utf-8 -*-
"""core/preprocess.py — 脉冲数据预处理纯函数。

功能：
    - clean_pa: 剔除 PA=255 的无效脉冲行
    - fix_toa_flip: 修正 TOA 时间翻折（溢出回绕）
    - detect_band: 根据 CF 均值推断频段名称
    - preprocess: 组合上述步骤，返回 PreprocessResult

迁移来源：
    cores/data_processor.py — DataProcessor.process_raw_data
    对齐差异：
        - 旧版通过 self.slice_dim=4 硬编码 TOA 列索引；新版改为显式传参，
          默认与旧版一致（COL_TOA=4）。
        - 旧版 logger 耦合在实例上；新版改为纯函数，不产生副作用。
        - 翻折判断阈值 -6e4（ms）与旧版保持一致。

约束：
    - 本模块不依赖 Qt / UI / infra，可在无 Qt 环境运行。
    - 不修改传入数组，所有操作在副本上进行。
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from core.models.pulse_batch import COL_CF, COL_PA, COL_TOA
from core.models.slice_result import PreprocessResult

# 日志器
LOGGER = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 常量
# -------------------------------------------------------------------
_INVALID_PA: int = 255
"""PA 无效值标记，等于 255 的脉冲将被剔除。"""

_TOA_FLIP_THRESHOLD: float = -6e4
"""TOA 差分小于该值（ms）时判定为时间翻折。与旧版 data_processor 一致。"""

# 频段 CF 均值边界（MHz）
_BAND_THRESHOLDS: list[tuple[float, str]] = [
    (1000.0, None),   # CF < 1000MHz → 丢弃（超低频段，不纳入后续处理）
    (2000.0, "L波段"),
    (4000.0, "S波段"),
    (8000.0, "C波段"),
]
_BAND_DEFAULT = "X波段"


# -------------------------------------------------------------------
# 公开纯函数
# -------------------------------------------------------------------

def clean_pa(data: np.ndarray, pa_col: int = COL_PA) -> np.ndarray:
    """剔除 PA 列等于 255 的无效脉冲行。

    功能描述：
        PA=255 为硬件无效标记，对应脉冲的幅度测量失效，需在所有下游
        处理前过滤掉。

    参数说明：
        data (np.ndarray): shape=(N, 5) 的脉冲数据数组（操作在副本上进行）。
        pa_col (int): PA 列的列索引，默认 COL_PA=3。

    返回值说明：
        np.ndarray: 剔除无效行后的新数组，shape=(M, 5)，M <= N。

    异常说明：
        ValueError: data.ndim != 2 或列数不足时抛出。
    """
    if data.ndim != 2 or data.shape[1] <= pa_col:
        raise ValueError(
            f"clean_pa: data 必须为至少 {pa_col + 1} 列的二维数组，"
            f"实际 shape={data.shape}"
        )
    # 布尔掩码：保留 PA != 255 的行
    valid_mask = data[:, pa_col] != _INVALID_PA
    cleaned = data[valid_mask]
    removed = len(data) - len(cleaned)
    if removed > 0:
        LOGGER.info("clean_pa: 剔除 PA=255 无效脉冲 %d 条，剩余 %d 条", removed, len(cleaned))
    return cleaned


def fix_toa_flip(
    data: np.ndarray,
    toa_col: int = COL_TOA,
    flip_threshold: float = _TOA_FLIP_THRESHOLD,
) -> tuple[np.ndarray, int]:
    """修正 TOA 时间轴翻折（计数器溢出回绕）。

    功能描述：
        雷达前端计数器在达到最大值后会从头计数（溢出回绕），表现为 TOA
        序列出现大幅下跌（diff < flip_threshold ms）。本函数通过检测下跌点，
        将后续段的 TOA 值平移修正，使时间轴单调递增，最终归零（以第一个
        脉冲时间为基准）。

        算法与旧版 DataProcessor.process_raw_data 完全对齐：
            for idx in flip_indices:
                delta = time_data[idx] - time_data[idx+1]
                time_data[idx+1:] += delta
            time_data -= time_data[0]

    参数说明：
        data (np.ndarray): shape=(N, 5) 的脉冲数据数组（不修改原数组）。
        toa_col (int): TOA 列的列索引，默认 COL_TOA=4。
        flip_threshold (float): 差分阈值（ms），低于此值判定为翻折，默认 -6e4。

    返回值说明：
        tuple[np.ndarray, int]:
            - 修正后的新数组（shape 不变）。
            - 检测到的翻折点数量（用于统计日志）。

    异常说明：
        ValueError: data.ndim != 2 或列数不足时抛出。
    """
    if data.ndim != 2 or data.shape[1] <= toa_col:
        raise ValueError(
            f"fix_toa_flip: data 必须为至少 {toa_col + 1} 列的二维数组，"
            f"实际 shape={data.shape}"
        )

    # 在副本上操作，不修改传入数组
    result = data.copy()
    time_data = result[:, toa_col].copy()

    # 计算相邻 TOA 差分，定位翻折点的前一行索引（与旧版 np.diff 语义一致）
    flip_indices = np.where(np.diff(time_data) < flip_threshold)[0]
    flip_count = len(flip_indices)

    if flip_count > 0:
        LOGGER.warning("fix_toa_flip: 检测到 %d 个时间翻折点，开始修正", flip_count)
        for idx in flip_indices:
            # delta = 翻折前最后一个值 - 翻折后第一个值（正数，代表需要叠加的偏移量）
            delta = time_data[idx] - time_data[idx + 1]
            # 将翻折点之后的所有 TOA 值向上平移
            time_data[idx + 1:] += delta
        # 时间轴归零：减去第一个脉冲的 TOA
        time_data -= time_data[0]
        result[:, toa_col] = time_data
        LOGGER.info("fix_toa_flip: TOA 修正完成，新时间范围 [%.2f, %.2f] ms",
                     float(time_data[0]), float(time_data[-1]))

    return result, flip_count


def detect_band(data: np.ndarray, cf_col: int = COL_CF) -> str | None:
    """根据 CF 列均值推断频段名称。

    功能描述：
        遍历预设频段阈值，按 CF 均值（MHz）映射到：
        - None   : CF < 1000 MHz（超低频，不纳入后续处理）
        - "L波段" : 1000 ≤ CF < 2000
        - "S波段" : 2000 ≤ CF < 4000
        - "C波段" : 4000 ≤ CF < 8000
        - "X波段" : CF ≥ 8000

    参数说明：
        data (np.ndarray): shape=(N, 5) 的脉冲数据数组。
        cf_col (int): CF 列的列索引，默认 COL_CF=0。

    返回值说明：
        str | None: 频段名称；数据为空或 CF < 1000 时返回 None。

    异常说明：
        ValueError: data.ndim != 2 或列数不足时抛出。
    """
    if data.ndim != 2 or data.shape[1] <= cf_col:
        raise ValueError(
            f"detect_band: data 必须为至少 {cf_col + 1} 列的二维数组，"
            f"实际 shape={data.shape}"
        )

    if len(data) == 0:
        LOGGER.debug("detect_band: 数据为空，返回 None")
        return None

    cf_mean = float(np.mean(data[:, cf_col]))
    LOGGER.debug("detect_band: CF 均值 = %.2f MHz", cf_mean)

    # 按升序阈值依次判断
    for threshold, band_name in _BAND_THRESHOLDS:
        if cf_mean < threshold:
            return band_name  # band_name 可能为 None（第一段）

    return _BAND_DEFAULT


def preprocess(
    data: np.ndarray,
    source_path: str = "",
    source_type: str = "unknown",
    slice_length_ms: float = 250.0,
    toa_col: int = COL_TOA,
    pa_col: int = COL_PA,
    cf_col: int = COL_CF,
) -> PreprocessResult:
    """组合预处理步骤，返回 PreprocessResult。

    功能描述：
        依次执行：
        1. 记录原始脉冲总数
        2. clean_pa — 剔除 PA=255 无效脉冲
        3. fix_toa_flip — 修正时间翻折
        4. 计算时间跨度与估算切片数量
        5. detect_band — 推断频段

        结果等价于旧版 DataProcessor.process_raw_data，但以纯函数形式提供，
        不依赖任何实例状态、日志器或绘图器。

    参数说明：
        data (np.ndarray): shape=(N, 5) 的原始脉冲数组。
        source_path (str): 数据来源路径，用于日志，默认空串。
        source_type (str): 数据来源类型，默认 "unknown"。
        slice_length_ms (float): 估算切片数的时间窗口，默认 250.0 ms。
        toa_col (int): TOA 列索引，默认 COL_TOA=4。
        pa_col (int): PA 列索引，默认 COL_PA=3。
        cf_col (int): CF 列索引，默认 COL_CF=0。

    返回值说明：
        PreprocessResult: 预处理结果数据对象。

    异常说明：
        ValueError: data 不符合 shape=(N, 5) 要求时，由内部函数抛出。
    """
    LOGGER.info("preprocess: 开始预处理，来源=%s type=%s 行数=%d",
                 source_path, source_type, len(data))

    total_pulses = len(data)

    # 步骤 1: 剔除无效 PA
    cleaned = clean_pa(data, pa_col=pa_col)
    filtered_pulses = total_pulses - len(cleaned)

    # 步骤 2: 修正 TOA 翻折
    fixed, flip_count = fix_toa_flip(cleaned, toa_col=toa_col)

    # 步骤 3: 计算时间跨度与预计切片数
    if len(fixed) > 0:
        toa_values = fixed[:, toa_col]
        time_range_ms = float(np.max(toa_values) - np.min(toa_values))
        estimated_slice_count = (
            int(np.ceil(time_range_ms / slice_length_ms)) if time_range_ms > 0 else 0
        )
    else:
        time_range_ms = 0.0
        estimated_slice_count = 0

    # 步骤 4: 推断频段
    band = detect_band(fixed, cf_col=cf_col) if len(fixed) > 0 else None

    LOGGER.info(
        "preprocess: 完成。总数=%d 剔除=%d 翻折点=%d 时间跨度=%.2f ms 估算切片=%d 频段=%s",
        total_pulses, filtered_pulses, flip_count,
        time_range_ms, estimated_slice_count, band,
    )

    return PreprocessResult(
        data=fixed,
        total_pulses=total_pulses,
        filtered_pulses=filtered_pulses,
        toa_flip_count=flip_count,
        time_range_ms=time_range_ms,
        estimated_slice_count=estimated_slice_count,
        band=band,
    )
