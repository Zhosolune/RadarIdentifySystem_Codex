"""导入数据控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from qfluentwidgets import InfoBar, InfoBarPosition

from app.signal_bus import signal_bus
from runtime.workflows.import_workflow import import_workflow
from ui.dialogs.processing_dialog import ProcessingDialog

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
        self._processing_dialog = None

        # 绑定按钮点击事件
        self.view.import_data_button.clicked.connect(self.handle_import)

        # 绑定全局生命周期信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)

        # 状态自检定时器
        self._check_timer = QTimer(self.view)
        self._check_timer.timeout.connect(self._check_workflow_state)
        self._check_timer.start(1000)  # 每秒检查一次

    def _check_workflow_state(self) -> None:
        """定期检查工作流状态，防止信号丢失导致 UI 卡死。"""
        if self._processing_dialog is not None and not import_workflow.is_running():
            # 此时表示对话框还在，但工作流已意外停止
            self._processing_dialog.close()
            self._processing_dialog = None
            self.view.import_data_button.setEnabled(True)
            self.view.import_data_button.setText("1. 从 Excel 导入数据")
            InfoBar.warning(
                title="警告",
                content="检测到导入工作流异常退出，已恢复界面状态。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.view
            )

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
            self.view.import_data_button.setText("读取与预处理中...")
            self.view.import_data_button.setEnabled(False)

            # 显示动画对话框
            self._processing_dialog = ProcessingDialog(self.view, title="导入数据", content="正在读取与预处理，请稍候...")
            self._processing_dialog.show()

            # 启动后台导入工作流
            import_workflow.start_import(self.view._test_session, file_path)

        except Exception as e:
            # 隐藏动画
            if self._processing_dialog:
                self._processing_dialog.close()
                self._processing_dialog = None
            
            # 恢复按钮状态
            self.view.import_data_button.setEnabled(True)
            self.view.import_data_button.setText("1. 从 Excel 导入数据")
            # 弹出错误提示
            InfoBar.error(
                title="导入失败",
                content=f"启动工作流失败:\n{str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self.view
            )

    def _on_stage_finished(self, session_id: str, stage: str, slice_index: int | None) -> None:
        """处理阶段完成信号。

        功能描述：
            校验会话 ID 与阶段，若匹配则更新 UI 界面显示导入成功状态。

        参数说明：
            session_id (str): 会话唯一标识。
            stage (str): 阶段名称。
            slice_index (int | None): 切片索引；导入阶段固定为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 校验会话与阶段
        if session_id == self.view._test_session.session_id and stage == "importing":
            if self._processing_dialog:
                self._processing_dialog.close()
                self._processing_dialog = None
                
            pulses = self.view._test_session.raw_batch.data.shape[0] if self.view._test_session.raw_batch else 0
            # 更新按钮文本
            self.view.import_data_button.setText(f"1. 导入完成 ({pulses}条数据)")
            # 启用按钮
            self.view.import_data_button.setEnabled(True)
            
            # 弹出成功提示
            InfoBar.success(
                title="导入成功",
                content=f"已成功读取并预处理 {pulses} 条脉冲数据！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.view
            )

    def _on_stage_failed(self, session_id: str, stage: str, slice_index: int | None, error_msg: str) -> None:
        """处理阶段失败信号。

        功能描述：
            校验会话 ID 与阶段，若匹配则恢复按钮状态并弹出错误提示。

        参数说明：
            session_id (str): 会话唯一标识。
            stage (str): 阶段名称。
            slice_index (int | None): 切片索引；导入阶段固定为 None。
            error_msg (str): 错误信息。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 校验会话与阶段
        if session_id == self.view._test_session.session_id and stage == "importing":
            if self._processing_dialog:
                self._processing_dialog.close()
                self._processing_dialog = None
                
            # 恢复按钮状态
            self.view.import_data_button.setText("1. 从 Excel 导入数据")
            self.view.import_data_button.setEnabled(True)
            # 弹出错误提示
            QMessageBox.critical(self.view, "导入失败", f"无法读取或预处理 Excel 文件:\n{error_msg}")
