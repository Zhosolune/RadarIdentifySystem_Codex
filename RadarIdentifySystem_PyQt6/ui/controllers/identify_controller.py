"""识别流程控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import logging

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QImage
from qfluentwidgets import InfoBar, InfoBarPosition

from app.signal_bus import signal_bus
from infra.plotting.types import RenderedImageBundle
from runtime.workflows.identify_workflow import identify_workflow
from runtime.workflows.render_workflow import render_workflow
from core.models.cluster_result import ClusterItem
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

        # 绑定全局生命周期信号与数据就绪信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)
        signal_bus.cluster_image_ready.connect(self._on_cluster_image_ready)

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
        min_cluster_size = 8  # 暂未在配置中提供，保持默认
        
        # 从 slice_controller 获取当前正在查看的切片索引
        slice_index = self.view._slice_controller.current_slice_index
        
        identify_workflow.start_identify(
            self.view._test_session,
            slice_index=slice_index,
            eps_cf=eps_cf,
            eps_pw=eps_pw,
            min_pts=min_pts,
            min_cluster_size=min_cluster_size
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
            position=InfoBarPosition.TOP,
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
        
        # 弹出错误提示
        slice_suffix = ""
        if slice_index is not None:
            slice_suffix = f"（第 {slice_index + 1} 片）"
            
        InfoBar.error(
            title=f"聚类处理失败{slice_suffix}",
            content=f"发生错误:\n{error_msg}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self.view
        )

    def _on_prev_cluster(self) -> None:
        """处理上一类别按钮点击。

        功能描述：
            递减类别索引并刷新聚类结果图像。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        self._current_cluster_index -= 1
        self.load_cluster_image(self.view._slice_controller.current_slice_index)

    def _on_next_cluster(self) -> None:
        """处理下一类别按钮点击。

        功能描述：
            递增类别索引并刷新聚类结果图像。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        self._current_cluster_index += 1
        self.load_cluster_image(self.view._slice_controller.current_slice_index)

    def update_cluster_navigation_buttons(self, current_slice_index: int) -> None:
        """更新聚类类别导航按钮可用状态。

        功能描述：
            根据当前切片的聚类结果总数和当前选择的索引，判断是否启用上一类和下一类按钮。

        Args:
            current_slice_index (int): 正在显示的切片索引。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        session = self.view._test_session
        if not session or not session.is_slice_clustered(current_slice_index):
            self.view.prev_cluster_button.setEnabled(False)
            self.view.next_cluster_button.setEnabled(False)
            return

        cluster_res = session.cluster_result.slice_results.get(current_slice_index)
        if not cluster_res or not cluster_res.clusters:
            self.view.prev_cluster_button.setEnabled(False)
            self.view.next_cluster_button.setEnabled(False)
            return
            
        total = len(cluster_res.clusters)
        self.view.prev_cluster_button.setEnabled(self._current_cluster_index > 0)
        self.view.next_cluster_button.setEnabled(self._current_cluster_index < total - 1)

    def load_cluster_image(self, current_slice_index: int, reset_index: bool = False) -> None:
        """加载并展示当前切片下指定索引的聚类结果图像。

        功能描述：
            校验切片与聚类结果的有效性，约束类别索引后发起渲染工作流，
            若切片无效或无结果则主动清空中间显示区域。

        Args:
            current_slice_index (int): 需要加载图像的切片索引。
            reset_index (bool, optional): 是否重置聚类索引为0，默认False。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if reset_index:
            self._current_cluster_index = 0
            
        session = self.view._test_session
        if not session or not session.is_slice_clustered(current_slice_index):
            self.clear_cluster_ui()
            self.update_cluster_navigation_buttons(current_slice_index)
            return

        if session.cluster_result is None:
            self.clear_cluster_ui()
            self.update_cluster_navigation_buttons(current_slice_index)
            return

        cluster_res = session.cluster_result.slice_results.get(current_slice_index)
        if not cluster_res or not cluster_res.clusters:
            self.clear_cluster_ui()
            self.update_cluster_navigation_buttons(current_slice_index)
            return
            
        # 约束索引范围
        if self._current_cluster_index < 0:
            self._current_cluster_index = 0
        elif self._current_cluster_index >= len(cluster_res.clusters):
            self._current_cluster_index = len(cluster_res.clusters) - 1
            
        self.update_cluster_navigation_buttons(current_slice_index)
        
        # 启动后台渲染类别图像
        LOGGER.info(f"加载切片 {current_slice_index + 1} 的类别 {self._current_cluster_index + 1} 图像，启动后台渲染", extra={"session_id": session.session_id})
        render_workflow.start_render(
            session=session, 
            slice_index=current_slice_index, 
            cluster_index=self._current_cluster_index,
            is_cluster_render=True
        )

    def _on_cluster_image_ready(self, session_id: str, slice_index: int, cluster_index: int, bundle: RenderedImageBundle) -> None:
        """接收类别渲染图片结果并展示到卡片。

        功能描述：
            校验会话 ID 及切片、聚类索引，将渲染完成的图像数据呈现到对应的维度卡片中。

        Args:
            session_id (str): 当前所属的会话 ID。
            slice_index (int): 所属的切片索引。
            cluster_index (int): 正在显示的聚类索引。
            bundle (RenderedImageBundle): 后台渲染生成的各维度聚类图像包。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        if session_id != self.view._test_session.session_id:
            return
            
        current_slice_index = self.view._slice_controller.current_slice_index
        if slice_index != current_slice_index or cluster_index != self._current_cluster_index:
            return
            
        session = self.view._test_session
        if not session.is_slice_clustered(slice_index) or session.cluster_result is None:
            return

        cluster_res = session.cluster_result.slice_results.get(slice_index)
        if not cluster_res or not cluster_res.clusters:
            return
            
        current_cluster = cluster_res.clusters[cluster_index]
        self._update_cluster_ui_with_bundle(bundle, current_cluster, len(cluster_res.clusters))

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

    def _update_cluster_ui_with_bundle(self, bundle: RenderedImageBundle, cluster_item: ClusterItem, total_clusters: int) -> None:
        """使用指定的聚类图像包更新聚类结果 UI。

        功能描述：
            根据传入的图像数据字典，逐个将维度图像转换为 QImage 并展示到对应的图像卡片中。

        Args:
            bundle (RenderedImageBundle): 渲染后的聚类图像数据包。
            cluster_item (ClusterItem): 正在展示的聚类簇信息模型。
            total_clusters (int): 当前切片下的总类别数，用于更新标题显示。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 更新中间标题文本，提示当前正在查看的类别进度
        if hasattr(self.view, 'cluster_title_label'):
            self.view.cluster_title_label.setText(
                f"第 {self._current_cluster_index + 1} / {total_clusters} 个类别  {cluster_item.dim_name}维聚类结果"
            )
        
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
