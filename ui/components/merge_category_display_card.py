"""合并结果来源类别的显示与显隐控制组件。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPaintEvent, QPainter, QResizeEvent
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import CheckBox, SimpleCardWidget, isDarkTheme


class _MergeSkeletonBar(QWidget):
    """绘制一条随主题变化的灰色圆角骨架占位。"""

    CORNER_RADIUS = 5.0

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化固定高度的骨架条。"""
        super().__init__(parent)
        self.setObjectName("mergeCategorySkeletonBar")
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

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
        painter.drawRoundedRect(self.rect(), self.CORNER_RADIUS, self.CORNER_RADIUS)


class MergeCategorySkeleton(QWidget):
    """展示三条等长、左对齐的类别显示控制骨架。

    Attributes:
        skeleton_bars [tuple[QWidget, ...]]: 三条骨架占位。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化类别显示控制骨架屏。

        Args:
            parent [QWidget | None]: 父级控件。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.setObjectName("mergeCategorySkeleton")
        self.skeleton_bars: tuple[QWidget, ...] = tuple(
            _MergeSkeletonBar(self) for _ in range(3)
        )
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


class _CategoryColorSwatch(QWidget):
    """绘制与合并图一致的来源类别颜色块。"""

    def __init__(
        self,
        color: tuple[int, int, int],
        parent: QWidget | None = None,
    ) -> None:
        """初始化固定颜色块。"""
        super().__init__(parent)
        self.color = color
        self.setFixedSize(14, 14)

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制圆角色块。"""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(*self.color))
        painter.drawRoundedRect(self.rect(), 3.0, 3.0)


class _CategoryControlRow(QWidget):
    """组合来源颜色块与双态复选框。"""

    def __init__(
        self,
        cluster_index: int,
        color: tuple[int, int, int],
        checked: bool,
        parent: QWidget | None = None,
    ) -> None:
        """初始化一个来源类别控制行。"""
        super().__init__(parent)
        self.swatch = _CategoryColorSwatch(color, self)
        self.checkbox = CheckBox(f"第{cluster_index}类", self)
        self.checkbox.setTristate(False)
        self.checkbox.setChecked(checked)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.swatch)
        layout.addWidget(self.checkbox)
        layout.addStretch()


class MergeCategoryDisplayCard(SimpleCardWidget):
    """显示当前合并结果的来源类别、颜色和双态显隐开关。

    Attributes:
        skeleton [MergeCategorySkeleton]: 尚无合并结果时的骨架屏。
        category_checkboxes [dict[int, CheckBox]]: 类簇编号到复选框的映射。
        category_colors [dict[int, tuple[int, int, int]]]: 类簇编号到RGB颜色的映射。
    """

    visibility_changed = pyqtSignal(int, bool)
    height_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化类别显示卡片。

        Args:
            parent [QWidget | None]: 父级控件。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.setObjectName("mergeCategoryDisplayCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.skeleton = MergeCategorySkeleton(self)
        self.category_checkboxes: dict[int, CheckBox] = {}
        self.category_colors: dict[int, tuple[int, int, int]] = {}
        self._rows: list[_CategoryControlRow] = []
        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(8)
        self._content_layout.addWidget(self.skeleton)
        self._sync_height()

    def set_categories(
        self,
        categories: Sequence[tuple[int, tuple[int, int, int]]],
        checked_indices: Iterable[int] | None = None,
    ) -> None:
        """显示当前结果全部来源类别。

        Args:
            categories [Sequence[tuple[int, tuple[int, int, int]]]]: 类簇编号与RGB颜色。
            checked_indices [Iterable[int] | None]: 当前可见类簇；为空表示全部选中。

        Returns:
            None: 无返回值。
        """
        # 切换结果时先销毁旧行，防止复选框信号和颜色映射残留到新结果。
        self._clear_rows()
        checked_set = (
            None if checked_indices is None else {int(index) for index in checked_indices}
        )
        # 有真实类别时隐藏骨架；无类别时继续展示固定三行占位。
        self.skeleton.setVisible(not categories)
        for cluster_index, color in categories:
            row = _CategoryControlRow(
                cluster_index,
                color,
                checked_set is None or cluster_index in checked_set,
                self,
            )
            # 默认参数固定当前循环的簇编号，避免闭包晚绑定导致全部信号指向末项。
            row.checkbox.toggled.connect(
                lambda checked, index=cluster_index: self.visibility_changed.emit(
                    index,
                    checked,
                )
            )
            self._rows.append(row)
            self.category_checkboxes[cluster_index] = row.checkbox
            self.category_colors[cluster_index] = color
            self._content_layout.addWidget(row)
        self._sync_height()

    def clear_categories(self) -> None:
        """清空类别控制并恢复骨架屏。

        Returns:
            None: 无返回值。
        """
        self._clear_rows()
        self.skeleton.show()
        self._sync_height()

    def visible_cluster_indices(self) -> tuple[int, ...]:
        """返回当前选中的来源类簇编号。

        Returns:
            tuple[int, ...]: 按显示顺序排列的可见类簇编号。
        """
        return tuple(
            cluster_index
            for cluster_index, checkbox in self.category_checkboxes.items()
            if checkbox.isChecked()
        )

    def set_all_checked(self) -> None:
        """将当前结果全部来源类别恢复为选中。

        Returns:
            None: 无返回值。
        """
        for checkbox in self.category_checkboxes.values():
            # 批量复位时阻断逐项toggled信号，由控制器在循环后只重绘一次。
            blocker = QSignalBlocker(checkbox)
            checkbox.setChecked(True)
            del blocker

    def _clear_rows(self) -> None:
        """移除当前动态类别行。"""
        for row in self._rows:
            # 先从布局移除，再交给Qt事件循环安全销毁控件。
            self._content_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self.category_checkboxes.clear()
        self.category_colors.clear()

    def _sync_height(self) -> None:
        """根据骨架或动态类别行更新固定高度。"""
        self._content_layout.activate()
        height = self.sizeHint().height()
        self.setFixedHeight(height)
        self.height_changed.emit(height)
