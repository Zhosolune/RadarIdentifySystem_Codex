"""切片页面双入口导航连接测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.controllers.identify_controller import IdentifyController
from ui.controllers.slice_controller import SliceController
from ui.interfaces.slice_interface import SliceInterface


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_graphic_and_text_navigation_buttons_share_controller_slots(
    monkeypatch: MonkeyPatch,
) -> None:
    """图形和文字导航按钮应触发同一组控制器槽函数。"""
    _app()
    calls = {
        "prev_slice": 0,
        "next_slice": 0,
        "prev_cluster": 0,
        "next_cluster": 0,
    }

    def count(name: str) -> Callable[[object], None]:
        """创建记录指定槽函数调用次数的替代函数。"""

        def slot(controller: object) -> None:
            """记录一次控制器槽函数调用。"""
            calls[name] += 1

        return slot

    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    monkeypatch.setattr(SliceController, "_on_prev_slice", count("prev_slice"))
    monkeypatch.setattr(SliceController, "_on_next_slice", count("next_slice"))
    monkeypatch.setattr(IdentifyController, "_on_prev_cluster", count("prev_cluster"))
    monkeypatch.setattr(IdentifyController, "_on_next_cluster", count("next_cluster"))
    interface = SliceInterface()

    interface.prev_slice_button.click()
    interface.navigation_control_card.prev_slice_button.click()
    interface.next_slice_button.click()
    interface.navigation_control_card.next_slice_button.click()
    interface.prev_cluster_button.click()
    interface.navigation_control_card.prev_cluster_button.click()
    interface.next_cluster_button.click()
    interface.navigation_control_card.next_cluster_button.click()

    assert calls == {
        "prev_slice": 2,
        "next_slice": 2,
        "prev_cluster": 2,
        "next_cluster": 2,
    }
    # 控制器定时器与页面存在引用环，测试结束时显式释放 Qt 对象。
    sip.delete(interface)
