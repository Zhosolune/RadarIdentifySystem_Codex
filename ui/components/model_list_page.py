"""模型列表页面组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel


class ModelListPage(QWidget):
    """模型列表页面组件。

    负责承载单一模型类型的滚动列表区域，并提供统一的空状态与卡片挂载方法。

    Attributes:
        model_type (str): 页面对应的模型类型。
        scroll_area (QScrollArea): 列表滚动区域。
        list_widget (QWidget): 列表内容容器。
        list_layout (QVBoxLayout): 列表布局。
    """

    def __init__(self, model_type: str, parent: QWidget | None = None) -> None:
        """初始化模型列表页面。

        Args:
            model_type (str): 页面对应的模型类型，支持 ``PA`` 或 ``DTOA``。
            parent (QWidget | None): 父组件。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 模型类型为空时抛出异常。
        """
        super().__init__(parent)
        if not model_type:
            raise ValueError("model_type 不能为空")

        self.model_type = model_type
        self.scroll_area = QScrollArea(self)
        self.list_widget = QWidget(self.scroll_area)
        self.list_layout = QVBoxLayout(self.list_widget)
        self.main_layout = QVBoxLayout(self)

        # 绑定页面路由名称
        self.setObjectName(f"{model_type.lower()}ModelListPage")
        # 绑定滚动区域对象名
        self.scroll_area.setObjectName("modelListScrollArea")
        # 绑定滚动视口对象名
        self.scroll_area.viewport().setObjectName("modelListViewport")
        # 绑定列表容器对象名
        self.list_widget.setObjectName("modelListWidget")

        self._init_widget()

    def _init_widget(self) -> None:
        """初始化页面结构。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 配置根布局
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 配置滚动区域
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 配置列表布局
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)

        # 装配滚动列表
        self.scroll_area.setWidget(self.list_widget)
        self.main_layout.addWidget(self.scroll_area, 1)

    def clear_items(self) -> None:
        """清空列表中的所有内容项。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # 销毁旧列表项
                widget.deleteLater()

    def add_item(self, widget: QWidget) -> None:
        """添加列表项组件。

        Args:
            widget (QWidget): 待添加的列表项组件。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 传入组件为空时抛出异常。
        """
        if widget is None:
            raise ValueError("widget 不能为空")

        # 挂载列表项组件
        self.list_layout.addWidget(widget)

    def show_empty_state(self, text: str) -> None:
        """显示空状态提示。

        Args:
            text (str): 空状态提示文本。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        empty_label = BodyLabel(text, self.list_widget)
        # 绑定空状态标签对象名
        empty_label.setObjectName("modelEmptyLabel")
        # 设置顶部留白
        empty_label.setContentsMargins(0, 40, 0, 0)
        # 居中空状态文本
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.list_layout.addWidget(empty_label)

    def add_bottom_stretch(self) -> None:
        """添加底部弹性空间。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 压紧列表到顶部
        self.list_layout.addStretch(1)
