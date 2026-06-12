# -*- coding: utf-8 -*-
"""文件仪表盘信息数据模型。

本模块只定义不同文件类型的仪表盘摘要数据契约，不包含 UI 展示逻辑，
也不依赖 Qt、pandas 或后台线程。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class ExcelDashboardInfo:
    """Excel 文件仪表盘摘要信息。

    Attributes:
        total_pulses: 原始脉冲总数。
        removed_pulses: 预处理阶段剔除的脉冲数量。
        amplitude_dropped_pulses: 因幅度无效被丢弃的脉冲数量。
        duration: 翻折修正后的持续时间，单位为 0.1us。
        band: 根据 CF 均值推断的波段名称；无法判断时为 None。
        estimated_slice_count: 按切片长度估算的切片数量。

    Example:
        >>> info = ExcelDashboardInfo(10, 2, 2, 2500000.0, "C波段", 1)
        >>> info.amplitude_dropped_pulses == info.removed_pulses
        True
    """

    total_pulses: int
    removed_pulses: int
    amplitude_dropped_pulses: int
    duration: float
    band: str | None
    estimated_slice_count: int


FileDashboardInfo: TypeAlias = ExcelDashboardInfo
"""所有文件类型仪表盘摘要信息的联合类型。

后续接入 bin/mat 时在此处扩展联合类型，避免 UI 层绑定到具体算法过程。
"""
