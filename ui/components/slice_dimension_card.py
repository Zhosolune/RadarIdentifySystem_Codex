"""切片维度卡片组件。"""

from __future__ import annotations
from collections.abc import Callable


from PyQt6.QtCore import QObject, QPoint, Qt, QRectF
from PyQt6.QtGui import QContextMenuEvent, QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget
from qfluentwidgets import (
    Action,
    CommandBarView,
    FluentIcon,
    Flyout,
    SimpleCardWidget,
)

from ui.components.image_snapshot_window import ImageSnapshotWindow


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

    def __init__(
        self,
        radius: int = 4,
        parent: QWidget | None = None,
        scale_mode_getter: Callable[[], str] | None = None,
    ) -> None:
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
        self._scale_mode_getter = scale_mode_getter

    def set_image(self, image: QImage) -> None:
        """设置源图像并触发更新。

        功能描述：
            保存源图像的深拷贝，并根据当前控件尺寸重新计算缓存图像。

        参数说明：
            image (QImage): 源图像。
        """
        if image.isNull():
            self.clear_image()
            return

        self._source_image = image.copy()
        self._update_scaled_pixmap()

    def clear_image(self) -> None:
        """清除源图像、缩放缓存及标签显示内容。

        Returns:
            None: 无返回值。
        """
        # 同时释放源图和派生缓存，避免空白状态继续绘制上一幅图像。
        self._source_image = None
        self._cached_pixmap = None
        self.clear()
        self.update()

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

        mode = self._scale_mode_getter() if self._scale_mode_getter else "STRETCH"
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

    提供左侧竖排维度标签与右侧图像卡片，并管理当前卡片的右键独立查看交互。

    Attributes:
        dimension_label [QLabel]: 竖排显示维度名称的标签。
        image_card [SimpleCardWidget]: 承载当前维度图像的卡片。
        image_label [RoundedImageLabel]: 绘制圆角图像的标签。
    """

    def __init__(
        self,
        label_text: str,
        object_name: str,
        parent: QWidget | None = None,
        scale_mode_getter: Callable[[], str] | None = None,
        *,
        snapshot_window_title: str,
    ) -> None:
        """初始化维度标签、图像卡片和独立窗口状态。

        Args:
            label_text [str]: 非空维度标签文本。
            object_name [str]: 非空组件对象名。
            parent [QWidget | None]: 父级控件，默认值为 None。
            scale_mode_getter [Callable[[], str] | None]: 图像缩放模式读取回调。
            snapshot_window_title [str]: 非空独立图像窗口标题。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当标签、对象名或独立窗口标题为空时抛出。
        """

        super().__init__(parent)
        if label_text.strip() == "":
            raise ValueError("label_text 不能为空")
        if object_name.strip() == "":
            raise ValueError("object_name 不能为空")
        if snapshot_window_title.strip() == "":
            raise ValueError("snapshot_window_title 不能为空")

        self.setObjectName(object_name)
        self._source_image: QImage | None = None
        self._snapshot_window: ImageSnapshotWindow | None = None
        self._snapshot_window_title_base = snapshot_window_title
        self._snapshot_window_title = snapshot_window_title
        self.dimension_label = QLabel("\n".join(label_text), self)
        self.dimension_label.setObjectName("sliceDimensionLabel")
        self.dimension_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dimension_label.setFixedWidth(25)

        self.image_card = SimpleCardWidget(self)
        self.image_card.setObjectName("sliceImageCard")
        self.image_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 添加用于显示圆角图像的 QLabel（内边距 0px，卡片外圆角 6px，故图片圆角设为 6px）
        self.image_label = RoundedImageLabel(
            radius=6,
            parent=self.image_card,
            scale_mode_getter=scale_mode_getter,
        )
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
        """保存源图像副本并更新卡片内图像。

        Args:
            image [QImage]: 要显示的源图像对象，允许空图像用于清空状态。

        Returns:
            None: 无返回值。
        """
        if image.isNull():
            self.clear_image()
            return

        # 卡片保存独立源图像，确保创建窗口时获得触发瞬间的稳定快照。
        self._source_image = image.copy()
        self.image_label.set_image(image)

    def clear_image(self) -> None:
        """将卡片切换为不可展开的空白图像状态。

        已经打开的独立窗口仍保留其固定快照，卡片后续右键不再响应。

        Returns:
            None: 无返回值。
        """
        self._source_image = None
        self.image_label.clear_image()

    def set_snapshot_slice_number(self, slice_number: int) -> None:
        """为独立图像窗口标题设置当前切片编号。

        Args:
            slice_number [int]: 1-based 切片编号，必须大于等于 1。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片编号小于 1 时抛出。
        """
        if slice_number < 1:
            raise ValueError("slice_number 必须大于等于 1")
        self._snapshot_window_title = (
            f"切片 {slice_number} - {self._snapshot_window_title_base}"
        )

    def set_snapshot_window_title(self, title: str) -> None:
        """更新后续独立图像窗口使用的完整标题。

        已打开窗口仍保留创建时的快照标题，只有后续新窗口使用更新值。

        Args:
            title [str]: 非空完整窗口标题。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当标题为空或只包含空白字符时抛出。
        """
        if not title.strip():
            raise ValueError("title 不能为空")
        self._snapshot_window_title = title

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """在有效图像卡片的右键位置显示独立查看命令。

        Args:
            event [QContextMenuEvent]: Qt 右键菜单事件。

        Returns:
            None: 无返回值。
        """
        if self._source_image is None or self._source_image.isNull():
            event.ignore()
            return

        self._show_command_bar(event.globalPos())
        event.accept()

    def _show_command_bar(self, global_pos: QPoint) -> None:
        """在指定全局坐标显示独立查看命令。

        Args:
            global_pos [QPoint]: 命令栏显示的全局坐标。

        Returns:
            None: 无返回值。
        """
        if self._source_image is None or self._source_image.isNull():
            return

        view = CommandBarView()
        view.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        action = Action(FluentIcon.FULL_SCREEN, "展开", view)
        action.triggered.connect(self._show_snapshot_window)
        view.addAction(action)
        view.resizeToSuitableWidth()
        Flyout.make(view, global_pos, self.window())

    def _show_snapshot_window(self) -> None:
        """创建图像快照窗口，或激活本卡片已有窗口。"""
        if self._source_image is None or self._source_image.isNull():
            return

        if self._snapshot_window is not None:
            self._snapshot_window.showNormal()
            self._snapshot_window.raise_()
            self._snapshot_window.activateWindow()
            return

        # 每个卡片只保留一个窗口引用，不同卡片仍可分别创建窗口进行对比。
        window = ImageSnapshotWindow(
            self._source_image,
            self._snapshot_window_title,
        )
        window.destroyed.connect(self._clear_snapshot_window)
        self._snapshot_window = window
        window.show()

    def _clear_snapshot_window(self, _object: QObject | None = None) -> None:
        """清除已销毁图像快照窗口的引用。"""
        self._snapshot_window = None

    def update_image_mode(self) -> None:
        """按当前配置更新内部图像标签的拉伸模式。

        Returns:
            None: 无返回值。
        """
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
