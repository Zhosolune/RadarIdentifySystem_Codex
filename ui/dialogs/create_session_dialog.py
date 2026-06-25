"""创建 Session 对话框。"""

from __future__ import annotations

from PyQt6.QtWidgets import QTextEdit, QWidget
from qfluentwidgets import BodyLabel, LineEdit, MessageBoxBase, SubtitleLabel


class CreateSessionDialog(MessageBoxBase):
    """创建 Session 对话框。

    基于组件库对话框基类构建 Session 创建弹窗，支持填写名称和备注，
    并为留空场景提供默认值提示。

    Attributes:
        name_line_edit: Session 名称输入框。
        remark_text_edit: Session 备注输入框。
    """

    def __init__(
        self,
        default_display_name: str,
        parent: QWidget | None = None,
    ) -> None:
        """初始化创建 Session 对话框。

        Args:
            default_display_name: 名称留空时使用的默认展示名称，通常为文件名。
            parent: 父组件，默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self._default_display_name = default_display_name.strip()

        # 创建标题文本。
        title_label = SubtitleLabel("创建 Session", self)
        # 创建名称说明文本。
        name_hint_label = BodyLabel("请输入 Session 名称", self)
        # 创建名称输入框。
        self.name_line_edit = LineEdit(self)
        self.name_line_edit.setPlaceholderText(
            f"留空则默认使用 {self._default_display_name}"
        )
        self.name_line_edit.setClearButtonEnabled(True)

        # 创建备注说明文本。
        remark_hint_label = BodyLabel("请输入备注信息", self)
        # 创建备注输入框。
        self.remark_text_edit = QTextEdit(self)
        self.remark_text_edit.setPlaceholderText("留空则默认使用“无”")
        self.remark_text_edit.setFixedHeight(100)

        # 组装视图布局。
        self.viewLayout.addWidget(title_label)
        self.viewLayout.addSpacing(12)
        self.viewLayout.addWidget(name_hint_label)
        self.viewLayout.addSpacing(6)
        self.viewLayout.addWidget(self.name_line_edit)
        self.viewLayout.addSpacing(12)
        self.viewLayout.addWidget(remark_hint_label)
        self.viewLayout.addSpacing(6)
        self.viewLayout.addWidget(self.remark_text_edit)

        # 设置按钮文案。
        self.yesButton.setText("创建")
        self.cancelButton.setText("取消")
        # 连接回车确认事件。
        self.name_line_edit.returnPressed.connect(self.yesButton.click)

        # 设置初始焦点。
        self.name_line_edit.setFocus()
        # 设置弹窗最小宽度。
        self.widget.setMinimumWidth(400)

    def get_session_name(self) -> str:
        """获取输入的 Session 名称。

        Args:
            无。

        Returns:
            str: 输入框中的 Session 名称原始字符串。

        Raises:
            无显式抛出异常。
        """
        return self.name_line_edit.text()

    def get_session_remark(self) -> str:
        """获取输入的 Session 备注。

        Args:
            无。

        Returns:
            str: 输入框中的 Session 备注原始字符串。

        Raises:
            无显式抛出异常。
        """
        return self.remark_text_edit.toPlainText()
