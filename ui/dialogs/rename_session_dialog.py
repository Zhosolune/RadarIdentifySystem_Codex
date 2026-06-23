"""重命名 Session 对话框。"""

from __future__ import annotations

from qfluentwidgets import BodyLabel, LineEdit, MessageBoxBase, SubtitleLabel


class RenameSessionDialog(MessageBoxBase):
    """重命名 Session 对话框。

    基于组件库对话框基类构建 Session 重命名弹窗，支持回车快速确认。

    Attributes:
        name_line_edit: Session 名称输入框。
    """

    def __init__(self, current_name: str, parent=None) -> None:
        """初始化 Session 重命名对话框。

        Args:
            current_name: 当前 Session 名称。
            parent: 父组件，默认值为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)

        # 创建标题文本。
        title_label = SubtitleLabel("重命名 Session", self)
        # 创建输入提示文本。
        hint_label = BodyLabel("请输入新的 Session 名称", self)
        # 创建名称输入框。
        self.name_line_edit = LineEdit(self)
        self.name_line_edit.setText(current_name)
        self.name_line_edit.selectAll()
        self.name_line_edit.setClearButtonEnabled(True)

        # 组装视图布局。
        self.viewLayout.addWidget(title_label)
        self.viewLayout.addSpacing(12)
        self.viewLayout.addWidget(hint_label)
        self.viewLayout.addSpacing(6)
        self.viewLayout.addWidget(self.name_line_edit)

        # 设置按钮文案。
        self.yesButton.setText("确认")
        self.cancelButton.setText("取消")
        # 连接回车确认事件。
        self.name_line_edit.returnPressed.connect(self.yesButton.click)

        # 设置初始焦点。
        self.name_line_edit.setFocus()
        # 设置弹窗最小宽度。
        self.widget.setMinimumWidth(360)

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
