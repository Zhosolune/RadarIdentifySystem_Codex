# -*- coding: utf-8 -*-
"""core/models/slice_result.py — 预处理与切片的输出数据结构。

本模块仅定义数据契约，不包含任何算法逻辑。
不依赖 UI / Qt / 线程，可在无 Qt 环境独立使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PreprocessResult:
    """预处理结果。

    功能描述：
        存储 preprocess.py 对原始 PulseBatch 完成 PA 清洗、
        TOA 翻折修复后的中间产物及统计信息。

    属性：
        data (np.ndarray): 预处理后的脉冲数据，shape=(M, 5)。
        total_pulses (int): 预处理前的脉冲总数。
        filtered_pulses (int): 因 PA=255 被剔除的脉冲数量。
        toa_flip_count (int): 检测到的时间翻折点数量。
        time_range_ms (float): 有效 TOA 的时间跨度（ms）。
        estimated_slice_count (int): 按默认 250ms 估算的切片数量。
        band (str | None): 根据 CF 均值推断的频段名称；<1000MHz 时为 None。
    """

    data: np.ndarray
    total_pulses: int = 0
    filtered_pulses: int = 0
    toa_flip_count: int = 0
    time_range_ms: float = 0.0
    estimated_slice_count: int = 0
    band: str | None = None

    @property
    def remaining_pulses(self) -> int:
        """预处理后剩余脉冲数量。

        返回值说明：
            int: 剩余脉冲数。
        """
        return len(self.data)


@dataclass
class SliceResult:
    """切片结果。

    功能描述：
        存储 slicing.py 对预处理数据完成时间维度切片后的结果集。
        slices 与 time_ranges 严格按索引对应，不包含空切片。

    属性：
        slices (list[np.ndarray]): 每个切片的脉冲数据数组列表，元素 shape=(K, 5)。
        time_ranges (list[tuple[float, float]]): 与 slices 一一对应的时间区间列表，
            每元素为 (start_ms, end_ms)。
        slice_length_ms (float): 本次切片所用的时间窗口长度（ms）。

    参数说明：
        slices: 切片数据列表，默认空列表。
        time_ranges: 时间区间列表，默认空列表。
        slice_length_ms: 切片步长，默认 250.0 ms。
    """

    slices: list[np.ndarray] = field(default_factory=list)
    time_ranges: list[tuple[float, float]] = field(default_factory=list)
    slice_length_ms: float = 250.0

    @property
    def slice_count(self) -> int:
        """实际有效切片数量（等于 slices 列表长度）。

        返回值说明：
            int: 切片总数。
        """
        return len(self.slices)

    def __post_init__(self) -> None:
        """校验 slices 与 time_ranges 长度一致性。

        功能描述：
            防止索引错位导致下游访问越界。

        异常说明：
            ValueError: slices 与 time_ranges 长度不一致时抛出。
        """
        if len(self.slices) != len(self.time_ranges):
            raise ValueError(
                f"SliceResult.slices 长度 ({len(self.slices)}) "
                f"与 time_ranges 长度 ({len(self.time_ranges)}) 不一致"
            )
