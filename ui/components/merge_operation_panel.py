"""合并操作面板占位组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets import SimpleCardWidget


class MergeOperationPanel(SimpleCardWidget):
    """合并工作区的空白操作面板 D。

    当前阶段仅提供稳定的面板边界和宽度约束，不创建任何业务控件。
    后续合并操作 UI 可以直接在该组件内部扩展，不影响切片页面组合结构。

    面板宽度由外部横向工作区统一设置为视口宽度的一半。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化空白合并操作面板。

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
            >>> panel.objectName()
            'mergeOperationPanel'
        """
        super().__init__(parent)
        self.setObjectName("mergeOperationPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
