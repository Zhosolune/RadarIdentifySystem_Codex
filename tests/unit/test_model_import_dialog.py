"""模型管理相关对话框输入契约校验测试。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget
from qfluentwidgets import TextEdit

from ui.dialogs.edit_model_remark_dialog import EditModelRemarkDialog
from ui.dialogs.import_model_dialog import ImportModelDialog


_APP: QApplication | None = None


def _app() -> QApplication:
    """获取测试进程共享的 QApplication。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        app = _APP
    return app


def test_dialog_keeps_open_state_and_shows_wrong_model_type(
    tmp_path: Path,
) -> None:
    """模型类型错选时应拒绝确认并在弹窗内显示可纠正提示。"""
    _app()
    model_path = tmp_path / "dtoa.onnx"
    model_path.touch()
    received: list[tuple[str, str]] = []

    def _reject_wrong_type(model_type: str, file_path: str) -> object:
        """记录参数并模拟 DTOA 模型被选为 PA。"""
        received.append((model_type, file_path))
        raise ValueError(
            "模型输入形状为 (1, 1, 250, 500)，符合 DTOA 模型，"
            "但当前选择的是 PA 模型；请检查模型类型是否选错"
        )

    parent = QWidget()
    parent.resize(800, 600)
    dialog = ImportModelDialog(
        parent=parent,
        model_validator=_reject_wrong_type,
    )
    dialog.pathLineEdit.setText(str(model_path))

    assert dialog.validate() is False
    assert received == [("PA", str(model_path))]
    assert not dialog.validationLabel.isHidden()
    assert "符合 DTOA 模型" in dialog.validationLabel.text()

    # 用户切换到 DTOA 后应清除旧错误，方便直接在原弹窗中纠正。
    dialog.typeCombo.setCurrentIndex(1)
    assert dialog.validationLabel.isHidden()
    dialog.deleteLater()
    parent.deleteLater()


def test_dialog_accepts_matching_model_contract(tmp_path: Path) -> None:
    """模型输入契约匹配时应允许对话框确认。"""
    _app()
    model_path = tmp_path / "pa.onnx"
    model_path.touch()
    parent = QWidget()
    parent.resize(800, 600)
    dialog = ImportModelDialog(
        parent=parent,
        model_validator=lambda model_type, file_path: (1, 1, 80, 400)
    )
    dialog.pathLineEdit.setText(str(model_path))

    assert dialog.validate() is True
    assert dialog.validationLabel.isHidden()
    dialog.deleteLater()
    parent.deleteLater()


def test_model_remark_dialog_uses_fluent_rich_text_editor() -> None:
    """模型备注弹窗应使用可随主题变化的组件库富文本框。"""
    _app()
    parent = QWidget()
    dialog = EditModelRemarkDialog("原备注", parent)

    assert isinstance(dialog.remark_text_edit, TextEdit)
    assert dialog.remark_text_edit.acceptRichText()
    assert dialog.remark_text_edit.toPlainText() == "原备注"

    dialog.remark_text_edit.setPlainText("新备注\n第二行")
    assert dialog.get_remark() == "新备注\n第二行"
    dialog.deleteLater()
    parent.deleteLater()
