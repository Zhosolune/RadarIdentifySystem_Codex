"""识别流程控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import logging

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QImage
from qfluentwidgets import InfoBar, InfoBarPosition

from app.signal_bus import signal_bus
from infra.plotting.types import RenderedImageBundle
from infra.plotting.facades import render_cluster_images
from runtime.workflows.identify_workflow import identify_workflow
from runtime.algorithm_params import get_clustering_params
from core.models.cluster_result import ClusterItem
from core.models.recognition_result import ClusterRecognition
from ui.dialogs.processing_dialog import ProcessingDialog

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface

LOGGER = logging.getLogger(__name__)


class IdentifyController(QObject):
    """识别流程控制器。

    功能描述：
        负责处理切片界面的识别（聚类）触发逻辑与聚类结果的渲染展示，将 UI 操作与后台工作流桥接。

    参数说明：
        view (SliceInterface): 绑定的视图实例。
    """

    def __init__(self, view: SliceInterface) -> None:
        """初始化识别控制器。

        功能描述：
            绑定视图对象，并连接识别相关按钮点击与全局生命周期信号。

        Args:
            view (SliceInterface): 绑定的视图实例。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        super().__init__(view)
        self.view = view
        self._processing_dialog = None
        self._current_cluster_index = 0

        # 绑定按钮点击事件
        self.view.navigation_control_card.start_recognition_button.clicked.connect(self.handle_identify)
        
        # 绑定聚类结果类别导航按钮
        self.view.prev_cluster_button.clicked.connect(self._on_prev_cluster)
        self.view.next_cluster_button.clicked.connect(self._on_next_cluster)

        # 绑定全局生命周期信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)

    def handle_identify(self) -> None:
        """处理识别按钮点击事件。

        功能描述：
            校验数据是否已切片，获取聚类参数并启动识别（聚类）工作流，同时更新按钮与弹窗状态。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 校验切片状态
        if not self.view._test_session.is_sliced:
            InfoBar.warning(
                title="提示",
                content="请先执行切片操作，再进行识别聚类。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
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
            content="正在执行雷达信号聚类分析，请稍候..."
        )
        self._processing_dialog.show()

        # 从运行时组装器获取聚类参数。
        clustering_params = get_clustering_params()
        
        # 从 slice_controller 获取当前正在查看的切片索引
        slice_index = self.view._slice_controller.current_slice_index
        
        identify_workflow.start_identify(
            self.view._test_session,
            slice_index=slice_index,
            clustering_params=clustering_params,
        )

    def _on_stage_finished(self, session_id: str, stage: str, slice_index: int | None) -> None:
        """处理阶段完成信号。

        功能描述：
            校验会话ID与阶段名称，若匹配则关闭进度对话框，恢复按钮状态，重置并渲染当前切片的第一个簇，并弹出成功提示。

        Args:
            session_id (str): 触发完成事件的会话ID。
            stage (str): 阶段名称。
            slice_index (int | None): 当前完成的切片索引。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if session_id != self.view._test_session.session_id or stage != "identifying":
            return

        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_recognition_button.setEnabled(True)
        
        # 聚类完成后，重置类别索引并渲染当前切片的第一个簇
        self._current_cluster_index = 0
        
        current_slice_index = self.view._slice_controller.current_slice_index
        self.load_cluster_image(current_slice_index)

        # 记录完成事件日志
        LOGGER.info(
            "收到识别完成事件，当前切片: %s，界面切片: %d",
            slice_index,
            current_slice_index,
            extra={"session_id": session_id},
        )

        target_slice_index = current_slice_index if slice_index is None else slice_index
        
        InfoBar.success(
            title="成功",
            content=f"第 {target_slice_index + 1} 切片信号聚类分析完成！",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=self.view
        )

    def _on_stage_failed(self, session_id: str, stage: str, slice_index: int | None, error_msg: str) -> None:
        """处理阶段失败信号。

        功能描述：
            校验会话ID与阶段名称，若匹配则关闭进度对话框，恢复按钮状态，并弹出携带详细错误信息的失败提示。

        Args:
            session_id (str): 触发失败事件的会话ID。
            stage (str): 阶段名称。
            slice_index (int | None): 发生错误的切片索引。
            error_msg (str): 错误信息内容。

        """
        if session_id != self.view._test_session.session_id or stage != "identifying":
            return

        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_recognition_button.setEnabled(True)
        
        # 弹出错误提示
        slice_suffix = ""
        if slice_index is not None:
            slice_suffix = f"（第 {slice_index + 1} 片）"
            
        InfoBar.error(
            title=f"聚类处理失败{slice_suffix}",
            content=f"发生错误:\n{error_msg}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=5000,
            parent=self.view
        )

    def _on_prev_cluster(self) -> None:
        """处理上一类别按钮点击。

        功能描述：
            递减类别索引并刷新聚类结果图像。

        """
        self._current_cluster_index -= 1
        self.load_cluster_image(self.view._slice_controller.current_slice_index)

    def _on_next_cluster(self) -> None:
        """处理下一类别按钮点击。

        功能描述：
            递增类别索引并刷新聚类结果图像。
        """
        self._current_cluster_index += 1
        self.load_cluster_image(self.view._slice_controller.current_slice_index)

    def update_cluster_navigation_buttons(self, current_slice_index: int) -> None:
        """更新聚类类别导航按钮可用状态。

        功能描述：
            根据当前切片的有效识别结果总数和当前选择的索引，判断是否启用上一类和下一类按钮。

        Args:
            current_slice_index (int): 正在显示的切片索引。

        """
        session = self.view._test_session
        if not session or not session.is_slice_recognized(current_slice_index):
            self.view.prev_cluster_button.setEnabled(False)
            self.view.next_cluster_button.setEnabled(False)
            return

        rec_res = session.recognition_result.slice_results.get(current_slice_index)
        if not rec_res or not rec_res.valid_clusters:
            self.view.prev_cluster_button.setEnabled(False)
            self.view.next_cluster_button.setEnabled(False)
            return
            
        total = len(rec_res.valid_clusters)
        self.view.prev_cluster_button.setEnabled(self._current_cluster_index > 0)
        self.view.next_cluster_button.setEnabled(self._current_cluster_index < total - 1)

    def load_cluster_image(self, current_slice_index: int, reset_index: bool = False) -> None:
        """加载并展示当前切片下指定索引的有效识别聚类结果图像。

        功能描述：
            校验切片与识别结果的有效性，约束类别索引后同步调用门面获取渲染图像，
            若切片无效或无结果则主动清空中间显示区域。

        Args:
            current_slice_index (int): 需要加载图像的切片索引。
            reset_index (bool, optional): 是否重置聚类索引为0，默认False。

        """
        if reset_index:
            self._current_cluster_index = 0
            
        session = self.view._test_session
        if not session or not session.is_slice_recognized(current_slice_index):
            self.clear_cluster_ui()
            self.update_cluster_navigation_buttons(current_slice_index)
            return

        rec_res = session.recognition_result.slice_results.get(current_slice_index)
        if not rec_res or not rec_res.valid_clusters:
            self.clear_cluster_ui()
            self.update_cluster_navigation_buttons(current_slice_index)
            return
            
        valid_clusters_info = rec_res.valid_clusters
            
        # 约束索引范围
        if self._current_cluster_index < 0:
            self._current_cluster_index = 0
        elif self._current_cluster_index >= len(valid_clusters_info):
            self._current_cluster_index = len(valid_clusters_info) - 1
            
        self.update_cluster_navigation_buttons(current_slice_index)
        
        # 同步获取聚类图像并更新界面
        LOGGER.info(f"加载切片 {current_slice_index + 1} 的有效识别簇 {self._current_cluster_index + 1} 图像", extra={"session_id": session.session_id})
        
        # 拿到对应识别结果
        target_rec = valid_clusters_info[self._current_cluster_index]
        
        # 去聚类结果中找到这个簇的数据点
        cluster_res = session.cluster_result.slice_results.get(current_slice_index)
        target_cluster = next(c for c in cluster_res.clusters if c.cluster_idx == target_rec.cluster_index)
        
        bundle = render_cluster_images(
            cluster_points=target_cluster.points,
            band=session.band,
            time_range=target_cluster.time_ranges
        )
        self._update_cluster_ui_with_bundle(bundle, target_rec, len(valid_clusters_info))

    def clear_cluster_ui(self) -> None:
        """清空聚类结果展示区域。

        功能描述：
            将聚类图像卡片显示重置为完全透明的状态，并重置提示标题。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 重置中间标题内容
        if hasattr(self.view, 'cluster_title_label'):
            self.view.cluster_title_label.setText("聚类结果暂无")
            
        # 获取所有需要重置的聚类卡片
        cards = [
            self.view.cluster_cf_card,
            self.view.cluster_pw_card,
            self.view.cluster_pa_card,
            self.view.cluster_dtoa_card,
            self.view.cluster_doa_card,
        ]
        
        # 创建完全透明的图像清空内容，代替黑底
        empty_image = QImage(100, 100, QImage.Format.Format_ARGB32)
        empty_image.fill(Qt.GlobalColor.transparent)
        
        # 将透明图像赋值给每个卡片
        for card in cards:
            card.set_image(empty_image)

    def _update_cluster_ui_with_bundle(self, bundle: RenderedImageBundle, cluster_rec: ClusterRecognition, total_clusters: int) -> None:
        """使用指定的聚类图像包更新聚类结果 UI。

        功能描述：
            根据传入的图像数据字典，逐个将维度图像转换为 QImage 并展示到对应的图像卡片中。
            同时在标题中展示识别标签和置信度信息。

        Args:
            bundle (RenderedImageBundle): 渲染后的聚类图像数据包。
            cluster_rec (ClusterRecognition): 正在展示的有效簇的识别结果模型。
            total_clusters (int): 当前切片下的总类别数，用于更新标题显示。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 更新中间标题文本，提示当前正在查看的类别进度和识别结果
        if hasattr(self.view, 'cluster_title_label'):
            pa_label = cluster_rec.pa_label
            dtoa_label = cluster_rec.dtoa_label
            pa_conf = cluster_rec.pa_confidence
            dtoa_conf = cluster_rec.dtoa_confidence
            joint_prob = cluster_rec.joint_prob
            
            title_text = (
                f"第 {self._current_cluster_index + 1} / {total_clusters} 个类别  "
                f"{cluster_rec.dim_name}维聚类结果  |  "
                f"PA: {pa_label}({pa_conf:.2f})  DTOA: {dtoa_label}({dtoa_conf:.2f})  "
                f"联合概率: {joint_prob:.2f}"
            )
            self.view.cluster_title_label.setText(title_text)
        
        # 构建维度到卡片的映射字典
        cards = {
            "CF": self.view.cluster_cf_card,
            "PW": self.view.cluster_pw_card,
            "PA": self.view.cluster_pa_card,
            "DTOA": self.view.cluster_dtoa_card,
            "DOA": self.view.cluster_doa_card,
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
                cards[dim_name].set_image(q_image)
