"""数据池创建两类同级 Session 的主窗口路由测试。"""

from __future__ import annotations

import numpy as np
from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from qfluentwidgets.common.router import qrouter

from core.models.dashboard_info import ExcelDashboardInfo
from core.models.data_package import DataPackage
from core.models.processing_session import ProcessingMode
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
from infra.data_pool_store import DataPoolStore
from infra.session_store import SessionStore
from runtime.data_pool_registry import DataPoolRegistry
from runtime.full_speed_session_registry import FullSpeedSessionRegistry
from runtime.session_registry import SessionRegistry
from ui.main_window import MainWindow


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _build_package() -> DataPackage:
    """构造可持久化的数据池测试包。"""
    data = np.array([[5000.0, 1.0, 90.0, 10.0, 11.0, 0.0]])
    dashboard = ExcelDashboardInfo(
        total_pulses=1,
        removed_pulses=0,
        amplitude_dropped_pulses=0,
        duration=0.0,
        band="C波段",
        estimated_slice_count=1,
    )
    return DataPackage(
        package_id="package-route",
        raw_batch=PulseBatch(
            data.copy(),
            "E:/data/demo.xlsx",
            "excel",
            1,
        ),
        preprocess_result=PreprocessResult(
            data.copy(),
            total_pulses=1,
            band="C波段",
            dashboard_info=dashboard,
        ),
        dashboard_info=dashboard,
    )


def test_main_window_routes_data_package_to_peer_session_systems(
    tmp_path,
    monkeypatch,
) -> None:
    """处理模式只决定 Session 体系，不改变共享数据池输入。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    data_pool_registry = DataPoolRegistry(
        DataPoolStore(tmp_path / "data_pool")
    )
    package = data_pool_registry.register(_build_package())
    interactive_registry = SessionRegistry(
        SessionStore(tmp_path / "interactive")
    )
    full_speed_registry = FullSpeedSessionRegistry(tmp_path / "full_speed")
    window = MainWindow(
        session_registry=interactive_registry,
        data_pool_registry=data_pool_registry,
        full_speed_session_registry=full_speed_registry,
    )
    try:
        interactive = window.home_controller.create_session(
            package.package_id,
            ProcessingMode.SLICE_INTERACTIVE,
            "交互任务",
            "无",
        )
        full_speed = window.home_controller.create_session(
            package.package_id,
            ProcessingMode.FULL_SPEED,
            "全速任务",
            "无",
        )

        assert interactive_registry.get(interactive.session_id) is interactive
        assert full_speed_registry.get(full_speed.session_id) is full_speed
        assert window.session_interface(interactive.session_id) is not None
        assert window.session_interface(full_speed.session_id) is None
        assert interactive.raw_batch is full_speed.raw_batch
        assert (
            full_speed.session_id
            in window.homeInterface.full_speed_session_panel._cards
        )
        assert full_speed.config_snapshot.business.auto_export

        # 参数窗口保存的是 Session 独立草稿。
        window.full_speed_controller.open_parameters(full_speed.session_id)
        params_window = window.full_speed_controller._param_windows[
            full_speed.session_id
        ]
        params_window.parameter_cards[
            "clustering.eps_cf"
        ].spinBox.setValue(7.25)
        params_window.save_button.click()
        QApplication.processEvents()
        assert full_speed.config_snapshot.clustering.eps_cf == 7.25

        full_speed_registry.set_output_dir(
            full_speed.session_id,
            str(tmp_path / "results"),
        )
        started: list[str] = []
        monkeypatch.setattr(
            window.full_speed_workflow,
            "start",
            started.append,
        )

        window.full_speed_controller.start_session(full_speed.session_id)

        assert started == [full_speed.session_id]
        # 首次开始只冻结该 Session 草稿，不得再用全局参数覆盖。
        assert full_speed.config_snapshot.clustering.eps_cf == 7.25
    finally:
        qrouter.history = [
            item
            for item in qrouter.history
            if item.stacked is not window.stackedWidget
        ]
        qrouter.stackHistories.pop(window.stackedWidget, None)
        window.close()
        QApplication.processEvents()
        sip.delete(window)
        QApplication.processEvents()
