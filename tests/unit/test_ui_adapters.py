"""UI 适配策略单元测试。"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from ui.adapters import ResponsiveContentWidthAdapter


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_responsive_content_width_adapter_centers_only_wide_content() -> None:
    """响应式适配器应在宽区域居中，在窄区域保留最小边距。"""
    _app()
    widget = QWidget()
    layout = QVBoxLayout(widget)
    adapter = ResponsiveContentWidthAdapter(
        widget,
        layout,
        max_content_width=860,
    )

    widget.resize(1000, 600)
    adapter.update_margins()
    assert layout.contentsMargins().left() == 70
    assert layout.contentsMargins().right() == 70

    widget.resize(800, 600)
    adapter.update_margins()
    assert layout.contentsMargins().left() == 36
    assert layout.contentsMargins().right() == 36
