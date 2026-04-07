"""导入数据控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from app.signal_bus import signal_bus
from runtime.workflows.import_workflow import import_workflow

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface


class ImportController(QObject):
    """导入功能控制器。

    功能描述：
        负责处理切片界面的 Excel 数据导入逻辑，将 UI 操作与后台工作流桥接。

    参数说明：
        view (SliceInterface): 绑定的视图实例。

    返回值说明：
        无。

    异常说明：
        无。
    """

    def __init__(self, view: SliceInterface) -> None:
        """初始化导入控制器。

        功能描述：
            绑定视图对象，并连接按钮点击与全局信号。

        参数说明：
            view (SliceInterface): 绑定的视图实例。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(view)
        self.view = view

        # 绑定按钮点击事件
        self.view.btn_import.clicked.connect(self.handle_import)

        # 绑定全局生命周期信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)

    def handle_import(self) -> None:
        """处理导入按钮点击事件。

        功能描述：
            唤起文件选择对话框选取 Excel，更新按钮状态并启动导入工作流。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self.view,
            "选择 Excel 文件",
            "",
            "Excel Files (*.xlsx *.xls)"
        )

        if not file_path:
            return

        try:
            # 更新按钮状态
            self.view.btn_import.setText("读取与预处理中...")
            self.view.btn_import.setEnabled(False)

            # 启动后台导入工作流
            import_workflow.start_import(self.view._test_session, file_path)

        except Exception as e:
            # 恢复按钮状态
            self.view.btn_import.setEnabled(True)
            self.view.btn_import.setText("1. 从 Excel 导入数据")
            # 弹出错误提示
            QMessageBox.critical(self.view, "导入失败", f"启动工作流失败:\n{str(e)}")

    def _on_stage_finished(self, session_id: str, stage: str) -> None:
        """处理阶段完成信号。

        功能描述：
            校验会话 ID 与阶段，若匹配则更新 UI 界面显示导入成功状态。

        参数说明：
            session_id (str): 会话唯一标识。
            stage (str): 阶段名称。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 校验会话与阶段
        if session_id == self.view._test_session.session_id and stage == "importing":
            pulses = self.view._test_session.raw_batch.data.shape[0] if self.view._test_session.raw_batch else 0
            # 更新按钮文本
            self.view.btn_import.setText(f"1. 导入完成 ({pulses}条数据)")
            # 启用按钮
            self.view.btn_import.setEnabled(True)

    def _on_stage_failed(self, session_id: str, stage: str, error_msg: str) -> None:
        """处理阶段失败信号。

        功能描述：
            校验会话 ID 与阶段，若匹配则恢复按钮状态并弹出错误提示。

        参数说明：
            session_id (str): 会话唯一标识。
            stage (str): 阶段名称。
            error_msg (str): 错误信息。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 校验会话与阶段
        if session_id == self.view._test_session.session_id and stage == "importing":
            # 恢复按钮状态
            self.view.btn_import.setText("1. 从 Excel 导入数据")
            self.view.btn_import.setEnabled(True)
            # 弹出错误提示
            QMessageBox.critical(self.view, "导入失败", f"无法读取或预处理 Excel 文件:\n{error_msg}")