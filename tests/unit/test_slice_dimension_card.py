"""切片维度卡片右键图像窗口交互单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QColor, QContextMenuEvent, QImage
from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch
from qfluentwidgets import CommandBarView

from ui.components import slice_dimension_card as slice_dimension_card_module
from ui.components.slice_dimension_card import SliceDimensionCard


_APP: QApplication | None = None


def _app() -> QApplication:
    """获取或创建测试使用的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _card(title: str = "原始图像 - 载频") -> SliceDimensionCard:
    """创建带有明确快照窗口标题的测试卡片。"""
    return SliceDimensionCard(
        "载频",
        "testDimensionCard",
        snapshot_window_title=title,
    )


def _delete_card(card: SliceDimensionCard) -> None:
    """关闭卡片持有的独立窗口并释放卡片。"""
    window = card._snapshot_window
    if window is not None and not sip.isdeleted(window):
        window.close()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()
    sip.delete(card)


def test_right_click_without_image_does_not_create_command_bar(
    monkeypatch: MonkeyPatch,
) -> None:
    """卡片无图像时右键应无反应。"""
    _app()
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        slice_dimension_card_module,
        "Flyout",
        SimpleNamespace(make=lambda *args, **kwargs: calls.append(args)),
        raising=False,
    )
    card = _card()

    try:
        card._show_command_bar(QPoint(10, 10))

        assert calls == []
    finally:
        _delete_card(card)


def test_cleared_image_cannot_open_command_bar_or_snapshot_window(
    monkeypatch: MonkeyPatch,
) -> None:
    """卡片清空图像后不应显示命令栏或展开既有图像。"""
    _app()
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        slice_dimension_card_module,
        "Flyout",
        SimpleNamespace(make=lambda *args, **kwargs: calls.append(args)),
        raising=False,
    )
    card = _card()

    try:
        card.resize(300, 180)
        card.show()
        QApplication.processEvents()
        card.set_image(QImage(20, 10, QImage.Format.Format_RGB32))
        card.clear_image()
        local_pos = card.image_label.rect().center()
        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            local_pos,
            card.image_label.mapToGlobal(local_pos),
        )

        QApplication.sendEvent(card.image_label, event)
        card._show_snapshot_window()

        assert calls == []
        assert card._source_image is None
        assert card.image_label._source_image is None
        assert card.image_label._cached_pixmap is None
        assert card._snapshot_window is None
    finally:
        _delete_card(card)


def test_right_click_with_image_creates_one_snapshot_action(
    monkeypatch: MonkeyPatch,
) -> None:
    """卡片有图像时命令栏应仅包含独立显示操作。"""
    _app()
    captured: list[CommandBarView] = []
    monkeypatch.setattr(
        slice_dimension_card_module,
        "Flyout",
        SimpleNamespace(make=lambda view, target, parent: captured.append(view)),
        raising=False,
    )
    card = _card()

    try:
        card.set_image(QImage(20, 10, QImage.Format.Format_RGB32))
        card._show_command_bar(QPoint(10, 10))

        assert len(captured) == 1
        assert len(captured[0].actions()) == 1
        assert captured[0].actions()[0].text() == "独立显示"
    finally:
        _delete_card(card)


def test_image_label_context_menu_event_reaches_dimension_card(
    monkeypatch: MonkeyPatch,
) -> None:
    """内部图像标签收到右键菜单事件时应由卡片显示命令栏。"""
    _app()
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        slice_dimension_card_module,
        "Flyout",
        SimpleNamespace(make=lambda *args, **kwargs: calls.append(args)),
    )
    card = _card()

    try:
        card.resize(300, 180)
        card.show()
        QApplication.processEvents()
        card.set_image(QImage(20, 10, QImage.Format.Format_RGB32))
        local_pos = card.image_label.rect().center()
        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            local_pos,
            card.image_label.mapToGlobal(local_pos),
        )

        QApplication.sendEvent(card.image_label, event)

        assert len(calls) == 1
    finally:
        _delete_card(card)


def test_same_card_reuses_window_but_different_cards_do_not() -> None:
    """同一卡片应复用窗口，不同卡片应分别持有窗口。"""
    _app()
    first = _card("原始图像 - 载频")
    second = _card("聚类结果 - 载频")
    image = QImage(20, 10, QImage.Format.Format_RGB32)

    try:
        first.set_image(image)
        second.set_image(image)
        first._show_snapshot_window()
        original_window = first._snapshot_window
        first._show_snapshot_window()
        second._show_snapshot_window()

        assert first._snapshot_window is original_window
        assert second._snapshot_window is not original_window
    finally:
        _delete_card(first)
        _delete_card(second)


def test_snapshot_window_opened_by_card_is_an_independent_normal_window() -> None:
    """卡片打开的快照应是带完整标题栏控制的独立顶层窗口。"""
    _app()
    card = _card()

    try:
        card.set_image(QImage(20, 10, QImage.Format.Format_RGB32))
        card._show_snapshot_window()
        window = card._snapshot_window
        assert window is not None
        QApplication.processEvents()

        assert window.parent() is None
        assert window.isWindow()
        assert window.titleBar.minBtn.isVisible()
        assert window.titleBar.maxBtn.isVisible()
        assert window.titleBar.closeBtn.isVisible()

        window.move(QPoint(120, 80))
        assert window.pos() == QPoint(120, 80)

        window.titleBar.minBtn.click()
        QApplication.processEvents()
        assert window.isMinimized()

        window.showNormal()
        window.titleBar.maxBtn.click()
        QApplication.processEvents()
        assert window.isMaximized()
    finally:
        _delete_card(card)


def test_existing_window_is_restored_and_activated() -> None:
    """重复触发时应恢复、置顶并激活已有窗口。"""
    _app()
    card = _card()
    calls: list[str] = []

    try:
        card.set_image(QImage(20, 10, QImage.Format.Format_RGB32))
        card._show_snapshot_window()
        window = card._snapshot_window
        assert window is not None
        window.showNormal = lambda: calls.append("showNormal")
        window.raise_ = lambda: calls.append("raise")
        window.activateWindow = lambda: calls.append("activateWindow")

        card._show_snapshot_window()

        assert calls == ["showNormal", "raise", "activateWindow"]
    finally:
        _delete_card(card)


def test_open_window_keeps_snapshot_and_can_be_recreated_after_close() -> None:
    """已打开窗口应保持快照，销毁后允许按卡片新图重新创建。"""
    _app()
    card = _card()
    red = QImage(20, 10, QImage.Format.Format_RGB32)
    red.fill(Qt.GlobalColor.red)
    blue = QImage(20, 10, QImage.Format.Format_RGB32)
    blue.fill(Qt.GlobalColor.blue)

    try:
        card.set_image(red)
        card._show_snapshot_window()
        first_window = card._snapshot_window
        assert first_window is not None

        card.set_image(blue)
        assert first_window.snapshot_image.pixelColor(0, 0) == QColor(Qt.GlobalColor.red)

        first_window.titleBar.closeBtn.click()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()
        assert card._snapshot_window is None

        card._show_snapshot_window()
        second_window = card._snapshot_window
        assert second_window is not None
        assert second_window.snapshot_image.pixelColor(0, 0) == QColor(Qt.GlobalColor.blue)
    finally:
        _delete_card(card)
