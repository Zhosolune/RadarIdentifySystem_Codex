"""合并操作卡片的类别显示卡片组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPaintEvent, QPainter, QResizeEvent
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import SimpleCardWidget, isDarkTheme


class _MergeSkeletonBar(QWidget):
    """绘制一条随主题变化的灰色圆角骨架占位。"""

    CORNER_RADIUS = 5.0

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化固定高度的骨架条。"""
        super().__init__(parent)
        self.setObjectName("mergeCategorySkeletonBar")
        self.setFixedHeight(20)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制无边框灰色圆角矩形。"""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            Qt.GlobalColor.lightGray
            if not isDarkTheme()
            else Qt.GlobalColor.darkGray
        )
        painter.drawRoundedRect(
            self.rect(),
            self.CORNER_RADIUS,
            self.CORNER_RADIUS,
        )


class MergeCategorySkeleton(QWidget):
    """展示三条等长、左对齐的类别显示控制骨架。

    Attributes:
        skeleton_bars [tuple[QWidget, ...]]: 三条等长骨架占位。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化类别显示控制骨架屏。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("mergeCategorySkeleton")
        self.skeleton_bars: tuple[QWidget, ...] = tuple(
            _MergeSkeletonBar(self) for _ in range(3)
        )
        self._init_layout()

    def _init_layout(self) -> None:
        """创建左对齐的三行骨架布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        for bar in self.skeleton_bars:
            layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignLeft)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """在类别卡片缩放时同步骨架为内容区宽度的一半。"""
        super().resizeEvent(event)
        target_width = max(0, self.width() // 2)
        for bar in self.skeleton_bars:
            bar.setFixedWidth(target_width)


class MergeCategoryDisplayCard(SimpleCardWidget):
    """独立包裹类别显示控制骨架屏的卡片。

    本组件只包含骨架屏；“类别显示控制”标签由外层操作卡片持有并显示在卡片
    上方，避免标题进入卡片内部。

    Attributes:
        skeleton [MergeCategorySkeleton]: 类别数据未就绪时的默认骨架屏。

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> app = QApplication.instance() or QApplication([])
        >>> card = MergeCategoryDisplayCard()
        >>> len(card.skeleton.skeleton_bars)
        3
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化仅包含骨架屏的类别显示卡片。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("mergeCategoryDisplayCard")
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.skeleton = MergeCategorySkeleton(self)
        self._init_layout()
        self.setFixedHeight(self.sizeHint().height())

    def _init_layout(self) -> None:
        """将骨架屏装入卡片并保留统一内边距。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.skeleton)
