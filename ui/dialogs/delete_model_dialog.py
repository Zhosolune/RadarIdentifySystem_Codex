# -*- coding: utf-8 -*-
"""删除模型确认对话框。"""

from qfluentwidgets import MessageBoxBase, SubtitleLabel, BodyLabel


class DeleteModelDialog(MessageBoxBase):
    """删除模型确认对话框。

    功能描述：
        基于组件库对话框基类构建删除确认弹窗，由控制器统一调用。

    Attributes:
        无。
    """

    def __init__(self, display_name: str, parent=None) -> None:
        """初始化删除模型确认对话框。

        Args:
            display_name (str): 待删除模型的展示名称。
            parent (QWidget | None): 父组件，默认值为 None。

        Returns:
            None: 无返回值。

        Raises:
            无: 当前构造函数不主动抛出异常。
        """
        super().__init__(parent)

        # 创建标题文本
        title_label = SubtitleLabel("删除模型", self)
        # 创建确认描述文本
        desc_label = BodyLabel(
            f"确认删除模型 “{display_name}” 吗？\n该操作将同时移除模型文件与名称映射。",
            self,
        )
        desc_label.setWordWrap(True)

        # 组装视图布局
        self.viewLayout.addWidget(title_label)
        self.viewLayout.addSpacing(10)
        self.viewLayout.addWidget(desc_label)

        # 设置按钮文案
        self.yesButton.setText("确认删除")
        self.cancelButton.setText("取消")
        # 设置最小宽度，避免内容换行过早
        self.widget.setMinimumWidth(380)
