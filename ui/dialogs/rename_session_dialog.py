"""Session 元数据编辑对话框。

该模块提供基于 Fluent `MessageBoxBase` 的 Session 信息编辑弹窗，
用于在一次操作中同时修改 Session 名称和备注。

Example:
    >>> dialog = RenameSessionDialog("A.xlsx", "备注")
    >>> dialog.get_session_name()
    'A.xlsx'
"""

from __future__ import annotations

from qfluentwidgets import (
    BodyLabel,
    LineEdit,
    MessageBoxBase,
    SubtitleLabel,
    TextEdit,
)


class RenameSessionDialog(MessageBoxBase):
    """Session 元数据编辑对话框。

    对话框沿用原有重命名入口，但在同一视图中增加备注输入，以便控制器
    一次提交完成名称和备注的同步更新。

    Attributes:
        name_line_edit: Session 名称输入框。
        remark_text_edit: Session 备注输入框。
    """

    def __init__(self, current_name: str, current_remark: str = "", parent=None) -> None:
        """初始化 Session 元数据编辑对话框。

        Args:
            current_name: 当前 Session 名称。
            current_remark: 当前 Session 备注，默认值为空字符串。
            parent: 父组件，默认值为 None。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> dialog = RenameSessionDialog("A.xlsx", "备注")
            >>> dialog.get_remark()
            '备注'
        """
        super().__init__(parent)

        # 创建对话框标题。
        title_label = SubtitleLabel("编辑 Session 信息", self)
        # 创建名称输入提示。
        name_hint_label = BodyLabel("Session 名称", self)
        # 创建名称输入框。
        self.name_line_edit = LineEdit(self)
        self.name_line_edit.setText(current_name)
        self.name_line_edit.selectAll()
        self.name_line_edit.setClearButtonEnabled(True)

        # 创建备注输入提示。
        remark_hint_label = BodyLabel("Session 备注", self)
        # 使用组件库富文本框统一焦点边框、菜单和滚动条样式。
        self.remark_text_edit = TextEdit(self)
        self.remark_text_edit.setPlaceholderText("可填写数据来源、处理目的或当前进度说明")
        self.remark_text_edit.setPlainText(current_remark)
        self.remark_text_edit.setFixedHeight(120)

        # 按 Fluent 对话框内容区顺序组装控件。(组件库默认setSpacing(12))
        self.viewLayout.addWidget(title_label)
        self.viewLayout.addSpacing(12)
        self.viewLayout.addWidget(name_hint_label)
        self.viewLayout.addWidget(self.name_line_edit)
        self.viewLayout.addSpacing(10)
        self.viewLayout.addWidget(remark_hint_label)
        self.viewLayout.addWidget(self.remark_text_edit)

        # 设置底部按钮文案。
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")
        # 保留回车快速保存名称的交互。
        self.name_line_edit.returnPressed.connect(self.yesButton.click)

        # 初始聚焦到名称输入框，延续原重命名体验。
        self.name_line_edit.setFocus()
        # 增加最小宽度，给多行备注留出可读空间。
        self.widget.setMinimumWidth(420)

    def get_session_name(self) -> str:
        """获取输入的 Session 名称。

        Args:
            无。

        Returns:
            str: 输入框中的 Session 名称原始字符串。

        Raises:
            无显式抛出异常。

        Example:
            >>> dialog = RenameSessionDialog("A.xlsx")
            >>> dialog.get_session_name()
            'A.xlsx'
        """
        # 返回原始名称，空白校验由控制器和 registry 处理。
        return self.name_line_edit.text()

    def get_remark(self) -> str:
        """获取输入的 Session 备注。

        Args:
            无。

        Returns:
            str: 输入框中的 Session 备注原始字符串。

        Raises:
            无显式抛出异常。

        Example:
            >>> dialog = RenameSessionDialog("A.xlsx", "备注")
            >>> dialog.get_remark()
            '备注'
        """
        # 返回原始备注，空白归一化由 registry 统一处理。
        return self.remark_text_edit.toPlainText()
