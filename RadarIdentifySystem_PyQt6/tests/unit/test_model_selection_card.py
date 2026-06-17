"""模型选择卡实例状态测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch
from qfluentwidgets import qconfig

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.app_config import appConfig
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


def test_model_selection_is_local_to_card(monkeypatch: MonkeyPatch) -> None:
    """切换模型时只更新卡片状态，不写入全局配置。"""
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
    original_pa = qconfig.get(appConfig.modelPaEnabledPath)
    original_dtoa = qconfig.get(appConfig.modelDtoaEnabledPath)

    card = ModelSelectionCard()
    card.pa_model_combo.setCurrentIndex(1)
    card.dtoa_model_combo.setCurrentIndex(1)

    assert card.selected_model_path("PA") == pa_paths[1]
    assert card.selected_model_path("DTOA") == dtoa_paths[1]
    assert qconfig.get(appConfig.modelPaEnabledPath) == original_pa
    assert qconfig.get(appConfig.modelDtoaEnabledPath) == original_dtoa
