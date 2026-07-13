"""图像快照独立窗口单元测试。"""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QScrollArea
from pytest import MonkeyPatch
from qfluentwidgets import ImageLabel, Slider

from ui.components.image_snapshot_window import ImageSnapshotWindow


_APP: QApplication | None = None


def _app() -> QApplication:
    """获取或创建测试使用的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_snapshot_window_keeps_an_independent_image_copy() -> None:
    """窗口应保存与调用方互不影响的图像快照。"""
    _app()
    source = QImage(40, 20, QImage.Format.Format_RGB32)
    source.fill(Qt.GlobalColor.red)
    window = ImageSnapshotWindow(source, "原始图像 - 载频")

    try:
        source.fill(Qt.GlobalColor.blue)

        assert window.snapshot_image.pixelColor(0, 0) == QColor(Qt.GlobalColor.red)
        assert window.windowTitle() == "原始图像 - 载频"
        assert window.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    finally:
        sip.delete(window)


def test_snapshot_window_uses_pixel_perfect_image_label() -> None:
    """窗口应使用组件库 ImageLabel 的像素无损子类。"""
    _app()
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.setPixelColor(0, 0, QColor(Qt.GlobalColor.red))
    image.setPixelColor(1, 0, QColor(Qt.GlobalColor.green))
    image.setPixelColor(0, 1, QColor(Qt.GlobalColor.blue))
    image.setPixelColor(1, 1, QColor(Qt.GlobalColor.white))
    window = ImageSnapshotWindow(image, "聚类结果 - 载频")

    try:
        assert isinstance(window.image_label, ImageLabel)
        assert window.image_label.size() == QSize(6, 6)
        canvas = QImage(window.image_label.size(), QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.transparent)

        window.image_label.render(canvas)

        expected_colors = {
            (0, 0): QColor(Qt.GlobalColor.red),
            (1, 0): QColor(Qt.GlobalColor.green),
            (0, 1): QColor(Qt.GlobalColor.blue),
            (1, 1): QColor(Qt.GlobalColor.white),
        }
        for (source_x, source_y), color in expected_colors.items():
            for offset_x in range(3):
                for offset_y in range(3):
                    assert canvas.pixelColor(
                        source_x * 3 + offset_x,
                        source_y * 3 + offset_y,
                    ) == color
    finally:
        sip.delete(window)


def test_snapshot_window_has_default_three_times_zoom_slider() -> None:
    """窗口应提供默认 3 倍、范围 1～10 的组件库 Slider。"""
    _app()
    image = QImage(500, 250, QImage.Format.Format_RGB32)
    window = ImageSnapshotWindow(image, "原始图像 - 载频")

    try:
        assert isinstance(window.zoom_slider, Slider)
        assert window.zoom_slider.minimum() == 1
        assert window.zoom_slider.maximum() == 10
        assert window.zoom_slider.singleStep() == 1
        assert window.zoom_slider.value() == 3
        assert window.image_label.size() == QSize(1500, 750)
        assert window.zoom_value_label.text() == "3×"
        assert window._window_size_for_zoom(3) == QSize(1524, 854)
    finally:
        sip.delete(window)


def test_snapshot_window_uses_non_resizable_scroll_area() -> None:
    """固定整数倍图像应由不可反向压缩的滚动区域承载。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )

    try:
        assert isinstance(window.scroll_area, QScrollArea)
        assert window.scroll_area.widget() is window.image_label
        assert not window.scroll_area.widgetResizable()
    finally:
        sip.delete(window)


def test_zoom_updates_image_and_window_size_until_maximized(
    monkeypatch: MonkeyPatch,
) -> None:
    """倍率变化应同步调整窗口，超屏时最大化并在降低倍率后恢复。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )

    try:
        monkeypatch.setattr(
            window,
            "_available_screen_size",
            lambda: QSize(1600, 900),
            raising=False,
        )
        window.show()
        QApplication.processEvents()

        window.zoom_slider.setValue(1)
        QApplication.processEvents()
        assert not window.isMaximized()
        assert window.size() == window._window_size_for_zoom(1)
        assert window.image_label.size() == QSize(400, 80)

        window.zoom_slider.setValue(3)
        QApplication.processEvents()
        assert not window.isMaximized()
        assert window.size() == window._window_size_for_zoom(3)
        assert window.image_label.size() == QSize(1200, 240)

        window.zoom_slider.setValue(10)
        QApplication.processEvents()
        assert window.isMaximized()
        assert window.image_label.size() == QSize(4000, 800)
        assert max(
            window.scroll_area.horizontalScrollBar().maximum(),
            window.scroll_area.verticalScrollBar().maximum(),
        ) > 0
        assert window.snapshot_image.size() == QSize(400, 80)

        window.zoom_slider.setValue(1)
        QApplication.processEvents()
        assert not window.isMaximized()
        assert window.size() == window._window_size_for_zoom(1)
    finally:
        sip.delete(window)


def test_snapshot_window_renders_a_visible_outer_outline() -> None:
    """窗口外缘应绘制区别于内部背景的可见轮廓。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(80, 40, QImage.Format.Format_RGB32),
        "原始图像 - 载频",
    )

    try:
        window.setMicaEffectEnabled(False)
        window.resize(480, 320)
        window.show()
        QApplication.processEvents()
        canvas = QImage(window.size(), QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.transparent)

        window.render(canvas)

        middle_y = window.height() // 2
        assert canvas.pixelColor(0, middle_y) != canvas.pixelColor(2, middle_y)
    finally:
        sip.delete(window)
