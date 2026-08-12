"""大端 PDW BIN 脉冲文件解析器。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeAlias

import numpy as np

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


BinDataFormat: TypeAlias = Literal["pdw_v1"]


class BinPulseParser:
    """解析每条 32 字节、由 16 个大端 uint16 组成的 PDW 文件。"""

    RECORD_WORD_COUNT = 16
    RECORD_SIZE = RECORD_WORD_COUNT * 2
    CHUNK_RECORD_COUNT = 100_000

    def parse(
        self,
        file_path: str,
        data_format: str | None = "pdw_v1",
    ) -> ParsedPulseSource:
        """分块解码 BIN 文件并保留当前项目所需的六个字段。

        Type 非 3/5/6 或 RF 为 0 的记录在结构解析阶段丢弃；F26 通过
        ``source_valid_mask`` 传给导入流程，PA=255 和 TOA 翻折由 Core 处理。
        PCSAOA/PCSPA 无效标记按既有行为不参与过滤，ACSPA 不乘 0.5。

        Args:
            file_path [str]: BIN 文件路径。
            data_format [str | None]: BIN 规则标识，目前仅支持 ``pdw_v1``。

        Returns:
            ParsedPulseSource: TOA 为原始 32 位 0.1us 计数值的六列数据。

        Raises:
            ValueError: 规则未知或文件长度不是 32 字节整数倍时抛出。
            OSError: 文件不存在或无法读取时抛出。

        Example:
            >>> BinPulseParser.RECORD_SIZE
            32
        """
        normalized_format = data_format or "pdw_v1"
        if normalized_format != "pdw_v1":
            raise ValueError(f"不支持的 BIN 数据格式：{normalized_format}")

        source_path = Path(file_path)
        file_size = source_path.stat().st_size
        if file_size % self.RECORD_SIZE != 0:
            raise ValueError(
                f"BIN 文件长度必须是 {self.RECORD_SIZE} 字节的整数倍，"
                f"实际为 {file_size} 字节"
            )

        data_chunks: list[np.ndarray] = []
        valid_mask_chunks: list[np.ndarray] = []
        total_records = file_size // self.RECORD_SIZE
        chunk_size = self.CHUNK_RECORD_COUNT * self.RECORD_SIZE
        with source_path.open("rb") as source_file:
            while chunk := source_file.read(chunk_size):
                chunk_data, chunk_valid_mask = self._decode_chunk(chunk)
                if len(chunk_data) == 0:
                    continue
                data_chunks.append(chunk_data)
                valid_mask_chunks.append(chunk_valid_mask)

        if data_chunks:
            normalized_data = np.vstack(data_chunks)
            source_valid_mask = np.concatenate(valid_mask_chunks)
        else:
            normalized_data = np.empty((0, PULSE_COLUMN_COUNT), dtype=float)
            source_valid_mask = np.empty((0,), dtype=bool)

        return ParsedPulseSource(
            data=normalized_data,
            source_path=str(source_path),
            source_type="bin",
            source_valid_mask=source_valid_mask,
            total_records=total_records,
        )

    def _decode_chunk(self, chunk: bytes) -> tuple[np.ndarray, np.ndarray]:
        """解码一个完整记录块并返回六列数据与 F26 有效性掩码。"""
        words = np.frombuffer(chunk, dtype=">u2").reshape(
            -1,
            self.RECORD_WORD_COUNT,
        )

        # Type 取 Word 1 低四位；RF=0 与旧实现一致视为结构无效记录。
        record_type = words[:, 0] & 0x0F
        rf_raw = words[:, 2]
        structural_mask = np.isin(record_type, (3, 5, 6)) & (rf_raw != 0)
        valid_words = words[structural_mask]
        if len(valid_words) == 0:
            return (
                np.empty((0, PULSE_COLUMN_COUNT), dtype=float),
                np.empty((0,), dtype=bool),
            )

        normalized_data = np.empty(
            (len(valid_words), PULSE_COLUMN_COUNT),
            dtype=float,
        )
        normalized_data[:, COL_CF] = valid_words[:, 2]
        normalized_data[:, COL_PW] = valid_words[:, 6] * 0.05
        # ACSPA 保持旧项目数值语义，不应用格式文档中的 0.5dB 缩放。
        normalized_data[:, COL_PA] = valid_words[:, 11] & 0xFF
        normalized_data[:, COL_DOA] = (valid_words[:, 7] & 0xFF) * 1.40625
        normalized_data[:, COL_PDOA] = valid_words[:, 14] * 0.01

        toa_high = valid_words[:, 4].astype(np.uint64) << 16
        toa_low = valid_words[:, 5].astype(np.uint64)
        normalized_data[:, COL_TOA] = toa_high + toa_low

        # F26 位于 Word 16 的 bit 10；PCSAOA/PCSPA 无效值不参与过滤。
        source_valid_mask = ((valid_words[:, 15] >> 10) & 0x01) == 0
        return normalized_data, source_valid_mask

