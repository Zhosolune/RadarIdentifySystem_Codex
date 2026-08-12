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
          默认使用统一六列契约（COL_TOA=5）。
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

from core.dashboard import DashboardInfoManager
from core.models.pulse_batch import COL_CF, COL_PA, COL_TOA
from core.models.slice_result import PreprocessResult

# 日志器
LOGGER = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 常量
# -------------------------------------------------------------------
_INVALID_PA: int = 255
"""PA 无效值标记，等于 255 的脉冲将被剔除。"""

_TOA_FLIP_THRESHOLD: float = -6e8
"""TOA 差分小于该值（0.1us）时判定为时间翻折。
旧版 -6e4 ms = -6e4 × 10000 = -6e8 (0.1us)。"""

_TOA_FLIP_PREVIOUS_STEP_COUNT: int = 2
"""翻折候选之前用于排除局部高值平台的连续增量数量。"""

_TOA_FLIP_MIN_POST_OBSERVATIONS: int = 2
"""翻折候选低位点开始至少需要确认的连续观测数量。"""

_TOA_FLIP_MAX_POST_OBSERVATIONS: int = 3
"""翻折候选低位点开始最多检查的连续观测数量。"""

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

def clean_pa(data: np.ndarray, pa_col: int = COL_PA, session_id: str = "-") -> np.ndarray:
    """剔除 PA 列等于 255 的无效脉冲行。

    功能描述：
        PA=255 为硬件无效标记，对应脉冲的幅度测量失效，需在所有下游
        处理前过滤掉。

    参数说明：
        data (np.ndarray): shape=(N, 6) 的脉冲数据数组（操作在副本上进行）。
        pa_col (int): PA 列的列索引，默认 COL_PA=2。
        session_id (str): 会话标识，用于日志追踪。

    返回值说明：
        np.ndarray: 剔除无效行后的新数组，shape=(M, 6)，M <= N。

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
        LOGGER.debug("剔除 PA=255 无效脉冲 %d 条，剩余 %d 条", removed, len(cleaned), extra={"session_id": session_id})
    return cleaned


def fix_toa_flip(
    data: np.ndarray,
    toa_col: int = COL_TOA,
    flip_threshold: float = _TOA_FLIP_THRESHOLD,
    session_id: str = "-",
) -> tuple[np.ndarray, int]:
    """修正 TOA 时间轴翻折（计数器溢出回绕）。

    功能描述：
        雷达前端计数器达到上限后从头计数，表现为 TOA 序列出现大幅下降。
        为避免单点局部极大值或局部极小值被误判为回卷，候选点还必须满足：
        1. 候选高值不是由同等级的大幅正向突刺形成；
        2. 回落后的连续观测仍低于翻折前基线；
        3. 回落后的短窗口保持非递减。

        仅通过确认的候选会平移其后全部 TOA；修正方式与既有实现一致，
        并在至少存在一个真实翻折时以首个脉冲为基准归零。

    Args:
        data [np.ndarray]: shape=(N, 6) 的脉冲数据数组，不修改原数组。
        toa_col [int]: TOA 列索引，默认 COL_TOA=5。
        flip_threshold [float]: 候选下降阈值，单位 0.1us，必须小于 0。
        session_id [str]: 会话标识，用于日志追踪。

    Returns:
        tuple[np.ndarray, int]: 修正后的同形状数组，以及确认的翻折点数量。

    Raises:
        ValueError: data.ndim != 2、列数不足或阈值不小于 0 时抛出。

    Example:
        >>> rows = np.zeros((7, 6), dtype=float)
        >>> rows[:, COL_TOA] = [4294000000, 4294100000, 4294200000, 100000, 200000, 300000, 400000]
        >>> fixed, count = fix_toa_flip(rows)
        >>> count
        1
        >>> bool(np.all(np.diff(fixed[:, COL_TOA]) >= 0))
        True
    """
    if data.ndim != 2 or data.shape[1] <= toa_col:
        raise ValueError(
            f"fix_toa_flip: data 必须为至少 {toa_col + 1} 列的二维数组，"
            f"实际 shape={data.shape}"
        )
    if flip_threshold >= 0:
        raise ValueError("flip_threshold 必须小于 0")

    # 在副本上操作，不修改传入数组
    result = data.copy()
    time_data = result[:, toa_col].copy()

    # 大幅下降只产生候选，必须结合前后连续趋势排除局部测量异常。
    flip_candidates = np.flatnonzero(np.diff(time_data) < flip_threshold)
    flip_indices = _confirm_toa_flip_candidates(
        time_data,
        flip_candidates,
        flip_threshold,
    )
    flip_count = len(flip_indices)

    rejected_count = len(flip_candidates) - flip_count
    if rejected_count > 0:
        LOGGER.debug(
            "排除 %d 个 TOA 伪翻折候选",
            rejected_count,
            extra={"session_id": session_id},
        )

    if flip_count > 0:
        LOGGER.warning("检测到 %d 个时间翻折点，开始修正", flip_count, extra={"session_id": session_id})
        for idx in flip_indices:
            # delta = 翻折前最后一个值 - 翻折后第一个值（正数，代表需要叠加的偏移量）
            delta = time_data[idx] - time_data[idx + 1]
            # 将翻折点之后的所有 TOA 值向上平移
            time_data[idx + 1:] += delta
        # 时间轴归零：减去第一个脉冲的 TOA
        time_data -= time_data[0]
        result[:, toa_col] = time_data
        LOGGER.debug("TOA 修正完成，新时间范围 [%.2f, %.2f] ms",
                     float(time_data[0]) / 1e4, float(time_data[-1]) / 1e4, extra={"session_id": session_id})

    return result, flip_count


def _confirm_toa_flip_candidates(
    time_data: np.ndarray,
    candidate_indices: np.ndarray,
    flip_threshold: float,
) -> np.ndarray:
    """结合候选点前后趋势筛出可信的 TOA 翻折位置。"""
    confirmed: list[int] = []
    max_normal_forward_step = abs(flip_threshold)

    for candidate in candidate_indices:
        index = int(candidate)

        # 翻折前至少需要两个连续增量，才能识别“正常值 -> 局部高值平台”
        # 这类不一定紧邻候选的大幅正向突刺。
        if index < _TOA_FLIP_PREVIOUS_STEP_COUNT:
            continue

        pre_window = time_data[
            index - _TOA_FLIP_PREVIOUS_STEP_COUNT : index + 1
        ]
        pre_steps = np.diff(pre_window)
        baseline_before_high = time_data[index - 1]

        # 局部极大值或短平台之前通常存在同等级巨大正跳；真实回卷前的
        # 计数应在最近两个增量内持续以正常幅度向前推进。
        if not bool(
            np.all((pre_steps >= 0) & (pre_steps <= max_normal_forward_step))
        ):
            continue

        post_end = min(
            len(time_data),
            index + 1 + _TOA_FLIP_MAX_POST_OBSERVATIONS,
        )
        post_window = time_data[
            index + 1 : post_end
        ]
        if len(post_window) < _TOA_FLIP_MIN_POST_OBSERVATIONS:
            continue

        # 真实回卷后的连续观测应持续处于翻折前基线以下；单点极大值
        # 回落后会迅速回到原基线，单点极小值也会在后续记录中反弹。
        if not bool(np.all(post_window < baseline_before_high)):
            continue

        # 回卷后的低位计数器应继续向前。要求完整窗口非递减，避免只验证
        # 第一条后继记录而漏过紧随其后的异常反弹或二次下跌。
        if not bool(np.all(np.diff(post_window) >= 0)):
            continue

        confirmed.append(index)

    return np.asarray(confirmed, dtype=np.int64)


def detect_band(data: np.ndarray, cf_col: int = COL_CF, session_id: str = "-") -> str | None:
    """根据 CF 列均值推断频段名称。

    功能描述：
        遍历预设频段阈值，按 CF 均值（MHz）映射到：
        - None   : CF < 1000 MHz（超低频，不纳入后续处理）
        - "L波段" : 1000 ≤ CF < 2000
        - "S波段" : 2000 ≤ CF < 4000
        - "C波段" : 4000 ≤ CF < 8000
        - "X波段" : CF ≥ 8000

    参数说明：
        data (np.ndarray): shape=(N, 6) 的脉冲数据数组。
        cf_col (int): CF 列的列索引，默认 COL_CF=0。
        session_id (str): 会话标识，用于日志追踪。

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
        LOGGER.debug("数据为空，返回 None", extra={"session_id": session_id})
        return None

    cf_mean = float(np.mean(data[:, cf_col]))
    LOGGER.debug("CF 均值 = %.2f MHz", cf_mean, extra={"session_id": session_id})

    # 按升序阈值依次判断
    for threshold, band_name in _BAND_THRESHOLDS:
        if cf_mean < threshold:
            return band_name  # band_name 可能为 None（第一段）

    return _BAND_DEFAULT


def preprocess(
    data: np.ndarray,
    source_path: str = "",
    source_type: str = "unknown",
    slice_length: float = 2_500_000,
    toa_col: int = COL_TOA,
    pa_col: int = COL_PA,
    cf_col: int = COL_CF,
    session_id: str = "-",
    source_total_pulses: int | None = None,
    source_amplitude_dropped_pulses: int | None = None,
    band_name: str | None = None,
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
        data (np.ndarray): shape=(N, 6) 的原始脉冲数组。
        source_path (str): 数据来源路径，用于日志，默认空串。
        source_type (str): 数据来源类型，默认 "unknown"。
        slice_length (float): 估算切片数的时间窗口，默认 2_500_000（0.1us，即 250ms）。
        toa_col (int): TOA 列索引，默认 COL_TOA=5。
        pa_col (int): PA 列索引，默认 COL_PA=2。
        cf_col (int): CF 列索引，默认 COL_CF=0。
        session_id (str): 会话标识，用于日志追踪。
        source_total_pulses (int | None): 来源组应用格式特有过滤前的脉冲数；
            为空时使用输入数据行数。
        source_amplitude_dropped_pulses (int | None): 来源组中 PA=255 的总数，
            用于保留与其他过滤原因重叠的统计；为空时从输入数据计算。
        band_name (str | None): 已由公共波段拆分确定的波段名称；为空时按 CF 推断。

    返回值说明：
        PreprocessResult: 预处理结果数据对象。

    异常说明：
        ValueError: 数据形状、来源总数或 PA 丢弃统计不合法时抛出。
    """
    LOGGER.info("开始预处理，来源=%s type=%s 行数=%d",
                 source_path, source_type, len(data), extra={"session_id": session_id})

    total_pulses = len(data) if source_total_pulses is None else source_total_pulses
    if total_pulses < len(data):
        raise ValueError("source_total_pulses 不能小于输入数据行数")

    # 步骤 1: 剔除无效 PA
    cleaned = clean_pa(data, pa_col=pa_col, session_id=session_id)
    # 同时计入格式特有过滤和 PA=255 清洗，确保多格式摘要统计口径一致。
    amplitude_dropped_pulses = (
        len(data) - len(cleaned)
        if source_amplitude_dropped_pulses is None
        else source_amplitude_dropped_pulses
    )
    if not (0 <= amplitude_dropped_pulses <= total_pulses):
        raise ValueError("source_amplitude_dropped_pulses 必须位于 0 和来源总数之间")
    filtered_pulses = total_pulses - len(cleaned)

    # 步骤 2: 修正 TOA 翻折
    fixed, flip_count = fix_toa_flip(cleaned, toa_col=toa_col, session_id=session_id)

    # 步骤 3: 计算时间跨度与预计切片数
    if len(fixed) > 0:
        toa_values = fixed[:, toa_col]
        time_range = float(np.max(toa_values) - np.min(toa_values))
        estimated_slice_count = (
            int(np.ceil(time_range / slice_length)) if time_range > 0 else 0
        )
    else:
        time_range = 0.0
        estimated_slice_count = 0

    # 步骤 4: 推断频段
    band = band_name
    if band is None and len(fixed) > 0:
        band = detect_band(fixed, cf_col=cf_col, session_id=session_id)

    LOGGER.info(
        "预处理完成。总数=%d 剔除=%d 翻折点=%d 时间跨度=%.2f ms 估算切片=%d 频段=%s",
        total_pulses, filtered_pulses, flip_count,
        time_range / 1e4, estimated_slice_count, band,
        extra={"session_id": session_id},
    )

    result = PreprocessResult(
        data=fixed,
        total_pulses=total_pulses,
        filtered_pulses=filtered_pulses,
        amplitude_dropped_pulses=amplitude_dropped_pulses,
        toa_flip_count=flip_count,
        time_range=time_range,
        estimated_slice_count=estimated_slice_count,
        band=band,
    )
    # 预处理阶段统一生成轻量摘要，供 UI 仪表盘只读展示。
    result.dashboard_info = DashboardInfoManager().build(
        source_type,
        result,
        slice_length=slice_length,
    )
    return result
