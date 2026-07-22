"""合并操作面板的水平按钮区组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import PrimaryPushButton, PushButton


class MergeActionButtonBar(QWidget):
    """水平承载合并及类别导航按钮。

    本组件只负责按钮创建和排版，不绑定合并业务，后续由控制器统一连接信号。

    Attributes:
        merge_button [PrimaryPushButton]: 触发合并操作的主题色按钮。
        prev_cluster_button [PushButton]: 切换至上一类别的普通按钮。
        next_cluster_button [PushButton]: 切换至下一类别的普通按钮。
        reset_button [PushButton]: 重置当前合并选择的普通按钮。

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> app = QApplication.instance() or QApplication([])
        >>> bar = MergeActionButtonBar()
        >>> bar.merge_button.text()
        '合并'
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化四个操作按钮及水平布局。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self.setObjectName("mergeActionButtonBar")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.merge_button: PrimaryPushButton = PrimaryPushButton("合并", self)
        self.prev_cluster_button: PushButton = PushButton("上一类", self)
        self.next_cluster_button: PushButton = PushButton("下一类", self)
        self.reset_button: PushButton = PushButton("重置", self)

        self._init_layout()

    def _init_layout(self) -> None:
        """按固定业务顺序等宽排列四个按钮。"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 添加按钮
        for button in (
            self.merge_button,
            self.prev_cluster_button,
            self.next_cluster_button,
            self.reset_button,
        ):
            button.setFixedWidth(80)
            layout.addWidget(button)
        # 添加弹性空间
        layout.addStretch()
