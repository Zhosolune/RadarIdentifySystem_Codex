"""合并操作面板组件。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import SimpleCardWidget


class MergeOperationPanel(QWidget):
    """承载合并标题栏和操作卡片的工作区面板 D。

    标题栏复用右侧操作面板的高度与样式对象名，操作卡片当前保持空白，
    后续合并操作 UI 可以直接在卡片内部扩展，不影响页面组合结构。

    面板宽度由外部横向工作区统一设置为视口宽度的一半。

    Attributes:
        title_label [QLabel]: 显示“合并操作”的固定高度标题。
        operate_panel_card [SimpleCardWidget]: 承载后续合并控件的操作卡片。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化合并操作标题栏和空白操作卡片。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> panel = MergeOperationPanel()
            >>> panel.title_label.text()
            '合并操作'
        """
        super().__init__(parent)
        self.setObjectName("mergeOperationPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        self.title_label = QLabel("合并操作面板", self)
        # 与右侧操作面板标题共用 QSS 选择器和固定高度。
        self.title_label.setObjectName("sliceMiddleTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(25)

        self.operate_panel_card = SimpleCardWidget(self)
        self.operate_panel_card.setObjectName("mergeOperationCard")
        self.operate_panel_card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        self._init_layout()

    def _init_layout(self) -> None:
        """创建与右侧面板一致的标题间距及纵向卡片布局。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.operate_panel_card, 1)
