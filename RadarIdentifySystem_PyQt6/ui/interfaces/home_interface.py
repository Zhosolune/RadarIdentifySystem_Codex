"""主页界面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget
from qfluentwidgets import StrongBodyLabel


class HomeInterface(QFrame):
    """主页界面（非滚动、两栏布局）。

    功能描述：
        提供一个固定两栏的主页骨架区域，不启用滚动，供后续业务组件填充。

    参数说明：
        parent (QWidget | None): 父级控件，默认值为 None。

    返回值说明：
        无。

    异常说明：
        无。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化主页界面。

        功能描述：
            创建左右两栏容器并设置基础布局约束，默认内容保持空白。

        参数说明：
            parent (QWidget | None): 父级控件，默认值为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        super().__init__(parent)
        self.setObjectName("homeInterface")
        self._init_layout()

    def _init_layout(self) -> None:
        """初始化两栏布局。

        功能描述：
            在主区域中创建左、右两个等宽栏位，并预留空白内容区。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        self.left_column = self._create_empty_column("leftColumn")
        self.right_column = self._create_empty_column("rightColumn")

        root_layout.addWidget(self.left_column, 1)
        root_layout.addWidget(self.right_column, 1)

    def _create_empty_column(self, object_name: str) -> QFrame:
        """创建空白栏位容器。

        功能描述：
            构建一个带圆角边框的占位栏位，内部仅保留空白区。

        参数说明：
            object_name (str): 栏位对象名。

        返回值说明：
            QFrame: 栏位容器对象。

        异常说明：
            无。
        """

        column = QFrame(self)
        column.setObjectName(object_name)
        column.setFrameShape(QFrame.Shape.StyledPanel)
        column.setStyleSheet(
            f"""
            QFrame#{object_name} {{
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 10px;
                background-color: transparent;
            }}
            """
        )

        column_layout = QHBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(0)
        placeholder = StrongBodyLabel("", column)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column_layout.addWidget(placeholder)
        return column
