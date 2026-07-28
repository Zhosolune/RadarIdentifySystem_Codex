# -*- coding: utf-8 -*-
"""切片界面抽屉接入单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics, QImage
from PyQt6.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget
from pytest import MonkeyPatch
from qfluentwidgets import (
    CheckBox,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SimpleCardWidget,
    TableWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from infra.plotting.types import RenderedImageBundle
from ui.interfaces.slice_interface import SliceInterface
from ui.components.analysis_result_card import (
    AnalysisResultCard,
    AnalysisResultTableWidget,
    RoundedAnalysisHeaderView,
)
from ui.components.cluster_image_column import ClusterImageColumn
from ui.components.merge_action_button_bar import MergeActionButtonBar
from ui.components.merge_category_display_card import MergeCategoryDisplayCard
from ui.components.merge_image_column import MergeImageColumn
from ui.components.merge_operation_card import MergeOperationCard
from ui.components.merge_operation_panel import MergeOperationPanel
from ui.components.merge_result_table_card import MergeResultTableCard
from ui.components.original_image_column import OriginalImageColumn
from ui.components.slice_right_panel import SliceRightPanel


_APP: QApplication | None = None


def _app() -> QApplication:
    """获取或创建测试用 QApplication。

    Args:
        无。

    Returns:
        QApplication: 当前进程内可用的 Qt 应用实例。

    Raises:
        无显式抛出异常。

    Example:
        >>> _app() is not None
        True
    """
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_slice_param_panel_is_mounted_in_matching_drawer(
    monkeypatch: MonkeyPatch,
) -> None:
    """参数面板应挂载到与右栏同宽的独立抽屉中。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    assert hasattr(interface, "slice_param_panel")
    assert hasattr(interface, "slice_param_drawer")
    assert not hasattr(interface, "slice_param_config")
    assert interface.right_panel.maximumWidth() == interface.RIGHT_COLUMN_MAX_WIDTH
    assert interface.slice_param_drawer.drawerSize() == interface.RIGHT_COLUMN_MAX_WIDTH
    assert interface.slice_param_drawer.contentWidget() is interface.slice_param_panel
    assert not hasattr(
        interface.right_panel.navigation_control_card,
        "auto_recognize_card",
    )
    assert interface.slice_param_panel.export_path_card is not None
    # 控制器定时器与页面存在引用环，测试结束时显式释放 Qt 对象。
    sip.delete(interface)


def test_analysis_result_table_is_mounted_in_right_bottom_card(
    monkeypatch: MonkeyPatch,
) -> None:
    """分析结果表格应以卡片形式挂载到右侧面板底部。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        expected_labels = [
            "载频/MHz",
            "脉宽/us",
            "PRI/us",
            "DOA/°",
            "PA预测结果",
            "PA预测分类",
            "DTOA预测结果",
            "DTOA预测分类",
            "联合预测概率",
        ]

        card = interface.findChild(AnalysisResultCard, "analysisResultCard")
        table = interface.findChild(TableWidget, "analysisResultTable")

        assert card is interface.right_panel.analysis_result_card
        assert table is interface.right_panel.analysis_result_card.table
        assert interface.right_panel.layout().indexOf(
            card
        ) > interface.right_panel.layout().indexOf(
            interface.right_panel.operate_panel_card
        )
        assert (
            interface.right_panel.findChild(ScrollArea, "rightPanelScrollArea")
            is None
        )
        assert table.columnCount() == 2
        assert table.rowCount() == len(expected_labels)
        assert table.horizontalHeaderItem(0).text() == "雷达信号"
        assert table.horizontalHeaderItem(1).text() == "分析结果"
        assert [table.item(row, 0).text() for row in range(table.rowCount())] == expected_labels
        assert [table.item(row, 1).text() for row in range(table.rowCount())] == [""] * len(
            expected_labels
        )
        assert isinstance(table.horizontalHeader(), RoundedAnalysisHeaderView)
        assert table.horizontalHeader().corner_radius == 4
        assert all(
            table.item(row, column).font().pixelSize() == 14
            for row in range(table.rowCount())
            for column in range(table.columnCount())
        )
        assert table.verticalHeader().isHidden()
        assert "selection-background-color: transparent" in table.styleSheet()
        assert "QTableView#analysisResultTable" in table.styleSheet()
    finally:
        sip.delete(interface)


def test_header_title_length_does_not_change_image_column_width(
    monkeypatch: MonkeyPatch,
) -> None:
    """标题变长时图像展示列宽应保持稳定。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        interface.resize(1400, 900)
        interface.show()
        QApplication.processEvents()

        middle_column = interface.findChild(QWidget, "sliceMiddleColumn")
        assert middle_column is not None

        original_width = middle_column.width()

        interface.cluster_column.title_label.setText(
            "CF维聚类结果  第123/123类  总第123/123类  识别状态：未通过  "
            "这是一个非常长非常长非常长的标题，用于验证标题文本不会再撑开图像展示区域宽度"
        )
        QApplication.processEvents()

        assert middle_column.width() == original_width
        assert interface.cluster_column.title_label.minimumWidth() == 0
        assert (
            interface.cluster_column.title_label.sizePolicy().horizontalPolicy()
            == QSizePolicy.Policy.Ignored
        )

        interface.original_column.title_label.setText(
            "第 123 / 123 个切片数据  原始图像  这是一个非常长非常长非常长的标题，用于验证原始图像列宽稳定"
        )
        QApplication.processEvents()

        left_column = interface.findChild(QWidget, "sliceLeftColumn")
        assert left_column is not None
        assert left_column.width() > 0
    finally:
        sip.delete(interface)


def test_slice_interface_uses_session_scale_mode_for_image_updates(
    monkeypatch: MonkeyPatch,
) -> None:
    """切片界面重绘图像时应读取当前 session 的绘制模式。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    used_modes: list[str] = []

    def fake_apply_scale_mode(
        q_image: QImage,
        target_width: int,
        target_height: int,
        mode: str,
    ) -> QImage:
        """记录当前用于缩放的绘制模式。"""
        used_modes.append(mode)
        return q_image

    monkeypatch.setattr(
        "ui.adapters.image_scaler.apply_scale_mode",
        fake_apply_scale_mode,
    )

    interface = SliceInterface()
    try:
        interface.show()
        QApplication.processEvents()
        test_image = QImage(16, 16, QImage.Format.Format_RGB32)

        interface.original_column.cf_card.set_image(test_image)
        assert used_modes[-1] == "STRETCH"

        interface.right_panel.plot_option_card.scale_mode_item.set(
            "STRETCH_BILINEAR"
        )
        QApplication.processEvents()
        assert used_modes[-1] == "STRETCH_BILINEAR"
    finally:
        sip.delete(interface)


def test_right_panel_keeps_controls_fixed_and_hides_table_scrollbar_when_height_is_limited(
    monkeypatch: MonkeyPatch,
) -> None:
    """右栏高度不足时应压缩结果表并保持表格滚动条隐藏。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        interface.resize(1400, 900)
        interface.show()
        QApplication.processEvents()

        panel = interface.right_panel
        table = panel.analysis_result_card.table
        tall_operate_geometry = panel.operate_panel_card.geometry()
        tall_table_height = table.height()
        assert table.verticalScrollBar().maximum() == 0

        interface.resize(1400, 560)
        QApplication.processEvents()

        assert panel.operate_panel_card.geometry() == tall_operate_geometry
        assert table.height() < tall_table_height
        assert table.verticalScrollBar().maximum() > 0
        assert table.scrollDelagate.vScrollBar._isForceHidden
        assert not table.scrollDelagate.vScrollBar.isVisible()
    finally:
        sip.delete(interface)


def test_slice_dimension_cards_have_explicit_snapshot_titles(
    monkeypatch: MonkeyPatch,
) -> None:
    """页面应为全部维度卡片提供明确的快照窗口标题。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        assert interface.original_column.cf_card._snapshot_window_title == "原始图像 - 载频"
        assert interface.original_column.pw_card._snapshot_window_title == "原始图像 - 脉宽"
        assert interface.original_column.pa_card._snapshot_window_title == "原始图像 - 幅度"
        assert interface.original_column.dtoa_card._snapshot_window_title == "原始图像 - 一级差"
        assert interface.original_column.doa_card._snapshot_window_title == "原始图像 - 方位角"
        assert interface.cluster_column.cf_card._snapshot_window_title == "聚类结果 - 载频"
        assert interface.cluster_column.pw_card._snapshot_window_title == "聚类结果 - 脉宽"
        assert interface.cluster_column.pa_card._snapshot_window_title == "聚类结果 - 幅度"
        assert interface.cluster_column.dtoa_card._snapshot_window_title == "聚类结果 - 一级差"
        assert interface.cluster_column.doa_card._snapshot_window_title == "聚类结果 - 方位角"
    finally:
        sip.delete(interface)


def test_merge_workspace_has_four_equal_panels_and_starts_locked_at_ab(
    monkeypatch: MonkeyPatch,
) -> None:
    """横向工作区应等宽承载 A/B/C/D，并在初始状态锁定 A+B。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        interface.resize(1500, 900)
        interface.show()
        QApplication.processEvents()

        assert isinstance(interface.original_column, OriginalImageColumn)
        assert isinstance(interface.cluster_column, ClusterImageColumn)
        assert isinstance(interface.merge_image_column, MergeImageColumn)
        assert isinstance(interface.merge_operation_panel, MergeOperationPanel)
        assert isinstance(interface.right_panel, SliceRightPanel)
        assert interface.image_workspace.panels == (
            interface.original_column,
            interface.cluster_column,
            interface.merge_image_column,
            interface.merge_operation_panel,
        )
        assert all(
            panel.parent() is interface.image_workspace.content_widget
            for panel in interface.image_workspace.panels
        )
        assert all(
            not panel.isHidden()
            for panel in interface.image_workspace.panels
        )
        assert not interface.right_panel.isHidden()
        assert not hasattr(interface, "original_cf_card")
        assert not hasattr(interface, "cluster_cf_card")
        assert not hasattr(interface, "navigation_control_card")
        assert not hasattr(interface, "right_column")

        panel_widths = {
            panel.width()
            for panel in interface.image_workspace.panels
        }
        assert panel_widths == {interface.image_workspace.panel_width()}
        assert (
            interface.image_workspace.panel_width() * 2
            + interface.image_workspace.COLUMN_SPACING
            <= interface.image_workspace.viewport().width()
        )
        assert interface.image_workspace.is_locked()
        assert not interface.image_workspace.is_merge_active()
        assert interface.image_workspace.current_pair_index() == 0
        assert interface.image_workspace.delegate.hScrollBar.value() == 0

        assert [
            card.objectName()
            for card in interface.merge_image_column.dimension_cards
        ] == [
            "mergeCfCard",
            "mergePwCard",
            "mergePaCard",
            "mergeDtoaCard",
            "mergeDoaCard",
        ]
        assert all(
            card._source_image is None
            for card in interface.merge_image_column.dimension_cards
        )
        merge_panel = interface.merge_operation_panel
        right_panel = interface.right_panel
        assert not isinstance(merge_panel, SimpleCardWidget)
        assert not merge_panel.autoFillBackground()
        assert merge_panel.title_label.text() == "合并操作面板"
        assert merge_panel.title_label.objectName() == "sliceMiddleTitle"
        assert (
            merge_panel.title_label.minimumHeight()
            == merge_panel.title_label.maximumHeight()
            == right_panel.slice_info_label.height()
            == 25
        )
        operation_card = merge_panel.operation_card
        assert isinstance(operation_card, MergeOperationCard)
        assert isinstance(operation_card, SimpleCardWidget)
        assert isinstance(
            merge_panel.result_table_card,
            MergeResultTableCard,
        )
        assert isinstance(operation_card.button_bar, MergeActionButtonBar)
        assert isinstance(operation_card.button_bar.merge_button, PrimaryPushButton)
        assert all(
            isinstance(button, PushButton)
            and not isinstance(button, PrimaryPushButton)
            for button in (
                operation_card.button_bar.prev_cluster_button,
                operation_card.button_bar.next_cluster_button,
                operation_card.button_bar.reset_button,
            )
        )
        assert [
            operation_card.button_bar.layout().itemAt(index).widget().text()
            for index in range(4)
        ] == ["合并", "上一类", "下一类", "重置"]
        assert operation_card.layout().indexOf(operation_card.button_bar) == 0
        assert operation_card.result_count_label.text() == "共获得？个合并结果"
        assert operation_card.result_count_label.objectName() == "sliceInfoLabel"
        assert operation_card.result_count_label.height() == 25
        assert operation_card.layout().indexOf(
            operation_card.result_count_label
        ) == 2
        assert operation_card.category_title_label.text() == "类别显示控制"
        assert operation_card.category_title_label.font().pixelSize() == 16
        assert operation_card.category_title_label.alignment() == (
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        assert operation_card.layout().indexOf(operation_card.category_header) == 4
        assert isinstance(operation_card.global_visibility_checkbox, CheckBox)
        assert operation_card.global_visibility_checkbox.isTristate()
        assert not operation_card.global_visibility_checkbox.isEnabled()
        assert (
            operation_card.global_visibility_checkbox.checkState()
            is Qt.CheckState.Unchecked
        )
        assert isinstance(
            operation_card.category_display_card,
            MergeCategoryDisplayCard,
        )
        assert operation_card.layout().indexOf(operation_card.category_display_card) == 6
        assert operation_card.button_bar.parent() is operation_card
        assert operation_card.result_count_label.parent() is operation_card
        assert operation_card.category_title_label.parent() is operation_card.category_header
        assert (
            operation_card.global_visibility_checkbox.parent()
            is operation_card.category_header
        )
        assert operation_card.category_display_card.parent() is operation_card
        category_skeleton = operation_card.category_display_card.skeleton
        assert category_skeleton.parent() is operation_card.category_display_card
        assert operation_card.category_display_card.layout().indexOf(
            category_skeleton
        ) == 0
        assert not hasattr(operation_card, "category_skeleton")
        assert not hasattr(merge_panel, "category_skeleton")
        skeleton_bars = category_skeleton.skeleton_bars
        assert len(skeleton_bars) == 3
        assert len({bar.width() for bar in skeleton_bars}) == 1
        assert skeleton_bars[0].width() == category_skeleton.width() // 2
        assert len({bar.x() for bar in skeleton_bars}) == 1
        assert all(
            bar.objectName() == "mergeCategorySkeletonBar"
            for bar in skeleton_bars
        )

        merge_table = merge_panel.result_table_card.table
        right_table = right_panel.analysis_result_card.table
        assert isinstance(merge_table, AnalysisResultTableWidget)
        assert merge_table.objectName() == "mergeResultTable"
        assert merge_table.columnCount() == 2
        assert merge_table.rowCount() + 1 == 5
        assert [
            merge_table.horizontalHeaderItem(column).text()
            for column in range(merge_table.columnCount())
        ] == ["类别", "合并结果"]
        assert isinstance(merge_table.horizontalHeader(), RoundedAnalysisHeaderView)
        assert (
            merge_table.horizontalHeader().corner_radius
            == right_table.horizontalHeader().corner_radius
            == 4
        )
        # 两张表共用组件库基础样式；右侧表格额外继承切片页整体 QSS。
        assert right_table.styleSheet().startswith(merge_table.styleSheet().rstrip())
        assert merge_table.showGrid() == right_table.showGrid()
        assert merge_table.verticalHeader().isHidden()
        assert all(
            merge_table.item(row, column).text() == ""
            and merge_table.item(row, column).font().pixelSize() == 14
            for row in range(merge_table.rowCount())
            for column in range(merge_table.columnCount())
        )
        assert merge_panel.layout().contentsMargins().isNull()
        assert merge_panel.layout().spacing() == 10
        assert merge_panel.layout().spacing() == right_panel.layout().spacing()
        assert merge_panel.layout().indexOf(merge_panel.title_label) == 0
        assert merge_panel.layout().indexOf(operation_card) == 1
        assert merge_panel.layout().indexOf(merge_panel.result_table_card) == 2
    finally:
        sip.delete(interface)


def test_merge_result_table_pri_row_grows_with_multiline_content() -> None:
    """合并结果PRI行应按实际窄列宽度分行并完整容纳文本。"""
    _app()
    card = MergeResultTableCard()

    try:
        card.resize(404, card.height())
        card.show()
        QApplication.processEvents()
        base_height = card.height()
        base_pri_height = card.table.rowHeight(2)
        card.update_rows(
            (
                ("CF", "100"),
                ("PW", "1"),
                (
                    "PRI",
                    "1234.6、2234.6、3234.6、4234.6、5234.6、6234.6、"
                    "7234.6、8234.6",
                ),
                ("DOA", "30"),
            )
        )
        QApplication.processEvents()

        pri_row = 2
        pri_item = card.table.item(pri_row, 1)
        pri_lines = pri_item.text().splitlines()
        font_metrics = QFontMetrics(pri_item.font())
        available_width = (
            card.table.columnWidth(1) - card.CELL_HORIZONTAL_PADDING
        )
        assert card.ROW_HEIGHT == AnalysisResultCard.DEFAULT_ROW_HEIGHT
        assert (
            card.ROW_VERTICAL_PADDING
            == AnalysisResultCard.ROW_VERTICAL_PADDING
        )
        assert len(pri_lines) >= 3
        assert all(
            font_metrics.horizontalAdvance(line) <= available_width
            for line in pri_lines
        )
        assert all(
            len(line.split("、")) <= card.PRI_MAX_VALUES_PER_LINE
            for line in pri_lines
        )
        assert card.table.rowHeight(pri_row) > card.ROW_HEIGHT
        assert card.table.rowHeight(pri_row) >= (
            len(pri_lines) * font_metrics.lineSpacing()
            + card.ROW_VERTICAL_PADDING
        )
        assert card.height() > base_height

        narrow_line_count = len(pri_lines)
        narrow_row_height = card.table.rowHeight(pri_row)
        card.resize(620, card.height())
        QApplication.processEvents()
        wide_lines = card.table.item(pri_row, 1).text().splitlines()
        assert len(wide_lines) < narrow_line_count
        assert card.table.rowHeight(pri_row) < narrow_row_height

        card.clear_rows()
        assert card.table.rowHeight(pri_row) == base_pri_height
        assert card.height() == base_height
    finally:
        sip.delete(card)


def test_merge_menu_unlocks_workspace_and_moves_between_ab_and_cd(
    monkeypatch: MonkeyPatch,
) -> None:
    """合并菜单应解锁并定位 C+D，退出后返回并锁定 A+B。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        interface.resize(1500, 900)
        interface.show()
        QApplication.processEvents()

        right_parent = interface.right_panel.parent()
        right_layout_index = interface.layout().indexOf(interface.right_panel)
        workspace = interface.image_workspace
        workspace.setScrollAnimation(Qt.Orientation.Horizontal, 0)
        merge_button = (
            interface.right_panel.navigation_control_card.merge_menu_button
        )

        assert merge_button.text() == "合并菜单"
        # 空session下业务控制器会禁用菜单；本测试仅验证工作区切换行为。
        assert not merge_button.isEnabled()
        merge_button.setEnabled(True)
        merge_button.click()
        QApplication.processEvents()
        assert merge_button.isChecked()
        assert workspace.is_merge_active()
        assert not workspace.is_locked()
        assert workspace.current_pair_index() == 2
        assert workspace.delegate.hScrollBar.value() == workspace.delegate.hScrollBar.maximum()

        # 解锁后用户可以移动到中间的 B+C 完整双列位置。
        workspace.scroll_to_pair(1, animated=False)
        assert workspace.current_pair_index() == 1
        assert workspace.delegate.hScrollBar.value() == (
            workspace.panel_width() + workspace.COLUMN_SPACING
        )

        merge_button.click()
        QApplication.processEvents()
        assert not merge_button.isChecked()
        assert not workspace.is_merge_active()
        assert workspace.is_locked()
        assert workspace.current_pair_index() == 0
        assert workspace.delegate.hScrollBar.value() == 0
        assert all(not panel.isHidden() for panel in workspace.panels)

        # 原有右侧面板的父级、布局位置和显示状态均未改变。
        assert interface.right_panel.parent() is right_parent
        assert interface.layout().indexOf(interface.right_panel) == right_layout_index
        assert not interface.right_panel.isHidden()
    finally:
        sip.delete(interface)


def test_original_snapshot_titles_include_current_slice_number(
    monkeypatch: MonkeyPatch,
) -> None:
    """切片控制器刷新原始图像时应同步其 1-based 切片编号。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        interface._slice_controller._update_ui_with_bundle(
            RenderedImageBundle(images={}),
            slice_index=6,
        )

        assert (
            interface.original_column.cf_card._snapshot_window_title
            == "第 7 个切片 - 原始图像 - 载频"
        )
        assert (
            interface.original_column.doa_card._snapshot_window_title
            == "第 7 个切片 - 原始图像 - 方位角"
        )
        assert (
            interface.cluster_column.cf_card._snapshot_window_title
            == "聚类结果 - 载频"
        )
    finally:
        sip.delete(interface)


if __name__ == "__main__":
    tests = [
        test_slice_param_panel_is_mounted_in_matching_drawer,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
