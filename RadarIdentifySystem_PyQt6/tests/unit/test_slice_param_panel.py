"""切片参数面板组件测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.components import SliceParamPanel
from ui.components.export_option_card import ExportOptionCard
from ui.components.model_selection_card import ModelSelectionCard


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_slice_param_panel_owns_drawer_cards(monkeypatch: MonkeyPatch) -> None:
    """参数面板应集中持有抽屉中的三类卡片。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    panel = SliceParamPanel()

    assert panel.auto_recognize_card.parent() is panel
    assert isinstance(panel.model_selection_card, ModelSelectionCard)
    assert isinstance(panel.export_path_card, ExportOptionCard)
