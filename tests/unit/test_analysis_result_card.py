# -*- coding: utf-8 -*-
"""分析结果卡片组件单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme
from qfluentwidgets import TableWidget

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.style_sheet import StyleSheet
from core.models.extraction_result import ExtractedClusterParams
from core.models.recognition_result import ClusterRecognition
from ui.components.analysis_result_card import AnalysisResultCard, RoundedAnalysisHeaderView


_APP: QApplication | None = None


def _app() -> QApplication:
    """获取或创建测试用 QApplication。

    Args:
        无。

    Returns:
        QApplication: 当前进程内可用的 Qt 应用实例。

    Raises:
        无显式抛出异常。

    Example:
        >>> _app() is not None
        True
    """
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_analysis_result_card_builds_default_table() -> None:
    """分析结果卡片应封装表格结构和默认指标行。"""
    _app()
    card = AnalysisResultCard()

    try:
        expected_labels = [
            "载频/MHz",
            "脉宽/us",
            "PRI/us",
            "DOA/°",
            "PA预测结果",
            "PA预测分类",
            "DTOA预测结果",
            "DTOA预测分类",
            "联合预测概率",
        ]

        table = card.findChild(TableWidget, "analysisResultTable")

        assert table is card.table
        assert table.columnCount() == 2
        assert table.rowCount() == len(expected_labels)
        assert table.horizontalHeaderItem(0).text() == "雷达信号"
        assert table.horizontalHeaderItem(1).text() == "分析结果"
        assert isinstance(table.horizontalHeader(), RoundedAnalysisHeaderView)
        assert table.horizontalHeader().corner_radius == 5
        assert [table.item(row, 0).text() for row in range(table.rowCount())] == expected_labels
        assert [table.item(row, 1).text() for row in range(table.rowCount())] == [""] * len(
            expected_labels
        )
        assert all(
            table.item(row, column).font().pixelSize() == 14
            for row in range(table.rowCount())
            for column in range(table.columnCount())
        )
        assert table.verticalHeader().isHidden()
    finally:
        sip.delete(card)


def test_analysis_result_card_updates_from_cached_recognition() -> None:
    """分析结果表格应读取识别缓存并按显示规则格式化。"""
    _app()
    card = AnalysisResultCard()

    try:
        recognition = ClusterRecognition(
            slice_index=0,
            dim_name="CF",
            cluster_index=1,
            valid_cluster_index=0,
            pa_label=2,
            pa_confidence=0.87654,
            dtoa_label=3,
            dtoa_confidence=0.76543,
            is_valid=True,
            joint_prob=0.82345,
            pa_conf_dict={0: 0.0, 1: 0.12345, 2: 0.87654, 3: 0.5, 4: 0.33335},
            dtoa_conf_dict={0: 0.0, 1: 0.22225, 2: 0.33335, 3: 0.76543, 4: 0.11114},
            extracted_params=ExtractedClusterParams(
                cf_values=[1000.5],
                pw_values=[1.25],
                pri_values=[10.04, 20.05, 30.05, 40.05, 50.05, 60.05, 70.05],
                doa_values=[359.95],
            ),
        )

        card.update_from_recognition(recognition)
        table = card.table
        row_by_label = {
            table.item(row, 0).text(): row
            for row in range(table.rowCount())
        }

        assert table.item(row_by_label["载频/MHz"], 1).text() == "1001"
        assert table.item(row_by_label["脉宽/us"], 1).text() == "1.3"
        assert table.item(row_by_label["PRI/us"], 1).text() == (
            "10.0、20.1、30.1、40.1、50.1、60.1\n70.1"
        )
        assert table.item(row_by_label["DOA/°"], 1).text() == "360.0"
        assert table.item(row_by_label["PA预测结果"], 1).text() == "部分包络"
        assert table.item(row_by_label["PA预测分类"], 1).text() == (
            "完整包络: 0\n"
            "残缺包络: 0.1235\n"
            "部分包络: 0.8765\n"
            "相扫: 0.5000\n"
            "旁瓣: 0.3334\n"
            "非雷达信号: 0"
        )
        assert table.item(row_by_label["DTOA预测结果"], 1).text() == "脉间脉组参差"
        assert table.item(row_by_label["DTOA预测分类"], 1).text() == (
            "常规: 0\n"
            "脉间参差: 0.2223\n"
            "脉组参差: 0.3334\n"
            "脉间脉组参差: 0.7654\n"
            "组变脉间: 0.1111\n"
            "非雷达信号: 0"
        )
        assert table.item(row_by_label["联合预测概率"], 1).text() == "0.8235"
        assert table.rowHeight(row_by_label["PRI/us"]) >= card.DEFAULT_ROW_HEIGHT
        assert table.rowHeight(row_by_label["PA预测分类"]) > card.DEFAULT_ROW_HEIGHT
        assert table.rowHeight(row_by_label["DTOA预测分类"]) > card.DEFAULT_ROW_HEIGHT

        card.clear_results()
        assert [table.item(row, 1).text() for row in range(table.rowCount())] == [
            ""
        ] * table.rowCount()
    finally:
        sip.delete(card)


def test_analysis_result_card_applies_theme_aware_table_styles() -> None:
    """分析结果表格样式应由切片页面深浅主题 QSS 管理。"""
    _app()
    card = AnalysisResultCard()

    try:
        project_root = Path(__file__).resolve().parents[2]
        light_qss_path = project_root / "resources" / "qss" / "light" / "slice_interface.qss"
        dark_qss_path = project_root / "resources" / "qss" / "dark" / "slice_interface.qss"
        old_light_qss_path = project_root / "resources" / "qss" / "light" / "analysis_result_card.qss"
        old_dark_qss_path = project_root / "resources" / "qss" / "dark" / "analysis_result_card.qss"
        light_qss = light_qss_path.read_text(encoding="utf-8")
        dark_qss = dark_qss_path.read_text(encoding="utf-8")

        assert light_qss_path.name == "slice_interface.qss"
        assert dark_qss_path.name == "slice_interface.qss"
        assert Path(StyleSheet.SLICE_INTERFACE.path(Theme.LIGHT)) == light_qss_path
        assert not old_light_qss_path.exists()
        assert not old_dark_qss_path.exists()
        assert "ANALYSIS_RESULT_CARD" not in StyleSheet.__members__
        assert "QTableView#analysisResultTable" in light_qss
        assert "QTableView {" not in light_qss
        assert "QTableView::item" not in light_qss
        assert "QTableView#analysisResultTable" in dark_qss
        assert card.table.horizontalHeader().styleSheet() == ""
    finally:
        sip.delete(card)
