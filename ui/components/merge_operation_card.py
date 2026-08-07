"""合并面板的操作卡片组件。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CheckBox, ComboBox, SimpleCardWidget

from .merge_action_button_bar import MergeActionButtonBar
from .merge_category_display_card import MergeCategoryDisplayCard


class MergeOperationCard(SimpleCardWidget):
    """组合合并按钮和类别显示控制的操作卡片。

    Attributes:
        button_bar [MergeActionButtonBar]: 水平排列的四按钮操作区。
        pri_mode_row [QWidget]: 承载 PRI 图像模式标签与下拉框的容器。
        pri_mode_label [BodyLabel]: PRI 图像模式标题。
        pri_mode_combo [ComboBox]: 来源叠加与合并序列重算的切换控件。
        result_count_label [QLabel]: 显示当前切片独立合并结果数量的标签。
        category_header [QWidget]: 同行承载类别标题和全局复选框的容器。
        category_title_label [StrongBodyLabel]: 类别控制标题。
        global_visibility_checkbox [CheckBox]: 汇总并控制全部来源类别显隐的三态复选框。
        category_display_card [MergeCategoryDisplayCard]: 包裹默认骨架屏的卡片。

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> app = QApplication.instance() or QApplication([])
        >>> card = MergeOperationCard()
        >>> card.button_bar.merge_button.text()
        '合并'
    """

    global_visibility_changed = pyqtSignal(bool)
    pri_image_mode_changed = pyqtSignal(bool)

    SOURCE_STACK_MODE_TEXT = "来源类簇 PRI 叠加"
    MERGED_RECOMPUTE_MODE_TEXT = "合并序列 PRI 重算"

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化按钮区和类别显示控制区。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("mergeOperationCard")
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.button_bar = MergeActionButtonBar(self)

        self.pri_mode_row = QWidget(self)
        self.pri_mode_label = BodyLabel("PRI 图像模式", self.pri_mode_row)
        self.pri_mode_combo = ComboBox(self.pri_mode_row)
        self.pri_mode_combo.addItems(
            [
                self.SOURCE_STACK_MODE_TEXT,
                self.MERGED_RECOMPUTE_MODE_TEXT,
            ]
        )
        self.pri_mode_combo.setCurrentIndex(0)
        self.pri_mode_combo.setMinimumWidth(190)
        self.pri_mode_combo.setToolTip(
            "重算模式按 TOA 合并全部可见脉冲，PRI 使用较大 TOA 所属类别颜色"
        )
        self.pri_mode_combo.currentIndexChanged.connect(
            self._on_pri_mode_changed
        )
        self._init_pri_mode_row()

        self.result_count_label = QLabel("共获得 ？个合并结果", self)
        self.result_count_label.setObjectName("sliceInfoLabel")
        self.result_count_label.setFixedHeight(25)

        self.category_header = QWidget(self)
        self.category_title_label = BodyLabel("类别显示控制", self.category_header)
        self.category_title_label.setObjectName("mergeCategoryTitleLabel")
        self.category_title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        category_title_font = self.category_title_label.font()
        category_title_font.setPixelSize(16)
        self.category_title_label.setFont(category_title_font)
        self.category_title_label.setFixedHeight(24)
        self.global_visibility_checkbox = CheckBox(
            "勾选全部",
            self.category_header,
        )
        self.global_visibility_checkbox.setTristate(True)
        self.global_visibility_checkbox.setEnabled(False)
        self.global_visibility_checkbox.clicked.connect(
            self._on_global_visibility_clicked
        )
        self._init_category_header()

        self.category_display_card = MergeCategoryDisplayCard(self)
        self.category_display_card.visibility_changed.connect(
            lambda _index, _visible: self.sync_global_visibility_checkbox()
        )
        # 类别行数量会改变子卡片高度，外层操作卡片必须同步更新固定高度。
        self.category_display_card.height_changed.connect(
            lambda _height: self._sync_height()
        )
        self._init_layout()
        self._sync_height()

    def _init_layout(self) -> None:
        """纵向排列按钮区、外部标签和类别骨架卡片。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        layout.addWidget(self.button_bar)
        layout.addSpacing(10)
        layout.addWidget(self.pri_mode_row)
        layout.addSpacing(10)
        layout.addWidget(self.result_count_label)
        layout.addSpacing(10)
        layout.addWidget(self.category_header)
        layout.addSpacing(5)
        layout.addWidget(self.category_display_card)

    def _init_pri_mode_row(self) -> None:
        """将 PRI 图像模式标签和下拉框排列在同一行。"""
        layout = QHBoxLayout(self.pri_mode_row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.pri_mode_label)
        layout.addStretch()
        layout.addWidget(self.pri_mode_combo)

    def _init_category_header(self) -> None:
        """将类别标题和全局三态复选框排列在同一行。"""
        layout = QHBoxLayout(self.category_header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.category_title_label)
        layout.addStretch()
        layout.addWidget(self.global_visibility_checkbox)

    def set_result_count(self, result_count: int | None) -> None:
        """更新当前切片的合并结果数量。

        Args:
            result_count [int | None]: 独立合并结果数量；``None`` 表示尚未完成合并。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 合并结果数量小于零时抛出。
        """
        if result_count is not None and result_count < 0:
            raise ValueError("合并结果数量不能为负数")
        count_text = "？" if result_count is None else str(result_count)
        self.result_count_label.setText(f"共获得 {count_text} 个合并结果")

    def set_categories(
        self,
        categories: Sequence[tuple[int, tuple[int, int, int]]],
        checked_indices: Iterable[int] | None = None,
    ) -> None:
        """显示当前结果来源类别并同步全局三态复选框。

        Args:
            categories [Sequence[tuple[int, tuple[int, int, int]]]]: 类簇编号与RGB颜色。
            checked_indices [Iterable[int] | None]: 当前可见的类簇编号。

        Returns:
            None: 无返回值。
        """
        self.category_display_card.set_categories(categories, checked_indices)
        self.sync_global_visibility_checkbox()

    def clear_categories(self) -> None:
        """清空来源类别并禁用全局三态复选框。

        Returns:
            None: 无返回值。
        """
        self.category_display_card.clear_categories()
        self.sync_global_visibility_checkbox()

    def sync_global_visibility_checkbox(self) -> None:
        """根据全部来源类别的当前状态同步全局复选框。"""
        checkboxes = tuple(self.category_display_card.category_checkboxes.values())
        checked_count = sum(checkbox.isChecked() for checkbox in checkboxes)
        if not checkboxes or checked_count == 0:
            check_state = Qt.CheckState.Unchecked
        elif checked_count == len(checkboxes):
            check_state = Qt.CheckState.Checked
        else:
            check_state = Qt.CheckState.PartiallyChecked

        # 汇总子项时阻断用户操作信号，避免状态回写再次批量切换子复选框。
        blocker = QSignalBlocker(self.global_visibility_checkbox)
        self.global_visibility_checkbox.setEnabled(bool(checkboxes))
        self.global_visibility_checkbox.setCheckState(check_state)
        del blocker

    def _on_global_visibility_clicked(self, checked: bool) -> None:
        """把用户点击转换为全部显示或全部隐藏。"""
        if not self.category_display_card.category_checkboxes:
            return
        self.category_display_card.set_all_visible(checked)
        self.sync_global_visibility_checkbox()
        self.global_visibility_changed.emit(checked)

    def _on_pri_mode_changed(self, mode_index: int) -> None:
        """把下拉框索引转换为是否重算完整合并序列的状态。"""
        self.pri_image_mode_changed.emit(mode_index == 1)

    def _sync_height(self) -> None:
        """根据动态类别控制卡片更新操作卡片高度。"""
        self.layout().activate()
        self.setFixedHeight(self.sizeHint().height())
