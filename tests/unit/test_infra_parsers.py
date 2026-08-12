"""infra.parsers 单元测试。

运行方式：
    python tests/unit/test_infra_parsers.py
    python -m pytest tests/unit/test_infra_parsers.py -v
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.models.pulse_batch import (
    COL_CF,
    COL_DOA,
    COL_PA,
    COL_PDOA,
    COL_PW,
    COL_TOA,
    PulseBatch,
)
from infra.parsers import BinPulseParser, ExcelPulseParser, create_pulse_parser


class TestExcelPulseParser(unittest.TestCase):
    """ExcelPulseParser 解析行为测试。"""

    def test_maps_legacy_columns(self) -> None:
        """验证旧格式映射到六列契约并使用 DOA 补齐 PDOA。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "sample.xlsx"
            source = pd.DataFrame(
                [
                    [0, 5100, 1.2, 0, 88, 42, 0, 123456],
                    [0, 6200, 2.4, 0, 99, 36, 0, 234567],
                ]
            )
            source.to_excel(excel_path, index=False)

            parsed = ExcelPulseParser().parse(str(excel_path), data_format="old")

        self.assertEqual(parsed.source_path, str(excel_path))
        self.assertEqual(parsed.source_type, "excel")
        self.assertEqual(parsed.total_records, 2)
        np.testing.assert_array_equal(parsed.source_valid_mask, np.ones(2, dtype=bool))
        np.testing.assert_array_equal(parsed.data[:, COL_CF], np.array([5100, 6200]))
        np.testing.assert_array_equal(parsed.data[:, COL_PW], np.array([1.2, 2.4]))
        np.testing.assert_array_equal(parsed.data[:, COL_DOA], np.array([88, 99]))
        np.testing.assert_array_equal(parsed.data[:, COL_PDOA], np.array([88, 99]))
        np.testing.assert_array_equal(parsed.data[:, COL_PA], np.array([42, 36]))
        np.testing.assert_array_equal(parsed.data[:, COL_TOA], np.array([123456, 234567]))
        self.assertEqual(parsed.data.shape, (2, 6))

    def test_maps_new_columns(self) -> None:
        """验证新格式按指定原始列映射到统一六列契约。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "new_format.xlsx"
            source = pd.DataFrame(
                [
                    [0, 5100, 999, 1.2, 88, 42, 123456, 77],
                    [0, 6200, 888, 2.4, 99, 36, 234567, 66],
                ]
            )
            source.to_excel(excel_path, index=False)

            parsed = ExcelPulseParser().parse(str(excel_path), data_format="new")

        expected = np.array(
            [
                [5100, 1.2, 42, 88, 77, 123456],
                [6200, 2.4, 36, 99, 66, 234567],
            ]
        )
        np.testing.assert_array_equal(parsed.data, expected)

    def test_keeps_toa_raw_unit(self) -> None:
        """验证 TOA 保持原始 0.1us 单位，不做旧版 /1e4 转换。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "toa_raw.xlsx"
            pd.DataFrame([[0, 1000, 2, 0, 30, 40, 0, 10000]]).to_excel(
                excel_path,
                index=False,
            )

            parsed = ExcelPulseParser().parse(str(excel_path), data_format="old")

        self.assertEqual(parsed.data[0, COL_TOA], 10000)

    def test_rejects_missing_columns(self) -> None:
        """验证列数不足时抛出明确异常。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "missing_columns.xlsx"
            pd.DataFrame([[1, 2, 3, 4, 5, 6, 7]]).to_excel(excel_path, index=False)

            with self.assertRaisesRegex(ValueError, "至少需要 8 列"):
                ExcelPulseParser().parse(str(excel_path))

    def test_rejects_unknown_data_format(self) -> None:
        """验证未知 Excel 格式不会被静默按某一协议解析。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "unknown_format.xlsx"
            pd.DataFrame([[0, 1, 2, 3, 4, 5, 6, 7]]).to_excel(
                excel_path,
                index=False,
            )

            with self.assertRaisesRegex(ValueError, "不支持的 Excel 数据格式"):
                ExcelPulseParser().parse(str(excel_path), data_format="unknown")

    def test_pulse_batch_rejects_non_normalized_column_count(self) -> None:
        """验证算法入口拒绝旧五列数组，避免下游静默错读列。"""
        with self.assertRaisesRegex(ValueError, r"shape=\(N, 6\)"):
            PulseBatch(data=np.zeros((1, 5), dtype=float))


class TestBinPulseParser(unittest.TestCase):
    """BinPulseParser 字段解码和旧规则兼容性测试。"""

    @staticmethod
    def _record(
        *,
        record_type: int = 3,
        rf: int = 1500,
        toa: int = 100,
        pw: int = 20,
        acsaoa: int = 10,
        acspa: int = 100,
        pcsp: int = 0,
        pcsaoa: int = 200,
        f26: int = 0,
    ) -> np.ndarray:
        """构造一条符合 16 Word 布局的测试 PDW。"""
        words = np.zeros(16, dtype=">u2")
        words[0] = record_type
        words[2] = rf
        words[4] = (toa >> 16) & 0xFFFF
        words[5] = toa & 0xFFFF
        words[6] = pw
        words[7] = acsaoa
        words[11] = ((pcsp & 0xFF) << 8) | (acspa & 0xFF)
        words[14] = pcsaoa
        words[15] = (f26 & 0x01) << 10
        return words

    def test_decodes_big_endian_fields_without_pa_scaling(self) -> None:
        """验证大端字段、原始 PA、PDOA 无效值和 F26 掩码。"""
        records = np.vstack(
            (
                self._record(
                    rf=1500,
                    toa=0x12345678,
                    acspa=100,
                    pcsp=255,
                    pcsaoa=65535,
                ),
                self._record(record_type=5, rf=3000, f26=1),
                self._record(record_type=6, rf=5000, acspa=255),
                self._record(record_type=2, rf=1500),
                self._record(record_type=3, rf=0),
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_path = Path(temp_dir) / "sample.bin"
            bin_path.write_bytes(records.astype(">u2", copy=False).tobytes())
            parsed = BinPulseParser().parse(str(bin_path), data_format="pdw_v1")

        self.assertEqual(parsed.total_records, 5)
        self.assertEqual(parsed.data.shape, (3, 6))
        np.testing.assert_array_equal(parsed.source_valid_mask, [True, False, True])
        self.assertEqual(parsed.data[0, COL_CF], 1500)
        self.assertEqual(parsed.data[0, COL_PW], 1.0)
        self.assertEqual(parsed.data[0, COL_PA], 100)
        self.assertEqual(parsed.data[0, COL_DOA], 14.0625)
        self.assertEqual(parsed.data[0, COL_PDOA], 655.35)
        self.assertEqual(parsed.data[0, COL_TOA], 0x12345678)
        self.assertEqual(parsed.data[2, COL_PA], 255)

    def test_rejects_incomplete_record(self) -> None:
        """验证残缺的 32 字节记录不会被静默截断。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_path = Path(temp_dir) / "broken.bin"
            bin_path.write_bytes(b"\x00" * 31)
            with self.assertRaisesRegex(ValueError, "32 字节的整数倍"):
                BinPulseParser().parse(str(bin_path))

    def test_registry_rejects_unknown_source_type(self) -> None:
        """验证解析器注册表不会为未知来源隐式选择实现。"""
        self.assertIsInstance(create_pulse_parser("bin"), BinPulseParser)
        with self.assertRaisesRegex(ValueError, "暂不支持解析"):
            create_pulse_parser("mat")


if __name__ == "__main__":
    unittest.main()
