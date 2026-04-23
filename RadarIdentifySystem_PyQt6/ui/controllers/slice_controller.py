"""切片流程控制器。"""



from __future__ import annotations

from typing import TYPE_CHECKING
from collections import OrderedDict

import logging
from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from qfluentwidgets import InfoBar, InfoBarPosition

from app.signal_bus import signal_bus
from infra.plotting.types import RenderedImageBundle
from infra.plotting.facades import render_slice_images
from runtime.workflows.slice_workflow import slice_workflow
from ui.dialogs.processing_dialog import ProcessingDialog

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface

LOGGER = logging.getLogger(__name__)

class SliceController(QObject):
    """切片流程控制器。

    功能描述：
        负责处理切片界面的切片触发逻辑与渲染结果展示，将 UI 操作与后台工作流桥接。

    参数说明：
        view (SliceInterface): 绑定的视图实例。

    """

    @property
    def current_slice_index(self) -> int:
        """获取当前显示的切片索引。

        功能描述：
            提供一个只读属性，返回当前界面正在展示的切片序号。

        """
        return self._current_slice_index

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
        self._current_slice_index = 0

        # 绑定按钮点击事件
        self.view.navigation_control_card.start_slicing_button.clicked.connect(self.handle_slice)
        
        # 绑定标题旁边的透明导航按钮
        self.view.prev_slice_button.clicked.connect(self._on_prev_slice)
        self.view.next_slice_button.clicked.connect(self._on_next_slice)

        # 绑定全局生命周期信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)

        # 绑定重绘请求信号
        self.view.redraw_option_card.redraw_requested.connect(self._on_redraw_requested)

        # 状态自检定时器
        self._check_timer = QTimer(self.view)
        self._check_timer.timeout.connect(self._check_workflow_state)
        self._check_timer.start(1000)

    def _check_workflow_state(self) -> None:
        """定期检查工作流状态，防止信号丢失导致 UI 卡死。

        功能描述：
            通过定时器轮询当前是否还在进行切片任务，若弹窗存在但任务已停止，
            说明发生了异常导致信号未到达，此时主动恢复界面状态。

        """
        if self._processing_dialog is None:
            return
            
        # 此时有进度条对话框正在显示
        is_slicing = slice_workflow.is_running()
        
        # 如果两者都不在运行，说明出现异常导致信号丢失
        if not is_slicing:
            self._processing_dialog.close()
            self._processing_dialog = None
            
            # 恢复按钮状态
            self.view.navigation_control_card.start_slicing_button.setEnabled(True)
            
            InfoBar.warning(
                title="警告",
                content="检测到后台任务异常退出，已恢复界面状态。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.view
            )

    def handle_slice(self) -> None:
        """处理切片按钮点击事件。

        功能描述：
            校验数据是否已导入，获取当前的切片模式（从按钮文字判断），更新按钮状态并启动切片工作流。

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
        is_adaptive = self.view.navigation_control_card.adaptive_slicing_checkbox.isChecked()
        current_mode = "自适应切片" if is_adaptive else "开始切片"
        
        # 也可以结合全局配置（此处暂存打印）
        from app.app_config import appConfig
        checkbox_adaptive = appConfig.autoRecognizeNextSlice.value
        LOGGER.info(f"执行切片，拆分按钮模式: {current_mode}, 自动识别全局配置状态: {checkbox_adaptive}")

        # 更新按钮状态
        self.view.navigation_control_card.start_slicing_button.setEnabled(False)

        # 显示动画对话框
        self._processing_dialog = ProcessingDialog(
            self.view, 
            title="切片处理", 
            content="正在执行数据切片与聚类渲染，请稍候..."
        )
        self._processing_dialog.show()

        # 启动后台切片工作流
        slice_workflow.start_slice(self.view._test_session)

    def handle_identify(self) -> None:
        """处理识别按钮点击事件。

        功能描述：
            校验数据是否已切片，更新按钮状态并启动识别（聚类）工作流。
        """
        # 校验切片状态
        if not self.view._test_session.is_sliced:
            InfoBar.warning(
                title="提示",
                content="请先执行切片操作，再进行识别聚类。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.view
            )
            return

        # 更新按钮状态
        self.view.navigation_control_card.start_recognition_button.setEnabled(False)

        # 显示动画对话框
        self._processing_dialog = ProcessingDialog(
            self.view, 
            title="聚类处理", 
            content="正在执行雷达信号级联聚类分析，请稍候..."
        )
        self._processing_dialog.show()

        # 获取聚类参数从全局配置中读取
        from app.app_config import appConfig
        eps_cf = appConfig.algorithmEpsilonCF.value
        eps_pw = appConfig.algorithmEpsilonPW.value
        min_pts = appConfig.algorithmMinPts.value
        # min_cluster_size 暂未在配置中提供，保持默认8或从其他地方读取
        min_cluster_size = 8
        
        identify_workflow.start_identify(
            self.view._test_session,
            slice_index=self._current_slice_index,
            eps_cf=eps_cf,
            eps_pw=eps_pw,
            min_pts=min_pts,
            min_cluster_size=min_cluster_size
        )

    def _on_stage_finished(self, session_id: str, stage: str, slice_index: int | None) -> None:
        """处理阶段完成信号。

        功能描述：
            作为中转站，根据不同阶段将处理逻辑分发到独立的方法中。

        Args:
            session_id (str): 会话唯一标识。
            stage (str): 阶段名称。
            slice_index (int | None): 切片索引；全局流程时为 None。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if session_id != self.view._test_session.session_id or stage != "slicing":
            return

        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_slicing_button.setEnabled(True)
        
        # 加载第0片
        self._load_slice_image(0)
        
        # 通知聚类控制器清空旧显示
        if hasattr(self.view, '_identify_controller'):
            self.view._identify_controller.load_cluster_image(0, reset_index=True)
        
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

    def _on_stage_failed(self, session_id: str, stage: str, slice_index: int | None, error_msg: str) -> None:
        """处理阶段失败信号。

        功能描述：
            校验会话 ID 与阶段，若匹配则恢复按钮状态并弹出错误提示。

        Args:
            session_id (str): 发生失败的会话 ID。
            stage (str): 失败的阶段名称。
            slice_index (int | None): 失败的切片索引。
            error_msg (str): 错误提示信息。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if session_id != self.view._test_session.session_id:
            return

        if stage != "slicing":
            return

        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_slicing_button.setEnabled(True)
        
        # 弹出错误提示
        InfoBar.error(
            title="切片处理失败",
            content=f"发生错误:\n{error_msg}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self.view
        )

    def _handle_slicing_finished(self) -> None:
        """处理切片完成后的逻辑。

        功能描述：
            关闭进度对话框，恢复按钮状态，加载首个切片并通知聚类界面清空。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_slicing_button.setEnabled(True)
        
        # 加载第0片
        self._load_slice_image(0)
        
        # 通知聚类控制器清空旧显示
        if hasattr(self.view, '_identify_controller'):
            self.view._identify_controller.load_cluster_image(0, reset_index=True)
        
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

    def _handle_identifying_finished(self, slice_index: int | None) -> None:
        """处理识别（聚类）完成后的逻辑。"""
        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_recognition_button.setEnabled(True)
        
        # 聚类完成后，重置类别索引并渲染当前切片的第一个簇
        self._current_cluster_index = 0
        self._load_cluster_image()

        # 记录完成事件日志
        LOGGER.info(
            "收到识别完成事件，当前切片: %s，界面切片: %d",
            slice_index,
            self._current_slice_index,
            extra={"session_id": self.view._test_session.session_id},
        )

        target_slice_index = self._current_slice_index if slice_index is None else slice_index
        
        InfoBar.success(
            title="成功",
            content=f"第 {target_slice_index + 1} 切片信号聚类分析完成！",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self.view
        )

    def _on_redraw_requested(self, slice_index: int) -> None:
        """处理重绘请求。
        
        功能描述：
            响应来自视图面板的重绘操作请求，重新加载当前切片对应的图像。

        Args:
            slice_index (int): 请求重绘的切片编号。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 重新触发绘制
        self._load_slice_image(self._current_slice_index)
        LOGGER.info(f"收到重绘请求，已重新渲染切片编号: {self._current_slice_index}")

    def _on_prev_slice(self) -> None:
        """处理上一片按钮点击。

        功能描述：
            将切片索引递减并触发该切片的图像加载和聚类结果更新。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        self._load_slice_image(self._current_slice_index - 1)
        if hasattr(self.view, '_identify_controller'):
            self.view._identify_controller.load_cluster_image(self._current_slice_index, reset_index=True)

    def _on_next_slice(self) -> None:
        """处理下一片按钮点击。

        功能描述：
            将切片索引递增并触发该切片的图像加载和聚类结果更新。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        self._load_slice_image(self._current_slice_index + 1)
        if hasattr(self.view, '_identify_controller'):
            self.view._identify_controller.load_cluster_image(self._current_slice_index, reset_index=True)

    def _update_navigation_buttons(self) -> None:
        """更新导航按钮可用状态。

        功能描述：
            根据当前总切片数量与正在查看的切片索引，动态开启或禁用“上一片”和“下一片”按钮。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        session = self.view._test_session
        if not session or not session.slice_result:
            return
        total = session.slice_result.slice_count
        self.view.prev_slice_button.setEnabled(self._current_slice_index > 0)
        self.view.next_slice_button.setEnabled(self._current_slice_index < total - 1)

    def _load_slice_image(self, index: int) -> None:
        """加载并展示指定索引的切片图像。

        功能描述：
            检查索引合法性后更新当前索引和导航按钮。同步调用底层门面
            提取切片数据完成渲染，并直接刷新 UI 界面。

        Args:
            index (int): 请求加载的切片索引。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        session = self.view._test_session
        if not session or not session.slice_result:
            return
        if index < 0 or index >= session.slice_result.slice_count:
            return

        self._current_slice_index = index
        self._update_navigation_buttons()

        # 同步渲染切片数据
        target_slice = session.slice_result.slices[index]
        bundle = render_slice_images(
            target_slice.data,
            band=session.band,
            time_range=target_slice.time_range,
        )
        self._update_ui_with_bundle(bundle, index)

    def _update_ui_with_bundle(self, bundle: RenderedImageBundle, slice_index: int) -> None:
        """使用指定的图像包更新 UI。

        功能描述：
            提取传入图像包中的各个维度数据，将其转为 QImage 格式并挂载到界面卡片中。

        Args:
            bundle (RenderedImageBundle): 需要显示的切片图像数据集合。
            slice_index (int): 对应的切片索引，用于刷新标题进度。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        session = self.view._test_session
        total = session.slice_result.slice_count if session.slice_result else 0

        # 更新左侧标题文本
        if hasattr(self.view, 'slice_title_label'):
            self.view.slice_title_label.setText(f"第 {slice_index + 1} / {total} 个切片数据  原始图像")
        
        # 组装图像维度与界面卡片的映射关系
        cards = {
            "CF": self.view.original_cf_card,
            "PW": self.view.original_pw_card,
            "PA": self.view.original_pa_card,
            "DTOA": self.view.original_dtoa_card,
            "DOA": self.view.original_doa_card,
        }

        # 遍历图像数据并设置到卡片对象
        for dim_name, image_data in bundle.images.items():
            if dim_name in cards:
                # 获取底层图像矩阵尺寸
                height, width = image_data.shape
                bytes_per_line = width
                
                # 转换数组为 QImage 结构
                q_image = QImage(
                    image_data.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_Grayscale8,
                )
                
                # 应用图像到对应卡片
                cards[dim_name].set_image(q_image)
