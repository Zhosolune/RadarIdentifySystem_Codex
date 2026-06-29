"""绘图选项卡片组件测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.models.processing_session import ProcessingSession
from ui.components.plot_option_card import PlotOptionCard


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_plot_option_card_updates_current_session_only() -> None:
    """绘图选项卡应只修改当前 session 的绘图快照。"""
    _app()
    changed: list[str] = []
    first_session = ProcessingSession(session_id="session-a")
    second_session = ProcessingSession(session_id="session-b")
    card = PlotOptionCard(
        session=first_session,
        on_config_changed=lambda: changed.append("saved"),
    )

    card.show_mode_combo.setCurrentIndex(0)
    card.scale_mode_combo.setCurrentIndex(2)

    assert first_session.config_snapshot.plot.only_show_identified == "ALL"
    assert first_session.config_snapshot.plot.scale_mode == "STRETCH_NEAREST_PRESERVE"
    assert second_session.config_snapshot.plot.only_show_identified == "IDENTIFIED_ONLY"
    assert second_session.config_snapshot.plot.scale_mode == "STRETCH"
    assert changed == ["saved", "saved"]


def test_plot_option_card_logs_plot_changes(monkeypatch) -> None:
    """绘图选项变更时应记录当前 session 的日志。"""
    _app()
    payloads: list[tuple[str, str]] = []
    session = ProcessingSession(session_id="session-log")

    def fake_info(message: str, value: str, extra: dict[str, str]) -> None:
        """记录日志调用参数。"""
        payloads.append((message % value, extra["session_id"]))

    monkeypatch.setattr("ui.components.plot_option_card.LOGGER.info", fake_info)
    card = PlotOptionCard(session=session)

    card.show_mode_combo.setCurrentIndex(0)
    card.scale_mode_combo.setCurrentIndex(1)

    assert payloads == [
        ("更新当前 Session 聚类展示模式：ALL", "session-log"),
        ("更新当前 Session 图像绘制模式：STRETCH_BILINEAR", "session-log"),
    ]
