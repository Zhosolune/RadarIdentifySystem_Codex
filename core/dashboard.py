# -*- coding: utf-8 -*-
"""文件仪表盘信息构建器。

本模块负责把核心预处理结果转换为不同文件类型的仪表盘摘要信息。
它属于 core 层纯数据逻辑，不依赖 Qt、UI 或 infra。
"""

from __future__ import annotations

from math import ceil

from core.models.dashboard_info import FileDashboardInfo, PulseDashboardInfo
from core.models.pulse_batch import COL_TOA
from core.models.slice_result import PreprocessResult


class DashboardInfoManager:
    """按文件类型构建仪表盘摘要信息。

    该类从统一预处理结果派生数据包摘要，不依赖 Excel、BIN 等外部容器格式。
    """

    def build(
        self,
        source_type: str,
        preprocess_result: PreprocessResult,
        slice_length: float = 2_500_000,
    ) -> FileDashboardInfo | None:
        """按文件类型生成仪表盘摘要信息。

        Args:
            source_type: 文件类型标识，例如 ``excel``、``bin`` 或 ``mat``。
            preprocess_result: 已完成 PA 清洗和 TOA 翻折修正的预处理结果。
            slice_length: 切片长度，单位为 0.1us，必须大于 0。

        Returns:
            仪表盘摘要信息。

        Raises:
            ValueError: 当 ``slice_length`` 小于或等于 0 时抛出。

        Example:
            >>> import numpy as np
            >>> from core.models.slice_result import PreprocessResult
            >>> result = PreprocessResult(data=np.empty((0, 6)))
            >>> DashboardInfoManager().build("bin", result).total_pulses
            0
        """
        if slice_length <= 0:
            raise ValueError("slice_length 必须大于 0")

        return self.build_pulse_info(preprocess_result, slice_length)

    def build_pulse_info(
        self,
        preprocess_result: PreprocessResult,
        slice_length: float = 2_500_000,
    ) -> PulseDashboardInfo:
        """生成统一脉冲数据包的仪表盘摘要信息。

        Args:
            preprocess_result: 已完成 PA 清洗和 TOA 翻折修正的预处理结果。
            slice_length: 切片长度，单位为 0.1us，必须大于 0。

        Returns:
            脉冲数据包摘要信息，包含总脉冲、剔除脉冲、幅度丢弃、
            持续时间、波段与预计切片数。

        Raises:
            ValueError: 当 ``slice_length`` 小于或等于 0 时抛出。

        Example:
            >>> import numpy as np
            >>> from core.models.slice_result import PreprocessResult
            >>> data = np.array([[5000, 1, 100, 90, 90, 0], [5000, 1, 100, 90, 90, 10]], dtype=float)
            >>> result = PreprocessResult(data=data, total_pulses=2, band="C波段")
            >>> DashboardInfoManager().build_pulse_info(result).duration
            10.0
        """
        if slice_length <= 0:
            raise ValueError("slice_length 必须大于 0")

        duration = self._duration_from_fixed_toa(preprocess_result)
        estimated_slice_count = int(ceil(duration / slice_length)) if duration > 0 else 0

        return PulseDashboardInfo(
            total_pulses=preprocess_result.total_pulses,
            removed_pulses=preprocess_result.filtered_pulses,
            amplitude_dropped_pulses=(
                preprocess_result.amplitude_dropped_pulses
            ),
            duration=duration,
            band=preprocess_result.band,
            estimated_slice_count=estimated_slice_count,
        )

    def _duration_from_fixed_toa(self, preprocess_result: PreprocessResult) -> float:
        """从翻折修正后的 TOA 列计算持续时间。"""
        if len(preprocess_result.data) == 0:
            return 0.0

        toa_values = preprocess_result.data[:, COL_TOA]
        return float(toa_values[-1] - toa_values[0])
