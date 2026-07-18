"""图像快照独立窗口单元测试。"""

from __future__ import annotations

from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QImage, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QScrollArea
from pytest import MonkeyPatch
from qfluentwidgets import (
    CaptionLabel,
    ImageLabel,
    SmoothScrollArea,
    SubtitleLabel,
    Theme,
    TransparentToolButton,
    qconfig,
    setTheme,
)

from app.style_sheet import StyleSheet
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


def test_snapshot_window_has_centered_zoom_buttons() -> None:
    """窗口应提供默认 3 倍且始终居中的组件库加减按钮。"""
    _app()
    image = QImage(500, 250, QImage.Format.Format_RGB32)
    window = ImageSnapshotWindow(image, "原始图像 - 载频")

    try:
        assert isinstance(window.zoom_out_button, TransparentToolButton)
        assert isinstance(window.zoom_in_button, TransparentToolButton)
        assert not hasattr(window, "zoom_slider")
        assert window.image_label.size() == QSize(1500, 750)
        assert window.zoom_value_label.text() == "3×"
        assert window._window_size_for_zoom(3) == QSize(1524, 916)
        window.show()
        QApplication.processEvents()

        controls_center = (
            window.zoom_out_button.geometry().left()
            + window.zoom_in_button.geometry().right()
        ) // 2
        assert abs(
            controls_center - window.zoom_control_widget.rect().center().x()
        ) <= 1

        window.resize(1800, window.height())
        QApplication.processEvents()
        resized_controls_center = (
            window.zoom_out_button.geometry().left()
            + window.zoom_in_button.geometry().right()
        ) // 2
        assert abs(
            resized_controls_center
            - window.zoom_control_widget.rect().center().x()
        ) <= 1
    finally:
        sip.delete(window)


def test_scroll_hint_is_right_aligned_and_adapts_to_overflow(
    monkeypatch: MonkeyPatch,
) -> None:
    """右下角组件库标签应说明当前可用的滚轮操作。"""
    _app()
    # 固定足够大的可用屏幕，避免测试环境的小尺寸虚拟屏幕触发最大化溢出。
    monkeypatch.setattr(
        ImageSnapshotWindow,
        "_available_screen_size",
        lambda _self: QSize(1920, 1080),
    )
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )

    try:
        window.show()
        QApplication.processEvents()

        assert isinstance(window.scroll_hint_label, CaptionLabel)
        assert window.scroll_hint_label.text() == "图像已完整显示，无需滚动"
        assert (
            window.scroll_hint_label.alignment()
            & Qt.AlignmentFlag.AlignRight
        )
        assert (
            window.scroll_hint_label.geometry().right()
            == window.width() - window.HORIZONTAL_MARGIN - 1
        )
        assert (
            window.scroll_hint_label.geometry().bottom()
            == window.height() - window.BOTTOM_MARGIN - 1
        )

        assert window._scroll_hint_text(False, True) == "滚轮：纵向滚动"
        assert window._scroll_hint_text(True, False) == "滚轮：横向滚动"
        assert window._scroll_hint_text(True, True) == (
            "滚轮：纵向滚动；Shift + 滚轮：横向滚动"
        )
    finally:
        sip.delete(window)


def test_window_is_centered_after_zoom_size_change(
    monkeypatch: MonkeyPatch,
) -> None:
    """应用倍率尺寸后窗口应位于当前屏幕可用区域中央。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )
    available_geometry = QRect(100, 50, 1600, 900)

    try:
        window.show()
        QApplication.processEvents()
        assert window.minimumSize() == window._window_size_for_zoom(1)
        monkeypatch.setattr(
            window,
            "_available_screen_geometry",
            lambda: available_geometry,
            raising=False,
        )

        window._apply_zoom(1)
        QApplication.processEvents()

        center = window.frameGeometry().center()
        assert abs(center.x() - available_geometry.center().x()) <= 1
        assert abs(center.y() - available_geometry.center().y()) <= 1
    finally:
        sip.delete(window)


def test_manual_window_resize_uses_largest_zoom_without_scrollbars() -> None:
    """拖动普通窗口尺寸时应采用完整容纳图像的最大整数倍率。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )

    try:
        window.show()
        QApplication.processEvents()

        window.resize(window._window_size_for_zoom(2))
        QApplication.processEvents()
        assert window.zoom_value_label.text() == "2×"
        assert window.image_label.size() == QSize(800, 160)
        assert window.scroll_area.horizontalScrollBar().maximum() == 0
        assert window.scroll_area.verticalScrollBar().maximum() == 0

        window.resize(window._window_size_for_zoom(4))
        QApplication.processEvents()
        assert window.zoom_value_label.text() == "4×"
        assert window.image_label.size() == QSize(1600, 320)
        assert window.scroll_area.horizontalScrollBar().maximum() == 0
        assert window.scroll_area.verticalScrollBar().maximum() == 0
    finally:
        sip.delete(window)


def test_bottom_hover_does_not_show_stale_horizontal_scrollbar() -> None:
    """无横向溢出时下边沿悬停不应显示瞬时残留的滚动条。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )

    try:
        window.show()
        window.resize(window._window_size_for_zoom(1))
        QApplication.processEvents()

        area = window.scroll_area
        horizontal_bar = area.delegate.hScrollBar
        assert area.horizontalScrollBar().maximum() == 0

        # 模拟布局过程中瞬时滚动范围留下的可见状态，再执行最终状态同步。
        horizontal_bar.setVisible(True)
        area._sync_scrollbar_reservation()
        QTest.mouseMove(
            area,
            QPoint(area.width() // 2, area.height() - 1),
        )
        QTest.qWait(250)

        assert not horizontal_bar.isVisible()
    finally:
        sip.delete(window)


def test_snapshot_window_displays_image_name_in_content_area() -> None:
    """内容区应展示由列标题和维度名称组成的图像名称。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "聚类结果 - 一级差",
    )

    try:
        assert isinstance(window.image_name_label, SubtitleLabel)
        assert window.image_name_label.text() == "聚类结果 - 一级差"
    finally:
        sip.delete(window)


def test_zoom_buttons_apply_integer_zoom_and_enforce_bounds() -> None:
    """加减按钮应立即应用整数倍率，并限制在 1～10 倍。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )

    try:
        window.show()
        QApplication.processEvents()
        window.zoom_out_button.click()
        QApplication.processEvents()
        assert window.zoom_value_label.text() == "2×"
        assert window.image_label.size() == QSize(800, 160)

        window.zoom_out_button.click()
        QApplication.processEvents()
        assert window.zoom_value_label.text() == "1×"
        assert not window.zoom_out_button.isEnabled()

        for _ in range(9):
            window.zoom_in_button.click()
            QApplication.processEvents()
        assert window.zoom_value_label.text() == "10×"
        assert not window.zoom_in_button.isEnabled()
    finally:
        sip.delete(window)


def test_snapshot_window_uses_bidirectional_smooth_scroll_area() -> None:
    """图像应由支持纵横双向滚动的组件库平滑滚动区域承载。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(400, 80, QImage.Format.Format_RGB32),
        "原始图像 - 脉宽",
    )

    try:
        assert isinstance(window.scroll_area, QScrollArea)
        assert isinstance(window.scroll_area, SmoothScrollArea)
        assert window.scroll_area.objectName() == "imageSnapshotScrollArea"
        assert "#imageSnapshotScrollArea" in window.styleSheet()
        assert window.scroll_area.widget() is window.image_label
        assert not window.scroll_area.widgetResizable()
    finally:
        sip.delete(window)


def test_mouse_wheel_routes_vertical_and_shift_horizontal(
    monkeypatch: MonkeyPatch,
) -> None:
    """普通滚轮应纵向滚动，Shift+滚轮应横向滚动。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(500, 250, QImage.Format.Format_RGB32),
        "原始图像 - 载频",
    )

    def wheel_event(modifiers: Qt.KeyboardModifier) -> QWheelEvent:
        """构造向下滚动一步的鼠标滚轮事件。"""
        return QWheelEvent(
            QPointF(20, 20),
            QPointF(20, 20),
            QPoint(),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            modifiers,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )

    try:
        monkeypatch.setattr(
            window,
            "_available_screen_size",
            lambda: QSize(800, 600),
            raising=False,
        )
        window.show()
        window._apply_zoom(10)
        QApplication.processEvents()

        vertical_bar = window.scroll_area.delegate.vScrollBar
        horizontal_bar = window.scroll_area.delegate.hScrollBar
        assert vertical_bar.maximum() > 0
        assert horizontal_bar.maximum() > 0

        QApplication.sendEvent(
            window.scroll_area.viewport(),
            wheel_event(Qt.KeyboardModifier.NoModifier),
        )
        QTest.qWait(300)
        assert vertical_bar.value() > 0
        assert horizontal_bar.value() == 0

        vertical_bar.ani.stop()
        vertical_bar.scrollTo(0, useAni=False)
        QApplication.sendEvent(
            window.scroll_area.viewport(),
            wheel_event(Qt.KeyboardModifier.ShiftModifier),
        )
        QTest.qWait(300)
        assert vertical_bar.value() == 0
        assert horizontal_bar.value() > 0

        # 仅存在横向溢出时，无需 Shift 也应自动使用横向滚动。
        vertical_bar.setRange(0, 0)
        assert window.scroll_area._should_route_horizontally(
            wheel_event(Qt.KeyboardModifier.NoModifier)
        )
    finally:
        sip.delete(window)


def test_high_zoom_reserves_visible_space_for_both_scrollbars(
    monkeypatch: MonkeyPatch,
) -> None:
    """高倍率横纵溢出时视口不应覆盖 Fluent 滚动条。"""
    _app()
    window = ImageSnapshotWindow(
        QImage(500, 250, QImage.Format.Format_RGB32),
        "原始图像 - 载频",
    )

    try:
        monkeypatch.setattr(
            window,
            "_available_screen_size",
            lambda: QSize(800, 600),
            raising=False,
        )
        window.show()
        window._apply_zoom(10)
        QApplication.processEvents()

        area = window.scroll_area
        horizontal_bar = area.delegate.hScrollBar
        vertical_bar = area.delegate.vScrollBar
        margins = area.viewportMargins()

        assert horizontal_bar.isVisible()
        assert vertical_bar.isVisible()
        assert margins.bottom() >= horizontal_bar.height()
        assert margins.right() >= vertical_bar.width()
        assert area.viewport().geometry().bottom() <= horizontal_bar.geometry().top()
        assert area.viewport().geometry().right() <= vertical_bar.geometry().left()
    finally:
        sip.delete(window)


def test_snapshot_scroll_area_transparency_is_defined_in_qss() -> None:
    """明暗主题 QSS 均应定义快照滚动区透明背景。"""
    for theme in (Theme.LIGHT, Theme.DARK):
        qss = Path(StyleSheet.SLICE_INTERFACE.path(theme)).read_text(
            encoding="utf-8",
        )
        assert "#imageSnapshotScrollArea" in qss
        assert "background: transparent" in qss


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

        window.zoom_out_button.click()
        window.zoom_out_button.click()
        QApplication.processEvents()
        assert not window.isMaximized()
        assert window.size() == window._window_size_for_zoom(1)
        assert window.image_label.size() == QSize(400, 80)

        window.zoom_in_button.click()
        window.zoom_in_button.click()
        QApplication.processEvents()
        assert not window.isMaximized()
        assert window.size() == window._window_size_for_zoom(3)
        assert window.image_label.size() == QSize(1200, 240)

        for _ in range(7):
            window.zoom_in_button.click()
        QApplication.processEvents()
        assert window.isMaximized()
        assert window.image_label.size() == QSize(4000, 800)
        assert max(
            window.scroll_area.horizontalScrollBar().maximum(),
            window.scroll_area.verticalScrollBar().maximum(),
        ) > 0
        assert window.snapshot_image.size() == QSize(400, 80)

        for _ in range(9):
            window.zoom_out_button.click()
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


def test_snapshot_window_background_adapts_to_runtime_theme_changes() -> None:
    """独立窗口应使用组件库明暗底色并跟随运行时主题切换。"""
    _app()
    previous_theme = qconfig.theme
    setTheme(Theme.LIGHT)
    window = ImageSnapshotWindow(
        QImage(80, 40, QImage.Format.Format_RGB32),
        "原始图像 - 载频",
    )

    def render_background_color() -> QColor:
        """渲染并返回窗口内容边缘处的实际背景色。"""
        canvas = QImage(window.size(), QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.transparent)
        window.render(canvas)
        return canvas.pixelColor(2, window.height() // 2)

    try:
        window.resize(480, 320)
        window.show()
        QApplication.processEvents()

        assert not window.isMicaEffectEnabled()
        assert render_background_color() == QColor(240, 244, 249)

        setTheme(Theme.DARK)
        QTest.qWait(150)
        QApplication.processEvents()

        assert render_background_color() == QColor(32, 32, 32)
    finally:
        sip.delete(window)
        setTheme(previous_theme)
