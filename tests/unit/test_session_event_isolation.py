"""数据包解析事件与 Session 生命周期隔离测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from core.models.data_package import DataPackage
from core.models.processing_session import ProcessingMode
from core.models.pulse_batch import PulseBatch
from infra.data_pool_store import DataPoolStore
from runtime.data_pool_registry import DataPoolRegistry
import runtime.threading.import_worker as import_worker_module
from runtime.threading.import_worker import ImportWorker, ImportWorkerResult
import runtime.workflows.import_workflow as import_workflow_module
from runtime.workflows.import_workflow import ImportWorkflow
import ui.controllers.home_controller as home_controller_module
from ui.controllers.home_controller import HomeController


class _SignalStub:
    """提供测试用连接接口的轻量信号替身。"""

    def __init__(self) -> None:
        """初始化回调列表。"""
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """记录连接的回调。"""
        self.callbacks.append(callback)


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
        self.excel_data_format = "old"
        self.files_by_type: object | None = None

    def set_files_by_type(self, files_by_type: object) -> None:
        """记录文件列表。"""
        self.files_by_type = files_by_type

    def current_format_key(self) -> str:
        """返回选中的文件类型。"""
        return "excel"

    def current_selected_row(self) -> int:
        """返回选中行。"""
        return 0

    def current_excel_data_format(self) -> str:
        """返回显式 Excel 格式。"""
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
    signal_bus.data_package_parsed.disconnect(
        controller.register_parsed_package
    )
    signal_bus.stage_failed.disconnect(controller._on_parse_stage_failed)


def test_data_package_event_does_not_emit_session_registered() -> None:
    """解析完成只发布数据包，不应隐式创建任何 Session。"""
    package = _build_package()
    received_packages: list[DataPackage] = []
    received_session_ids: list[str] = []
    signal_bus.data_package_parsed.connect(received_packages.append)
    signal_bus.session_registered.connect(received_session_ids.append)
    try:
        signal_bus.data_package_parsed.emit(package)
        assert received_packages == [package]
        assert received_session_ids == []
    finally:
        signal_bus.data_package_parsed.disconnect(received_packages.append)
        signal_bus.session_registered.disconnect(received_session_ids.append)


def test_import_workflow_finished_emits_data_package() -> None:
    """导入工作流成功后应只发布新的数据包事件。"""
    package = _build_package()
    received: list[DataPackage] = []
    workflow = ImportWorkflow()
    fake_worker = _FakeImportWorker()
    workflow._worker = cast(Any, fake_worker)
    signal_bus.data_package_parsed.connect(received.append)
    try:
        workflow._on_worker_finished(
            package.package_id,
            ImportWorkerResult(True, package, "ok"),
        )
        assert received == [package]
        assert fake_worker.delete_later_called
        assert workflow._worker is None
    finally:
        signal_bus.data_package_parsed.disconnect(received.append)


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
        home_controller_module.import_workflow,
        "is_running",
        lambda: False,
    )
    monkeypatch.setattr(
        home_controller_module.import_workflow,
        "start_import",
        lambda file_path, data_format: (
            captured.update(file_path=file_path, data_format=data_format)
            or "package-new"
        ),
    )
    monkeypatch.setattr(controller, "_show_processing_dialog", lambda: None)
    try:
        controller.parse_selected_file()
        assert captured == {
            "file_path": "new_format.xlsx",
            "data_format": "new",
        }
        assert controller._active_parse_package_id == "package-new"
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

        def parse(self, file_path: str, data_format: str = "old") -> PulseBatch:
            """返回单脉冲批次。"""
            captured.update(file_path=file_path, data_format=data_format)
            return PulseBatch(
                np.array([[5000.0, 1.0, 100.0, 90.0, 90.0, 0.0]]),
                source_path=file_path,
                source_type="excel",
                total_pulses=1,
            )

    monkeypatch.setattr(import_worker_module, "ExcelPulseParser", _ParserStub)
    worker = ImportWorker(
        "new_format.xlsx",
        data_format="new",
        package_id="package-new",
    )
    worker.finished_signal.connect(
        lambda _package_id, result: results.append(result)
    )
    worker.run()

    assert captured == {
        "file_path": "new_format.xlsx",
        "data_format": "new",
    }
    assert results[0].success
    assert results[0].package.package_id == "package-new"
    assert not results[0].package.preprocess_result.data.flags.writeable


def test_import_workflow_passes_format_and_package_id_to_worker(
    monkeypatch,
) -> None:
    """工作流应把预分配数据包 ID 和格式传给后台线程。"""
    captured: dict[str, object] = {}

    class _WorkerStub:
        """记录线程构造参数并模拟启动。"""

        def __init__(
            self,
            file_path: str,
            data_format: str = "old",
            package_id: str | None = None,
            parent: QObject | None = None,
        ) -> None:
            """保存构造参数。"""
            captured.update(
                file_path=file_path,
                data_format=data_format,
                package_id=package_id,
                parent=parent,
            )
            self.finished_signal = _SignalStub()

        def isRunning(self) -> bool:
            """模拟未运行状态。"""
            return False

        def start(self) -> None:
            """记录启动调用。"""
            captured["started"] = True

    monkeypatch.setattr(import_workflow_module, "ImportWorker", _WorkerStub)
    workflow = ImportWorkflow()
    package_id = workflow.start_import(
        "new_format.xlsx",
        data_format="new",
    )

    assert captured["file_path"] == "new_format.xlsx"
    assert captured["data_format"] == "new"
    assert captured["package_id"] == package_id
    assert captured["parent"] is workflow
    assert captured["started"] is True


def test_home_controller_registers_parsed_package_in_data_pool(
    tmp_path,
    monkeypatch,
) -> None:
    """主页收到匹配的解析结果后应持久化数据包并刷新数据池。"""
    view = _HomeViewStub()
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    controller = HomeController(view, registry)
    package = _build_package("package-home")
    controller._active_parse_package_id = package.package_id
    controller._processing_dialog = None
    monkeypatch.setattr(
        home_controller_module.InfoBar,
        "success",
        lambda **_kwargs: None,
    )
    try:
        controller.register_parsed_package(package)
        assert registry.get(package.package_id) is package
        assert view.data_pool_panel.packages == [package]
        assert view.data_pool_panel.selected_package_id == package.package_id
        assert controller._active_parse_package_id is None
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

    class _DialogStub:
        """返回确定的全速 Session 配置。"""

        def __init__(self, _default_name: str, _parent=None) -> None:
            """忽略构造参数。"""

        def exec(self) -> bool:
            """模拟确认创建。"""
            return True

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
    controller._show_top_warning = lambda _title, _content: None
    monkeypatch.setattr(home_controller_module, "CreateSessionDialog", _DialogStub)
    monkeypatch.setattr(
        home_controller_module.InfoBar,
        "success",
        lambda **_kwargs: None,
    )

    controller.create_session_from_package(package.package_id)
    assert captured["args"] == (
        package.package_id,
        ProcessingMode.FULL_SPEED,
        "全速任务",
        "测试备注",
    )
