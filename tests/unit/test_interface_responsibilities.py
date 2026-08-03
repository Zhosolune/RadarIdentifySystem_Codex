"""Interface 职责边界回归测试。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch
from qfluentwidgets import qconfig

from app.app_config import appConfig
import ui.components.log_setting_card as log_setting_card_module
import ui.controllers.setting_controller as setting_controller_module
from ui.adapters import ResponsiveContentWidthAdapter
from ui.controllers.setting_controller import SettingController
from ui.interfaces.model_manager_interface import ModelManagerInterface
from ui.interfaces.params_interface import ParamsInterface
from ui.interfaces.setting_interface import SettingInterface


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_interfaces_do_not_recreate_migrated_non_view_responsibilities() -> None:
    """Interface 不得重新承接系统服务、日志编排或控制器装配。"""
    setting_source = (
        PROJECT_ROOT / "ui" / "interfaces" / "setting_interface.py"
    ).read_text(encoding="utf-8")
    model_source = (
        PROJECT_ROOT / "ui" / "interfaces" / "model_manager_interface.py"
    ).read_text(encoding="utf-8")
    slice_source = (
        PROJECT_ROOT / "ui" / "interfaces" / "slice_interface.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "QDesktopServices",
        "QFileDialog",
        "clear_all_logs",
        "get_current_log_file_path",
    ):
        assert forbidden not in setting_source
    assert "ModelManagerController(self)" in model_source
    assert "ProcessingSession()" not in slice_source
    assert "SliceController(self)" in slice_source
    assert "IdentifyController(self)" in slice_source
    assert "MergeController(self)" in slice_source


def test_setting_controller_owns_log_actions_and_initial_path(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """设置控制器应绑定日志操作并把配置路径写入视图。"""
    _app()
    monkeypatch.setattr(
        setting_controller_module,
        "get_log_dir_path",
        lambda _value: tmp_path,
    )
    view = SettingInterface()

    controller = view._controller

    assert controller.parent() is view
    assert view.log_card.card.contentLabel.text() == str(tmp_path)
    assert isinstance(
        view._responsive_width_adapter,
        ResponsiveContentWidthAdapter,
    )


def test_repeated_width_policy_is_attached_as_adapter() -> None:
    """设置、参数和模型页面应复用同一响应式宽度适配策略。"""
    _app()
    setting_interface = SettingInterface()
    params_interface = ParamsInterface()
    model_interface = ModelManagerInterface()

    assert isinstance(
        setting_interface._responsive_width_adapter,
        ResponsiveContentWidthAdapter,
    )
    assert isinstance(
        params_interface._responsive_width_adapter,
        ResponsiveContentWidthAdapter,
    )
    assert isinstance(
        model_interface._responsive_width_adapter,
        ResponsiveContentWidthAdapter,
    )
    assert isinstance(
        setting_interface._controller,
        SettingController,
    )
    assert model_interface._controller.parent() is model_interface


def test_setting_advanced_group_exposes_full_speed_performance_limits() -> None:
    """设置页高级组应提供设备、任务并发和识别线程上限。"""
    _app()
    interface = SettingInterface()

    assert interface._full_speed_device_card.card.titleLabel.text() == (
        "全速推理设备"
    )
    assert interface._full_speed_concurrency_card.spinBox.minimum() == 1
    assert interface._full_speed_concurrency_card.spinBox.maximum() == 4
    assert interface._full_speed_workers_card.spinBox.minimum() == 1
    assert interface._full_speed_workers_card.spinBox.maximum() == 8
    assert qconfig.get(appConfig.fullSpeedComputeDevice) in {
        "AUTO",
        "CPU",
        "GPU",
    }
    level_combo = interface.log_card.log_level_combo
    assert tuple(
        level_combo.itemText(index) for index in range(level_combo.count())
    ) == ("DEBUG", "INFO", "WARN", "ERROR")
    assert level_combo.currentText() == qconfig.get(appConfig.logLevel)
    assert qconfig.get(appConfig.logLevel) in {
        "DEBUG",
        "INFO",
        "WARN",
        "ERROR",
    }


def test_log_option_level_combo_writes_selected_config(
    monkeypatch: MonkeyPatch,
) -> None:
    """日志选项内的下拉框应写入所选日志等级。"""
    _app()
    interface = SettingInterface()
    combo = interface.log_card.log_level_combo
    writes: list[tuple[object, object]] = []

    def record_config_write(
        config_item: object,
        value: object,
        **_kwargs: object,
    ) -> None:
        """记录下拉框发起的配置写入而不修改磁盘配置。"""
        writes.append((config_item, value))

    monkeypatch.setattr(
        log_setting_card_module.qconfig,
        "set",
        record_config_write,
    )
    target_index = (combo.currentIndex() + 1) % combo.count()
    combo.setCurrentIndex(target_index)

    assert writes[-1] == (
        appConfig.logLevel,
        combo.itemText(target_index),
    )
