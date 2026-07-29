"""主页数据池面板。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, FluentIcon, PushButton, SimpleCardWidget, setFont

from core.models.data_package import DataPackage
from ui.components.card_navigation_list import CardNavigationList


class DataPoolPanel(SimpleCardWidget):
    """展示已解析数据包并提供创建 Session 的入口。

    Attributes:
        createSessionRequested: 携带选中 ``package_id`` 的创建请求信号。
        deletePackageRequested: 携带选中 ``package_id`` 的删除请求信号。
        package_list: 数据包卡片列表。
    """

    createSessionRequested = pyqtSignal(str)
    deletePackageRequested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化数据池面板。

        Args:
            parent [QWidget | None]: 父组件。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.setObjectName("homeDataPoolPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 8, 8, 7)
        title_label = BodyLabel("数据池", self)
        title_label.setFixedHeight(34)
        setFont(title_label, 14)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        root_layout.addLayout(header_layout)

        separator = QWidget(self)
        separator.setObjectName("homePanelSeparator")
        separator.setFixedHeight(1)
        separator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root_layout.addWidget(separator)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(8)

        self.empty_label = BodyLabel("解析完成的数据包会显示在这里", body)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_layout.addWidget(self.empty_label, 1)

        self.package_list = CardNavigationList(body)
        self.package_list.setVisible(False)
        body_layout.addWidget(self.package_list, 1)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        self.create_button = PushButton(FluentIcon.ADD, "创建 Session", body)
        self.delete_button = PushButton(FluentIcon.DELETE, "删除数据包", body)
        self.create_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        action_layout.addWidget(self.create_button)
        action_layout.addWidget(self.delete_button)
        body_layout.addLayout(action_layout)
        root_layout.addWidget(body, 1)

        self.package_list.itemSelected.connect(self._on_selected)
        self.create_button.clicked.connect(self._emit_create_request)
        self.delete_button.clicked.connect(self._emit_delete_request)

    def set_packages(
        self,
        packages: list[DataPackage],
        *,
        selected_package_id: str | None = None,
    ) -> None:
        """刷新数据包列表。

        Args:
            packages [list[DataPackage]]: 按展示顺序排列的数据包。
            selected_package_id [str | None]: 刷新后优先选中的数据包 ID。

        Returns:
            None: 无返回值。
        """
        self.package_list.clear_items()
        for package in packages:
            subtitle = (
                f"ID {package.package_id[:8]} · "
                f"{package.band or '未知波段'} · "
                f"{package.pulse_count} 条有效脉冲"
            )
            self.package_list.add_item(
                package.package_id,
                package.display_name,
                subtitle,
                FluentIcon.DOCUMENT,
            )

        has_packages = bool(packages)
        self.empty_label.setVisible(not has_packages)
        self.package_list.setVisible(has_packages)
        if not has_packages:
            self._on_selected("")
            return

        available_ids = {package.package_id for package in packages}
        target_id = (
            selected_package_id
            if selected_package_id in available_ids
            else packages[0].package_id
        )
        self.package_list.set_current_key(target_id)
        self._on_selected(target_id)

    def current_package_id(self) -> str | None:
        """返回当前选中的数据包 ID。

        Returns:
            str | None: 当前数据包 ID；没有选择时返回 None。
        """
        return self.package_list.current_key()

    def _on_selected(self, package_id: str) -> None:
        """按选择状态同步操作按钮。"""
        enabled = bool(package_id)
        self.create_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def _emit_create_request(self) -> None:
        """发出当前数据包的创建 Session 请求。"""
        package_id = self.current_package_id()
        if package_id:
            self.createSessionRequested.emit(package_id)

    def _emit_delete_request(self) -> None:
        """发出当前数据包的删除请求。"""
        package_id = self.current_package_id()
        if package_id:
            self.deletePackageRequested.emit(package_id)
