"""图像快照独立窗口单元测试。"""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

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


def test_snapshot_window_scales_image_with_aspect_ratio() -> None:
    """窗口缩放后图像标签应保持源图像宽高比。"""
    _app()
    image = QImage(80, 40, QImage.Format.Format_RGB32)
    window = ImageSnapshotWindow(image, "聚类结果 - 载频")

    try:
        window.image_label.resize(200, 200)
        window.refresh_pixmap()
        pixmap = window.image_label.pixmap()

        assert pixmap is not None
        assert pixmap.size() == QSize(200, 100)
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
