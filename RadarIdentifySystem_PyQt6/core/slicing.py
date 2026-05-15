# -*- coding: utf-8 -*-
"""core/slicing.py — TOA 时间维度切片纯函数。

功能：
    - slice_by_toa: 按固定时间窗口将脉冲数据切分为多个子数组

迁移来源：
    cores/data_processor.py — DataProcessor._slice_data
    对齐差异：
        - 旧版通过 self.data 挂载状态；新版改为参数传入，无副作用。
        - 旧版 time_ranges 写入实例属性；新版封装在 SliceResult 返回。
        - 切片边界计算、掩码逻辑、空切片跳过规则完全与旧版对齐。

约束：
    - 本模块不依赖 Qt / UI / infra，可在无 Qt 环境运行。
    - 不修改传入数组。
"""

from __future__ import annotations

import logging

import numpy as np

from core.models.pulse_batch import COL_TOA
from core.models.slice_result import PreprocessResult, SliceResult, SingleSlice

# 日志器
LOGGER = logging.getLogger(__name__)


def slice_by_toa(
    data: np.ndarray,
    slice_length: float = 2_500_000,
    toa_col: int = COL_TOA,
    session_id: str = "-",
) -> SliceResult:
    """将脉冲数据按 TOA 时间窗口切片。

    功能描述：
        根据 TOA 列的最小值与最大值，以 slice_length 为步长生成等宽
        时间窗口，将落入各窗口的脉冲行提取为独立子数组。
        空切片（该窗口内无脉冲）自动跳过，不进入结果列表。
        SliceResult.slices 与 SliceResult.time_ranges 严格按索引对应。

        算法与旧版 DataProcessor._slice_data 完全对齐：
            boundaries = arange(t_min, t_max + step, step)
            for i in range(len(boundaries) - 1):
                mask = (toa >= boundaries[i]) & (toa < boundaries[i+1])
                if mask.any():
                    append slice and time_range

    参数说明：
        data (np.ndarray): shape=(N, 5) 的预处理后脉冲数组。
        slice_length (float): 时间窗口长度（0.1us），默认 2_500_000（250ms）。
        toa_col (int): TOA 列的列索引，默认 COL_TOA=4。
        session_id (str): 会话标识，用于日志追踪。

    返回值说明：
        SliceResult: 包含切片列表与时间范围列表的结果对象。
            - slice_count=0 当 data 为空时。

    异常说明：
        ValueError: data.ndim != 2 或列数不足时抛出。
        ValueError: slice_length <= 0 时抛出。
    """
    if data.ndim != 2 or data.shape[1] <= toa_col:
        raise ValueError(
            f"slice_by_toa: data 必须为至少 {toa_col + 1} 列的二维数组，"
            f"实际 shape={data.shape}"
        )
    if slice_length <= 0:
        raise ValueError(f"slice_length 必须 > 0，实际值={slice_length}")

    # 空数据直接返回
    if len(data) == 0:
        LOGGER.warning("接收到空数据，返回空切片结果", extra={"session_id": session_id})
        return SliceResult(slices=[], slice_length=slice_length)

    # 提取 TOA 列
    toa_values = data[:, toa_col]
    t_min = float(np.min(toa_values))
    t_max = float(np.max(toa_values))

    LOGGER.info(
        "开始切片，时间范围 [%.2f, %.2f] ms，步长 %.1f ms",
        t_min / 1e4, t_max / 1e4, slice_length / 1e4,
        extra={"session_id": session_id},
    )

    # 生成切片边界（包含右边 padding 以覆盖最后一条脉冲）
    # 边界情况：当 t_min == t_max（单条脉冲或所有脉冲 TOA 完全相同）时，
    # arange 仅生成单点 [t_min]，无法形成任何窗口。
    # 此时手动构造 [t_min, t_min + step] 两点边界，确保生成 1 个窗口。
    boundaries = np.arange(t_min, t_max + slice_length, slice_length)
    if len(boundaries) < 2:
        boundaries = np.array([t_min, t_min + slice_length])

    slices: list[SingleSlice] = []
    slice_index = 0

    # 遍历相邻边界对，提取各窗口内的脉冲
    for i in range(len(boundaries) - 1):
        start = float(boundaries[i])
        end = float(boundaries[i + 1])

        # 掩码：左闭右开区间 [start, end)
        mask = (toa_values >= start) & (toa_values < end)
        current_slice = data[mask]

        # 跳过空切片（与旧版行为一致）
        if len(current_slice) == 0:
            continue

        slices.append(SingleSlice(
            index=slice_index,
            data=current_slice,
            time_range=(start, end)
        ))
        slice_index += 1

    LOGGER.info(
        "切片完成，有效切片 %d 个（跳过空切片 %d 个）",
        len(slices),
        (len(boundaries) - 1) - len(slices),
        extra={"session_id": session_id},
    )

    return SliceResult(
        slices=slices,
        slice_length=slice_length,
    )


def slice_from_preprocess(
    result: PreprocessResult,
    slice_length: float = 2_500_000,
    session_id: str = "-",
) -> SliceResult:
    """从预处理结果直接切片（便捷包装）。

    功能描述：
        等同于 slice_by_toa(result.data, slice_length)，
        让调用方可以直接将 preprocess() 返回值传入。

    参数说明：
        result (PreprocessResult): preprocess() 的返回值。
        slice_length (float): 时间窗口长度（0.1us），默认 2_500_000（250ms）。
        session_id (str): 会话标识，用于日志追踪。

    返回值说明：
        SliceResult: 切片结果。

    异常说明：
        同 slice_by_toa。
    """
    return slice_by_toa(result.data, slice_length=slice_length, session_id=session_id)
