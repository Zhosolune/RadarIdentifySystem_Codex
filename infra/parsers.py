"""数据文件解析适配器。

本模块负责将外部数据文件读取并归一化为 core 层统一数据契约。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeAlias

import numpy as np
import pandas as pd

from core.models.pulse_batch import (
    COL_CF,
    COL_DOA,
    COL_PA,
    COL_PDOA,
    COL_PW,
    COL_TOA,
    PULSE_COLUMN_COUNT,
    PulseBatch,
)


ExcelDataFormat: TypeAlias = Literal["old", "new"]


class ExcelPulseParser:
    """Excel 雷达脉冲文件解析器。

    根据调用方选择的新旧格式读取 Excel，并统一转换为 ``PulseBatch`` 约定的
    ``[CF, PW, PA, DOA, PDOA, TOA]`` 六列数据。旧格式缺少 PDOA 时，使用
    同一行的 DOA 值补齐。
    """

    _MIN_COLUMN_COUNT = 8

    def parse(
        self,
        file_path: str,
        data_format: ExcelDataFormat = "old",
    ) -> PulseBatch:
        """读取 Excel 文件并构造脉冲批次。

        Args:
            file_path [str]: Excel 文件路径，支持 pandas 可读取的 xls/xlsx 文件。
            data_format [ExcelDataFormat]: 原始列格式，``old`` 表示旧格式，
                ``new`` 表示新格式，默认使用旧格式。

        Returns:
            PulseBatch: 归一化后的脉冲批次，TOA 保持原始 0.1us 单位。

        Raises:
            ValueError: 格式标识未知、Excel 列数不足 8 列或数据无法转换为数值时抛出。
            OSError: 文件不存在或无法读取时由 pandas 抛出。

        Example:
            >>> parser = ExcelPulseParser()
            >>> isinstance(parser, ExcelPulseParser)
            True
        """
        if data_format not in ("old", "new"):
            raise ValueError(f"不支持的 Excel 数据格式：{data_format}")

        source_path = str(Path(file_path))
        data_tmp = pd.read_excel(source_path).values
        if data_tmp.ndim != 2 or data_tmp.shape[1] < self._MIN_COLUMN_COUNT:
            raise ValueError(
                "Excel 文件至少需要 8 列，才能读取 CF/PW/PA/DOA/PDOA/TOA 数据"
            )

        # 解析器是外部格式进入算法的唯一列重排边界，下游只消费固定六列契约。
        raw_data = np.zeros((len(data_tmp), PULSE_COLUMN_COUNT), dtype=float)
        raw_data[:, COL_CF] = data_tmp[:, 1]
        raw_data[:, COL_DOA] = data_tmp[:, 4]
        raw_data[:, COL_PA] = data_tmp[:, 5]
        if data_format == "new":
            raw_data[:, COL_PW] = data_tmp[:, 3]
            raw_data[:, COL_PDOA] = data_tmp[:, 7]
            raw_data[:, COL_TOA] = data_tmp[:, 6]
        else:
            raw_data[:, COL_PW] = data_tmp[:, 2]
            # 旧格式没有比相方位角，按契约使用比幅方位角补齐。
            raw_data[:, COL_PDOA] = raw_data[:, COL_DOA]
            raw_data[:, COL_TOA] = data_tmp[:, 7]

        return PulseBatch(
            data=raw_data,
            source_path=source_path,
            source_type="excel",
            total_pulses=len(data_tmp),
        )
