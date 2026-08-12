"""合并工作区五维多颜色图像列组件。"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
from PyQt6.QtCore import QEvent, QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Theme,
    ToolTipFilter,
    ToolTipPosition,
    TransparentToolButton,
)

from app.custom_icon import CustomIcon
from ui.components.image_snapshot_window import ImageSnapshotWindow
from ui.components.slice_dimension_card import SliceDimensionCard


_DIMENSION_DISPLAY_NAMES: dict[str, str] = {
    "CF": "载频",
    "PW": "脉宽",
    "PA": "幅度",
    "DTOA": "一级差",
    "DOA": "方位角",
}


class _MergePriModeToggleButton(TransparentToolButton):
    """绘制半透明白底和固定深色图标的 PRI 模式切换按钮。"""

    BACKGROUND_ALPHA: int = 152
    HOVER_BACKGROUND_ALPHA: int = 200
    PRESSED_BACKGROUND_ALPHA: int = 255

    def __init__(self, parent: QWidget) -> None:
        """初始化固定使用深色同步图标的覆盖按钮。"""
        super().__init__(parent)
        self.setIcon(CustomIcon.ARROW_LEFTRIGHT.icon(Theme.LIGHT))

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制在黑色图像上清晰可见的半透明白色圆角按钮。"""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.isPressed:
            alpha = self.PRESSED_BACKGROUND_ALPHA
        elif self.isHover:
            alpha = self.HOVER_BACKGROUND_ALPHA
        else:
            alpha = self.BACKGROUND_ALPHA
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, alpha))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 7, 7)

        # 图标固定为黑色，不再跟随深色主题切换为白色后融入白色按钮底。
        icon_size = self.iconSize()
        icon_x = (self.width() - icon_size.width()) // 2
        icon_y = (self.height() - icon_size.height()) // 2
        self.icon().paint(
            painter,
            icon_x,
            icon_y,
            icon_size.width(),
            icon_size.height(),
        )


class _MergePriDimensionCard(SliceDimensionCard):
    """按 PRI 显示模式分别持有两个独立图像快照窗口。"""

    SOURCE_MODE_KEY = "source_stack"
    RECOMPUTED_MODE_KEY = "merged_recomputed"
    SOURCE_MODE_TITLE = "来源类簇 PRI 叠加"
    RECOMPUTED_MODE_TITLE = "合并序列 PRI 重算"

    def __init__(
        self,
        label_text: str,
        object_name: str,
        parent: QWidget,
        scale_mode_getter: Callable[[], str] | None,
        *,
        snapshot_window_title: str,
    ) -> None:
        """初始化模式状态及其各自的快照窗口引用。"""
        self._snapshot_mode_key = self.SOURCE_MODE_KEY
        self._snapshot_mode_title = self.SOURCE_MODE_TITLE
        self._snapshot_windows_by_mode: dict[str, ImageSnapshotWindow] = {}
        super().__init__(
            label_text,
            object_name,
            parent,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title=snapshot_window_title,
        )

    def _set_snapshot_mode(self, recompute_merged_dtoa: bool) -> None:
        """同步后续展开动作使用的 PRI 模式键和显示名称。"""
        if recompute_merged_dtoa:
            self._snapshot_mode_key = self.RECOMPUTED_MODE_KEY
            self._snapshot_mode_title = self.RECOMPUTED_MODE_TITLE
        else:
            self._snapshot_mode_key = self.SOURCE_MODE_KEY
            self._snapshot_mode_title = self.SOURCE_MODE_TITLE

    def _show_snapshot_window(self) -> None:
        """为当前 PRI 模式创建或激活其专属快照窗口。"""
        if self._source_image is None or self._source_image.isNull():
            return

        mode_key = self._snapshot_mode_key
        existing_window = self._snapshot_windows_by_mode.get(mode_key)
        if existing_window is not None:
            existing_window.showNormal()
            existing_window.raise_()
            existing_window.activateWindow()
            return

        window = ImageSnapshotWindow(
            self._source_image,
            f"{self._snapshot_window_title} - {self._snapshot_mode_title}",
        )
        window.destroyed.connect(
            lambda _object=None, key=mode_key: self._clear_mode_snapshot_window(
                key
            )
        )
        self._snapshot_windows_by_mode[mode_key] = window
        window.show()

    def _clear_mode_snapshot_window(self, mode_key: str) -> None:
        """清除已销毁的指定 PRI 模式快照窗口引用。"""
        self._snapshot_windows_by_mode.pop(mode_key, None)


class MergeImageColumn(QWidget):
    """承载五维合并图像的等宽内容列。

    Attributes:
        title_label [QLabel]: 合并图像列标题。
        merge_cf_card [SliceDimensionCard]: 载频合并图像卡片。
        merge_pw_card [SliceDimensionCard]: 脉宽合并图像卡片。
        merge_pa_card [SliceDimensionCard]: 幅度合并图像卡片。
        merge_dtoa_card [SliceDimensionCard]: 一级差合并图像卡片。
        merge_doa_card [SliceDimensionCard]: 方位角合并图像卡片。
        pri_mode_toggle_button [TransparentToolButton]: PRI 图像右上角的
            hover 模式切换按钮。
        dimension_cards [tuple[SliceDimensionCard, ...]]: 按五维显示顺序排列的卡片集合。
        cards_by_dimension [dict[str, SliceDimensionCard]]: 维度名到图像卡片的映射。
    """

    pri_mode_toggle_requested = pyqtSignal()

    PRI_TOGGLE_MARGIN: int = 8

    def __init__(
        self,
        parent: QWidget | None = None,
        scale_mode_getter: Callable[[], str] | None = None,
    ) -> None:
        """初始化合并图像列。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。
            scale_mode_getter [Callable[[], str] | None]: 当前图像缩放模式读取回调。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> column = MergeImageColumn()
            >>> len(column.dimension_cards)
            5
        """
        super().__init__(parent)
        self.setObjectName("sliceMergeColumn")

        self.title_label = QLabel("合并结果", self)
        # 复用切片页现有标题样式，避免为同类标题新增平行样式规则。
        self.title_label.setObjectName("sliceMiddleTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(25)
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )

        self.merge_cf_card = SliceDimensionCard(
            "载频",
            "mergeCfCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 载频",
        )
        self.merge_pw_card = SliceDimensionCard(
            "脉宽",
            "mergePwCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 脉宽",
        )
        self.merge_pa_card = SliceDimensionCard(
            "幅度",
            "mergePaCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 幅度",
        )
        self.merge_dtoa_card = _MergePriDimensionCard(
            "一级差",
            "mergeDtoaCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 一级差",
        )
        self.merge_doa_card = SliceDimensionCard(
            "方位角",
            "mergeDoaCard",
            self,
            scale_mode_getter=scale_mode_getter,
            snapshot_window_title="合并结果 - 方位角",
        )
        self.dimension_cards = (
            self.merge_cf_card,
            self.merge_pw_card,
            self.merge_pa_card,
            self.merge_dtoa_card,
            self.merge_doa_card,
        )
        self.cards_by_dimension = dict(
            zip(
                ("CF", "PW", "PA", "DTOA", "DOA"),
                self.dimension_cards,
                strict=True,
            )
        )

        self._has_pri_image: bool = False
        self._recompute_merged_dtoa: bool = False
        self.pri_mode_toggle_button = _MergePriModeToggleButton(
            self.merge_dtoa_card.image_card,
        )
        self.pri_mode_toggle_button.setObjectName("mergePriModeToggleButton")
        self.pri_mode_toggle_button.setFixedSize(30, 30)
        self.pri_mode_toggle_button.setIconSize(QSize(18, 18))
        self.pri_mode_toggle_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.pri_mode_toggle_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # 使用 Fluent Tooltip 过滤器接管原生提示事件，保持主题与动效一致。
        self.pri_mode_toggle_button.installEventFilter(
            ToolTipFilter(
                self.pri_mode_toggle_button,
                1000,
                ToolTipPosition.TOP,
            )
        )
        self.pri_mode_toggle_button.hide()
        self.pri_mode_toggle_button.clicked.connect(
            lambda _checked=False: self.pri_mode_toggle_requested.emit()
        )
        self.merge_dtoa_card.image_card.setMouseTracking(True)
        self.merge_dtoa_card.image_label.setMouseTracking(True)
        self.merge_dtoa_card.image_card.installEventFilter(self)
        self.merge_dtoa_card.image_label.installEventFilter(self)
        self.pri_mode_toggle_button.installEventFilter(self)
        self.set_pri_recompute_mode(False)

        self._init_layout()
        self._position_pri_mode_toggle_button()

    def update_images(
        self,
        images: Mapping[str, np.ndarray],
        title: str,
    ) -> None:
        """显示runtime提供的当前合并结果五维图像。

        Args:
            images [Mapping[str, np.ndarray]]: 维度名到RGB图像的映射。
            title [str]: 当前结果标题。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 图像不是 ``H×W×3`` 的 uint8 RGB 数组时抛出。
        """
        self.title_label.setText(title)
        self._has_pri_image = False
        for dimension, card in self.cards_by_dimension.items():
            image_data = images.get(dimension)
            # runtime可能只返回部分维度；缺失项必须清空，不能保留上一结果旧图。
            if image_data is None:
                card.clear_image()
                continue
            if (
                image_data.ndim != 3
                or image_data.shape[2] != 3
                or image_data.dtype.name != "uint8"
            ):
                raise ValueError(f"{dimension} 合并图像必须为 H×W×3 的 uint8 RGB 数组")
            # NumPy数组采用连续RGB三通道布局，每行字节数固定为width * 3。
            height, width, _channels = image_data.shape
            q_image = QImage(
                image_data.data,
                width,
                height,
                width * 3,
                QImage.Format.Format_RGB888,
            )
            # 卡片负责持有QImage并刷新独立窗口标题，UI层不参与再次绘图。
            card.set_image(q_image)
            if dimension == "DTOA":
                self._has_pri_image = True
            card.set_snapshot_window_title(
                f"{title} - {_DIMENSION_DISPLAY_NAMES[dimension]}"
            )
        if not self._has_pri_image:
            self.pri_mode_toggle_button.hide()

    def clear_images(self) -> None:
        """清空全部合并图像并恢复默认标题。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.title_label.setText("合并结果")
        self._has_pri_image = False
        self.pri_mode_toggle_button.hide()
        for card in self.dimension_cards:
            card.clear_image()

    def set_pri_recompute_mode(self, enabled: bool) -> None:
        """同步 PRI 图像按钮所表示的当前模式。

        Args:
            enabled [bool]: ``True`` 表示完整合并序列重算模式，``False``
                表示来源类簇 PRI 分别计算后叠加。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self._recompute_merged_dtoa = bool(enabled)
        self.merge_dtoa_card._set_snapshot_mode(
            self._recompute_merged_dtoa
        )
        if self._recompute_merged_dtoa:
            tooltip = "当前：合并序列 PRI 重算；点击切换为来源类簇 PRI 叠加"
        else:
            tooltip = "当前：来源类簇 PRI 叠加；点击切换为合并序列 PRI 重算"
        self.pri_mode_toggle_button.setToolTip(tooltip)
        self.pri_mode_toggle_button.setAccessibleName(tooltip)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """处理 PRI 图像 hover、按钮透明度和覆盖位置变化。

        Args:
            watched [QObject]: 当前产生事件的 PRI 图像容器或切换按钮。
            event [QEvent]: Qt 事件对象。

        Returns:
            bool: 始终返回父类处理结果，不拦截原图像或按钮事件。

        Raises:
            无显式抛出异常。
        """
        image_card = self.merge_dtoa_card.image_card
        hover_targets = (
            image_card,
            self.merge_dtoa_card.image_label,
            self.pri_mode_toggle_button,
        )
        if watched is image_card and event.type() is QEvent.Type.Resize:
            self._position_pri_mode_toggle_button()
        if watched in hover_targets:
            if event.type() in (
                QEvent.Type.Enter,
                QEvent.Type.MouseMove,
            ):
                self._set_pri_toggle_hovered(True)
            elif event.type() is QEvent.Type.Leave:
                if watched is image_card:
                    self._set_pri_toggle_hovered(False)
        return super().eventFilter(watched, event)

    def _set_pri_toggle_hovered(self, hovered: bool) -> None:
        """按 PRI 图像 hover 状态显示或隐藏切换按钮。"""
        visible = bool(hovered and self._has_pri_image)
        self.pri_mode_toggle_button.setVisible(visible)
        if visible:
            self._position_pri_mode_toggle_button()
            self.pri_mode_toggle_button.raise_()

    def _position_pri_mode_toggle_button(self) -> None:
        """把切换按钮固定在 PRI 图像容器右上角。"""
        image_card = self.merge_dtoa_card.image_card
        x = max(
            0,
            image_card.width()
            - self.pri_mode_toggle_button.width()
            - self.PRI_TOGGLE_MARGIN,
        )
        y = min(
            self.PRI_TOGGLE_MARGIN,
            max(0, image_card.height() - self.pri_mode_toggle_button.height()),
        )
        self.pri_mode_toggle_button.move(x, y)

    def _init_layout(self) -> None:
        """创建标题栏和五维图像卡片布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self.title_label)
        for card in self.dimension_cards:
            layout.addWidget(card, 1)
