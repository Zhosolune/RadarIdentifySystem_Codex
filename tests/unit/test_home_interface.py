"""主页布局测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
from PyQt6.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget
from qfluentwidgets import Flyout, FlyoutAnimationType

from core.models.dashboard_info import ExcelDashboardInfo
from core.models.data_package import DataPackage
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
from ui.components.card_navigation_list import CardNavigationItem
from ui.components.data_pool_panel import DataPackageDetailFlyoutView, DataPoolPanel
from ui.interfaces.home_interface import HomeInterface
from ui.components.import_data_panel import ImportDataPanel


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _build_data_package(
    package_id: str,
    source_type: str,
) -> DataPackage:
    """构造用于主页数据池布局测试的数据包。"""
    data = np.array(
        [
            [5000.0, 1.0, 90.0, 10.0, 11.0, 0.0],
            [5001.0, 1.2, 91.0, 12.0, 13.0, 100.0],
        ]
    )
    dashboard = ExcelDashboardInfo(
        total_pulses=2,
        removed_pulses=0,
        amplitude_dropped_pulses=0,
        duration=100.0,
        band="C波段",
        estimated_slice_count=1,
    )
    return DataPackage(
        package_id=package_id,
        display_name=f"{source_type}-{package_id}",
        source_path=f"E:/data/{package_id}.{source_type}",
        source_type=source_type,
        data_format="new" if source_type == "excel" else None,
        raw_batch=PulseBatch(
            data.copy(),
            source_path=f"E:/data/{package_id}.{source_type}",
            source_type=source_type,
            total_pulses=2,
        ),
        preprocess_result=PreprocessResult(
            data.copy(),
            total_pulses=2,
            time_range=100.0,
            estimated_slice_count=1,
            band="C波段",
            dashboard_info=dashboard,
        ),
        dashboard_info=dashboard,
    )


def test_home_interface_hosts_data_pool_and_two_peer_session_panels() -> None:
    """主页左侧应落地数据池，右侧应展示两类同级 Session 面板。"""
    _app()
    interface = HomeInterface()

    left_layout = interface.left_column.layout()
    right_layout = interface.right_column.layout()

    assert interface.findChild(QWidget, "homeLeftScrollArea") is not None
    assert left_layout.count() == 1
    assert interface.data_pool_panel.minimumHeight() == 350
    assert interface.data_pool_panel.maximumHeight() == 350
    assert interface.import_panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert right_layout.count() == 2
    assert right_layout.stretch(0) == 1
    assert right_layout.stretch(1) == 1
    assert (
        interface.full_speed_session_panel.objectName()
        == "homeFullSpeedSessionPanel"
    )


def test_import_data_panel_reports_selected_excel_format() -> None:
    """导入菜单的新旧格式单选状态应转换为稳定格式键。"""
    _app()
    panel = ImportDataPanel()

    assert panel.current_excel_data_format() == "old"

    panel.newFormatAction.setChecked(True)

    assert panel.current_excel_data_format() == "new"
    assert panel.oldFormatAction.isChecked() is False


def test_data_pool_responsively_uses_two_to_four_equal_card_columns() -> None:
    """数据池应按类型分组，并随可用宽度在两至四列之间切换。"""
    app = _app()
    panel = DataPoolPanel()
    packages = [
        _build_data_package(f"excel-{index}", "excel")
        for index in range(4)
    ]
    packages.extend(
        [
            _build_data_package("bin-1", "bin"),
            _build_data_package("mat-1", "mat"),
        ]
    )

    panel.resize(500, 300)
    panel.set_packages(packages)
    panel.show()
    app.processEvents()

    assert panel.tab_widget.count() == 4
    assert len(panel.package_pages["excel"].cards) == 4
    assert len(panel.package_pages["bin"].cards) == 1
    assert len(panel.package_pages["mat"].cards) == 1
    excel_page = panel.package_pages["excel"]
    excel_layout = panel.package_pages["excel"].grid_layout
    assert excel_page.column_count() == 2
    assert [
        excel_layout.getItemPosition(index)[:2]
        for index in range(4)
    ] == [(0, 0), (0, 1), (1, 0), (1, 1)]

    first_row_cards = list(panel.package_pages["excel"].cards.values())[:2]
    assert max(card.width() for card in first_row_cards) - min(
        card.width() for card in first_row_cards
    ) <= 1
    assert first_row_cards[1].geometry().right() < (
        panel.package_pages["excel"].content_widget.width()
    )
    first_card = first_row_cards[0]
    assert isinstance(first_card, CardNavigationItem)
    assert first_card.title_label.text() == packages[0].display_name
    assert first_card.subtitle_label is not None
    assert first_card.subtitle_label.text() == "C波段"
    visible_text = " ".join(
        label.text()
        for label in first_card.findChildren(QLabel)
    )
    assert "ID " not in visible_text
    assert "有效脉冲" not in visible_text

    panel.resize(800, 300)
    app.processEvents()
    assert excel_page.column_count() == 3
    assert [
        excel_layout.getItemPosition(index)[:2]
        for index in range(4)
    ] == [(0, 0), (0, 1), (0, 2), (1, 0)]

    panel.resize(1050, 300)
    app.processEvents()
    assert excel_page.column_count() == 4
    assert [
        excel_layout.getItemPosition(index)[:2]
        for index in range(4)
    ] == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert panel.current_package_id() == packages[0].package_id


def test_home_interface_responsively_expands_data_pool_height() -> None:
    """主页高度充足时数据池面板应依次扩展到 400 和 500px。"""
    app = _app()
    interface = HomeInterface()
    interface.show()

    interface.resize(
        1200,
        interface._MEDIUM_HEIGHT_BREAKPOINT - 50,
    )
    app.processEvents()
    assert interface.data_pool_panel.height() == 350

    interface.resize(
        1200,
        interface._MEDIUM_HEIGHT_BREAKPOINT + 50,
    )
    app.processEvents()
    assert interface.data_pool_panel.height() == 400

    interface.resize(
        1200,
        interface._LARGE_HEIGHT_BREAKPOINT + 50,
    )
    app.processEvents()
    assert interface.data_pool_panel.height() == 500


def test_data_pool_details_uses_upward_panel_width_flyout() -> None:
    """详情按钮应选中来源卡片并使用与数据池等宽的向上 Flyout。"""
    _app()
    panel = DataPoolPanel()
    first_package = _build_data_package("excel-first", "excel")
    package = _build_data_package("excel-detail", "excel")
    panel.resize(720, 300)
    panel.set_packages([first_package, package])
    fake_flyout = MagicMock()
    first_card = panel.package_pages["excel"].cards[
        first_package.package_id
    ]
    detail_card = panel.package_pages["excel"].cards[
        package.package_id
    ]
    assert first_card.is_selected()
    assert not detail_card.is_selected()

    with patch.object(Flyout, "make", return_value=fake_flyout) as make:
        detail_card.details_button.click()

    view, target, _parent = make.call_args.args
    assert panel.current_package_id() == package.package_id
    assert detail_card.is_selected()
    assert not first_card.is_selected()
    assert isinstance(view, DataPackageDetailFlyoutView)
    assert view.width() + 30 == panel.width()
    assert len(view.metric_cards) == 6
    assert target.objectName() == "dataPoolDetailsButton"
    assert make.call_args.kwargs["aniType"] is FlyoutAnimationType.PULL_UP
    assert view.close_button.objectName() == "dataPoolDetailCloseButton"
    view.close_button.click()
    fake_flyout.close.assert_called_once_with()
