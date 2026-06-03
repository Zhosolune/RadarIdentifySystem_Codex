# -*- coding: utf-8 -*-
"""文件列表中的单个文件行组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QWidget, QSizePolicy

from qfluentwidgets import CaptionLabel, BodyLabel


class FileItem(QWidget):
    """文件列表中的单个文件行。

    展示一个文件的名称、修改日期、大小三列信息。
    """

    def __init__(
        self,
        file_name: str,
        mod_time: str = "—",
        file_size: str = "—",
        parent: QWidget | None = None,
    ) -> None:
        """
        Args:
            file_name: 显示在第一列的文件名。
            mod_time: 修改日期文本，默认 "—"。
            file_size: 文件大小文本，默认 "—"。
            parent: 父级控件，默认为 None。
        """
        super().__init__(parent)
        self.setObjectName("fileItem")
        self._is_selected: bool = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # 实例化组件
        self._name_label = BodyLabel(file_name, self)
        self._name_label.setObjectName("fileItemName")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._date_label = CaptionLabel(mod_time, self)
        self._date_label.setObjectName("fileItemDate")
        self._date_label.setFixedWidth(130)
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._size_label = CaptionLabel(file_size, self)
        self._size_label.setObjectName("fileItemSize")
        self._size_label.setFixedWidth(72)
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._name_label, 3)
        layout.addWidget(self._date_label, 2)
        layout.addWidget(self._size_label, 0)

        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setSelected(self, selected: bool) -> None:
        """设置选中状态并刷新 QSS。

        Args:
            selected: True 选中，False 取消选中。

        Returns:
            None: 无返回值。
        """
        self._is_selected = selected
        self.setProperty("isSelected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def isSelected(self) -> bool:
        """返回当前选中状态。

        Returns:
            bool: 当前选中状态。
        """
        return self._is_selected
