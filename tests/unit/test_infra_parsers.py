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

from core.models.pulse_batch import COL_CF, COL_DOA, COL_PA, COL_PW, COL_TOA
from infra.parsers import ExcelPulseParser


class TestExcelPulseParser(unittest.TestCase):
    """ExcelPulseParser 解析行为测试。"""

    def test_maps_legacy_columns(self) -> None:
        """验证 Excel 解析器按旧版固定列协议重排数据。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "sample.xlsx"
            source = pd.DataFrame(
                [
                    [0, 5100, 1.2, 0, 88, 42, 0, 123456],
                    [0, 6200, 2.4, 0, 99, 36, 0, 234567],
                ]
            )
            source.to_excel(excel_path, index=False)

            batch = ExcelPulseParser().parse(str(excel_path))

        self.assertEqual(batch.source_path, str(excel_path))
        self.assertEqual(batch.source_type, "excel")
        self.assertEqual(batch.total_pulses, 2)
        np.testing.assert_array_equal(batch.data[:, COL_CF], np.array([5100, 6200]))
        np.testing.assert_array_equal(batch.data[:, COL_PW], np.array([1.2, 2.4]))
        np.testing.assert_array_equal(batch.data[:, COL_DOA], np.array([88, 99]))
        np.testing.assert_array_equal(batch.data[:, COL_PA], np.array([42, 36]))
        np.testing.assert_array_equal(batch.data[:, COL_TOA], np.array([123456, 234567]))

    def test_keeps_toa_raw_unit(self) -> None:
        """验证 TOA 保持原始 0.1us 单位，不做旧版 /1e4 转换。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "toa_raw.xlsx"
            pd.DataFrame([[0, 1000, 2, 0, 30, 40, 0, 10000]]).to_excel(
                excel_path,
                index=False,
            )

            batch = ExcelPulseParser().parse(str(excel_path))

        self.assertEqual(batch.data[0, COL_TOA], 10000)

    def test_rejects_missing_columns(self) -> None:
        """验证列数不足时抛出明确异常。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "missing_columns.xlsx"
            pd.DataFrame([[1, 2, 3, 4, 5, 6, 7]]).to_excel(excel_path, index=False)

            with self.assertRaisesRegex(ValueError, "至少需要 8 列"):
                ExcelPulseParser().parse(str(excel_path))


if __name__ == "__main__":
    unittest.main()
