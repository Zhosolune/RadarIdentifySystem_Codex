# -*- coding: utf-8 -*-
"""单个数据格式标签页的内容区组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLabel, QSizePolicy

from qfluentwidgets import ScrollArea, CaptionLabel, BodyLabel

from ui.components.file_item import FileItem


class FileListPage(QWidget):
    """单个数据格式标签页的内容区。

    包含：列标题行 + 可滚动文件列表 + 空状态占位符。
    文件数据通过 set_files() 注入。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Args:
            parent: 父级控件，默认为 None。
        """
        super().__init__(parent)
        self.setObjectName("fileListPage")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 列标题行 ──────────────────────────────────────────────────
        header = QWidget(self)
        header.setObjectName("fileListHeader")
        header.setFixedHeight(32)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(8)

        lbl_name = CaptionLabel("文件名", header)
        lbl_name.setObjectName("fileListHeaderLabel")
        lbl_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        lbl_date = CaptionLabel("修改日期", header)
        lbl_date.setObjectName("fileListHeaderLabel")
        lbl_date.setFixedWidth(130)
        lbl_date.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        lbl_size = CaptionLabel("大小", header)
        lbl_size.setObjectName("fileListHeaderLabel")
        lbl_size.setFixedWidth(72)
        lbl_size.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header_layout.addWidget(lbl_name, 3)
        header_layout.addWidget(lbl_date, 2)
        header_layout.addWidget(lbl_size, 0)

        root_layout.addWidget(header)

        # ── 可滚动列表区 ──────────────────────────────────────────────
        self._scroll = ScrollArea(self)
        self._scroll.setObjectName("fileListScrollArea")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.enableTransparentBackground()

        self._list_container = QWidget()
        self._list_container.setObjectName("fileListContainer")

        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 4, 0, 4)
        self._list_layout.setSpacing(0)
        # 末尾弹性空间，防止条目被拉伸
        self._list_layout.addStretch(1)

        self._scroll.setWidget(self._list_container)
        root_layout.addWidget(self._scroll, 1)

        # ── 空状态占位 ────────────────────────────────────────────────
        self._empty_widget = QWidget(self)
        self._empty_widget.setObjectName("fileListEmpty")

        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_icon = QLabel("📂", self._empty_widget)
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 32px;")

        empty_text = BodyLabel("暂无文件，请点击「添加文件」导入数据", self._empty_widget)
        empty_text.setObjectName("fileListEmptyText")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_layout.addWidget(empty_icon)
        empty_layout.addSpacing(8)
        empty_layout.addWidget(empty_text)

        root_layout.addWidget(self._empty_widget)

        # 初始显示空状态，隐藏列表
        self._scroll.hide()
        self._empty_widget.show()

    def set_files(self, files: list[tuple[str, str, str]]) -> None:
        """设置文件列表数据。

        清空原有数据并重新填充。

        Args:
            files: 包含文件信息的元组列表，每项为 (文件名, 修改日期, 大小)。

        Returns:
            None: 无返回值。
        """
        # 移除旧组件
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not files:
            self._scroll.hide()
            self._empty_widget.show()
            return

        self._empty_widget.hide()
        self._scroll.show()

        for name, date, size in files:
            row = FileItem(name, date, size, self._list_container)
            # 在 stretch 之前插入
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
