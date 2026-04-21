"""切片维度卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget
from qfluentwidgets import SimpleCardWidget


class RoundedImageLabel(QLabel):
    """支持圆角绘制的图像标签。

    功能描述：
        重写绘制事件，利用 QPainterPath 对设置的 QPixmap 进行圆角裁剪与缩放。
        内置缓存机制与模式适配：根据当前大小和设定的图像拉伸模式预先生成 QPixmap，提升重绘性能。

    参数说明：
        radius (int): 圆角半径，默认值为 4。
        parent (QWidget | None): 父级控件，默认值为 None。

    返回值说明：
        无。

    异常说明：
        无。
    """

    def __init__(self, radius: int = 4, parent: QWidget | None = None) -> None:
        """初始化圆角图像标签。

        功能描述：
            设置圆角半径并初始化内部图像引用。

        参数说明：
            radius (int): 圆角半径，默认值为 4。
            parent (QWidget | None): 父级控件，默认值为 None。
        """
        super().__init__(parent)
        self._radius = radius
        self._source_image: QImage | None = None
        self._cached_pixmap: QPixmap | None = None

    def set_image(self, image: QImage) -> None:
        """设置源图像并触发更新。

        功能描述：
            保存源图像的深拷贝，并根据当前控件尺寸重新计算缓存图像。

        参数说明：
            image (QImage): 源图像。
        """
        self._source_image = image.copy()
        self._update_scaled_pixmap()

    def resizeEvent(self, event) -> None:
        """窗口尺寸变化事件。

        功能描述：
            尺寸改变时重新计算拉伸后的缓存图像。
        """
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def update_image_mode(self) -> None:
        """主动触发缓存图像更新（供外部配置变更时调用）。"""
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self) -> None:
        """内部方法：根据当前缩放模式生成尺寸完全匹配的 QPixmap 缓存。"""
        if self._source_image is None or self._source_image.isNull():
            return
            
        if self.width() <= 0 or self.height() <= 0:
            return
            
        from ui.adapters.image_scaler import apply_scale_mode
        from app.app_config import appConfig
        
        mode = appConfig.plotScaleMode.value
        scaled_qimage = apply_scale_mode(self._source_image, self.width(), self.height(), mode)
        self._cached_pixmap = QPixmap.fromImage(scaled_qimage)
        self.update()

    def paintEvent(self, event) -> None:
        """绘制带有圆角的图像。

        功能描述：
            如果存在缓存图像，则使用 QPainter 开启抗锯齿并应用圆角裁剪路径后，绘制该图像。
            由于图像已经按尺寸缩放，无需再指定 SmoothPixmapTransform。

        参数说明：
            event (QPaintEvent): 绘制事件对象。
        """
        if self._cached_pixmap is None or self._cached_pixmap.isNull():
            super().paintEvent(event)
            return

        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 构建圆角裁剪路径
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
            painter.setClipPath(path)

            painter.drawPixmap(self.rect(), self._cached_pixmap)


class SliceDimensionCard(QWidget):
    """切片维度卡片组件。

    功能描述：
        提供“左侧竖排维度标签 + 右侧图片占位卡片”的组合组件，用于切片页面维度图像展示位。

    参数说明：
        label_text (str): 维度标签文本。
        object_name (str): 组件对象名。
        parent (QWidget | None): 父级控件，默认值为 None。

    返回值说明：
        无。

    异常说明：
        ValueError: 当 `label_text` 或 `object_name` 为空字符串时抛出。
    """

    def __init__(self, label_text: str, object_name: str, parent: QWidget | None = None) -> None:
        """初始化切片维度卡片组件。

        功能描述：
            构建标签与卡片的水平布局并完成对象命名。

        参数说明：
            label_text (str): 维度标签文本。
            object_name (str): 组件对象名。
            parent (QWidget | None): 父级控件，默认值为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            ValueError: 当 `label_text` 或 `object_name` 为空字符串时抛出。
        """

        super().__init__(parent)
        if label_text.strip() == "":
            raise ValueError("label_text 不能为空")
        if object_name.strip() == "":
            raise ValueError("object_name 不能为空")

        self.setObjectName(object_name)
        self.dimension_label = QLabel("\n".join(label_text), self)
        self.dimension_label.setObjectName("sliceDimensionLabel")
        self.dimension_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dimension_label.setFixedWidth(25)

        self.image_card = SimpleCardWidget(self)
        self.image_card.setObjectName("sliceImageCard")
        self.image_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 添加用于显示圆角图像的 QLabel（内边距 0px，卡片外圆角 6px，故图片圆角设为 6px）
        self.image_label = RoundedImageLabel(radius=6, parent=self.image_card)
        self.image_label.setObjectName("sliceImageLabel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        # 为 image_card 设置布局（无内边距）
        card_layout = QHBoxLayout(self.image_card)
        card_layout.setContentsMargins(1, 1, 1, 1)
        card_layout.addWidget(self.image_label)

        self._init_layout()

    def set_image(self, image: QImage) -> None:
        """设置卡片内的图像。

        功能描述：
            将 QImage 源图像设置到图片标签中。

        参数说明：
            image (QImage): 要显示的源图像对象。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        self.image_label.set_image(image)

    def update_image_mode(self) -> None:
        """更新内部图像标签的拉伸模式。"""
        self.image_label.update_image_mode()

    def _init_layout(self) -> None:
        """初始化组件布局。

        功能描述：
            将标签与图片卡片按固定间距加入水平布局。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self.dimension_label)
        row_layout.addWidget(self.image_card, 1)
