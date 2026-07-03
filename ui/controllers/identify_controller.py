"""识别流程控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox
from app.signal_bus import signal_bus
from core.models.cluster_result import ClusterItem, SliceClusterResult
from core.models.processing_session import ProcessingSession
from infra.plotting.types import RenderedImageBundle
from infra.plotting.facades import render_cluster_images
from runtime.workflows.identify_workflow import IdentifyWorkflow
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

    EMPTY_CLUSTER_TITLE = "暂无聚类结果"

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
        # 为当前 session 页面创建独立识别工作流，允许不同 session 并行处理。
        self._workflow = IdentifyWorkflow(self)
        self._processing_dialog = None
        self._current_cluster_index = 0
        self._connect_signals()
        self.refresh_cluster_view_state(reset_index=True)

    def _connect_signals(self) -> None:
        """连接识别相关按钮点击事件。"""
        # 绑定按钮点击事件
        self.view.navigation_control_card.start_recognition_button.clicked.connect(
            lambda: self.handle_identify()
        )
        
        # 绑定聚类结果类别导航按钮
        self.view.prev_cluster_button.clicked.connect(self._on_prev_cluster)
        self.view.next_cluster_button.clicked.connect(self._on_next_cluster)
        # 右侧控制卡的文字按钮复用同一组类别导航槽函数。
        self.view.navigation_control_card.prev_cluster_button.clicked.connect(
            self._on_prev_cluster
        )
        self.view.navigation_control_card.next_cluster_button.clicked.connect(
            self._on_next_cluster
        )

        # 绑定全局生命周期信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)

        # 监听当前 session 展示模式变化，并立即刷新当前聚类结果。
        self.view.plot_option_card.showModeChanged.connect(
            self._on_plot_show_mode_changed
        )

    def handle_identify(self, target_slice_index: int | None = None) -> None:
        """处理识别按钮点击事件。

        功能描述：
            校验数据是否已切片，获取聚类参数并启动识别（聚类）工作流，同时更新按钮与弹窗状态。

        Args:
            target_slice_index (int | None): 需要识别的 0-based 切片索引；为 None 时读取当前界面切片索引。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 校验切片状态
        if not self.view._session.is_sliced:
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

        # 显示动画对话框
        self._processing_dialog = ProcessingDialog(
            self.view, 
            title="聚类处理", 
            content="正在执行雷达信号聚类分析，请稍候..."
        )
        self._processing_dialog.show()

        # 校验识别模型启用状态
        if not self._validate_enabled_models():
            return

        # 自动识别入口会显式传入目标索引，手动按钮入口继续读取当前界面索引。
        slice_index = (
            self.view._slice_controller.current_slice_index
            if target_slice_index is None
            else target_slice_index
        )

        # 更新按钮状态
        self.view.navigation_control_card.start_recognition_button.setEnabled(False)
        # 清空旧聚类空态并禁用导航按钮。
        self.clear_cluster_ui()
        self.update_cluster_navigation_buttons(slice_index)
        
        # 启动识别工作流，参数由 runtime 层内部自行获取
        self._workflow.start_identify(
            self.view._session,
            slice_index=slice_index,
        )

    def is_identifying_running(self) -> bool:
        """返回当前 session 页面是否仍有识别任务在运行。

        Returns:
            bool: 当前页面的识别工作流仍在执行时返回 True。

        Raises:
            无。
        """
        return self._workflow.is_running()

    def _validate_enabled_models(self) -> bool:
        """校验 PA/DTOA 启用模型是否完整可用。

        Args:
            无。

        Returns:
            bool: 校验通过返回 True，否则返回 False。

        Raises:
            无。
        """
        selection = self.view._session.model_selection
        pa_path = selection.pa_model_path
        dtoa_path = selection.dtoa_model_path
        if (
            not pa_path
            or not dtoa_path
            or not Path(pa_path).exists()
            or not Path(dtoa_path).exists()
        ):
            InfoBar.warning(
                title="模型未就绪",
                content="请先在当前 Session 中分别选择一个 PA 模型和一个 DTOA 模型。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=3500,
                parent=self.view,
            )
            return False
        return True

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
        if session_id != self.view._session.session_id or stage != "identifying":
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
            "收到识别完成事件，当前切片: %s",
            slice_index + 1,
            extra={"session_id": session_id},
        )

        target_slice_index = current_slice_index if slice_index is None else slice_index

        # 检查当前切片是否存在通过识别的雷达信号，若无则弹出消息框提醒用户
        session = self.view._session
        slice_recognition = None
        if session.recognition_result is not None:
            slice_recognition = session.recognition_result.slice_results.get(current_slice_index)

        if slice_recognition is None or not slice_recognition.valid_clusters:
            # 当前切片没有通过识别的雷达信号，弹出消息框提醒用户
            no_signal_msg = MessageBox(
                "无识别结果",
                f"第 {target_slice_index + 1} 切片没有通过识别的雷达信号。",
                self.view,
            )
            # 仅需用户确认，隐藏取消按钮并保持布局居中
            no_signal_msg.hideCancelButton()
            no_signal_msg.yesButton.setText("知道了")
            no_signal_msg.exec()
            return

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
        if session_id != self.view._session.session_id or stage != "identifying":
            return

        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_recognition_button.setEnabled(True)
        self.clear_cluster_ui()
        current_slice_index = self.view._slice_controller.current_slice_index
        self.update_cluster_navigation_buttons(current_slice_index)
        
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

    def _on_plot_show_mode_changed(self, mode: str) -> None:
        """响应聚类展示模式变化。"""
        LOGGER.info(
            "切换聚类展示模式为 %s",
            mode,
            extra={"session_id": self.view._session.session_id},
        )
        # 重置浏览索引，避免从较大索引切到较小结果集时越界。
        self.refresh_cluster_view_state(reset_index=True)

    def _is_identified_only_mode(self) -> bool:
        """返回当前是否仅展示识别通过的聚类结果。"""
        return (
            str(self.view._session.config_snapshot.plot.only_show_identified)
            == "IDENTIFIED_ONLY"
        )

    def _get_slice_cluster_result(
        self,
        session: ProcessingSession,
        current_slice_index: int,
    ) -> SliceClusterResult | None:
        """获取当前切片的聚类结果。"""
        if session.cluster_result is None:
            return None
        return session.cluster_result.slice_results.get(current_slice_index)

    def _build_cluster_recognition_map(
        self,
        session: ProcessingSession,
        current_slice_index: int,
    ) -> dict[int, ClusterRecognition]:
        """构建簇索引到识别结果的映射。"""
        if session.recognition_result is None:
            return {}

        slice_recognition = session.recognition_result.slice_results.get(current_slice_index)
        if slice_recognition is None:
            return {}

        cluster_map: dict[int, ClusterRecognition] = {}
        # 合并有效簇和无效簇，便于“展示全部”模式读取识别状态。
        for cluster_rec in [
            *slice_recognition.valid_clusters,
            *slice_recognition.invalid_clusters,
        ]:
            cluster_map[cluster_rec.cluster_index] = cluster_rec
        return cluster_map

    def _get_display_clusters(
        self,
        session: ProcessingSession,
        current_slice_index: int,
    ) -> list[tuple[ClusterItem, ClusterRecognition | None]]:
        """按当前展示模式返回可浏览的簇列表。"""
        slice_cluster_result = self._get_slice_cluster_result(session, current_slice_index)
        if slice_cluster_result is None or not slice_cluster_result.clusters:
            return []

        recognition_map = self._build_cluster_recognition_map(session, current_slice_index)
        if self._is_identified_only_mode():
            # 仅保留识别通过的簇，顺序跟随聚类结果列表。
            return [
                (cluster, recognition_map[cluster.cluster_idx])
                for cluster in slice_cluster_result.clusters
                if (
                    cluster.cluster_idx in recognition_map
                    and recognition_map[cluster.cluster_idx].is_valid
                )
            ]

        # 展示全部模式下，同时保留已有识别状态，便于标题展示。
        return [
            (cluster, recognition_map.get(cluster.cluster_idx))
            for cluster in slice_cluster_result.clusters
        ]

    def update_cluster_navigation_buttons(self, current_slice_index: int) -> None:
        """更新聚类类别导航按钮可用状态。

        功能描述：
            根据当前切片的有效识别结果总数和当前选择的索引，判断是否启用上一类和下一类按钮。

        Args:
            current_slice_index (int): 正在显示的切片索引。

        """
        session = self.view._session
        if not session:
            self._set_cluster_navigation_enabled(False, False)
            return

        display_clusters = self._get_display_clusters(session, current_slice_index)
        if not display_clusters:
            self._set_cluster_navigation_enabled(False, False)
            return

        total = len(display_clusters)
        self._set_cluster_navigation_enabled(
            self._current_cluster_index > 0,
            self._current_cluster_index < total - 1,
        )

    def refresh_cluster_view_state(self, reset_index: bool = False) -> None:
        """刷新当前切片的聚类结果空态与导航状态。"""
        current_slice_index = self.view._slice_controller.current_slice_index
        self.load_cluster_image(current_slice_index, reset_index=reset_index)

    def _set_cluster_navigation_enabled(
        self,
        prev_enabled: bool,
        next_enabled: bool,
    ) -> None:
        """同步更新两组类别导航按钮状态。"""
        # 同步更新中间列图形按钮。
        self.view.prev_cluster_button.setEnabled(prev_enabled)
        self.view.next_cluster_button.setEnabled(next_enabled)
        # 同步更新右侧控制卡文字按钮。
        self.view.navigation_control_card.prev_cluster_button.setEnabled(prev_enabled)
        self.view.navigation_control_card.next_cluster_button.setEnabled(next_enabled)

    def load_cluster_image(self, current_slice_index: int, reset_index: bool = False) -> None:
        """加载并展示当前切片下指定索引的聚类结果图像。

        功能描述：
            按当前展示模式从聚类结果中筛选可浏览簇，约束类别索引后同步调用门面获取渲染图像，
            若当前切片无可显示结果则主动清空中间显示区域。

        Args:
            current_slice_index (int): 需要加载图像的切片索引。
            reset_index (bool, optional): 是否重置聚类索引为0，默认False。

        """
        if reset_index:
            self._current_cluster_index = 0
            
        session = self.view._session
        if not session:
            self.clear_cluster_ui()
            self.update_cluster_navigation_buttons(current_slice_index)
            return

        slice_cluster_result = self._get_slice_cluster_result(session, current_slice_index)
        display_clusters = self._get_display_clusters(session, current_slice_index)
        if slice_cluster_result is None or not display_clusters:
            self.clear_cluster_ui()
            self.update_cluster_navigation_buttons(current_slice_index)
            return

        # 约束索引范围
        if self._current_cluster_index < 0:
            self._current_cluster_index = 0
        elif self._current_cluster_index >= len(display_clusters):
            self._current_cluster_index = len(display_clusters) - 1

        self.update_cluster_navigation_buttons(current_slice_index)

        target_cluster, target_rec = display_clusters[self._current_cluster_index]

        # 同步获取聚类图像并更新界面
        cluster_type = "有效识别簇" if self._is_identified_only_mode() else "聚类簇"
        LOGGER.info(
            "加载切片 %d 的%s %d 图像",
            current_slice_index + 1,
            cluster_type,
            self._current_cluster_index + 1,
            extra={"session_id": session.session_id},
        )

        bundle = render_cluster_images(
            cluster_points=target_cluster.points,
            band=session.band,
            time_range=target_cluster.time_ranges
        )
        self._update_cluster_ui_with_bundle(
            bundle=bundle,
            cluster=target_cluster,
            cluster_rec=target_rec,
            display_index=self._current_cluster_index + 1,
            display_total=len(display_clusters),
            total_all=len(slice_cluster_result.clusters),
        )

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
            self.view.cluster_title_label.setText(self.EMPTY_CLUSTER_TITLE)
            
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

        # 清空右侧分析结果表格，避免无类别时残留上一次识别结果。
        if hasattr(self.view, "analysis_result_card"):
            self.view.analysis_result_card.clear_results()

    def _update_cluster_ui_with_bundle(
        self,
        bundle: RenderedImageBundle,
        cluster: ClusterItem,
        cluster_rec: ClusterRecognition | None,
        display_index: int,
        display_total: int,
        total_all: int,
    ) -> None:
        """使用指定的聚类图像包更新聚类结果 UI。"""
        # 更新中间标题文本
        if hasattr(self.view, 'cluster_title_label'):
            title_text = self._build_cluster_title(
                cluster=cluster,
                cluster_rec=cluster_rec,
                display_index=display_index,
                display_total=display_total,
                total_all=total_all,
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

        # 使用识别阶段缓存的参数和概率刷新右侧表格，不在切换类别时重新提取。
        if hasattr(self.view, "analysis_result_card"):
            self.view.analysis_result_card.update_from_recognition(cluster_rec)

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

    def _build_cluster_title(
        self,
        cluster: ClusterItem,
        cluster_rec: ClusterRecognition | None,
        display_index: int,
        display_total: int,
        total_all: int,
    ) -> str:
        """构建聚类结果标题文本。"""
        if self._is_identified_only_mode() and cluster_rec is not None:
            valid_idx = (cluster_rec.valid_cluster_index or 0) + 1
            return (
                f"{cluster_rec.dim_name}维聚类结果  "
                f"第{valid_idx}/{display_total}类  "
                f"总第{cluster_rec.cluster_index}/{total_all}类"
            )

        return (
            f"{cluster.dim_name}维聚类结果  "
            f"第{display_index}/{display_total}类  "
            f"总第{cluster.cluster_idx}/{total_all}类"
        )
