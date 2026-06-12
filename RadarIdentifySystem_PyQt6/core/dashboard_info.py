# -*- coding: utf-8 -*-
"""文件仪表盘信息构建器。

本模块负责把核心预处理结果转换为不同文件类型的仪表盘摘要信息。
它属于 core 层纯数据逻辑，不依赖 Qt、UI 或 infra。
"""

from __future__ import annotations

from math import ceil

from core.models.dashboard_info import ExcelDashboardInfo, FileDashboardInfo
from core.models.pulse_batch import COL_TOA
from core.models.slice_result import PreprocessResult


class DashboardInfoManager:
    """按文件类型构建仪表盘摘要信息。

    该类集中管理不同数据文件类型的仪表盘指标派生规则。当前仅实现 Excel，
    bin/mat 后续接入时应新增对应构建方法，而不是把判断逻辑散落到 UI 或线程层。
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
            仪表盘摘要信息；暂未实现的文件类型返回 None。

        Raises:
            ValueError: 当 ``slice_length`` 小于或等于 0 时抛出。

        Example:
            >>> import numpy as np
            >>> from core.models.slice_result import PreprocessResult
            >>> result = PreprocessResult(data=np.empty((0, 5)))
            >>> DashboardInfoManager().build("bin", result) is None
            True
        """
        if slice_length <= 0:
            raise ValueError("slice_length 必须大于 0")

        normalized_type = source_type.strip().lower()
        if normalized_type == "excel":
            return self.build_excel_info(preprocess_result, slice_length)
        return None

    def build_excel_info(
        self,
        preprocess_result: PreprocessResult,
        slice_length: float = 2_500_000,
    ) -> ExcelDashboardInfo:
        """生成 Excel 文件仪表盘摘要信息。

        Args:
            preprocess_result: 已完成 PA 清洗和 TOA 翻折修正的预处理结果。
            slice_length: 切片长度，单位为 0.1us，必须大于 0。

        Returns:
            Excel 文件仪表盘摘要信息，包含总脉冲、剔除脉冲、幅度丢弃、
            持续时间、波段与预计切片数。

        Raises:
            ValueError: 当 ``slice_length`` 小于或等于 0 时抛出。

        Example:
            >>> import numpy as np
            >>> from core.models.slice_result import PreprocessResult
            >>> data = np.array([[5000, 1, 90, 100, 0], [5000, 1, 90, 100, 10]], dtype=float)
            >>> result = PreprocessResult(data=data, total_pulses=2, band="C波段")
            >>> DashboardInfoManager().build_excel_info(result).duration
            10.0
        """
        if slice_length <= 0:
            raise ValueError("slice_length 必须大于 0")

        duration = self._duration_from_fixed_toa(preprocess_result)
        estimated_slice_count = int(ceil(duration / slice_length)) if duration > 0 else 0

        # Excel 现阶段只有 PA=255 清洗一种剔除来源，因此二者保持一致。
        amplitude_dropped_pulses = preprocess_result.filtered_pulses
        return ExcelDashboardInfo(
            total_pulses=preprocess_result.total_pulses,
            removed_pulses=preprocess_result.filtered_pulses,
            amplitude_dropped_pulses=amplitude_dropped_pulses,
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
