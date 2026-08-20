# -*- coding: utf-8 -*-
"""导入模型对话框。"""

import os
from typing import Callable

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHBoxLayout, QFileDialog, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon,
    LineEdit,
    MessageBoxBase,
    PushButton,
    SubtitleLabel,
    TextEdit,
)


class ImportModelDialog(MessageBoxBase):
    """导入模型对话框。"""

    def __init__(
        self,
        default_type: str = "PA",
        parent: QWidget | None = None,
        *,
        model_validator: Callable[[str, str], object] | None = None,
    ) -> None:
        """初始化导入模型对话框。

        Args:
            default_type [str]: 默认选中的模型类型，取值为 PA 或 DTOA。
            parent [QWidget | None]: 父组件。
            model_validator [Callable[[str, str], object] | None]: 确认导入前执行的模型输入契约校验函数。
        """
        super().__init__(parent)
        self._model_validator = model_validator
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
        self.pathLineEdit.setPlaceholderText("例如：D:/models/pa/model.onnx")
        
        self.browseBtn = PushButton(text="浏览", icon=FluentIcon.FOLDER)
        self.browseBtn.clicked.connect(self._onBrowse)
        
        self.pathLayout.addWidget(self.pathLineEdit)
        self.pathLayout.addWidget(self.browseBtn)
        self.validationLabel = CaptionLabel("")
        self.validationLabel.setWordWrap(True)
        self.validationLabel.setTextColor(
            QColor("#c42b1c"),
            QColor("#ff99a4"),
        )
        self.validationLabel.hide()

        # 模型名称
        self.nameLabel = BodyLabel("模型名称 (可选)")
        self.nameLineEdit = LineEdit()
        self.nameLineEdit.setPlaceholderText("留空则自动从文件名提取")

        # 模型备注
        self.remarkLabel = BodyLabel("备注信息 (可选)")
        self.remarkTextEdit = TextEdit()
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
        self.viewLayout.addWidget(self.validationLabel)
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
        self.typeCombo.currentIndexChanged.connect(
            self._clear_validation_error
        )
        self.pathLineEdit.textChanged.connect(
            self._clear_validation_error
        )

    def _onBrowse(self) -> None:
        """打开文件选择对话框浏览模型文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择模型文件",
            "",
            "ONNX Models (*.onnx)",
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

    def validate(self) -> bool:
        """在关闭对话框前校验文件存在性与模型输入契约。

        Returns:
            bool: 模型可以按当前所选类型导入时返回 True，否则返回 False。
        """
        model_type, file_path, _, _ = self.getModelInfo()
        if not file_path or not os.path.isfile(file_path):
            self._show_validation_error("请选择有效的 ONNX 模型文件")
            return False
        if self._model_validator is None:
            return True

        try:
            self._model_validator(model_type, file_path)
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            self._show_validation_error(str(error))
            return False
        self._clear_validation_error()
        return True

    def _show_validation_error(self, message: str) -> None:
        """在文件选择区下方显示模型校验失败原因。"""
        self.validationLabel.setText(message)
        self.validationLabel.show()

    def _clear_validation_error(self, *args: object) -> None:
        """用户修改模型类型或路径后清除旧校验提示。"""
        self.validationLabel.clear()
        self.validationLabel.hide()
