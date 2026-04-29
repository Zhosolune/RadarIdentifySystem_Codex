# -*- coding: utf-8 -*-
"""编辑模型备注对话框。"""

from PyQt6.QtWidgets import QTextEdit
from qfluentwidgets import MessageBoxBase, SubtitleLabel, BodyLabel


class EditModelRemarkDialog(MessageBoxBase):
    """编辑模型备注对话框。

    功能描述：
        基于组件库对话框基类构建模型备注编辑弹窗，支持填写或清空备注信息。

    Attributes:
        remark_text_edit (QTextEdit): 备注输入框。
    """

    def __init__(self, current_remark: str, parent=None) -> None:
        """初始化编辑模型备注对话框。

        Args:
            current_remark (str): 当前模型备注。
            parent (QWidget | None): 父组件，默认值为 None。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        super().__init__(parent)

        # 创建标题文本
        title_label = SubtitleLabel("编辑备注", self)
        # 创建提示文本
        hint_label = BodyLabel("请输入模型备注信息", self)
        # 创建备注输入框
        self.remark_text_edit = QTextEdit(self)
        self.remark_text_edit.setPlaceholderText("可填写模型用途、来源或适用说明")
        self.remark_text_edit.setPlainText(current_remark)
        self.remark_text_edit.setFixedHeight(120)

        # 组装视图布局
        self.viewLayout.addWidget(title_label)
        self.viewLayout.addSpacing(12)
        self.viewLayout.addWidget(hint_label)
        self.viewLayout.addSpacing(6)
        self.viewLayout.addWidget(self.remark_text_edit)

        # 设置按钮文案
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

        # 设置初始焦点
        self.remark_text_edit.setFocus()
        # 设置弹窗最小宽度
        self.widget.setMinimumWidth(400)

    def get_remark(self) -> str:
        """获取输入的备注信息。

        Args:
            无。

        Returns:
            str: 输入框中的备注文本。

        Raises:
            无。
        """
        # 返回备注输入内容
        return self.remark_text_edit.toPlainText()
