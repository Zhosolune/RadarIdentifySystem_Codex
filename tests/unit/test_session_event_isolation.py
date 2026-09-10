"""数据包解析事件与 Session 生命周期隔离测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from PyQt6 import sip
from PyQt6.QtCore import QEventLoop, QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QDialog

from app.signal_bus import signal_bus
from core.models.data_package import DataPackage
from core.models.processing_session import ProcessingMode
from core.models.pulse_batch import PulseBatch
from infra.data_pool_store import DataPoolStore
from infra.parsers import ParsedPulseSource
from runtime.data_pool_registry import DataPoolRegistry
import runtime.threading.import_worker as import_worker_module
from runtime.threading.import_worker import (
    ImportExecutionRequest,
    ImportWorker,
    ImportWorkerResult,
)
import runtime.workflows.import_workflow as import_workflow_module
from runtime.workflows.import_workflow import ImportWorkflow
import ui.controllers.home_controller as home_controller_module
from ui.controllers.home_controller import HomeController


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回进程级 Qt 应用并持有强引用。"""
    global _APP
    app = QApplication.instance() or QApplication([])
    _APP = app
    return app


class _SignalStub:
    """提供测试用连接接口的轻量信号替身。"""

    def __init__(self) -> None:
        """初始化回调列表。"""
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """记录连接的回调。"""
        self.callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """按连接顺序同步调用全部回调。"""
        for callback in self.callbacks:
            callback(*args)


class _ActionStub:
    """提供 ``triggered`` 信号的动作替身。"""

    def __init__(self) -> None:
        """初始化动作信号。"""
        self.triggered = _SignalStub()


class _ButtonStub:
    """记录按钮启用状态和文本。"""

    def __init__(self) -> None:
        """初始化按钮替身。"""
        self.clicked = _SignalStub()
        self.enabled = True
        self.text = "解析"

    def setEnabled(self, enabled: bool) -> None:
        """记录按钮启用状态。"""
        self.enabled = enabled

    def setText(self, text: str) -> None:
        """记录按钮文本。"""
        self.text = text


class _ImportPanelStub:
    """提供主页控制器所需的导入面板接口。"""

    def __init__(self) -> None:
        """初始化动作、按钮和选择状态。"""
        self.refresh_action = _ActionStub()
        self.remove_action = _ActionStub()
        self.nameAction = _ActionStub()
        self.sizeAction = _ActionStub()
        self.dateAction = _ActionStub()
        self.ascendAction = _ActionStub()
        self.descendAction = _ActionStub()
        self.parseButton = _ButtonStub()
        self.fileSelectionChanged = _SignalStub()
        self.excel_data_format = "old"
        self.files_by_type: object | None = None

    def set_files_by_type(self, files_by_type: object) -> None:
        """记录文件列表。"""
        self.files_by_type = files_by_type

    def set_removed_directory_rows(self, rows: dict[str, set[int]]) -> None:
        """记录目录失效标记。"""
        self.removed_directory_rows = rows

    def current_format_key(self) -> str:
        """返回选中的文件类型。"""
        return "excel"

    def current_selected_row(self) -> int:
        """返回选中行。"""
        return 0

    def current_data_format(self) -> str:
        """返回当前来源的显式解析格式。"""
        return self.excel_data_format


class _DataPoolPanelStub:
    """提供主页控制器所需的数据池面板接口。"""

    def __init__(self) -> None:
        """初始化信号与渲染记录。"""
        self.createSessionRequested = _SignalStub()
        self.deletePackageRequested = _SignalStub()
        self.packages: list[DataPackage] = []
        self.selected_package_id: str | None = None

    def set_packages(
        self,
        packages: list[DataPackage],
        *,
        selected_package_id: str | None = None,
    ) -> None:
        """记录数据池列表。"""
        self.packages = packages
        self.selected_package_id = selected_package_id


class _HomeViewStub(QObject):
    """提供 HomeController 初始化所需的最小主页视图。"""

    def __init__(self) -> None:
        """初始化主页子组件替身。"""
        super().__init__()
        self.import_panel = _ImportPanelStub()
        self.data_pool_panel = _DataPoolPanelStub()

    def window(self):
        """模拟未挂载到主窗口。"""
        return None


class _FakeImportWorker:
    """模拟导入工作流完成后的线程对象。"""

    def __init__(self) -> None:
        """初始化释放状态。"""
        self.delete_later_called = False

    def deleteLater(self) -> None:
        """记录释放请求。"""
        self.delete_later_called = True


def _build_package(package_id: str = "package1") -> DataPackage:
    """构造解析成功的数据包。"""
    data = np.array([[5000.0, 1.0, 100.0, 90.0, 90.0, 0.0]])
    batch = PulseBatch(
        data.copy(),
        source_path="demo.xlsx",
        source_type="excel",
        total_pulses=1,
    )
    from core.preprocess import preprocess

    preprocessed = preprocess(
        batch.data,
        source_path=batch.source_path,
        source_type=batch.source_type,
    )
    return DataPackage(
        package_id=package_id,
        raw_batch=batch,
        preprocess_result=preprocessed,
        dashboard_info=preprocessed.dashboard_info,
        data_format="new",
    )


def _disconnect_home_controller(controller: HomeController) -> None:
    """断开控制器注册到全局总线的测试信号。"""
    signal_bus.data_packages_parsed.disconnect(
        controller.register_parsed_packages
    )
    signal_bus.stage_failed.disconnect(controller._on_parse_stage_failed)
    home_controller_module.appConfig.importDataDirs.valueChanged.disconnect(
        controller._sync_directory_status
    )


def test_data_package_event_does_not_emit_session_registered() -> None:
    """解析完成只发布数据包，不应隐式创建任何 Session。"""
    package = _build_package()
    received_packages: list[tuple[str, tuple[DataPackage, ...]]] = []
    received_session_ids: list[str] = []
    callback = lambda import_id, packages: received_packages.append(
        (import_id, packages)
    )
    signal_bus.data_packages_parsed.connect(callback)
    signal_bus.session_registered.connect(received_session_ids.append)
    try:
        signal_bus.data_packages_parsed.emit("import-1", (package,))
        assert received_packages == [("import-1", (package,))]
        assert received_session_ids == []
    finally:
        signal_bus.data_packages_parsed.disconnect(callback)
        signal_bus.session_registered.disconnect(received_session_ids.append)


def test_directory_config_change_does_not_trigger_file_scan(
    tmp_path,
    monkeypatch,
) -> None:
    """目录配置变化不应扫描文件，只有刷新动作可以显式触发扫描。"""
    refresh_calls: list[str] = []
    monkeypatch.setattr(
        HomeController,
        "refresh_import_files",
        lambda _controller: refresh_calls.append("refresh"),
    )
    view = _HomeViewStub()
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    controller = HomeController(view, registry)
    try:
        home_controller_module.appConfig.importDataDirs.valueChanged.emit(
            [str(tmp_path)]
        )
        assert refresh_calls == []

        refresh_callback = view.import_panel.refresh_action.triggered.callbacks[0]
        refresh_callback()
        assert refresh_calls == ["refresh"]
    finally:
        _disconnect_home_controller(controller)


@pytest.mark.parametrize("format_key,extension", [("excel", "xlsx"), ("bin", "bin"), ("mat", "mat")])
def test_removed_directory_status_preserves_filename_and_parse_state(
    tmp_path: Path,
    monkeypatch,
    format_key: str,
    extension: str,
) -> None:
    """目录移除、排序、重新添加及刷新应同步独立状态列和解析按钮。"""
    from qfluentwidgets import FluentSystemColor, qconfig
    from infra.import_file_list_manager import ImportFileListManager
    from infra.import_file_list_store import ImportFileListStore
    from ui.components.import_data_panel import ImportDataPanel
    from qfluentwidgets.components.widgets.tool_tip import ItemViewToolTipDelegate

    app = _app()
    source = tmp_path / "source"
    source.mkdir()
    filename = f"完整原文件名_不能被状态覆盖.{extension}"
    (source / filename).touch()
    config_item = home_controller_module.appConfig.importDataDirs
    original = list(qconfig.get(config_item))
    view = _HomeViewStub()
    panel = ImportDataPanel()
    view.import_panel = panel
    controller = HomeController(view, DataPoolRegistry(DataPoolStore(tmp_path / "pool")))
    manager = ImportFileListManager(ImportFileListStore(tmp_path / "files.json"))
    controller.file_manager = manager
    try:
        qconfig.set(config_item, [str(source)], save=False)
        controller.refresh_import_files()
        app.processEvents()
        panel.tab_widget.setCurrentIndex(["excel", "bin", "mat"].index(format_key))
        table = panel.file_pages[format_key]
        table.selectRow(0)
        assert isinstance(table.delegate.tooltipDelegate, ItemViewToolTipDelegate)
        assert table.horizontalHeaderItem(3).text() == "状态"
        assert not table.isColumnHidden(3)
        assert table.item(0, 3).text() == "正常"
        assert (
            table.item(0, 3).foreground().color()
            == FluentSystemColor.SUCCESS_FOREGROUND.color()
        )
        assert panel.parseButton.isEnabled()
        with monkeypatch.context() as context:
            context.setattr(manager, "scan", lambda _dirs: pytest.fail("配置变化不应扫描"))
            qconfig.set(config_item, [], save=False)
            assert table.rowCount() == 1
            assert table.item(0, 0).text() == filename
            assert table.item(0, 3).text() == "目录移除"
            assert (
                table.item(0, 3).foreground().color()
                == FluentSystemColor.CAUTION_FOREGROUND.color()
            )
            assert not table.isColumnHidden(3)
            panel.resize(850, 350)
            panel.show()
            app.processEvents()
            name_rect = table.visualItemRect(table.item(0, 0))
            status_rect = table.visualItemRect(table.item(0, 3))
            assert not name_rect.intersects(status_rect)
            available_width = table.viewport().width()
            expected_widths = [
                available_width * stretch // 12
                for stretch in (5, 3, 2)
            ]
            expected_widths.append(available_width - sum(expected_widths))
            assert [table.columnWidth(column) for column in range(4)] == expected_widths
            assert "刷新后" in table.item(0, 3).data(Qt.ItemDataRole.ToolTipRole)
            assert not panel.parseButton.isEnabled()
            controller.apply_sort()
            assert table.item(0, 3).text() == "目录移除"
            # 等价目录仍覆盖该文件；恢复只重绘，不扫描。
            qconfig.set(config_item, [str(source / ".")], save=False)
            table.selectRow(0)
            assert table.item(0, 3).text() == "正常"
            assert not table.isColumnHidden(3)
            assert panel.parseButton.isEnabled()
            controller._active_import_id = "busy"
            qconfig.set(config_item, [], save=False)
            qconfig.set(config_item, [str(source)], save=False)
            assert not panel.parseButton.isEnabled()
            controller._active_import_id = None
        qconfig.set(config_item, [], save=False)
        controller.refresh_import_files()
        assert table.rowCount() == 0
        assert not panel.parseButton.isEnabled()
    finally:
        _disconnect_home_controller(controller)
        qconfig.set(config_item, original, save=False)
        sip.delete(controller)
        sip.delete(panel)


def test_import_workflow_finished_emits_data_package() -> None:
    """结果发布时不得销毁仍未发出原生 finished 的 QThread。"""
    package = _build_package()
    received: list[tuple[str, tuple[DataPackage, ...]]] = []
    workflow = ImportWorkflow()
    fake_worker = _FakeImportWorker()
    workflow._worker = cast(Any, fake_worker)
    callback = lambda import_id, packages: received.append((import_id, packages))
    signal_bus.data_packages_parsed.connect(callback)
    try:
        workflow._on_worker_finished(
            "import-1",
            ImportWorkerResult(True, (package,), "ok"),
        )
        assert received == [("import-1", (package,))]
        assert not fake_worker.delete_later_called
        assert workflow._worker is fake_worker

        workflow._on_worker_thread_finished()

        assert fake_worker.delete_later_called
        assert workflow._worker is None
    finally:
        signal_bus.data_packages_parsed.disconnect(callback)


def test_import_workflow_deletes_real_worker_only_after_native_finished(
    tmp_path,
    monkeypatch,
) -> None:
    """真实 QThread 在结果发出后继续收尾时不得被提前销毁。"""
    app = _app()
    source_file = tmp_path / "thread-lifecycle.xlsx"
    source_file.write_bytes(b"source")

    class _ParserStub:
        """返回单波段数据以驱动真实 ImportWorker。"""

        def parse(
            self,
            file_path: str,
            data_format: str | None = None,
        ) -> ParsedPulseSource:
            """构造单条 C 波段解析结果。"""
            return ParsedPulseSource(
                data=np.array([[5000.0, 1.0, 100.0, 90.0, 90.0, 0.0]]),
                source_path=file_path,
                source_type="excel",
                source_valid_mask=np.ones(1, dtype=bool),
                total_records=1,
            )

    class _SlowFinalImportWorker(ImportWorker):
        """结果发出后保留短暂原生线程收尾窗口。"""

        def run(self) -> None:
            """执行真实导入并延迟返回，放大错误销毁时序。"""
            super().run()
            self.msleep(100)

    monkeypatch.setattr(
        import_worker_module,
        "create_pulse_parser",
        lambda _source_type: _ParserStub(),
    )
    monkeypatch.setattr(
        import_workflow_module,
        "ImportWorker",
        _SlowFinalImportWorker,
    )
    workflow = ImportWorkflow()
    workflow.start_import(
        str(source_file),
        source_type="excel",
        data_format="new",
    )
    worker = workflow._worker
    assert worker is not None
    result_states: list[tuple[bool, bool]] = []
    worker.finished_signal.connect(
        lambda _import_id, _result: result_states.append(
            (worker.isRunning(), sip.isdeleted(worker))
        )
    )
    event_loop = QEventLoop()
    worker.finished.connect(event_loop.quit)
    QTimer.singleShot(3_000, event_loop.quit)

    event_loop.exec()
    app.processEvents()

    assert result_states == [(True, False)]
    assert workflow._worker is None
    app.processEvents()
    assert sip.isdeleted(worker)


def test_home_controller_passes_selected_excel_format(
    tmp_path,
    monkeypatch,
) -> None:
    """主页解析入口应冻结并传递当前 Excel 格式。"""
    view = _HomeViewStub()
    view.import_panel.excel_data_format = "new"
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    controller = HomeController(view, registry)
    captured: dict[str, object] = {}
    entry = SimpleNamespace(path=Path("new_format.xlsx"), format_key="excel")
    monkeypatch.setattr(
        controller.file_manager,
        "get_entry_at",
        lambda _format_key, _row_index: entry,
    )
    monkeypatch.setattr(
        controller.file_manager,
        "is_entry_importable",
        lambda _entry, _directories: True,
    )
    monkeypatch.setattr(
        home_controller_module.import_workflow,
        "is_running",
        lambda: False,
    )
    monkeypatch.setattr(
        home_controller_module.import_workflow,
        "start_import",
        lambda file_path, source_type, data_format: (
            captured.update(
                file_path=file_path,
                source_type=source_type,
                data_format=data_format,
            )
            or "package-new"
        ),
    )
    monkeypatch.setattr(controller, "_show_processing_dialog", lambda: None)
    try:
        controller.parse_selected_file()
        assert captured == {
            "file_path": "new_format.xlsx",
            "source_type": "excel",
            "data_format": "new",
        }
        assert controller._active_import_id == "package-new"
    finally:
        _disconnect_home_controller(controller)


def test_home_controller_passes_selected_bin_rule(
    tmp_path,
    monkeypatch,
) -> None:
    """主页 BIN 入口应显式传递来源类型和固定 PDW 规则。"""
    view = _HomeViewStub()
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    controller = HomeController(view, registry)
    captured: dict[str, object] = {}
    entry = SimpleNamespace(path=Path("mixed.bin"), format_key="bin")
    monkeypatch.setattr(
        controller.file_manager,
        "get_entry_at",
        lambda _format_key, _row_index: entry,
    )
    monkeypatch.setattr(
        controller.file_manager,
        "is_entry_importable",
        lambda _entry, _directories: True,
    )
    monkeypatch.setattr(
        view.import_panel,
        "current_data_format",
        lambda: "pdw_v1",
    )
    monkeypatch.setattr(
        home_controller_module.import_workflow,
        "is_running",
        lambda: False,
    )
    monkeypatch.setattr(
        home_controller_module.import_workflow,
        "start_import",
        lambda file_path, source_type, data_format: (
            captured.update(
                file_path=file_path,
                source_type=source_type,
                data_format=data_format,
            )
            or "import-bin"
        ),
    )
    monkeypatch.setattr(controller, "_show_processing_dialog", lambda: None)
    try:
        controller.parse_selected_file()
        assert captured == {
            "file_path": "mixed.bin",
            "source_type": "bin",
            "data_format": "pdw_v1",
        }
        assert controller._active_import_id == "import-bin"
    finally:
        _disconnect_home_controller(controller)


def test_home_controller_rejects_entry_outside_current_directories(
    tmp_path,
    monkeypatch,
) -> None:
    """目录已移除时解析入口应清理失效列表项且不启动后台任务。"""
    view = _HomeViewStub()
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    controller = HomeController(view, registry)
    entry = SimpleNamespace(
        path=tmp_path / "removed" / "stale.xlsx",
        format_key="excel",
    )
    empty_rows = {"excel": [], "bin": [], "mat": []}
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        controller.file_manager,
        "get_entry_at",
        lambda _format_key, _row_index: entry,
    )
    monkeypatch.setattr(
        controller.file_manager,
        "is_entry_importable",
        lambda _entry, _directories: False,
    )
    monkeypatch.setattr(
        controller.file_manager,
        "scan",
        lambda directories: empty_rows,
    )
    monkeypatch.setattr(controller, "_get_import_directories", lambda: [])
    monkeypatch.setattr(
        controller,
        "_show_top_warning",
        lambda title, content: warnings.append((title, content)),
    )
    monkeypatch.setattr(
        home_controller_module.import_workflow,
        "start_import",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("失效文件不应启动解析")
        ),
    )
    try:
        controller.parse_selected_file()
        assert view.import_panel.files_by_type == empty_rows
        assert warnings == [
            (
                "文件已失效",
                "所选文件已不在当前数据目录中，或文件当前无法访问。",
            )
        ]
        assert controller._active_import_id is None
    finally:
        _disconnect_home_controller(controller)


def test_import_worker_passes_excel_format_and_returns_package(
    monkeypatch,
) -> None:
    """后台导入线程应使用显式格式并返回数据包而非临时 Session。"""
    captured: dict[str, str] = {}
    results: list[ImportWorkerResult] = []

    class _ParserStub:
        """记录解析参数并返回六列批次。"""

        def parse(
            self,
            file_path: str,
            data_format: str | None = "old",
        ) -> ParsedPulseSource:
            """返回单脉冲批次。"""
            captured.update(file_path=file_path, data_format=str(data_format))
            return ParsedPulseSource(
                data=np.array([[5000.0, 1.0, 100.0, 90.0, 90.0, 0.0]]),
                source_path=file_path,
                source_type="excel",
                source_valid_mask=np.ones(1, dtype=bool),
                total_records=1,
            )

    monkeypatch.setattr(
        import_worker_module,
        "create_pulse_parser",
        lambda _source_type: _ParserStub(),
    )
    worker = ImportWorker(
        ImportExecutionRequest(
            import_id="import-new",
            file_path="new_format.xlsx",
            source_type="excel",
            data_format="new",
        )
    )
    worker.finished_signal.connect(
        lambda _import_id, result: results.append(result)
    )
    worker.run()

    assert captured == {
        "file_path": "new_format.xlsx",
        "data_format": "new",
    }
    assert results[0].success
    assert len(results[0].packages) == 1
    assert results[0].packages[0].preprocess_result.band == "C波段"
    assert not results[0].packages[0].preprocess_result.data.flags.writeable


def test_bin_import_worker_returns_independent_lsc_packages(tmp_path) -> None:
    """BIN 导入应按公共规则生成 L/S/C 数据包并保留旧过滤语义。"""
    records = np.zeros((3, 16), dtype=">u2")
    records[:, 0] = [3, 5, 6]
    records[:, 2] = [1500, 3000, 5000]
    records[:, 5] = [100, 200, 300]
    records[:, 6] = 20
    records[:, 7] = 10
    records[:, 11] = [100, 255, 255]
    records[:, 14] = [100, 200, 300]
    records[1, 15] = 1 << 10
    bin_path = tmp_path / "mixed.bin"
    bin_path.write_bytes(records.tobytes())

    results: list[ImportWorkerResult] = []
    worker = ImportWorker(
        ImportExecutionRequest(
            import_id="import-bin",
            file_path=str(bin_path),
            source_type="bin",
            data_format="pdw_v1",
        )
    )
    worker.finished_signal.connect(
        lambda _import_id, result: results.append(result)
    )

    worker.run()

    assert results[0].success
    packages = results[0].packages
    assert [package.preprocess_result.band for package in packages] == [
        "L波段",
        "S波段",
        "C波段",
    ]
    assert [package.raw_batch.total_pulses for package in packages] == [1, 1, 1]
    assert all(
        package.source_size_bytes == bin_path.stat().st_size
        for package in packages
    )
    assert packages[0].raw_batch.data[0, 2] == 100
    assert packages[0].raw_batch.data[0, 5] == 100
    assert packages[0].preprocess_result.remaining_pulses == 1
    assert packages[1].raw_batch.n_pulses == 0
    assert packages[1].preprocess_result.filtered_pulses == 1
    assert packages[1].preprocess_result.amplitude_dropped_pulses == 1
    assert packages[2].raw_batch.n_pulses == 1
    assert packages[2].preprocess_result.remaining_pulses == 0
    assert packages[2].preprocess_result.amplitude_dropped_pulses == 1


def test_import_workflow_passes_format_and_package_id_to_worker(
    monkeypatch,
) -> None:
    """工作流应把预分配数据包 ID 和格式传给后台线程。"""
    captured: dict[str, object] = {}

    class _WorkerStub:
        """记录线程构造参数并模拟启动。"""

        def __init__(
            self,
            request: ImportExecutionRequest,
            parent: QObject | None = None,
        ) -> None:
            """保存构造参数。"""
            captured.update(
                request=request,
                parent=parent,
            )
            self.finished_signal = _SignalStub()
            self.finished = _SignalStub()

        def isRunning(self) -> bool:
            """模拟未运行状态。"""
            return False

        def start(self) -> None:
            """记录启动调用。"""
            captured["started"] = True

    monkeypatch.setattr(import_workflow_module, "ImportWorker", _WorkerStub)
    workflow = ImportWorkflow()
    import_id = workflow.start_import(
        "new_format.xlsx",
        source_type="excel",
        data_format="new",
    )

    request = cast(ImportExecutionRequest, captured["request"])
    assert request.file_path == "new_format.xlsx"
    assert request.source_type == "excel"
    assert request.data_format == "new"
    assert request.import_id == import_id
    assert captured["parent"] is workflow
    assert captured["started"] is True
    worker = cast(Any, workflow._worker)
    assert worker.finished.callbacks == [workflow._on_worker_thread_finished]


def test_home_controller_registers_parsed_package_in_data_pool(
    tmp_path,
    monkeypatch,
) -> None:
    """主页收到匹配的解析结果后应持久化数据包并刷新数据池。"""
    view = _HomeViewStub()
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    controller = HomeController(view, registry)
    package = _build_package("package-home")
    controller._active_import_id = "import-home"
    controller._processing_dialog = None
    monkeypatch.setattr(
        home_controller_module.InfoBar,
        "success",
        lambda **_kwargs: None,
    )
    try:
        controller.register_parsed_packages("import-home", (package,))
        assert registry.get(package.package_id) is package
        assert view.data_pool_panel.packages == [package]
        assert view.data_pool_panel.selected_package_id == package.package_id
        assert controller._active_import_id is None
    finally:
        _disconnect_home_controller(controller)


def test_session_lifecycle_signals_still_use_session_id() -> None:
    """两类 Session 注册后的生命周期信号仍只传递 Session ID。"""
    received: list[str] = []
    signal_bus.session_registered.connect(received.append)
    try:
        signal_bus.session_registered.emit("session1")
        assert received == ["session1"]
    finally:
        signal_bus.session_registered.disconnect(received.append)


def test_home_create_action_delegates_mode_and_package(
    tmp_path,
    monkeypatch,
) -> None:
    """数据池创建入口应把数据包 ID、模式、名称和备注交给主窗口。"""
    package = _build_package("package-create")
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    registry.register(package)
    captured: dict[str, Any] = {}

    class _DialogStub(QObject):
        """返回确定的全速 Session 配置。"""

        finished = pyqtSignal(int)

        def __init__(self, _default_name: str, _parent=None) -> None:
            """忽略构造参数。"""
            super().__init__()

        def show(self) -> None:
            """保留窗口，等待测试模拟确认或取消。"""

        def get_session_name(self) -> str:
            """返回名称。"""
            return "全速任务"

        def get_session_remark(self) -> str:
            """返回备注。"""
            return "测试备注"

        def get_processing_mode(self) -> ProcessingMode:
            """返回全速模式。"""
            return ProcessingMode.FULL_SPEED

    class _View(QObject):
        """提供消息条父对象的最小视图。"""

        def __init__(self) -> None:
            """初始化最小视图。"""
            super().__init__()

        def window(self):
            """返回自身作为消息条父对象。"""
            return self

    class _Coordinator:
        """记录 Session 构造与注册请求的协调器替身。"""

        def build_session_from_data_package(self, *args):
            """记录构造参数并返回展示对象。"""
            captured["args"] = args
            return SimpleNamespace(session_id="full-speed", display_name=args[2])

        def register_full_speed_session(self, session):
            """记录全速 Session 注册对象。"""
            captured["registered"] = session
            return session

    controller = HomeController.__new__(HomeController)
    controller.view = _View()
    controller.data_pool_registry = registry
    controller.session_coordinator = _Coordinator()
    controller.interactive_session_registrar = None
    controller._create_session_dialog = None
    controller._show_top_warning = lambda _title, _content: None
    monkeypatch.setattr(home_controller_module, "CreateSessionDialog", _DialogStub)
    monkeypatch.setattr(
        home_controller_module.InfoBar,
        "success",
        lambda **_kwargs: None,
    )

    controller.create_session_from_package(package.package_id)
    assert captured == {}
    controller._create_session_dialog.finished.emit(0)
    assert captured == {}
    assert controller._create_session_dialog is None
    controller.create_session_from_package(package.package_id)
    controller._create_session_dialog.finished.emit(1)
    assert controller._create_session_dialog is None
    assert captured["args"] == (
        package.package_id,
        ProcessingMode.FULL_SPEED,
        "全速任务",
        "测试备注",
    )


def test_home_delete_action_waits_for_nonmodal_confirmation(
    tmp_path,
    monkeypatch,
) -> None:
    """数据包只能在非模态确认窗口返回接受结果后删除。"""
    package = _build_package("package-delete")
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    registry.register(package)
    refresh_calls: list[str] = []

    class _DialogStub(QObject):
        """提供删除确认窗口所需的最小异步接口。"""

        finished = pyqtSignal(int)

        def __init__(self, _title: str, _content: str, _parent=None) -> None:
            """初始化窗口状态。"""
            super().__init__()
            self.shown = False

        def show(self) -> None:
            """记录非模态显示动作。"""
            self.shown = True

        def raise_(self) -> None:
            """兼容重复触发时的窗口提升。"""

        def activateWindow(self) -> None:
            """兼容重复触发时的窗口激活。"""

    class _View(QObject):
        """提供确认窗口父对象的最小视图。"""

        def window(self):
            """返回自身作为窗口父对象。"""
            return self

    controller = HomeController.__new__(HomeController)
    controller.view = _View()
    controller.data_pool_registry = registry
    controller.session_coordinator = None
    controller._delete_data_package_dialog = None
    controller._show_top_warning = lambda _title, _content: None
    controller.refresh_data_pool_panel = lambda: refresh_calls.append("refresh")
    monkeypatch.setattr(home_controller_module, "MessageBox", _DialogStub)

    controller.delete_data_package(package.package_id)
    dialog = controller._delete_data_package_dialog
    assert dialog is not None
    assert dialog.shown
    assert registry.get(package.package_id) is package

    dialog.finished.emit(0)
    assert registry.get(package.package_id) is package
    assert refresh_calls == []

    controller.delete_data_package(package.package_id)
    dialog = controller._delete_data_package_dialog
    assert dialog is not None
    dialog.finished.emit(1)
    assert registry.get(package.package_id) is None
    assert refresh_calls == ["refresh"]


def test_home_remove_file_warns_and_keeps_file_hidden_after_refresh(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """文件列表删除应先说明持久隐藏语义，确认后刷新也不得恢复原路径。"""
    from infra.import_file_list_manager import ImportFileListManager
    from infra.import_file_list_store import ImportFileListStore

    excel_file = tmp_path / "待隐藏.xlsx"
    excel_file.write_text("placeholder", encoding="utf-8")
    manager = ImportFileListManager(ImportFileListStore(tmp_path / "files.json"))
    manager.scan([str(tmp_path)])
    created_dialogs: list[_DialogStub] = []

    class _ButtonTextStub:
        """记录确认窗口按钮文本。"""

        def __init__(self) -> None:
            """初始化空按钮文本。"""
            self.text = ""

        def setText(self, text: str) -> None:
            """记录设置的按钮文本。"""
            self.text = text

    class _DialogStub(QObject):
        """记录文件删除确认内容及非模态生命周期。"""

        finished = pyqtSignal(int)

        def __init__(self, title: str, content: str, _parent=None) -> None:
            """保存确认文案和按钮状态。"""
            super().__init__()
            self.title = title
            self.content = content
            self.yesButton = _ButtonTextStub()
            self.cancelButton = _ButtonTextStub()
            self.shown = False
            self.raised = False
            created_dialogs.append(self)

        def show(self) -> None:
            """记录窗口已显示。"""
            self.shown = True

        def raise_(self) -> None:
            """记录重复请求提升已有窗口。"""
            self.raised = True

        def activateWindow(self) -> None:
            """兼容重复请求激活已有窗口。"""

    view = _HomeViewStub()
    controller = HomeController.__new__(HomeController)
    controller.view = view
    controller.file_manager = manager
    controller._remove_import_file_dialog = None
    controller._active_import_id = None
    controller._get_import_directories = lambda: [str(tmp_path)]
    monkeypatch.setattr(home_controller_module, "MessageBox", _DialogStub)

    controller.remove_selected_file()
    dialog = controller._remove_import_file_dialog
    assert dialog is not None
    assert dialog.shown
    assert dialog.title == "从文件列表中删除"
    assert "删除软件对当前目录下此文件的可见性" in dialog.content
    assert "不会删除磁盘上的原文件" in dialog.content
    assert "软件将不再识别位于该目录下的此文件" in dialog.content
    assert "重命名" in dialog.content
    assert "移至其他目录" in dialog.content
    assert dialog.yesButton.text == "删除"
    assert dialog.cancelButton.text == "取消"
    assert manager.get_entry_at("excel", 0) is not None

    # 重复点击只能提升已有确认框，避免叠加窗口或重复删除。
    controller.remove_selected_file()
    assert created_dialogs == [dialog]
    assert dialog.raised

    dialog.finished.emit(QDialog.DialogCode.Rejected.value)
    assert controller._remove_import_file_dialog is None
    assert manager.get_entry_at("excel", 0) is not None

    controller.remove_selected_file()
    dialog = controller._remove_import_file_dialog
    assert dialog is not None
    dialog.finished.emit(QDialog.DialogCode.Accepted.value)
    assert controller._remove_import_file_dialog is None
    assert manager.get_entry_at("excel", 0) is None
    assert excel_file.exists()

    controller.refresh_import_files()
    assert manager.files_by_type["excel"] == []
    assert excel_file.exists()
