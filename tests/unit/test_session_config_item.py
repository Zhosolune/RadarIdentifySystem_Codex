"""Session 设置适配项测试。"""

from __future__ import annotations

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, RangeValidator

import app.session_config_item as session_config_item_module
from app.session_config_item import SessionConfigItem, SessionConfigWriter
from core.models.session_config import SessionConfigSnapshot
from ui.components.double_spin_box_setting_card import DoubleSpinBoxSettingCard
from ui.components.spin_box_setting_card import SpinBoxSettingCard


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试用 QApplication 实例。"""
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


class CustomConfidenceValidator:
    """测试用自定义 validator。"""

    def correct(self, value: object) -> object:
        """将任意输入修正为固定置信度。"""
        return 0.33


def test_session_config_item_writes_snapshot_field() -> None:
    """设置适配项应写回绑定的快照字段。"""
    changed_values: list[object] = []
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(
        snapshot,
        "clustering.eps_cf",
        2.0,
        on_changed=lambda: changed_values.append("saved"),
    )
    item.valueChanged.connect(lambda value: changed_values.append(value))

    item.set(3.5)

    assert snapshot.clustering.eps_cf == 3.5
    assert item.value == 3.5
    assert changed_values == [3.5, "saved"]


def test_session_config_item_skips_unchanged_value() -> None:
    """相同值不应触发信号或保存回调。"""
    changed_values: list[object] = []
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(
        snapshot,
        "clustering.eps_cf",
        2.0,
        on_changed=lambda: changed_values.append("saved"),
    )
    item.valueChanged.connect(lambda value: changed_values.append(value))

    item.set(2.0)

    assert changed_values == []


def test_session_config_item_applies_validator() -> None:
    """设置值应先经过 validator 修正。"""
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(
        snapshot,
        "recognition.pa_confidence_threshold",
        0.8,
        validator=RangeValidator(0.0, 1.0),
    )

    item.set(2.5)

    assert snapshot.recognition.pa_confidence_threshold == 1.0
    assert item.value == 1.0


def test_session_config_item_accepts_custom_validator() -> None:
    """设置项应接受任意提供 correct 方法的 validator。"""
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(
        snapshot,
        "recognition.pa_confidence_threshold",
        0.8,
        validator=CustomConfidenceValidator(),
    )

    item.set("raw")

    assert snapshot.recognition.pa_confidence_threshold == 0.33


def test_session_config_item_does_not_import_specific_validator_classes() -> None:
    """设置适配模块不应为了类型绑定具体 validator 类。"""
    assert not hasattr(session_config_item_module, "BoolValidator")
    assert not hasattr(session_config_item_module, "RangeValidator")


@pytest.mark.parametrize(
    "path",
    ["eps_cf", "missing.eps_cf", "clustering.missing"],
)
def test_session_config_item_rejects_invalid_path(path: str) -> None:
    """非法字段路径应统一抛出 ValueError。"""
    with pytest.raises(ValueError, match=path):
        SessionConfigItem(SessionConfigSnapshot.default(), path, 0)


def test_session_config_writer_gets_and_sets_item() -> None:
    """SessionConfigWriter 应通过适配项读写快照字段。"""
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(snapshot, "business.auto_export", False)
    writer = SessionConfigWriter()

    writer.set(item, True)

    assert writer.get(item) is True
    assert snapshot.business.auto_export is True


def test_spin_box_setting_card_writes_session_item() -> None:
    """整型设置卡应支持写入 session 子配置。"""
    _app()
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(
        snapshot,
        "clustering.min_pts_cf",
        2,
        validator=RangeValidator(1, 10),
    )
    card = SpinBoxSettingCard(
        item,
        FluentIcon.SETTING,
        "候选数量",
        config_writer=SessionConfigWriter(),
    )

    card.spinBox.setValue(8)

    assert snapshot.clustering.min_pts_cf == 8
    sip.delete(card)
    QApplication.processEvents()


def test_double_spin_box_setting_card_writes_session_item() -> None:
    """浮点设置卡应支持写入 session 子配置并保留归一化行为。"""
    _app()
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(
        snapshot,
        "clustering.eps_cf",
        2.0,
        validator=RangeValidator(0.1, 10.0),
    )
    card = DoubleSpinBoxSettingCard(
        item,
        FluentIcon.SETTING,
        "载频半径",
        decimals=1,
        config_writer=SessionConfigWriter(),
    )

    card.spinBox.setValue(3.26)

    assert snapshot.clustering.eps_cf == 3.3
    sip.delete(card)
    QApplication.processEvents()


def test_numeric_setting_cards_route_wheel_to_outer_scroll_area() -> None:
    """整数和浮点设置卡应禁止滚轮改值，并继续滚动外层页面。"""
    _app()
    snapshot = SessionConfigSnapshot.default()
    writer = SessionConfigWriter()
    integer_item = SessionConfigItem(
        snapshot,
        "clustering.min_pts_cf",
        2,
        validator=RangeValidator(1, 10),
    )
    double_item = SessionConfigItem(
        snapshot,
        "clustering.eps_cf",
        2.0,
        validator=RangeValidator(0.1, 10.0),
    )
    integer_card = SpinBoxSettingCard(
        integer_item,
        FluentIcon.SETTING,
        "整数参数",
        config_writer=writer,
    )
    double_card = DoubleSpinBoxSettingCard(
        double_item,
        FluentIcon.SETTING,
        "浮点参数",
        config_writer=writer,
    )
    scroll_area = QScrollArea()
    scroll_area.resize(500, 240)
    content = QWidget()
    content.setMinimumHeight(1000)
    layout = QVBoxLayout(content)
    layout.addWidget(integer_card)
    layout.addWidget(double_card)
    layout.addStretch(1)
    scroll_area.setWidget(content)
    scroll_area.setWidgetResizable(True)
    scroll_area.show()
    QApplication.processEvents()

    def wheel_down() -> QWheelEvent:
        """构造向下滚动一步的滚轮事件。"""
        return QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )

    try:
        original_values = (
            integer_card.spinBox.value(),
            double_card.spinBox.value(),
        )
        for card in (integer_card, double_card):
            scroll_area.verticalScrollBar().setValue(0)
            QApplication.sendEvent(card.spinBox, wheel_down())
            QApplication.processEvents()

            assert scroll_area.verticalScrollBar().value() > 0

        assert integer_card.spinBox.value() == original_values[0]
        assert double_card.spinBox.value() == original_values[1]
        assert snapshot.clustering.min_pts_cf == original_values[0]
        assert snapshot.clustering.eps_cf == original_values[1]
    finally:
        sip.delete(scroll_area)
        QApplication.processEvents()
