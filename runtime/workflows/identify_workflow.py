"""识别（聚类）核心编排层。"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSlot

from app.app_config import appConfig, qconfig
from app.logger import bind_session_log_context, unbind_session_log_context
from app.model_bootstrap import get_cached_inference_service
from app.signal_bus import signal_bus
from core.models.algorithm_params import ClusteringParams, RecognitionParams
from core.models.processing_session import ProcessingSession
from runtime.threading.identify_worker import IdentifyWorker


LOGGER = logging.getLogger(__name__)


def _cluster_params_from_session(session: ProcessingSession) -> ClusteringParams:
    """从 session 子配置组装聚类参数。

    Args:
        session [ProcessingSession]: 当前识别流程所属 session。

    Returns:
        ClusteringParams: 根据 session 子配置生成的聚类参数。

    Raises:
        无显式抛出异常。

    Example:
        >>> session = ProcessingSession()
        >>> _cluster_params_from_session(session).eps_cf
        2.0
    """
    cfg = session.config_snapshot.clustering
    return ClusteringParams(
        eps_cf=cfg.eps_cf,
        min_pts_cf=cfg.min_pts_cf,
        eps_pw=cfg.eps_pw,
        min_pts_pw=cfg.min_pts_pw,
        eps_doa=cfg.eps_doa,
        min_pts_doa=cfg.min_pts_doa,
        clip_threshold_doa=cfg.clip_threshold_doa,
    )


def _recognition_params_from_session(session: ProcessingSession) -> RecognitionParams:
    """从 session 子配置组装识别参数。

    Args:
        session [ProcessingSession]: 当前识别流程所属 session。

    Returns:
        RecognitionParams: 根据 session 子配置生成的识别参数。

    Raises:
        无显式抛出异常。

    Example:
        >>> session = ProcessingSession()
        >>> _recognition_params_from_session(session).max_candidates
        5
    """
    cfg = session.config_snapshot.recognition
    return RecognitionParams(
        tolerance=cfg.tolerance,
        min_confidence=cfg.min_confidence,
        max_candidates=cfg.max_candidates,
    )


class IdentifyWorkflow(QObject):
    """识别（聚类）工作流编排。

    负责统筹从“切片完成”到“聚类完成”之间的流程调度，
    包括启动子线程、监听进度并发布全局事件。
    严格遵守单一职责原则，只负责调度，不负责具体线程计算。

    Attributes:
        _worker (IdentifyWorker | None): 绑定的后台识别（聚类）任务子线程实例。
    """

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化工作流实例。

        Args:
            parent (QObject | None, optional): Qt 挂载父节点。
        """
        super().__init__(parent)
        self._worker: Optional[IdentifyWorker] = None
        self._active_slice_index: int | None = None
        self._active_session_id: str | None = None
        self._inference_service: Optional[object] = None

    def is_running(self) -> bool:
        """返回工作流当前是否正在运行。"""
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
            session (ProcessingSession): 目标数据会话。
            slice_index (int): 切片索引。
            
        Returns:
            None
        """
        session_id = session.session_id
        # 绑定会话日志上下文，使本主线程段日志（模型路径、推理服务创建等）归属当前 session
        log_token = bind_session_log_context(session_id)
        try:
            if not session.is_sliced:
                LOGGER.warning("切片尚未完成，无法启动识别", extra={"session_id": session_id})
                return

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
            # 从 model_bootstrap 获取缓存的推理服务，内部自动处理复用或重建
            self._inference_service = get_cached_inference_service(
                pa_path=pa_path, dtoa_path=dtoa_path, temp_dir=temp_dir
            )

            # 发送流程开始全局信号
            signal_bus.stage_started.emit(session_id, "identifying", slice_index)
            LOGGER.info(
                "发射识别开始事件，当前切片: %d",
                slice_index,
                extra={"session_id": session_id},
            )

            # 挂载计算线程，并在线程结束时挂接回调
            self._worker = IdentifyWorker(
                session=session,
                slice_index=slice_index,
                inference_service=self._inference_service,
                cluster_params=_cluster_params_from_session(session),
                recognize_params=_recognition_params_from_session(session),
                parent=self
            )
            self._active_slice_index = slice_index
            # 记录当前运行 session，便于完成回调和调试定位。
            self._active_session_id = session_id
            self._worker.progress_signal.connect(self._on_worker_progress)
            self._worker.finished_signal.connect(self._on_worker_finished)
            self._worker.start()
        finally:
            # 复位会话日志上下文（Worker 子线程有独立绑定，互不影响）
            unbind_session_log_context(log_token)

    @pyqtSlot(str, int, int)
    def _on_worker_progress(self, session_id: str, current: int, total: int) -> None:
        """子线程进度回调。

        用于在识别（聚类）耗时任务时向外通知进度。

        Args:
            session_id (str): 会话唯一ID。
            current (int): 当前已处理的切片数。
            total (int): 总切片数。
        """
        # 如果需要在 UI 上显示进度，可通过 signal_bus 增加进度信号
        # 这里暂时只记录日志
        pass

    @pyqtSlot(str, bool, str)
    def _on_worker_finished(self, session_id: str, success: bool, error_msg: str) -> None:
        """子线程完成回调。

        解析后台任务发送过来的处理结果并向全局发送相应的流程终态事件，
        并释放线程资源。

        Args:
            session_id (str): 执行会话的唯一ID。
            success (bool): 标志线程执行是否成功。
            error_msg (str): 如果执行失败附带的报错信息。
        """
        # 发送处理结果相关的生命周期信号
        if success:
            signal_bus.stage_finished.emit(session_id, "identifying", self._active_slice_index)
            LOGGER.info(
                "发射识别完成事件，当前切片: %s",
                self._active_slice_index,
                extra={"session_id": session_id},
            )
        else:
            signal_bus.stage_failed.emit(session_id, "identifying", self._active_slice_index, error_msg)
            LOGGER.error(
                "发射识别失败事件，当前切片: %s, 错误: %s",
                self._active_slice_index,
                error_msg,
                extra={"session_id": session_id},
            )
        
        # 释放线程对象
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self._active_slice_index = None
        self._active_session_id = None
