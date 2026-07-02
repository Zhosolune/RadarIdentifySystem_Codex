"""识别（聚类）核心编排层。"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSlot

from app.app_config import appConfig, qconfig
from app.logger import bind_session_log_context, unbind_session_log_context
from app.model_bootstrap import get_cached_inference_service
from app.signal_bus import signal_bus
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import ClusteringResult, SliceClusterResult
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.recognition_result import RecognitionResult, SliceRecognitionResult
from runtime.threading.identify_worker import IdentifyWorker, IdentifyWorkerResult


LOGGER = logging.getLogger(__name__)


class IdentifyWorkflow(QObject):
    """识别（聚类）工作流编排。

    负责统筹从“切片完成”到“聚类完成”之间的流程调度，
    包括启动子线程、监听进度并发布全局事件。
    严格遵守单一职责原则，只负责调度，不负责具体线程计算。

    Attributes:
        _worker [IdentifyWorker | None]: 绑定的后台识别（聚类）任务子线程实例。
    """

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化工作流实例。

        Args:
            parent [QObject | None]: Qt 挂载父节点。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        # 持有当前运行中的识别线程实例。
        self._worker: Optional[IdentifyWorker] = None
        # 记录当前运行的切片索引，供线程回调落位结果时使用。
        self._active_slice_index: int | None = None
        # 记录当前运行的 session_id，供进度与完成回调做归属校验。
        self._active_session_id: str | None = None
        # 缓存当前运行的 session 引用，由 workflow 统一维护写回。
        self._active_session: ProcessingSession | None = None
        # 缓存当前线程使用的推理服务，避免重复初始化。
        self._inference_service: Optional[object] = None

    def is_running(self) -> bool:
        """返回工作流当前是否正在运行。

        Returns:
            bool: 当前存在运行中的识别线程时返回 True。

        Raises:
            无显式抛出异常。
        """
        return self._worker is not None and self._worker.isRunning()

    @pyqtSlot(ProcessingSession, int)
    def start_identify(
        self, 
        session: ProcessingSession,
        slice_index: int,
    ) -> None:
        """启动指定切片的聚类与识别任务。

        功能描述：
            检查前置条件，初始化推理服务，挂载 IdentifyWorker，绑定进度与完成信号，最后启动线程。
            聚类与识别参数由当前 session 子配置组装后注入 Worker。

        Args:
            session [ProcessingSession]: 目标数据会话。
            slice_index [int]: 切片索引。
            
        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常；前置条件不满足时会记录日志后直接返回。
        """
        session_id = session.session_id
        # 绑定会话日志上下文，使本主线程段日志（模型路径、推理服务创建等）归属当前 session
        log_token = bind_session_log_context(session_id)
        try:
            # 校验切片阶段前置条件，避免在无切片数据时启动线程。
            if not session.is_sliced:
                LOGGER.warning("切片尚未完成，无法启动识别", extra={"session_id": session_id})
                return
            if session.slice_result is None or not (0 <= slice_index < session.slice_result.slice_count):
                LOGGER.warning(
                    "切片索引越界，无法启动识别：%s",
                    slice_index,
                    extra={"session_id": session_id},
                )
                return

            # 避免同一 workflow 实例重复启动并发线程。
            if self._worker is not None and self._worker.isRunning():
                LOGGER.warning("识别工作流正在运行，忽略本次请求", extra={"session_id": session_id})
                return

            # 读取当前 session 选择的模型路径。
            pa_path = session.model_selection.pa_model_path
            dtoa_path = session.model_selection.dtoa_model_path
            LOGGER.info("启用模型路径: PA=%s, DTOA=%s", pa_path, dtoa_path)
            if not pa_path or not dtoa_path:
                LOGGER.warning("session 模型路径为空，推理将无法执行！请在当前 session 中选择 PA 和 DTOA 模型。")
                return

            temp_dir = qconfig.get(appConfig.logDir)
            # 获取缓存推理服务，由 app 层负责模型实例复用或重建。
            self._inference_service = get_cached_inference_service(
                pa_path=pa_path, dtoa_path=dtoa_path, temp_dir=temp_dir
            )
            clustering_config = session.config_snapshot.clustering
            recognition_config = session.config_snapshot.recognition
            extract_config = session.config_snapshot.extract
            # 按当前 session 快照构造聚类参数对象，避免跨函数来回跳转。
            cluster_params = ClusteringParams(
                eps_cf=clustering_config.eps_cf,
                min_pts_cf=clustering_config.min_pts_cf,
                eps_pw=clustering_config.eps_pw,
                min_pts_pw=clustering_config.min_pts_pw,
                eps_doa=clustering_config.eps_doa,
                min_pts_doa=clustering_config.min_pts_doa,
                clip_threshold_doa=clustering_config.clip_threshold_doa,
            )
            # 按当前 session 快照构造识别参数对象，保证线程只接收值对象。
            recognize_params = RecognitionParams(
                tolerance=recognition_config.tolerance,
                min_confidence=recognition_config.min_confidence,
                max_candidates=recognition_config.max_candidates,
            )
            # 按当前 session 快照构造提取参数对象，供识别通过类提取典型参数。
            extract_params = ExtractParams(
                eps_cf=extract_config.eps_cf,
                min_pts_cf=extract_config.min_pts_cf,
                threshold_ratio_cf=extract_config.threshold_ratio_cf,
                eps_pw=extract_config.eps_pw,
                min_pts_pw=extract_config.min_pts_pw,
                threshold_ratio_pw=extract_config.threshold_ratio_pw,
                eps_pri=extract_config.eps_pri,
                min_pts_pri=extract_config.min_pts_pri,
                threshold_ratio_pri=extract_config.threshold_ratio_pri,
                filter_threshold_pri=extract_config.filter_threshold_pri,
                harmonic_tolerance_pri=extract_config.harmonic_tolerance_pri,
            )

            with session.lock:
                # 初始化识别阶段结果容器，由 workflow 统一维护 session 写入。
                if session.cluster_result is None:
                    session.cluster_result = ClusteringResult()
                if session.recognition_result is None:
                    session.recognition_result = RecognitionResult()
                # 先把聚类状态置为运行中，识别状态保持待开始，等线程进入识别阶段再推进。
                session.mark_slice_cluster_running(slice_index)
                session.mark_slice_recognition_pending(slice_index)

            # 发射阶段开始事件，通知 UI 和其它监听者进入 identifying 流程。
            signal_bus.stage_started.emit(session_id, "identifying", slice_index)
            LOGGER.info(
                "发射识别开始事件，当前切片: %d",
                slice_index + 1,
                extra={"session_id": session_id},
            )

            # 创建纯执行线程，并把当前 session 的算法参数快照注入线程。
            self._worker = IdentifyWorker(
                session_id=session_id,
                slice_index=slice_index,
                slice_data=session.slice_result.slices[slice_index],
                inference_service=self._inference_service,
                cluster_params=cluster_params,
                recognize_params=recognize_params,
                extract_params=extract_params,
                parent=self
            )
            self._active_slice_index = slice_index
            # 记录当前运行上下文，便于完成回调和调试定位。
            self._active_session_id = session_id
            self._active_session = session
            self._worker.progress_signal.connect(self._on_worker_progress)
            self._worker.finished_signal.connect(self._on_worker_finished)
            self._worker.start()
        finally:
            # 复位会话日志上下文（Worker 子线程有独立绑定，互不影响）
            unbind_session_log_context(log_token)

    @pyqtSlot(str, str, int, int)
    def _on_worker_progress(
        self,
        session_id: str,
        phase: str,
        current: int,
        total: int,
    ) -> None:
        """子线程进度回调。

        用于在识别（聚类）耗时任务时向外通知进度。

        Args:
            session_id [str]: 会话唯一 ID。
            phase [str]: 当前阶段名称。
            current [int]: 当前进度值。
            total [int]: 总进度值。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        LOGGER.info(
            "识别线程进度更新：phase=%s, current=%d, total=%d",
            phase,
            current,
            total,
            extra={"session_id": session_id},
        )
        # 仅当活动上下文匹配且线程已进入识别阶段时，才推进识别状态。
        if (
            phase == "recognition"
            and session_id == self._active_session_id
            and self._active_session is not None
            and self._active_slice_index is not None
        ):
            with self._active_session.lock:
                # 把当前切片识别状态推进为运行中，保持 cluster/recognition 状态语义分离。
                self._active_session.mark_slice_recognition_running(
                    self._active_slice_index
                )

    @pyqtSlot(str, object)
    def _on_worker_finished(
        self,
        session_id: str,
        result: IdentifyWorkerResult,
    ) -> None:
        """子线程完成回调。

        解析后台任务发送过来的处理结果并向全局发送相应的流程终态事件，
        并释放线程资源。

        Args:
            session_id [str]: 执行会话的唯一 ID。
            result [IdentifyWorkerResult]: 线程执行结果对象。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        active_session = self._active_session
        active_slice_index = self._active_slice_index

        # 容错处理：如果运行上下文已经丢失，则仅清理线程引用，避免悬空状态写回。
        if active_session is None or active_slice_index is None:
            LOGGER.warning("识别线程回调到达时缺少活动 session 上下文", extra={"session_id": session_id})
            self._cleanup_worker_context()
            return

        with active_session.lock:
            if result.success:
                # 确保 session 结果容器存在，再由 workflow 统一写回当前切片结果。
                if active_session.cluster_result is None:
                    active_session.cluster_result = ClusteringResult()
                if active_session.recognition_result is None:
                    active_session.recognition_result = RecognitionResult()

                cluster_result, recognition_result = self._normalize_result_slice_index(
                    result=result,
                    active_slice_index=active_slice_index,
                    session_id=session_id,
                )

                if cluster_result is not None:
                    active_session.cluster_result.slice_results[active_slice_index] = (
                        cluster_result
                    )
                if recognition_result is not None:
                    active_session.recognition_result.slice_results[active_slice_index] = (
                        recognition_result
                    )

                # 线程成功后统一推进当前切片状态。
                active_session.mark_slice_cluster_succeeded(active_slice_index)
                active_session.mark_slice_recognition_succeeded(active_slice_index)
                # 仅当全量切片都已完成识别时，才推进全局阶段到 RECOGNIZED。
                active_session.stage = (
                    ProcessingStage.RECOGNIZED
                    if active_session.are_all_slices_clustered()
                    and active_session.is_recognized
                    else ProcessingStage.SLICED
                )
            else:
                # 聚类失败一定意味着当前切片本轮处理失败。
                active_session.mark_slice_cluster_failed(
                    active_slice_index,
                    result.error_message,
                )
                if result.failed_phase == "recognition":
                    # 只有在线程已经进入识别阶段后，才把识别状态标记为失败。
                    active_session.mark_slice_recognition_failed(
                        active_slice_index,
                        result.error_message,
                    )
                else:
                    # 如果失败发生在聚类阶段，则识别状态仍保持未开始。
                    active_session.mark_slice_recognition_pending(
                        active_slice_index
                    )
                active_session.stage = ProcessingStage.SLICED

        # 发射处理结果相关的生命周期信号，供 UI 和其它监听方刷新状态。
        if result.success:
            signal_bus.stage_finished.emit(session_id, "identifying", active_slice_index)
            LOGGER.info(
                "发射识别完成事件，当前切片: %s",
                active_slice_index + 1,
                extra={"session_id": session_id},
            )
        else:
            signal_bus.stage_failed.emit(
                session_id,
                "identifying",
                active_slice_index,
                result.error_message,
            )
            LOGGER.error(
                "发射识别失败事件，当前切片: %s, 阶段: %s, 错误: %s",
                active_slice_index,
                result.failed_phase,
                result.error_message,
                extra={"session_id": session_id},
            )
        self._cleanup_worker_context()

    def _cleanup_worker_context(self) -> None:
        """释放线程对象并清空当前运行上下文。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        if self._worker is not None:
            # 延迟销毁线程对象，遵循 Qt 对象生命周期管理方式。
            self._worker.deleteLater()
            self._worker = None
        # 清空活动运行上下文，避免后续回调误写旧 session。
        self._active_slice_index = None
        self._active_session_id = None
        self._active_session = None

    def _normalize_result_slice_index(
        self,
        result: IdentifyWorkerResult,
        active_slice_index: int,
        session_id: str,
    ) -> tuple[SliceClusterResult | None, SliceRecognitionResult | None]:
        """统一 worker 结果对象中的切片索引。"""
        cluster_result = result.cluster_result
        recognition_result = result.recognition_result
        if cluster_result is not None and cluster_result.slice_idx != active_slice_index:
            LOGGER.warning(
                "识别结果切片索引与启动索引不一致，已校正：result=%d, active=%d",
                cluster_result.slice_idx,
                active_slice_index,
                extra={"session_id": session_id},
            )
            # 以 workflow 启动索引作为唯一写回口径，避免结果元数据和字典键漂移。
            cluster_result.slice_idx = active_slice_index
        if recognition_result is not None and recognition_result.slice_index != active_slice_index:
            LOGGER.warning(
                "识别记录切片索引与启动索引不一致，已校正：result=%d, active=%d",
                recognition_result.slice_index,
                active_slice_index,
                extra={"session_id": session_id},
            )
            # SliceRecognitionResult 是冻结值对象，需要创建新实例替换索引字段。
            recognition_result = SliceRecognitionResult(
                slice_index=active_slice_index,
                valid_clusters=recognition_result.valid_clusters,
                invalid_clusters=recognition_result.invalid_clusters,
            )
        return cluster_result, recognition_result
