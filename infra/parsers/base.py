"""脉冲文件解析器公共契约。

解析器只负责把外部文件解码为统一六列数据，并提供格式特有的行有效性
掩码；波段拆分、PA 清洗和 TOA 翻折仍由 Core 统一处理。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from core.models.pulse_batch import PULSE_COLUMN_COUNT


@dataclass(frozen=True, slots=True)
class ParsedPulseSource:
    """保存单个来源文件完成字段解码后的脉冲数据。

    Attributes:
        data: 统一六列数据，列顺序为 ``CF/PW/PA/DOA/PDOA/TOA``。
        source_path: 原始文件路径。
        source_type: 来源类型，如 ``excel`` 或 ``bin``。
        source_valid_mask: 与数据逐行对应的格式特有有效性掩码。
        total_records: 文件中的物理记录总数，包含结构性无效记录。
    """

    data: np.ndarray
    source_path: str
    source_type: str
    source_valid_mask: np.ndarray
    total_records: int

    def __post_init__(self) -> None:
        """校验解析结果的数据形状和掩码长度。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 数据不是统一六列、掩码不是一维或长度不匹配时抛出。
        """
        if self.data.ndim != 2 or self.data.shape[1] != PULSE_COLUMN_COUNT:
            raise ValueError(
                f"解析结果必须为 shape=(N, {PULSE_COLUMN_COUNT}) 的二维数组，"
                f"实际 shape={self.data.shape}"
            )
        if self.source_valid_mask.ndim != 1:
            raise ValueError("source_valid_mask 必须为一维数组")
        if len(self.source_valid_mask) != len(self.data):
            raise ValueError("source_valid_mask 长度必须与数据行数一致")
        if self.total_records < len(self.data):
            raise ValueError("total_records 不能小于已解码数据行数")


class PulseSourceParser(Protocol):
    """外部脉冲文件解析器协议。"""

    def parse(
        self,
        file_path: str,
        data_format: str | None = None,
    ) -> ParsedPulseSource:
        """解析来源文件并返回统一字段数据。

        Args:
            file_path [str]: 待解析文件路径。
            data_format [str | None]: 来源内部格式规则；为空时使用解析器默认值。

        Returns:
            ParsedPulseSource: 完成字段解码的数据和格式特有有效性掩码。

        Raises:
            OSError: 文件不存在或无法读取时抛出。
            ValueError: 格式未知或文件内容不合法时抛出。
        """
