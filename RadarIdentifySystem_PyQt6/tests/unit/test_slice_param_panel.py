"""切片参数面板组件测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch
from qfluentwidgets import ScrollArea, qconfig

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.app_config import appConfig
from core.models.processing_session import ProcessingSession
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
    session = ProcessingSession()
    panel = SliceParamPanel(session=session)

    assert isinstance(panel.drawer_scroll_area, ScrollArea)
    assert panel.drawer_scroll_area.widgetResizable()
    assert panel.drawer_scroll_area.widget() is panel.drawer_scroll_widget

    margins = panel.drawer_scroll_layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        16,
        8,
        16,
        16,
    )
    assert panel.auto_recognize_card.parent() is panel.cards_group
    assert panel.auto_recognize_item.value is True
    assert isinstance(panel.model_selection_card, ModelSelectionCard)
    assert panel.model_selection_card.parent() is panel.cards_group
    assert isinstance(panel.export_path_card, ExportOptionCard)
    assert panel.export_path_card.parent() is panel.cards_group


def test_slice_param_panel_updates_session_auto_recognize_only(
    monkeypatch: MonkeyPatch,
) -> None:
    """自动识别卡片应只修改当前 session 子配置。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    changed: list[str] = []
    session = ProcessingSession()
    global_value = qconfig.get(appConfig.autoRecognizeNextSlice)
    panel = SliceParamPanel(
        session=session,
        on_config_changed=lambda: changed.append("saved"),
    )

    panel.auto_recognize_card.setChecked(False)

    assert session.config_snapshot.business.auto_recognize_next_slice is False
    assert panel.auto_recognize_item.value is False
    assert changed == ["saved"]
    assert qconfig.get(appConfig.autoRecognizeNextSlice) == global_value


def test_slice_param_panel_binds_model_selection_to_session(
    monkeypatch: MonkeyPatch,
) -> None:
    """模型选择卡片应写入当前 session 的模型选择快照。"""
    _app()
    pa_paths = [r"C:\models\pa-default.onnx", r"C:\models\pa-session.onnx"]
    dtoa_paths = [r"C:\models\dtoa-default.onnx", r"C:\models\dtoa-session.onnx"]
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: pa_paths if model_type == "PA" else dtoa_paths,
    )
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_enabled_model_path",
        lambda model_type: pa_paths[0] if model_type == "PA" else dtoa_paths[0],
    )
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_display_name",
        lambda path, model_type: Path(path).stem,
    )
    changed: list[str] = []
    session = ProcessingSession()

    panel = SliceParamPanel(
        session=session,
        on_config_changed=lambda: changed.append("saved"),
    )

    assert session.model_selection.pa_model_path == pa_paths[0]
    assert session.model_selection.dtoa_model_path == dtoa_paths[0]
    assert changed == []

    panel.model_selection_card.pa_model_combo.setCurrentIndex(1)
    panel.model_selection_card.dtoa_model_combo.setCurrentIndex(1)

    assert session.model_selection.pa_model_path == pa_paths[1]
    assert session.model_selection.dtoa_model_path == dtoa_paths[1]
    assert changed == ["saved", "saved"]
