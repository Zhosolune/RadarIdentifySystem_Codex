"""数据池创建两类同级 Session 的主窗口路由测试。"""

from __future__ import annotations

from pathlib import Path, PurePath

import numpy as np
import pytest
from pytest import MonkeyPatch
from PyQt6 import sip
from PyQt6.QtCore import QEventLoop, QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QWidget
from qfluentwidgets import Dialog, qconfig
from qfluentwidgets.common.router import qrouter

from app.app_config import appConfig
from core.models.dashboard_info import PulseDashboardInfo
from core.models.data_package import DataPackage
from core.models.processing_session import ProcessingMode
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
from infra.data_pool_store import DataPoolStore
from infra.import_file_list_manager import ImportFileListManager
from infra.import_file_list_store import ImportFileListStore
from infra.parsers import ParsedPulseSource
from infra.session_store import SessionStore
from runtime.data_pool_registry import DataPoolRegistry
from runtime.full_speed_session_registry import FullSpeedSessionRegistry
from runtime.session_registry import SessionRegistry
import runtime.threading.import_worker as import_worker_module
from runtime.workflows.import_workflow import ImportWorkflow
from ui.dialogs.create_session_dialog import CreateSessionDialog
from ui.dialogs.processing_dialog import ProcessingDialog
from ui.main_window import MainWindow
from qfluentwidgets.components.settings.folder_list_setting_card import FolderItem


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _click_visible_widget(widget: QWidget) -> None:
    """按屏幕坐标点击真实命中的控件，避免绕过上层透明遮罩。"""
    global_pos = widget.mapToGlobal(widget.rect().center())
    target = QApplication.widgetAt(global_pos)
    assert target is not None
    assert target is widget or widget.isAncestorOf(target), (
        f"控件被 {type(target).__name__} 遮挡"
    )
    QTest.mouseClick(
        target,
        Qt.MouseButton.LeftButton,
        pos=target.mapFromGlobal(global_pos),
    )


def _build_package(
    source_path: str = "E:/data/demo.xlsx",
    source_size_bytes: int | None = None,
) -> DataPackage:
    """构造可持久化的数据池测试包。"""
    data = np.array([[5000.0, 1.0, 90.0, 10.0, 11.0, 0.0]])
    dashboard = PulseDashboardInfo(
        total_pulses=1,
        removed_pulses=0,
        amplitude_dropped_pulses=0,
        duration=0.0,
        band="C波段",
        estimated_slice_count=1,
    )
    return DataPackage(
        package_id="package-route",
        source_path=source_path,
        source_size_bytes=source_size_bytes,
        raw_batch=PulseBatch(
            data.copy(),
            source_path,
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


def test_create_session_after_directory_refresh_does_not_access_source_file(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """目录移除并刷新后，创建 Session 只能使用数据包缓存元数据。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_enabled_model_paths",
        lambda _model_type: [],
    )
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "demo.xlsx"
    source_file.write_bytes(b"cached-data")
    source_size_bytes = source_file.stat().st_size

    file_manager = ImportFileListManager(
        ImportFileListStore(tmp_path / "import_file_list.json")
    )
    file_manager.scan([str(source_dir)])
    assert file_manager.files_by_type["excel"]
    cleared_rows = file_manager.scan([])
    assert cleared_rows["excel"] == []

    package = _build_package(str(source_file), source_size_bytes)
    data_pool_registry = DataPoolRegistry(
        DataPoolStore(tmp_path / "data_pool")
    )
    data_pool_registry.register(package)
    interactive_registry = SessionRegistry(
        SessionStore(tmp_path / "interactive")
    )
    full_speed_registry = FullSpeedSessionRegistry(tmp_path / "full_speed")
    window = MainWindow(
        session_registry=interactive_registry,
        data_pool_registry=data_pool_registry,
        full_speed_session_registry=full_speed_registry,
    )

    class _NoFilesystemPath:
        """仅允许提取文件名，任何源文件系统查询都令测试失败。"""

        def __init__(self, value: str) -> None:
            """保存纯路径文件名。"""
            self.name = PurePath(value).name

        def exists(self) -> bool:
            """禁止详情面板回查源文件是否存在。"""
            raise AssertionError("Session 详情不应访问源文件系统")

        def stat(self) -> None:
            """禁止详情面板回查源文件属性。"""
            raise AssertionError("Session 详情不应访问源文件系统")

    try:
        window.home_controller.file_manager = file_manager
        window.homeInterface.import_panel.set_files_by_type(cleared_rows)
        monkeypatch.setattr(
            "ui.components.session_manager_panel.PurePath",
            _NoFilesystemPath,
        )

        session = window.home_controller.create_session(
            package.package_id,
            ProcessingMode.SLICE_INTERACTIVE,
            "目录已移除任务",
            "无",
        )

        assert interactive_registry.get(session.session_id) is session
        assert session.raw_batch is package.raw_batch
        assert session.source_size_bytes == source_size_bytes
        assert (
            window.homeInterface.session_manager_panel._file_size_value_label.text()
            == "11 B"
        )
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


@pytest.mark.parametrize("remove_source", [False, True])
@pytest.mark.parametrize("full_speed", [False, True])
def test_real_create_dialog_closes_after_directory_refresh(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    remove_source: bool,
    full_speed: bool,
) -> None:
    """目录移除并刷新后，真实创建窗口应能确认并返回事件循环。"""
    _app()
    original_directories = list(qconfig.get(appConfig.importDataDirs))
    monkeypatch.setattr(
        "ui.controllers.home_controller.InfoBar.success",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_enabled_model_paths",
        lambda _model_type: [],
    )
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "demo.xlsx"
    source_file.write_bytes(b"cached-data")
    data_pool_registry = DataPoolRegistry(DataPoolStore(tmp_path / "data_pool"))
    interactive_registry = SessionRegistry(SessionStore(tmp_path / "interactive"))
    qconfig.set(appConfig.importDataDirs, [str(source_dir)], save=False)
    window = MainWindow(
        session_registry=interactive_registry,
        data_pool_registry=data_pool_registry,
        full_speed_session_registry=FullSpeedSessionRegistry(
            tmp_path / "full_speed"
        ),
    )
    file_manager = ImportFileListManager(
        ImportFileListStore(tmp_path / "import_file_list.json")
    )
    file_manager.scan([str(source_dir)])

    class _ParserStub:
        """构造接近真实复现规模的解析结果。"""

        def parse(
            self,
            file_path: str,
            data_format: str | None = None,
        ) -> ParsedPulseSource:
            """返回 55,815 条 C 波段有效脉冲。"""
            pulse_count = 55_815
            data = np.zeros((pulse_count, 6), dtype=np.float64)
            data[:, 0] = 5_000.0
            data[:, 1] = 1.0
            data[:, 2] = 90.0
            data[:, 5] = np.arange(pulse_count, dtype=np.float64)
            return ParsedPulseSource(
                data=data,
                source_path=file_path,
                source_type="excel",
                source_valid_mask=np.ones(pulse_count, dtype=bool),
                total_records=pulse_count,
            )

    class _AutoConfirmCreateSessionDialog(CreateSessionDialog):
        """使用真实窗口实现并在事件循环启动后自动确认。"""

        def __init__(self, default_display_name: str, parent=None) -> None:
            """初始化真实创建窗口并安排确认动作。"""
            super().__init__(default_display_name, parent)
            self.watchdog_expired = False
            QTimer.singleShot(350, self._click_confirm)
            self._watchdog = QTimer(self)
            self._watchdog.setSingleShot(True)
            self._watchdog.timeout.connect(self._abort_stuck_dialog)
            self._watchdog.start(3000)
            self.finished.connect(self._watchdog.stop)

        def _click_confirm(self) -> None:
            """通过鼠标事件确认，验证窗口能接收用户输入。"""
            if full_speed:
                _click_visible_widget(self.full_speed_radio)
            _click_visible_widget(self.yesButton)

        def _abort_stuck_dialog(self) -> None:
            """在模态状态异常时退出，避免回归测试无限挂起。"""
            self.watchdog_expired = True
            QDialog.done(self, QDialog.DialogCode.Rejected)

    class _AutoConfirmDirectoryDialog(Dialog):
        """使用真实目录确认窗口并在事件循环启动后自动确认。"""

        def __init__(self, title: str, content: str, parent=None) -> None:
            """初始化真实确认窗口并安排确认动作。"""
            super().__init__(title, content, parent)
            QTimer.singleShot(
                350,
                lambda: _click_visible_widget(self.yesButton),
            )

    try:
        window.home_controller.file_manager = file_manager
        monkeypatch.setattr(
            import_worker_module,
            "create_pulse_parser",
            lambda _source_type: _ParserStub(),
        )
        monkeypatch.setattr(
            "qfluentwidgets.components.settings.folder_list_setting_card.Dialog",
            _AutoConfirmDirectoryDialog,
        )
        monkeypatch.setattr(
            "ui.controllers.home_controller.CreateSessionDialog",
            _AutoConfirmCreateSessionDialog,
        )

        # 显示主窗口以覆盖真实布局、绘制和目录删除后的控件生命周期。
        window.show()
        # 等待生产代码的一秒启动画面正常结束，避免测试自身绕过启动流程。
        QTest.qWait(1_200)

        # 先走真实 QThread 导入链，确保结果信号与原生 finished 清理均完成。
        workflow = ImportWorkflow()
        monkeypatch.setattr(
            "ui.controllers.home_controller.import_workflow", workflow,
        )
        window.home_controller.refresh_import_files()
        window.homeInterface.import_panel.file_pages["excel"].selectRow(0)
        window.homeInterface.import_panel.parseButton.click()
        worker = workflow._worker
        assert worker is not None
        event_loop = QEventLoop()
        worker.finished.connect(event_loop.quit)
        QTimer.singleShot(5_000, event_loop.quit)
        event_loop.exec()
        QApplication.processEvents()
        packages = data_pool_registry.all_packages()
        assert len(packages) == 1
        package = packages[0]
        assert workflow._worker is None

        # 让解析遮罩完整结束，再模拟用户移除目录。
        QTest.qWait(350)
        assert window.homeInterface.findChildren(ProcessingDialog) == []

        window.homeInterface.import_dir_card.setExpand(True)
        QTest.qWait(250)
        folder_item = window.homeInterface.import_dir_card.findChild(FolderItem)
        assert folder_item is not None
        _click_visible_widget(folder_item.removeButton)
        assert qconfig.get(appConfig.importDataDirs) == []
        assert QApplication.activeModalWidget() is None
        QTest.qWait(1)
        assert window.findChildren(_AutoConfirmDirectoryDialog) == []
        if remove_source:
            source_file.unlink()
            source_dir.rmdir()

        window.homeInterface.import_panel.refresh_action.trigger()
        window.home_controller.refresh_data_pool_panel(package.package_id)
        _click_visible_widget(window.homeInterface.data_pool_panel.create_button)
        dialog = window.home_controller._create_session_dialog
        assert dialog is not None
        # 创建窗口依靠自身全窗遮罩阻止背景操作，不得进入原生模态栈。
        assert QApplication.activeModalWidget() is None
        # 创建入口应立即返回；重复触发只能激活同一个窗口。
        window.home_controller.create_session_from_package(package.package_id)
        assert window.home_controller._create_session_dialog is dialog
        QTest.qWait(800)
        assert not dialog.watchdog_expired
        assert window.home_controller._create_session_dialog is None
        registry = (
            window.home_controller.session_coordinator.full_speed_session_registry
            if full_speed else interactive_registry
        )
        assert len(registry.all_sessions()) == 1
        assert registry.all_sessions()[0].raw_batch is package.raw_batch
    finally:
        qconfig.set(appConfig.importDataDirs, original_directories, save=False)
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


def test_main_window_routes_data_package_to_peer_session_systems(
    tmp_path,
    monkeypatch,
) -> None:
    """处理模式只决定 Session 体系，不改变共享数据池输入。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.get_enabled_model_paths",
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
