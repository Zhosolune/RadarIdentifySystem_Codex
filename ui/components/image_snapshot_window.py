"""提供独立显示固定图像快照的 Fluent 窗口。"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QRect, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    FluentWidget,
    ImageLabel,
    SmoothScrollArea,
    SubtitleLabel,
    TransparentToolButton,
    isDarkTheme,
)

from app.style_sheet import StyleSheet


class PixelPerfectImageLabel(ImageLabel):
    """使用最近邻方式绘制整数倍栅格图像的组件库图像标签。"""

    def paintEvent(self, event: QPaintEvent) -> None:
        """在不启用平滑插值的情况下绘制完整源图像。

        Args:
            event [QPaintEvent]: Qt 图像标签绘制事件。

        Returns:
            None: 无返回值。
        """
        if self.isNull():
            return

        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawImage(self.rect(), self.image)


class _BidirectionalSmoothScrollArea(SmoothScrollArea):
    """支持普通滚轮纵向及 Shift+滚轮横向的平滑滚动区域。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化双向滚动区域并优先安装滚轮路由过滤器。"""
        super().__init__(parent)
        self._reservation_suspended = False
        self._updating_viewport_margins = False
        # 后安装的过滤器会先处理事件，再将普通纵向事件交回组件库代理。
        self.viewport().installEventFilter(self)
        self.delegate.hScrollBar.rangeChanged.connect(
            self._sync_scrollbar_reservation
        )
        self.delegate.vScrollBar.rangeChanged.connect(
            self._sync_scrollbar_reservation
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """根据溢出方向和 Shift 修饰键分派滚轮事件。

        Args:
            watched [QObject]: 当前接收事件的对象。
            event [QEvent]: Qt 输入事件。

        Returns:
            bool: 已处理横向滚动时返回 True，否则交由组件库继续处理。
        """
        if (
            watched is self.viewport()
            and event.type() == QEvent.Type.Wheel
            and isinstance(event, QWheelEvent)
            and event.angleDelta().y() != 0
            and self._should_route_horizontally(event)
        ):
            self.delegate.hScrollBar.scrollValue(-event.angleDelta().y())
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _should_route_horizontally(self, event: QWheelEvent) -> bool:
        """判断垂直滚轮增量是否应改用于横向滚动。"""
        horizontal_bar = self.delegate.hScrollBar
        vertical_bar = self.delegate.vScrollBar
        has_horizontal_overflow = (
            horizontal_bar.maximum() > horizontal_bar.minimum()
        )
        has_vertical_overflow = vertical_bar.maximum() > vertical_bar.minimum()
        shift_pressed = bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        return has_horizontal_overflow and (
            shift_pressed or not has_vertical_overflow
        )

    def _begin_content_update(self) -> None:
        """更新图像尺寸前暂时移除旧滚动条预留空间。"""
        self._reservation_suspended = True
        self.setViewportMargins(0, 0, 0, 0)

    def _end_content_update(self) -> None:
        """图像尺寸更新后恢复实际所需的滚动条预留空间。"""
        self._reservation_suspended = False
        self._sync_scrollbar_reservation()

    def _sync_scrollbar_reservation(
        self,
        _range: tuple[int, int] | None = None,
    ) -> None:
        """按实际溢出方向为 Fluent 滚动条动态预留视口边距。"""
        del _range
        if self._reservation_suspended or self._updating_viewport_margins:
            return

        self._updating_viewport_margins = True
        try:
            # 先还原未预留滚动条时的基础视口，避免边距自身制造 12 px 假溢出。
            margins = self.viewportMargins()
            base_width = (
                self.viewport().width() + margins.left() + margins.right()
            )
            base_height = (
                self.viewport().height() + margins.top() + margins.bottom()
            )
            content = self.widget()
            content_size = content.size() if content is not None else QSize()
            has_horizontal_overflow = content_size.width() > base_width
            has_vertical_overflow = content_size.height() > base_height

            # 某一方向的真实溢出会占用另一方向空间，有限迭代至状态稳定。
            for _ in range(3):
                horizontal_bar = self.delegate.hScrollBar
                vertical_bar = self.delegate.vScrollBar
                available_width = base_width - (
                    vertical_bar.width() if has_vertical_overflow else 0
                )
                available_height = base_height - (
                    horizontal_bar.height() if has_horizontal_overflow else 0
                )
                next_horizontal_overflow = (
                    content_size.width() > available_width
                )
                next_vertical_overflow = (
                    content_size.height() > available_height
                )
                if (
                    next_horizontal_overflow == has_horizontal_overflow
                    and next_vertical_overflow == has_vertical_overflow
                ):
                    break
                has_horizontal_overflow = next_horizontal_overflow
                has_vertical_overflow = next_vertical_overflow

            self.setViewportMargins(
                0,
                0,
                vertical_bar.width() if has_vertical_overflow else 0,
                horizontal_bar.height() if has_horizontal_overflow else 0,
            )

            # 视口和图像均不得覆盖组件库的浮动滚动条。
            self.delegate.hScrollBar.raise_()
            self.delegate.vScrollBar.raise_()
        finally:
            self._updating_viewport_margins = False


class ImageSnapshotWindow(FluentWidget):
    """在独立 Fluent 窗口中显示固定图像快照。

    窗口持有传入图像的深拷贝，后续源图像变化不会影响当前显示内容。

    Attributes:
        image_label [PixelPerfectImageLabel]: 用于整数倍显示图像快照的标签。
        image_name_label [SubtitleLabel]: 展示列标题与维度名称组成的图像名称。
        scroll_area [SmoothScrollArea]: 支持纵横双向滚轮浏览的图像区域。
        zoom_control_widget [QWidget]: 承载居中倍率按钮的控制区。
        zoom_out_button [TransparentToolButton]: 将图像倍率降低一级的按钮。
        zoom_in_button [TransparentToolButton]: 将图像倍率提高一级的按钮。
        zoom_value_label [BodyLabel]: 显示当前倍率的文本标签。
        scroll_hint_label [CaptionLabel]: 在右下角显示自适应滚轮操作说明。
        snapshot_image [QImage]: 当前窗口持有的图像快照副本。
    """

    MIN_ZOOM = 1
    MAX_ZOOM = 10
    DEFAULT_ZOOM = 3
    HORIZONTAL_MARGIN = 12
    TOP_MARGIN = 52
    BOTTOM_MARGIN = 12
    CONTROL_HEIGHT = 32
    CONTROL_SPACING = 8
    NAME_LABEL_HEIGHT = 28
    ZOOM_BUTTON_SIZE = 32
    ZOOM_ICON_SIZE = 16
    SCROLL_HINT_HEIGHT = 18

    def __init__(
        self,
        image: QImage,
        title: str,
    ) -> None:
        """初始化图像快照窗口。

        Args:
            image [QImage]: 需要独立显示的非空图像。
            title [str]: 非空窗口标题。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当图像为空或窗口标题为空时抛出。
        """
        if image.isNull():
            raise ValueError("image 不能为空图像")
        if not title.strip():
            raise ValueError("title 不能为空")

        # 不设置 parent，确保对象保持可自由移动和缩放的独立顶层窗口。
        super().__init__()
        self._snapshot_image = image.copy()
        self._zoom = self.DEFAULT_ZOOM
        self._syncing_window_geometry = False
        self._manual_resize_enabled = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(title)

        self.image_label = PixelPerfectImageLabel(self._snapshot_image)
        self.image_label.setObjectName("imageSnapshotImageLabel")
        self.image_label.setBorderRadius(0, 0, 0, 0)

        # 在内容区固定展示图像名称，避免仅依赖系统标题栏识别图像。
        self.image_name_label = SubtitleLabel(title, self)
        self.image_name_label.setFixedHeight(self.NAME_LABEL_HEIGHT)

        self.scroll_area = _BidirectionalSmoothScrollArea(self)
        self.scroll_area.setObjectName("imageSnapshotScrollArea")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

        self.zoom_control_widget = QWidget(self)
        self.zoom_control_widget.setFixedHeight(self.CONTROL_HEIGHT)
        control_layout = QHBoxLayout(self.zoom_control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)

        self.zoom_out_button = TransparentToolButton(
            FluentIcon.REMOVE,
            self.zoom_control_widget,
        )
        self.zoom_out_button.setFixedSize(
            self.ZOOM_BUTTON_SIZE,
            self.ZOOM_BUTTON_SIZE,
        )
        self.zoom_out_button.setIconSize(
            QSize(self.ZOOM_ICON_SIZE, self.ZOOM_ICON_SIZE),
        )
        self.zoom_value_label = BodyLabel(
            f"{self.DEFAULT_ZOOM}×",
            self.zoom_control_widget,
        )
        self.zoom_value_label.setFixedWidth(36)
        self.zoom_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_in_button = TransparentToolButton(
            FluentIcon.ADD,
            self.zoom_control_widget,
        )
        self.zoom_in_button.setFixedSize(
            self.ZOOM_BUTTON_SIZE,
            self.ZOOM_BUTTON_SIZE,
        )
        self.zoom_in_button.setIconSize(
            QSize(self.ZOOM_ICON_SIZE, self.ZOOM_ICON_SIZE),
        )

        # 两侧使用等权伸缩空间，确保按钮组始终保持在窗口水平中心。
        control_layout.addStretch(1)
        control_layout.addWidget(self.zoom_out_button)
        control_layout.addWidget(self.zoom_value_label)
        control_layout.addWidget(self.zoom_in_button)
        control_layout.addStretch(1)

        self.scroll_hint_label = CaptionLabel(
            "图像已完整显示，无需滚动",
            self,
        )
        self.scroll_hint_label.setFixedHeight(self.SCROLL_HINT_HEIGHT)
        self.scroll_hint_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.scroll_hint_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.HORIZONTAL_MARGIN,
            self.TOP_MARGIN,
            self.HORIZONTAL_MARGIN,
            self.BOTTOM_MARGIN,
        )
        layout.setSpacing(self.CONTROL_SPACING)
        layout.addWidget(self.image_name_label)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.zoom_control_widget)
        layout.addWidget(
            self.scroll_hint_label,
            0,
            Qt.AlignmentFlag.AlignRight,
        )

        # 显式忽略 clicked(bool) 参数，避免布尔值被误作缩放步长。
        self.zoom_out_button.clicked.connect(
            lambda _checked=False: self._change_zoom(-1)
        )
        self.zoom_in_button.clicked.connect(
            lambda _checked=False: self._change_zoom(1)
        )
        self.scroll_area.delegate.hScrollBar.rangeChanged.connect(
            self._update_scroll_hint
        )
        self.scroll_area.delegate.vScrollBar.rangeChanged.connect(
            self._update_scroll_hint
        )
        StyleSheet.SLICE_INTERFACE.apply(self)
        # 保证普通窗口至少能完整容纳 1 倍原图，满足无滚动条适配下限。
        self.setMinimumSize(self._window_size_for_zoom(self.MIN_ZOOM))
        self._manual_resize_enabled = True
        self._apply_zoom(self.DEFAULT_ZOOM)
        self._update_scroll_hint()

    @property
    def snapshot_image(self) -> QImage:
        """返回窗口持有的图像快照副本。

        Returns:
            QImage: 与窗口内部存储相互独立的图像副本。
        """
        return self._snapshot_image.copy()

    def _apply_zoom(self, zoom: int) -> None:
        """应用整数倍率并同步调整窗口状态与尺寸。"""
        bounded_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, int(zoom)))
        self._set_zoom_content(bounded_zoom)

        window_size = self._window_size_for_zoom(bounded_zoom)
        available_size = self._available_screen_size()
        exceeds_screen = (
            window_size.width() > available_size.width()
            or window_size.height() > available_size.height()
        )
        self._syncing_window_geometry = True
        try:
            if exceeds_screen:
                self.setWindowState(
                    self.windowState() | Qt.WindowState.WindowMaximized
                )
                return

            if self.isMaximized():
                self.showNormal()
            self.resize(window_size)
        finally:
            self._syncing_window_geometry = False
        self._center_window()

    def _set_zoom_content(self, zoom: int) -> None:
        """仅更新图像倍率与控制状态，不改变窗口几何。"""
        bounded_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, int(zoom)))
        self._zoom = bounded_zoom
        scaled_size = QSize(
            self._snapshot_image.width() * bounded_zoom,
            self._snapshot_image.height() * bounded_zoom,
        )
        self.scroll_area._begin_content_update()
        try:
            self.image_label.setScaledSize(scaled_size)
        finally:
            self.scroll_area._end_content_update()
        self.zoom_value_label.setText(f"{bounded_zoom}×")
        self.zoom_out_button.setEnabled(bounded_zoom > self.MIN_ZOOM)
        self.zoom_in_button.setEnabled(bounded_zoom < self.MAX_ZOOM)

    def _change_zoom(self, step: int) -> None:
        """按指定步长应用新的整数倍率。"""
        self._apply_zoom(self._zoom + step)

    def _window_size_for_zoom(self, zoom: int) -> QSize:
        """计算指定倍率下包含边距和控制区的窗口目标尺寸。"""
        return QSize(
            self._snapshot_image.width() * zoom + self.HORIZONTAL_MARGIN * 2,
            self._snapshot_image.height() * zoom
            + self.TOP_MARGIN
            + self.NAME_LABEL_HEIGHT
            + self.CONTROL_SPACING
            + self.CONTROL_SPACING
            + self.CONTROL_HEIGHT
            + self.CONTROL_SPACING
            + self.SCROLL_HINT_HEIGHT
            + self.BOTTOM_MARGIN,
        )

    @staticmethod
    def _scroll_hint_text(
        has_horizontal_overflow: bool,
        has_vertical_overflow: bool,
    ) -> str:
        """返回当前横纵溢出组合对应的滚轮操作说明。"""
        if has_horizontal_overflow and has_vertical_overflow:
            return "滚轮：纵向滚动；Shift + 滚轮：横向滚动"
        if has_horizontal_overflow:
            return "滚轮：横向滚动"
        if has_vertical_overflow:
            return "滚轮：纵向滚动"
        return "图像已完整显示，无需滚动"

    def _update_scroll_hint(
        self,
        _range: tuple[int, int] | None = None,
    ) -> None:
        """根据当前横纵滚动范围刷新右下角操作说明。"""
        del _range
        horizontal_bar = self.scroll_area.delegate.hScrollBar
        vertical_bar = self.scroll_area.delegate.vScrollBar
        self.scroll_hint_label.setText(
            self._scroll_hint_text(
                horizontal_bar.maximum() > horizontal_bar.minimum(),
                vertical_bar.maximum() > vertical_bar.minimum(),
            )
        )

    def _largest_fitting_zoom(self, window_size: QSize) -> int:
        """计算指定普通窗口尺寸可完整容纳的最大整数倍率。"""
        for zoom in range(self.MAX_ZOOM, self.MIN_ZOOM - 1, -1):
            target_size = self._window_size_for_zoom(zoom)
            if (
                target_size.width() <= window_size.width()
                and target_size.height() <= window_size.height()
            ):
                return zoom
        return self.MIN_ZOOM

    def _available_screen_size(self) -> QSize:
        """返回窗口当前屏幕的可用尺寸。"""
        return self._available_screen_geometry().size()

    def _available_screen_geometry(self) -> QRect:
        """返回窗口当前屏幕的可用区域。"""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, 1920, 1080)
        return screen.availableGeometry()

    def _center_window(self) -> None:
        """将普通状态窗口移动到当前屏幕可用区域中央。"""
        # 隐藏窗口 resize 后 frameGeometry 可能仍保留旧尺寸，直接使用目标尺寸定位。
        target_geometry = QRect(0, 0, self.width(), self.height())
        target_geometry.moveCenter(self._available_screen_geometry().center())
        self.move(target_geometry.topLeft())

    def resizeEvent(self, event: QResizeEvent) -> None:
        """手动调整普通窗口时自动应用完整适配的最大整数倍率。

        Args:
            event [QResizeEvent]: Qt 窗口尺寸变化事件。

        Returns:
            None: 无返回值。
        """
        super().resizeEvent(event)
        if (
            not self._manual_resize_enabled
            or self._syncing_window_geometry
            or self.isMaximized()
        ):
            return
        self._set_zoom_content(self._largest_fitting_zoom(event.size()))

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制 Fluent 背景和主题适配的窗口外轮廓。

        Args:
            event [QPaintEvent]: Qt 窗口绘制事件。

        Returns:
            None: 无返回值。
        """
        super().paintEvent(event)
        outline_color = (
            QColor(90, 90, 90, 220)
            if isDarkTheme()
            else QColor(160, 160, 160, 220)
        )
        with QPainter(self) as painter:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(outline_color, 1))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
