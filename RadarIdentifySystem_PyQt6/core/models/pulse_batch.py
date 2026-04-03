# -*- coding: utf-8 -*-
"""core/models/pulse_batch.py — 脉冲批次输入数据结构。

本模块仅定义数据契约，不包含任何算法逻辑。
不依赖 UI / Qt / 线程，可在无 Qt 环境独立使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# 数据列索引（0-based），与 data_processor 保持一致
COL_CF = 0   # 载频 (MHz)
COL_PW = 1   # 脉宽 (us)
COL_DOA = 2  # 到达角 (度)
COL_PA = 3   # 脉冲幅度 (dB)
COL_TOA = 4  # 到达时间 (ms)


@dataclass
class PulseBatch:
    """经过归一化整理后的脉冲批次。

    功能描述：
        表示从任意来源（Excel / Bin / MAT）加载并完成列顺序整理后的
        原始脉冲数据集合，作为预处理与切片的统一输入契约。

    属性：
        data (np.ndarray): shape=(N, 5)，列顺序为
            [CF(MHz), PW(us), DOA(度), PA(dB), TOA(ms)]。
        source_path (str): 数据来源文件路径，用于日志与审计追踪。
        source_type (str): 数据来源类型，如 "excel" / "bin" / "mat"。
        total_pulses (int): 归一化前的脉冲总数（含无效脉冲）。

    参数说明：
        data: 归一化后的 ndarray，shape=(N, 5)。
        source_path: 文件路径字符串，默认空串。
        source_type: 来源类型标识，默认 "unknown"。
        total_pulses: 原始总脉冲数，默认 0（由调用方在过滤前记录）。
    """

    data: np.ndarray
    source_path: str = ""
    source_type: str = "unknown"
    total_pulses: int = 0

    def __post_init__(self) -> None:
        """校验数据形状合法性。

        功能描述：
            确保 data 为二维数组且列数恰好为 5，防止后续列索引越界。

        参数说明：
            无。

        返回值说明：
            None。

        异常说明：
            ValueError: data 的 ndim != 2 或 shape[1] != 5 时抛出。
        """
        if self.data.ndim != 2 or self.data.shape[1] != 5:
            raise ValueError(
                f"PulseBatch.data 必须为 shape=(N, 5) 的二维数组，"
                f"实际 shape={self.data.shape}"
            )

    @property
    def n_pulses(self) -> int:
        """当前批次有效脉冲总数（过滤后）。

        返回值说明：
            int: 脉冲数量。
        """
        return len(self.data)
