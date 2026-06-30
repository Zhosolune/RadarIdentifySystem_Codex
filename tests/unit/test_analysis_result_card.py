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
