"""Session 设置适配项测试。"""

from __future__ import annotations

import pytest
from qfluentwidgets import RangeValidator

import app.session_config_item as session_config_item_module
from app.session_config_item import SessionConfigItem, SessionConfigWriter
from core.models.session_config import SessionConfigSnapshot


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
        "recognition.min_confidence",
        0.8,
        validator=RangeValidator(0.0, 1.0),
    )

    item.set(2.5)

    assert snapshot.recognition.min_confidence == 1.0
    assert item.value == 1.0


def test_session_config_item_accepts_custom_validator() -> None:
    """设置项应接受任意提供 correct 方法的 validator。"""
    snapshot = SessionConfigSnapshot.default()
    item = SessionConfigItem(
        snapshot,
        "recognition.min_confidence",
        0.8,
        validator=CustomConfidenceValidator(),
    )

    item.set("raw")

    assert snapshot.recognition.min_confidence == 0.33


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
