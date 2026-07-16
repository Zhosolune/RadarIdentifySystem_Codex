"""切片页面双入口导航连接测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import numpy as np
from PyQt6 import sip
from PyQt6.QtWidgets import QApplication, QLayout
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.models.cluster_result import (
    ClusterItem,
    ClusterState,
    ClusteringResult,
    SliceClusterResult,
)
from core.models.recognition_result import (
    ClusterRecognition,
    RecognitionResult,
    SliceRecognitionResult,
)
from core.models.processing_session import ProcessingSession
from core.models.slice_result import SingleSlice, SliceResult
from app.signal_bus import signal_bus
from ui.controllers.identify_controller import IdentifyController
from ui.controllers.slice_controller import SliceController
from ui.components.navigation_control_card import NavigationControlCard
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


def _layout_widgets(layout: QLayout) -> list[object]:
    """返回布局中按顺序排列的直接子控件。"""
    return [
        item.widget()
        for index in range(layout.count())
        if (item := layout.itemAt(index)).widget() is not None
    ]


def test_navigation_card_uses_requested_two_row_button_order() -> None:
    """导航卡应按切片行和类别行固定排列按钮。"""
    _app()
    card = NavigationControlCard()

    try:
        assert card.merge_menu_button.text() == "合并菜单"
        assert _layout_widgets(card.slice_navigation_layout) == [
            card.prev_slice_button,
            card.next_slice_button,
            card.merge_menu_button,
        ]
        assert _layout_widgets(card.cluster_navigation_layout) == [
            card.prev_cluster_button,
            card.next_cluster_button,
            card.reset_cur_slice_button,
        ]
    finally:
        sip.delete(card)


def _fake_cluster_bundle() -> object:
    """构造测试用的伪造聚类图像包。"""
    return type(
        "FakeBundle",
        (),
        {
            "images": {
                "CF": np.zeros((4, 4), dtype=np.uint8),
                "PW": np.zeros((4, 4), dtype=np.uint8),
                "PA": np.zeros((4, 4), dtype=np.uint8),
                "DTOA": np.zeros((4, 4), dtype=np.uint8),
                "DOA": np.zeros((4, 4), dtype=np.uint8),
            }
        },
    )()


def _fake_slice_bundle() -> object:
    """构造测试用的伪造切片图像包。"""
    return _fake_cluster_bundle()


def _build_cluster(cluster_idx: int, dim_name: str, state: ClusterState) -> ClusterItem:
    """构造测试用的聚类簇。"""
    return ClusterItem(
        cluster_idx=cluster_idx,
        dim_name=dim_name,
        points=np.zeros((4, 5), dtype=float),
        points_indices=np.arange(4),
        slice_idx=0,
        time_ranges=(0.0, 1.0),
        state=state,
        valid_cluster_idx=0 if state is ClusterState.VALID else None,
    )


def _build_recognition_result() -> RecognitionResult:
    """构造同时包含有效簇和无效簇的识别结果。"""
    return RecognitionResult(
        slice_results={
            0: SliceRecognitionResult(
                slice_index=0,
                valid_clusters=[
                    ClusterRecognition(0, "CF", 1, 0, 1, 0.9, 1, 0.8, True),
                ],
                invalid_clusters=[
                    ClusterRecognition(0, "PW", 2, None, 2, 0.2, 2, 0.1, False),
                ],
            )
        }
    )


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
    try:
        interface.plot_option_card.show_mode_item.set("IDENTIFIED_ONLY")
        interface._session.slice_result = SliceResult(
            slices=[
                SingleSlice(0, np.zeros((2, 5), dtype=float), (0.0, 1.0)),
                SingleSlice(1, np.ones((2, 5), dtype=float), (1.0, 2.0)),
                SingleSlice(2, np.full((2, 5), 2.0, dtype=float), (2.0, 3.0)),
            ]
        )
        interface._session.cluster_result = ClusteringResult(
            slice_results={
                1: SliceClusterResult(
                    slice_idx=1,
                    clusters=[
                        _build_cluster(1, "CF", ClusterState.VALID),
                        _build_cluster(2, "PW", ClusterState.VALID),
                        _build_cluster(3, "CF", ClusterState.VALID),
                    ],
                )
            }
        )
        interface._slice_controller._load_slice_image(1)
        interface._session.mark_slice_cluster_succeeded(1)
        interface._session.mark_slice_recognition_succeeded(1)
        interface._session.recognition_result = RecognitionResult(
            slice_results={
                1: SliceRecognitionResult(
                    slice_index=1,
                    valid_clusters=[
                        ClusterRecognition(1, "CF", 1, 0, 1, 0.9, 1, 0.8, True),
                        ClusterRecognition(1, "PW", 2, 1, 2, 0.85, 2, 0.75, True),
                        ClusterRecognition(1, "CF", 3, 2, 3, 0.8, 3, 0.7, True),
                    ],
                )
            }
        )
        interface._identify_controller._current_cluster_index = 1
        interface._identify_controller.update_cluster_navigation_buttons(1)

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
    finally:
        # 控制器定时器与页面存在引用环，测试结束时显式释放 Qt 对象。
        sip.delete(interface)


def test_navigation_buttons_are_disabled_in_initial_state(
    monkeypatch: MonkeyPatch,
) -> None:
    """初始状态下两组导航按钮和聚类标题应处于空态。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    assert interface.cluster_title_label.text() == "暂无聚类结果"
    assert not interface.prev_slice_button.isEnabled()
    assert not interface.next_slice_button.isEnabled()
    assert not interface.navigation_control_card.prev_slice_button.isEnabled()
    assert not interface.navigation_control_card.next_slice_button.isEnabled()
    assert not interface.prev_cluster_button.isEnabled()
    assert not interface.next_cluster_button.isEnabled()
    assert not interface.navigation_control_card.prev_cluster_button.isEnabled()
    assert not interface.navigation_control_card.next_cluster_button.isEnabled()

    sip.delete(interface)


def test_navigation_buttons_follow_slice_and_cluster_boundaries(
    monkeypatch: MonkeyPatch,
) -> None:
    """切片和类别导航按钮应根据边界索引同步禁用。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()
    try:
        interface.plot_option_card.show_mode_item.set("IDENTIFIED_ONLY")
        interface._session.slice_result = SliceResult(
            slices=[
                SingleSlice(0, np.zeros((2, 5), dtype=float), (0.0, 1.0)),
                SingleSlice(1, np.ones((2, 5), dtype=float), (1.0, 2.0)),
            ]
        )
        interface._session.cluster_result = ClusteringResult(
            slice_results={
                0: SliceClusterResult(
                    slice_idx=0,
                    clusters=[
                        _build_cluster(1, "CF", ClusterState.VALID),
                        _build_cluster(2, "PW", ClusterState.VALID),
                    ],
                )
            }
        )
        interface._slice_controller.refresh_navigation_state()
        interface._slice_controller._load_slice_image(0)

        assert not interface.prev_slice_button.isEnabled()
        assert interface.next_slice_button.isEnabled()
        assert not interface.navigation_control_card.prev_slice_button.isEnabled()
        assert interface.navigation_control_card.next_slice_button.isEnabled()

        interface._session.mark_slice_cluster_succeeded(0)
        interface._session.mark_slice_recognition_succeeded(0)
        interface._session.recognition_result = RecognitionResult(
            slice_results={
                0: SliceRecognitionResult(
                    slice_index=0,
                    valid_clusters=[
                        ClusterRecognition(0, "CF", 1, 0, 1, 0.9, 1, 0.8, True),
                        ClusterRecognition(0, "PW", 2, 1, 2, 0.85, 2, 0.75, True),
                    ],
                )
            }
        )

        interface._identify_controller._current_cluster_index = 0
        interface._identify_controller.update_cluster_navigation_buttons(0)
        assert not interface.prev_cluster_button.isEnabled()
        assert interface.next_cluster_button.isEnabled()
        assert not interface.navigation_control_card.prev_cluster_button.isEnabled()
        assert interface.navigation_control_card.next_cluster_button.isEnabled()

        interface._identify_controller._current_cluster_index = 1
        interface._identify_controller.update_cluster_navigation_buttons(0)
        assert interface.prev_cluster_button.isEnabled()
        assert not interface.next_cluster_button.isEnabled()
        assert interface.navigation_control_card.prev_cluster_button.isEnabled()
        assert not interface.navigation_control_card.next_cluster_button.isEnabled()
    finally:
        sip.delete(interface)


def test_next_slice_auto_recognize_passes_target_slice_index(
    monkeypatch: MonkeyPatch,
) -> None:
    """下一片自动识别应显式使用切换后的目标切片索引。"""
    _app()
    captured_indices: list[int | None] = []

    def fake_handle_identify(
        controller: IdentifyController,
        target_slice_index: int | None = None,
    ) -> None:
        """记录自动识别入口收到的目标切片索引。"""
        del controller
        captured_indices.append(target_slice_index)

    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    monkeypatch.setattr(
        "ui.controllers.slice_controller.render_slice_images",
        lambda *args, **kwargs: _fake_slice_bundle(),
    )
    monkeypatch.setattr(IdentifyController, "handle_identify", fake_handle_identify)

    interface = SliceInterface()
    try:
        interface._session.config_snapshot.business.auto_recognize_next_slice = True
        interface._session.slice_result = SliceResult(
            slices=[
                SingleSlice(0, np.zeros((2, 5), dtype=float), (0.0, 1.0)),
                SingleSlice(1, np.ones((2, 5), dtype=float), (1.0, 2.0)),
                SingleSlice(2, np.full((2, 5), 2.0, dtype=float), (2.0, 3.0)),
            ]
        )
        interface._slice_controller._load_slice_image(0)

        interface._slice_controller._on_next_slice()

        assert interface._slice_controller.current_slice_index == 1
        assert captured_indices == [1]
    finally:
        sip.delete(interface)


def test_redraw_auto_recognize_passes_target_slice_index(
    monkeypatch: MonkeyPatch,
) -> None:
    """指定编号绘图自动识别应显式使用转换后的 0-based 目标索引。"""
    _app()
    captured_indices: list[int | None] = []

    def fake_handle_identify(
        controller: IdentifyController,
        target_slice_index: int | None = None,
    ) -> None:
        """记录自动识别入口收到的目标切片索引。"""
        del controller
        captured_indices.append(target_slice_index)

    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    monkeypatch.setattr(
        "ui.controllers.slice_controller.render_slice_images",
        lambda *args, **kwargs: _fake_slice_bundle(),
    )
    monkeypatch.setattr(IdentifyController, "handle_identify", fake_handle_identify)

    interface = SliceInterface()
    try:
        interface._session.config_snapshot.business.auto_recognize_next_slice = True
        interface._session.slice_result = SliceResult(
            slices=[
                SingleSlice(0, np.zeros((2, 5), dtype=float), (0.0, 1.0)),
                SingleSlice(1, np.ones((2, 5), dtype=float), (1.0, 2.0)),
                SingleSlice(2, np.full((2, 5), 2.0, dtype=float), (2.0, 3.0)),
            ]
        )
        interface._slice_controller._load_slice_image(0)

        interface._slice_controller._on_redraw_requested(3)

        assert interface._slice_controller.current_slice_index == 2
        assert captured_indices == [2]
    finally:
        sip.delete(interface)


def test_manual_recognize_button_uses_current_slice_index(
    monkeypatch: MonkeyPatch,
) -> None:
    """手动识别按钮点击时应忽略 clicked 信号参数并读取当前切片索引。"""
    _app()
    captured_indices: list[int] = []

    class FakeProcessingDialog:
        """测试用处理对话框桩。"""

        def __init__(self, *args, **kwargs) -> None:
            """忽略真实对话框构造参数。"""
            return None

        def show(self) -> None:
            """忽略显示操作。"""
            return None

    def fake_start_identify(self, session, slice_index: int) -> None:
        """记录 workflow 启动时收到的切片索引。"""
        del self, session
        captured_indices.append(slice_index)

    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    monkeypatch.setattr(
        IdentifyController,
        "_validate_enabled_models",
        lambda self: True,
    )
    monkeypatch.setattr(
        "ui.controllers.identify_controller.ProcessingDialog",
        FakeProcessingDialog,
    )
    monkeypatch.setattr(
        "runtime.workflows.identify_workflow.IdentifyWorkflow.start_identify",
        fake_start_identify,
    )

    interface = SliceInterface()
    try:
        interface._session.slice_result = SliceResult(
            slices=[
                SingleSlice(0, np.zeros((2, 5), dtype=float), (0.0, 1.0)),
                SingleSlice(1, np.ones((2, 5), dtype=float), (1.0, 2.0)),
                SingleSlice(2, np.full((2, 5), 2.0, dtype=float), (2.0, 3.0)),
            ]
        )
        interface._slice_controller._current_slice_index = 2

        interface.navigation_control_card.start_recognition_button.click()

        assert captured_indices == [2]
    finally:
        sip.delete(interface)


def test_slice_controller_uses_constructor_session(
    monkeypatch: MonkeyPatch,
) -> None:
    """切片控制器应复用 SliceInterface 构造时绑定的 session。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    session = ProcessingSession(session_id="constructor_session")

    interface = SliceInterface(session=session)

    assert interface._session is session
    assert interface._slice_controller.view._session is session

    sip.delete(interface)


def test_import_completed_does_not_replace_constructor_session(
    monkeypatch: MonkeyPatch,
) -> None:
    """全局导入完成事件不应替换构造时绑定的 session。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    constructor_session = ProcessingSession(session_id="constructor_session")
    emitted_session = ProcessingSession(session_id="emitted_session")

    interface = SliceInterface(session=constructor_session)

    signal_bus.import_completed.emit(emitted_session)

    assert interface._session is constructor_session
    assert interface.cluster_title_label.text() == "暂无聚类结果"
    assert not interface.prev_slice_button.isEnabled()
    assert not interface.navigation_control_card.prev_cluster_button.isEnabled()

    sip.delete(interface)


def test_plot_show_mode_switches_between_identified_and_all_clusters(
    monkeypatch: MonkeyPatch,
) -> None:
    """展示模式切换后应在有效簇和全部簇之间正确切换。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    monkeypatch.setattr(
        "ui.controllers.identify_controller.render_cluster_images",
        lambda **kwargs: _fake_cluster_bundle(),
    )

    interface = SliceInterface()
    try:
        interface._session.slice_result = SliceResult(
            slices=[SingleSlice(0, np.zeros((2, 5), dtype=float), (0.0, 1.0))]
        )
        interface._session.cluster_result = ClusteringResult(
            slice_results={
                0: SliceClusterResult(
                    slice_idx=0,
                    clusters=[
                        _build_cluster(1, "CF", ClusterState.VALID),
                        _build_cluster(2, "PW", ClusterState.INVALID),
                    ],
                )
            }
        )
        interface._session.recognition_result = _build_recognition_result()
        interface._session.mark_slice_cluster_succeeded(0)
        interface._session.mark_slice_recognition_succeeded(0)
        interface._slice_controller.refresh_navigation_state()

        interface.plot_option_card.show_mode_item.set("IDENTIFIED_ONLY")
        interface._identify_controller.load_cluster_image(0, reset_index=True)
        assert interface.cluster_title_label.text() == "CF维聚类结果  第1/1类  总第1/2类"
        assert (
            interface.cluster_cf_card._snapshot_window_title
            == "第 1 个切片 - CF维聚类结果  第1/1类  总第1/2类 - 载频"
        )
        assert (
            interface.cluster_doa_card._snapshot_window_title
            == "第 1 个切片 - CF维聚类结果  第1/1类  总第1/2类 - 方位角"
        )
        assert not interface.next_cluster_button.isEnabled()

        interface.plot_option_card.show_mode_item.set("ALL")
        QApplication.processEvents()
        assert interface.cluster_title_label.text() == "CF维聚类结果  第1/2类  总第1/2类"
        assert interface.next_cluster_button.isEnabled()

        interface._identify_controller._on_next_cluster()
        assert interface.cluster_title_label.text() == "PW维聚类结果  第2/2类  总第2/2类"
        assert (
            interface.cluster_pw_card._snapshot_window_title
            == "第 1 个切片 - PW维聚类结果  第2/2类  总第2/2类 - 脉宽"
        )
        assert interface.prev_cluster_button.isEnabled()
        assert not interface.next_cluster_button.isEnabled()
    finally:
        sip.delete(interface)
