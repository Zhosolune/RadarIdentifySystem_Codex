"""提供独立显示固定图像快照的 Fluent 窗口。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout
from qfluentwidgets import FluentWidget, isDarkTheme


class ImageSnapshotWindow(FluentWidget):
    """在独立 Fluent 窗口中显示固定图像快照。

    窗口持有传入图像的深拷贝，后续源图像变化不会影响当前显示内容。

    Attributes:
        image_label [QLabel]: 用于等比例显示图像快照的标签。
        snapshot_image [QImage]: 当前窗口持有的图像快照副本。
    """

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
        self.resize(960, 640)
        self.setMinimumSize(480, 320)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 52, 12, 12)
        layout.addWidget(self.image_label)
        self.refresh_pixmap()

    @property
    def snapshot_image(self) -> QImage:
        """返回窗口持有的图像快照副本。

        Returns:
            QImage: 与窗口内部存储相互独立的图像副本。
        """
        return self._snapshot_image.copy()

    def refresh_pixmap(self) -> None:
        """按图像标签当前尺寸等比例刷新显示内容。

        Returns:
            None: 无返回值。
        """
        size = self.image_label.size()
        if size.width() <= 0 or size.height() <= 0:
            return

        pixmap = QPixmap.fromImage(self._snapshot_image).scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """在窗口尺寸变化时保持图像快照的宽高比。

        Args:
            event [QResizeEvent]: Qt 窗口尺寸变化事件。

        Returns:
            None: 无返回值。
        """
        super().resizeEvent(event)
        self.refresh_pixmap()

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
