"""切片流程控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QImage, QPixmap
from qfluentwidgets import InfoBar, InfoBarPosition

from app.signal_bus import signal_bus
from infra.plotting.types import RenderedImageBundle
from runtime.workflows.slice_workflow import slice_workflow
from ui.dialogs.processing_dialog import ProcessingDialog

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface


class SliceController(QObject):
    """切片流程控制器。

    功能描述：
        负责处理切片界面的切片触发逻辑与渲染结果展示，将 UI 操作与后台工作流桥接。

    参数说明：
        view (SliceInterface): 绑定的视图实例。

    返回值说明：
        无。

    异常说明：
        无。
    """

    def __init__(self, view: SliceInterface) -> None:
        """初始化切片控制器。

        功能描述：
            绑定视图对象，并连接按钮点击与全局图像就绪、阶段完成信号。

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
        self.view.main_action_card.start_slicing_button.clicked.connect(self.handle_slice)

        # 绑定全局生命周期信号与数据就绪信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.slice_image_ready.connect(self._on_slice_image_ready)

    def handle_slice(self) -> None:
        """处理切片按钮点击事件。

        功能描述：
            校验数据是否已导入，获取当前的切片模式（从按钮文字判断），更新按钮状态并启动切片工作流。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 校验数据导入状态
        if not self.view._test_session.is_imported:
            InfoBar.warning(
                title="提示",
                content="请先从 Excel 导入雷达脉冲数据，再执行切片操作。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.view
            )
            return

        # 判断当前选择的切片模式
        current_mode = self.view.main_action_card.start_slicing_button.text()
        is_adaptive = (current_mode == "自适应切片")
        
        # 也可以结合全局配置（此处暂存打印）
        from app.app_config import appConfig
        checkbox_adaptive = appConfig.autoRecognizeNextSlice.value
        print(f"执行切片，拆分按钮模式: {current_mode}, 自动识别全局配置状态: {checkbox_adaptive}")

        # 更新按钮状态
        self.view.main_action_card.start_slicing_button.setEnabled(False)

        # 显示动画对话框
        self._processing_dialog = ProcessingDialog(
            self.view, 
            title="切片处理", 
            content="正在执行数据切片与聚类渲染，请稍候..."
        )
        self._processing_dialog.show()

        # 启动后台切片工作流
        slice_workflow.start_slice(self.view._test_session)

    def _on_stage_finished(self, session_id: str, stage: str) -> None:
        """处理阶段完成信号。

        功能描述：
            校验会话 ID 与阶段，若切片完成则恢复按钮状态。

        参数说明：
            session_id (str): 会话唯一标识。
            stage (str): 阶段名称。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 校验会话与阶段
        if session_id == self.view._test_session.session_id and stage == "slicing":
            if self._processing_dialog:
                self._processing_dialog.close()
                self._processing_dialog = None
                
            # 恢复按钮状态
            self.view.main_action_card.start_slicing_button.setEnabled(True)
            
            # 弹出成功提示
            InfoBar.success(
                title="成功",
                content="数据切片与图像渲染完成！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.view
            )

    def _on_slice_image_ready(self, session_id: str, slice_index: int, bundle: RenderedImageBundle) -> None:
        """接收渲染图片结果并展示到卡片。

        功能描述：
            校验会话 ID，将渲染结果中的 numpy 数组转换为 QPixmap 并更新到对应的卡片组件中。

        参数说明：
            session_id (str): 会话唯一标识。
            slice_index (int): 切片索引。
            bundle (RenderedImageBundle): 渲染结果图像包。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        # 校验会话 ID
        if session_id != self.view._test_session.session_id:
            return

        # 更新左侧标题
        if hasattr(self.view, 'slice_title_label'):
            self.view.slice_title_label.setText(f"第{slice_index}个切片数据  原始图像")
        
        # 构建维度到卡片的映射字典
        cards = {
            "CF": self.view.original_cf_card,
            "PW": self.view.original_pw_card,
            "PA": self.view.original_pa_card,
            "DTOA": self.view.original_dtoa_card,
            "DOA": self.view.original_doa_card,
        }

        # 遍历图像数据并更新卡片
        for dim_name, image_data in bundle.images.items():
            if dim_name in cards:
                # 获取图像尺寸
                height, width = image_data.shape
                bytes_per_line = width
                
                # 转换为 QImage
                q_image = QImage(
                    image_data.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_Grayscale8,
                )
                
                # 设置图像到卡片
                cards[dim_name].set_image(QPixmap.fromImage(q_image))