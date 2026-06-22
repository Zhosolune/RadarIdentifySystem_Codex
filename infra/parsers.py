"""数据文件解析适配器。

本模块负责将外部数据文件读取并归一化为 core 层统一数据契约。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.models.pulse_batch import (
    COL_CF,
    COL_DOA,
    COL_PA,
    COL_PW,
    COL_TOA,
    PulseBatch,
)


class ExcelPulseParser:
    """Excel 雷达脉冲文件解析器。

    按旧版 `DataProcessor.load_excel_file()` 的固定列协议读取 Excel：
    CF/PW/DOA/PA/TOA 分别来自原始列 1/2/4/5/7，并归一化为
    `PulseBatch` 约定的 `[CF, PW, DOA, PA, TOA]`。
    """

    _MIN_COLUMN_COUNT = 8

    def parse(self, file_path: str) -> PulseBatch:
        """读取 Excel 文件并构造脉冲批次。

        Args:
            file_path: Excel 文件路径，支持 pandas 可读取的 xls/xlsx 文件。

        Returns:
            PulseBatch: 归一化后的脉冲批次，TOA 保持原始 0.1us 单位。

        Raises:
            ValueError: Excel 列数不足 8 列时抛出。
            OSError: 文件不存在或无法读取时由 pandas 抛出。

        Example:
            >>> parser = ExcelPulseParser()
            >>> isinstance(parser, ExcelPulseParser)
            True
        """
        source_path = str(Path(file_path))
        data_tmp = pd.read_excel(source_path).values
        if data_tmp.ndim != 2 or data_tmp.shape[1] < self._MIN_COLUMN_COUNT:
            raise ValueError(
                "Excel 文件至少需要 8 列，才能按旧版列协议读取 "
                "CF/PW/DOA/PA/TOA 数据"
            )

        raw_data = np.zeros((len(data_tmp), 5), dtype=float)
        raw_data[:, COL_CF] = data_tmp[:, 1]
        raw_data[:, COL_PW] = data_tmp[:, 2]
        raw_data[:, COL_DOA] = data_tmp[:, 4]
        raw_data[:, COL_PA] = data_tmp[:, 5]
        # 新项目统一保留原始 0.1us 单位，不执行旧版 / 1e4 转 ms。
        raw_data[:, COL_TOA] = data_tmp[:, 7]

        return PulseBatch(
            data=raw_data,
            source_path=source_path,
            source_type="excel",
            total_pulses=len(data_tmp),
        )
