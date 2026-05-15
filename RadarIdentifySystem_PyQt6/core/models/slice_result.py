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
        time_range (float): 有效 TOA 的时间跨度（0.1us）。
        estimated_slice_count (int): 按默认 250ms 估算的切片数量。
        band (str | None): 根据 CF 均值推断的频段名称；<1000MHz 时为 None。
    """

    data: np.ndarray
    total_pulses: int = 0
    filtered_pulses: int = 0
    toa_flip_count: int = 0
    time_range: float = 0.0
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
class SingleSlice:
    """单个切片数据容器。

    功能描述：
        存储单个切片的数据矩阵及其对应的时间范围与索引信息。

    属性：
        index (int): 切片在全局切片序列中的索引下标。
        data (np.ndarray): 本切片包含的脉冲数据，shape=(K, 5)。
        time_range (tuple[float, float]): 本切片的时间跨度 (start, end)，单位 0.1us。
    """

    index: int
    data: np.ndarray
    time_range: tuple[float, float]

    @property
    def pulse_count(self) -> int:
        """获取本切片的脉冲数量。

        返回值说明：
            int: 脉冲数。
        """
        return len(self.data)


@dataclass
class SliceResult:
    """切片结果集。

    功能描述：
        存储 slicing.py 对预处理数据完成时间维度切片后的结果集。
        内部通过 SingleSlice 对象列表来维护切片序列。

    属性：
        slices (list[SingleSlice]): 切片对象列表。
        slice_length (float): 本次切片所用的时间窗口长度（0.1us）。
    """

    slices: list[SingleSlice] = field(default_factory=list)
    slice_length: float = 2_500_000  # 250ms = 2,500,000 × 0.1us

    @property
    def slice_count(self) -> int:
        """实际有效切片数量。

        返回值说明：
            int: 切片总数。
        """
        return len(self.slices)
