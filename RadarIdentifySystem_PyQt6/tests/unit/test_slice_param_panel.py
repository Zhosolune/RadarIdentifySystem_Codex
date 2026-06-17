"""切片参数面板组件测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch
from qfluentwidgets import ScrollArea, SimpleCardWidget

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.components import SliceParamPanel
from ui.components.export_option_card import ExportOptionCard
from ui.components.model_selection_card import ModelSelectionCard
from ui.components.jitter_free_container import JitterFreeCardGroup


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

    assert isinstance(panel.scroll_area, ScrollArea)
    assert panel.scroll_area.widgetResizable()
    assert panel.scroll_area.widget() is panel.scroll_content_widget
    assert isinstance(panel.panel_card, SimpleCardWidget)
    assert isinstance(panel.cards_group, JitterFreeCardGroup)

    margins = panel.scroll_content_layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        16,
        8,
        16,
        16,
    )
    assert panel.auto_recognize_card.parent() is panel.cards_group
    assert isinstance(panel.model_selection_card, ModelSelectionCard)
    assert panel.model_selection_card.parent() is panel.cards_group
    assert isinstance(panel.export_path_card, ExportOptionCard)
    assert panel.export_path_card.parent() is panel.cards_group
