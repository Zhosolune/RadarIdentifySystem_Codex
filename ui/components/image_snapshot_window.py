"""提供独立显示固定图像快照的 Fluent 窗口。"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    FluentWidget,
    ImageLabel,
    ScrollArea,
    Slider,
    isDarkTheme,
)


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


class ImageSnapshotWindow(FluentWidget):
    """在独立 Fluent 窗口中显示固定图像快照。

    窗口持有传入图像的深拷贝，后续源图像变化不会影响当前显示内容。

    Attributes:
        image_label [PixelPerfectImageLabel]: 用于整数倍显示图像快照的标签。
        scroll_area [ScrollArea]: 保持图像固定尺寸并提供滚动查看的区域。
        zoom_slider [Slider]: 选择 1～10 倍整数显示倍率的滑块。
        zoom_value_label [BodyLabel]: 显示当前倍率的文本标签。
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
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(title)
        self.setMinimumSize(320, 180)

        self.image_label = PixelPerfectImageLabel(self._snapshot_image)
        self.image_label.setBorderRadius(0, 0, 0, 0)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

        control_widget = QWidget(self)
        control_widget.setFixedHeight(self.CONTROL_HEIGHT)
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)

        zoom_title_label = BodyLabel("显示倍率", control_widget)
        self.zoom_slider = Slider(Qt.Orientation.Horizontal, control_widget)
        self.zoom_slider.setRange(self.MIN_ZOOM, self.MAX_ZOOM)
        self.zoom_slider.setSingleStep(1)
        self.zoom_slider.setPageStep(1)
        self.zoom_slider.setValue(self.DEFAULT_ZOOM)
        self.zoom_value_label = BodyLabel(
            f"{self.DEFAULT_ZOOM}×",
            control_widget,
        )
        self.zoom_value_label.setMinimumWidth(28)

        control_layout.addWidget(zoom_title_label)
        control_layout.addWidget(self.zoom_slider, 1)
        control_layout.addWidget(self.zoom_value_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.HORIZONTAL_MARGIN,
            self.TOP_MARGIN,
            self.HORIZONTAL_MARGIN,
            self.BOTTOM_MARGIN,
        )
        layout.setSpacing(self.CONTROL_SPACING)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(control_widget)

        self.zoom_slider.valueChanged.connect(self._apply_zoom)
        self._apply_zoom(self.DEFAULT_ZOOM)

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
        scaled_size = QSize(
            self._snapshot_image.width() * bounded_zoom,
            self._snapshot_image.height() * bounded_zoom,
        )
        self.image_label.setScaledSize(scaled_size)
        self.zoom_value_label.setText(f"{bounded_zoom}×")

        window_size = self._window_size_for_zoom(bounded_zoom)
        available_size = self._available_screen_size()
        exceeds_screen = (
            window_size.width() > available_size.width()
            or window_size.height() > available_size.height()
        )
        if exceeds_screen:
            self.setWindowState(
                self.windowState() | Qt.WindowState.WindowMaximized
            )
            return

        if self.isMaximized():
            self.showNormal()
        self.resize(window_size)

    def _window_size_for_zoom(self, zoom: int) -> QSize:
        """计算指定倍率下包含边距和控制区的窗口目标尺寸。"""
        return QSize(
            self._snapshot_image.width() * zoom + self.HORIZONTAL_MARGIN * 2,
            self._snapshot_image.height() * zoom
            + self.TOP_MARGIN
            + self.CONTROL_SPACING
            + self.CONTROL_HEIGHT
            + self.BOTTOM_MARGIN,
        )

    def _available_screen_size(self) -> QSize:
        """返回窗口当前屏幕的可用尺寸。"""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return QSize(1920, 1080)
        return screen.availableGeometry().size()

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
