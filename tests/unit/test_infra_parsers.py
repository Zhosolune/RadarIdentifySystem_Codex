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
from infra.parsers import ExcelPulseParser


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

            batch = ExcelPulseParser().parse(str(excel_path), data_format="old")

        self.assertEqual(batch.source_path, str(excel_path))
        self.assertEqual(batch.source_type, "excel")
        self.assertEqual(batch.total_pulses, 2)
        np.testing.assert_array_equal(batch.data[:, COL_CF], np.array([5100, 6200]))
        np.testing.assert_array_equal(batch.data[:, COL_PW], np.array([1.2, 2.4]))
        np.testing.assert_array_equal(batch.data[:, COL_DOA], np.array([88, 99]))
        np.testing.assert_array_equal(batch.data[:, COL_PDOA], np.array([88, 99]))
        np.testing.assert_array_equal(batch.data[:, COL_PA], np.array([42, 36]))
        np.testing.assert_array_equal(batch.data[:, COL_TOA], np.array([123456, 234567]))
        self.assertEqual(batch.data.shape, (2, 6))

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

            batch = ExcelPulseParser().parse(str(excel_path), data_format="new")

        expected = np.array(
            [
                [5100, 1.2, 42, 88, 77, 123456],
                [6200, 2.4, 36, 99, 66, 234567],
            ]
        )
        np.testing.assert_array_equal(batch.data, expected)

    def test_keeps_toa_raw_unit(self) -> None:
        """验证 TOA 保持原始 0.1us 单位，不做旧版 /1e4 转换。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "toa_raw.xlsx"
            pd.DataFrame([[0, 1000, 2, 0, 30, 40, 0, 10000]]).to_excel(
                excel_path,
                index=False,
            )

            batch = ExcelPulseParser().parse(str(excel_path), data_format="old")

        self.assertEqual(batch.data[0, COL_TOA], 10000)

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


if __name__ == "__main__":
    unittest.main()
