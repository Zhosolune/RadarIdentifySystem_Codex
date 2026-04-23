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
from runtime.workflows.slice_workflow import slice_workflow
from runtime.workflows.render_workflow import render_workflow
from runtime.workflows.identify_workflow import identify_workflow
from infra.plotting.facades import render_cluster_images
from core.models.cluster_result import ClusterState, ClusterItem
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
        self._image_cache: OrderedDict[int, RenderedImageBundle] = OrderedDict[int, RenderedImageBundle]()
        self._current_slice_index = 0
        self._max_cache_size = 50
        
        # 聚类相关状态
        self._current_cluster_index = 0

        # 绑定按钮点击事件
        self.view.navigation_control_card.start_slicing_button.clicked.connect(self.handle_slice)
        self.view.navigation_control_card.start_recognition_button.clicked.connect(self.handle_identify)
        
        # 绑定标题旁边的透明导航按钮
        self.view.prev_slice_button.clicked.connect(self._on_prev_slice)
        self.view.next_slice_button.clicked.connect(self._on_next_slice)
        self.view.prev_cluster_button.clicked.connect(self._on_prev_cluster)
        self.view.next_cluster_button.clicked.connect(self._on_next_cluster)

        # 绑定全局生命周期信号与数据就绪信号
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)
        signal_bus.slice_image_ready.connect(self._on_slice_image_ready)
        signal_bus.cluster_image_ready.connect(self._on_cluster_image_ready)

        # 绑定重绘请求信号
        self.view.redraw_option_card.redraw_requested.connect(self._on_redraw_requested)

        # 状态自检定时器
        self._check_timer = QTimer(self.view)
        self._check_timer.timeout.connect(self._check_workflow_state)
        self._check_timer.start(1000)

    def _check_workflow_state(self) -> None:
        """定期检查工作流状态，防止信号丢失导致 UI 卡死。"""
        if self._processing_dialog is None:
            return
            
        # 此时有进度条对话框正在显示
        is_slicing = slice_workflow.is_running()
        is_identifying = identify_workflow.is_running()
        
        # 如果两者都不在运行，说明出现异常导致信号丢失
        if not is_slicing and not is_identifying:
            self._processing_dialog.close()
            self._processing_dialog = None
            
            # 恢复按钮状态
            self.view.navigation_control_card.start_slicing_button.setEnabled(True)
            self.view.navigation_control_card.start_recognition_button.setEnabled(True)
            
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
        参数说明：
            session_id (str): 会话唯一标识。
            stage (str): 阶段名称。
            slice_index (int | None): 切片索引；全局流程时为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        if session_id != self.view._test_session.session_id:
            return

        if stage == "slicing":
            self._handle_slicing_finished()
        elif stage == "identifying":
            self._handle_identifying_finished(slice_index)

    def _on_stage_failed(self, session_id: str, stage: str, slice_index: int | None, error_msg: str) -> None:
        """处理阶段失败信号。

        功能描述：
            校验会话 ID 与阶段，若匹配则恢复按钮状态并弹出错误提示。
        """
        if session_id != self.view._test_session.session_id:
            return

        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_slicing_button.setEnabled(True)
        self.view.navigation_control_card.start_recognition_button.setEnabled(True)
        
        # 弹出错误提示
        stage_name = "切片处理" if stage == "slicing" else "聚类处理"
        slice_suffix = ""
        if slice_index is not None:
            # 拼接切片提示
            slice_suffix = f"（第 {slice_index + 1} 片）"
        InfoBar.error(
            title=f"{stage_name}失败{slice_suffix}",
            content=f"发生错误:\n{error_msg}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self.view
        )

    def _handle_slicing_finished(self) -> None:
        """处理切片完成后的逻辑。"""
        if self._processing_dialog:
            self._processing_dialog.close()
            self._processing_dialog = None
            
        # 恢复按钮状态
        self.view.navigation_control_card.start_slicing_button.setEnabled(True)
        
        # 清空缓存并加载第0片
        self._image_cache.clear()
        self._current_cluster_index = 0
        self._load_slice(0)
        self._clear_cluster_ui()
        self._update_cluster_navigation_buttons()
        
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
        
        参数说明：
            slice_index (int): 请求重绘的切片编号。
        """
        # 清空缓存并重新触发绘制
        self._image_cache.clear()
        self._load_slice(self._current_slice_index)
        LOGGER.info(f"收到重绘请求，已清空缓存并重新渲染切片编号: {self._current_slice_index}")

    def _on_prev_slice(self) -> None:
        """处理上一片按钮点击。"""
        self._load_slice(self._current_slice_index - 1)
        self._current_cluster_index = 0
        self._load_cluster_image()

    def _on_next_slice(self) -> None:
        """处理下一片按钮点击。"""
        self._load_slice(self._current_slice_index + 1)
        self._current_cluster_index = 0
        self._load_cluster_image()

    def _on_prev_cluster(self) -> None:
        """处理上一类别按钮点击。"""
        self._current_cluster_index -= 1
        self._load_cluster_image()

    def _on_next_cluster(self) -> None:
        """处理下一类别按钮点击。"""
        self._current_cluster_index += 1
        self._load_cluster_image()

    def _update_navigation_buttons(self) -> None:
        """更新导航按钮可用状态。"""
        session = self.view._test_session
        if not session or not session.slice_result:
            return
        total = session.slice_result.slice_count
        self.view.prev_slice_button.setEnabled(self._current_slice_index > 0)
        self.view.next_slice_button.setEnabled(self._current_slice_index < total - 1)

    def _update_cluster_navigation_buttons(self) -> None:
        """更新聚类类别导航按钮可用状态。"""
        session = self.view._test_session
        if not session or not session.is_slice_clustered(self._current_slice_index):
            self.view.prev_cluster_button.setEnabled(False)
            self.view.next_cluster_button.setEnabled(False)
            return

        cluster_res = session.cluster_result.slice_results.get(self._current_slice_index)
        if not cluster_res or not cluster_res.clusters:
            self.view.prev_cluster_button.setEnabled(False)
            self.view.next_cluster_button.setEnabled(False)
            return
            
        total = len(cluster_res.clusters)
        self.view.prev_cluster_button.setEnabled(self._current_cluster_index > 0)
        self.view.next_cluster_button.setEnabled(self._current_cluster_index < total - 1)

    def _load_slice(self, index: int) -> None:
        """加载并展示指定索引的切片图像。"""
        session = self.view._test_session
        if not session or not session.slice_result:
            return
        if index < 0 or index >= session.slice_result.slice_count:
            return

        self._current_slice_index = index
        self._update_navigation_buttons()

        # 尝试命中缓存
        if index in self._image_cache:
            bundle = self._image_cache.pop(index)
            self._image_cache[index] = bundle  # 更新 LRU 顺序
            self._update_ui_with_bundle(bundle, index)
            LOGGER.info(f"加载切片 {index + 1} 命中缓存，当前缓存容量: {len(self._image_cache)}/{self._max_cache_size}", extra={"session_id": session.session_id})
        else:
            # 缓存未命中，启动后台渲染
            LOGGER.info(f"加载切片 {index + 1} 未命中缓存，开始后台渲染", extra={"session_id": session.session_id})
            render_workflow.start_render(
                session=session, 
                slice_index=index, 
                is_cluster_render=False
            )

    def _on_slice_image_ready(self, session_id: str, slice_index: int, bundle: RenderedImageBundle) -> None:
        """接收渲染图片结果并展示到卡片。

        功能描述：
            校验会话 ID，将渲染结果缓存，如果是当前索引则更新 UI。
        """
        if session_id != self.view._test_session.session_id:
            return

        # 存入 LRU 缓存
        if slice_index in self._image_cache:
            self._image_cache.pop(slice_index)
        self._image_cache[slice_index] = bundle

        # 淘汰超出容量的最早数据
        while len(self._image_cache) > self._max_cache_size:
            self._image_cache.popitem(last=False)

        # 仅在回调回来的切片是当前用户正在查看的切片时，才刷新 UI
        if slice_index == self._current_slice_index:
            self._update_ui_with_bundle(bundle, slice_index)

    def _load_cluster_image(self) -> None:
        """加载并展示当前切片下指定索引的聚类结果图像。"""
        session = self.view._test_session
        if not session or not session.is_slice_clustered(self._current_slice_index):
            self._clear_cluster_ui()
            self._update_cluster_navigation_buttons()
            return

        if session.cluster_result is None:
            self._clear_cluster_ui()
            self._update_cluster_navigation_buttons()
            return

        cluster_res = session.cluster_result.slice_results.get(self._current_slice_index)
        if not cluster_res or not cluster_res.clusters:
            self._clear_cluster_ui()
            self._update_cluster_navigation_buttons()
            return
            
        # 约束索引范围
        if self._current_cluster_index < 0:
            self._current_cluster_index = 0
        elif self._current_cluster_index >= len(cluster_res.clusters):
            self._current_cluster_index = len(cluster_res.clusters) - 1
            
        self._update_cluster_navigation_buttons()
        
        # 启动后台渲染类别图像
        LOGGER.info(f"加载切片 {self._current_slice_index + 1} 的类别 {self._current_cluster_index + 1} 图像，启动后台渲染", extra={"session_id": session.session_id})
        render_workflow.start_render(
            session=session, 
            slice_index=self._current_slice_index, 
            cluster_index=self._current_cluster_index,
            is_cluster_render=True
        )

    def _on_cluster_image_ready(self, session_id: str, slice_index: int, cluster_index: int, bundle: RenderedImageBundle) -> None:
        """接收类别渲染图片结果并展示到卡片。

        功能描述：
            校验会话 ID 及当前显示的索引，将结果渲染到 UI。
        """
        if session_id != self.view._test_session.session_id:
            return
            
        if slice_index != self._current_slice_index or cluster_index != self._current_cluster_index:
            return
            
        session = self.view._test_session
        if not session.is_slice_clustered(slice_index) or session.cluster_result is None:
            return

        cluster_res = session.cluster_result.slice_results.get(slice_index)
        if not cluster_res or not cluster_res.clusters:
            return
            
        current_cluster = cluster_res.clusters[cluster_index]
        self._update_cluster_ui_with_bundle(bundle, current_cluster, len(cluster_res.clusters))

    def _clear_cluster_ui(self) -> None:
        """清空聚类结果展示区域。"""
        if hasattr(self.view, 'cluster_title_label'):
            self.view.cluster_title_label.setText("聚类结果暂无")
            
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
        for card in cards:
            card.set_image(empty_image)

    def _update_cluster_ui_with_bundle(self, bundle: RenderedImageBundle, cluster_item: ClusterItem, total_clusters: int) -> None:
        """使用指定的聚类图像包更新聚类结果 UI。"""
        # 更新中间标题
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

    def _update_ui_with_bundle(self, bundle: RenderedImageBundle, slice_index: int) -> None:
        """使用指定的图像包更新 UI。"""
        session = self.view._test_session
        total = session.slice_result.slice_count if session.slice_result else 0

        # 更新左侧标题
        if hasattr(self.view, 'slice_title_label'):
            self.view.slice_title_label.setText(f"第 {slice_index + 1} / {total} 个切片数据  原始图像")
        
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
                cards[dim_name].set_image(q_image)
