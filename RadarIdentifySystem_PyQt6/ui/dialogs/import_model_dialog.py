# -*- coding: utf-8 -*-
"""导入模型对话框。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog, QTextEdit
from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, ComboBox, LineEdit, 
    BodyLabel, FluentIcon, PushButton
)

class ImportModelDialog(MessageBoxBase):
    """导入模型对话框。"""

    def __init__(self, default_type: str = "PA", parent=None):
        """初始化导入模型对话框。

        Args:
            default_type (str, optional): 默认选中的模型类型（"PA" 或 "DTOA"）。
            parent (QWidget, optional): 父组件。
        """
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("导入模型", self)

        # 模型类型
        self.typeLabel = BodyLabel("模型类型")
        self.typeCombo = ComboBox()
        self.typeCombo.addItems(["PA 模型", "DTOA 模型"])
        if default_type == "DTOA":
            self.typeCombo.setCurrentIndex(1)

        # 模型文件路径
        self.pathLabel = BodyLabel("模型文件路径")
        self.pathLayout = QHBoxLayout()
        self.pathLayout.setContentsMargins(0, 0, 0, 0)
        self.pathLayout.setSpacing(8)
        
        self.pathLineEdit = LineEdit()
        self.pathLineEdit.setPlaceholderText("例如：/models/pa/v2/model.onnx")
        
        self.browseBtn = PushButton(text = "浏览", icon = FluentIcon.FOLDER)
        self.browseBtn.clicked.connect(self._onBrowse)
        
        self.pathLayout.addWidget(self.pathLineEdit)
        self.pathLayout.addWidget(self.browseBtn)

        # 模型名称
        self.nameLabel = BodyLabel("模型名称 (可选)")
        self.nameLineEdit = LineEdit()
        self.nameLineEdit.setPlaceholderText("留空则自动从文件名提取")

        # 模型备注
        self.remarkLabel = BodyLabel("备注信息 (可选)")
        self.remarkTextEdit = QTextEdit()
        self.remarkTextEdit.setPlaceholderText("可填写模型用途、来源或适用说明")
        self.remarkTextEdit.setFixedHeight(88)

        # 将组件添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(16)
        self.viewLayout.addWidget(self.typeLabel)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(self.typeCombo)
        self.viewLayout.addSpacing(16)
        self.viewLayout.addWidget(self.pathLabel)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addLayout(self.pathLayout)
        self.viewLayout.addSpacing(16)
        self.viewLayout.addWidget(self.nameLabel)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(self.nameLineEdit)
        self.viewLayout.addSpacing(16)
        self.viewLayout.addWidget(self.remarkLabel)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(self.remarkTextEdit)

        # 设置对话框最小宽度
        self.widget.setMinimumWidth(380)
        
        # 修改按钮文本
        self.yesButton.setText("确认导入")
        self.cancelButton.setText("取消")

    def _onBrowse(self):
        """打开文件选择对话框浏览模型文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模型文件", "", "Model Files (*.onnx *.pkl *.pt *.pth);;All Files (*)"
        )
        if path:
            self.pathLineEdit.setText(path)

    def getModelInfo(self) -> tuple[str, str, str, str]:
        """获取对话框输入的信息。

        Returns:
            tuple[str, str, str, str]: 模型类型、模型文件路径、自定义模型名称、备注信息。
        """
        model_type = "PA" if self.typeCombo.currentIndex() == 0 else "DTOA"
        file_path = self.pathLineEdit.text().strip()
        model_name = self.nameLineEdit.text().strip()
        remark = self.remarkTextEdit.toPlainText().strip()
        return model_type, file_path, model_name, remark
