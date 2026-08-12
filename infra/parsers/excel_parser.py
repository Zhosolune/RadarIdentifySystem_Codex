"""Excel 脉冲文件解析器。"""

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
)
from infra.parsers.base import ParsedPulseSource


ExcelDataFormat: TypeAlias = Literal["old", "new"]


class ExcelPulseParser:
    """将新旧 Excel 列布局归一化为统一六列脉冲数据。"""

    _MIN_COLUMN_COUNT = 8

    def parse(
        self,
        file_path: str,
        data_format: str | None = "old",
    ) -> ParsedPulseSource:
        """读取 Excel 文件并构造格式无关的解析结果。

        Args:
            file_path [str]: Excel 文件路径，支持 pandas 可读取的 xls/xlsx 文件。
            data_format [str | None]: ``old`` 表示旧格式，``new`` 表示新格式；
                为空时使用旧格式。

        Returns:
            ParsedPulseSource: TOA 保持原始 0.1us 单位的六列脉冲数据。

        Raises:
            ValueError: 格式未知、列数不足或数据无法转换为数值时抛出。
            OSError: 文件不存在或无法读取时由 pandas 抛出。

        Example:
            >>> parser = ExcelPulseParser()
            >>> isinstance(parser, ExcelPulseParser)
            True
        """
        normalized_format = data_format or "old"
        if normalized_format not in ("old", "new"):
            raise ValueError(f"不支持的 Excel 数据格式：{normalized_format}")

        source_path = str(Path(file_path))
        source_data = pd.read_excel(source_path).values
        if source_data.ndim != 2 or source_data.shape[1] < self._MIN_COLUMN_COUNT:
            raise ValueError(
                "Excel 文件至少需要 8 列，才能读取 CF/PW/PA/DOA/PDOA/TOA 数据"
            )

        # 外部列只在解析边界重排，下游始终消费固定六列契约。
        normalized_data = np.zeros(
            (len(source_data), PULSE_COLUMN_COUNT),
            dtype=float,
        )
        normalized_data[:, COL_CF] = source_data[:, 1]
        normalized_data[:, COL_DOA] = source_data[:, 4]
        normalized_data[:, COL_PA] = source_data[:, 5]
        if normalized_format == "new":
            normalized_data[:, COL_PW] = source_data[:, 3]
            normalized_data[:, COL_PDOA] = source_data[:, 7]
            normalized_data[:, COL_TOA] = source_data[:, 6]
        else:
            normalized_data[:, COL_PW] = source_data[:, 2]
            # 旧格式没有比相方位角，继续使用比幅方位角补齐统一列。
            normalized_data[:, COL_PDOA] = normalized_data[:, COL_DOA]
            normalized_data[:, COL_TOA] = source_data[:, 7]

        return ParsedPulseSource(
            data=normalized_data,
            source_path=source_path,
            source_type="excel",
            source_valid_mask=np.ones(len(normalized_data), dtype=bool),
            total_records=len(source_data),
        )

