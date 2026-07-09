"""识别（聚类）工作线程。

功能描述：
    作为 runtime/threading 层的具体执行单元，在子线程中调用
    ``core.identify_pipeline.SliceIdentifyPipeline`` 执行单切片的 CF/PW/DOA 聚类
    与识别流程，并把结果通过 Qt 信号回传到工作流。该模块不承载任何算法
    实现，仅负责线程调度、参数校验、进度信号发射和异常归属处理。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.logger import bind_session_log_context, unbind_session_log_context
from core.identify_pipeline import (
    PHASE_CLUSTERING,
    IdentifyPipelineContext,
    SliceIdentifyPipeline,
)
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import SliceClusterResult
from core.models.recognition_result import SliceRecognitionResult
from core.recognition import InferenceService


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentifyWorkerResult:
    """识别线程执行结果。

    Attributes:
        success [bool]: 线程是否执行成功。
        cluster_result [SliceClusterResult | None]: 当前切片的聚类结果，失败时为 None。
        recognition_result [SliceRecognitionResult | None]: 当前切片的识别结果，失败时为 None。
        failed_phase [str]: 失败发生的阶段名称，成功时为空字符串。
        error_message [str]: 失败消息，成功时为空字符串。
    """

    success: bool
    cluster_result: SliceClusterResult | None = None
    recognition_result: SliceRecognitionResult | None = None
    failed_phase: str = ""
    error_message: str = ""


class IdentifyWorker(QThread):
    """识别（聚类+识别）后台工作线程。

    功能描述：
        作为 runtime/threading 层的具体执行单元，在子线程中调用 core 层的
        ``SliceIdentifyPipeline`` 完成单切片处理。本类只负责线程调度、参数
        快照校验、进度与完成信号的发射，业务算法与流程编排均在 core 层实现。

    Attributes:
        finished_signal [pyqtSignal]: 线程完成信号，参数为 session_id 和执行结果对象。
        progress_signal [pyqtSignal]: 线程进度信号，参数为 session_id、阶段名、当前进度和总进度。
    """

    finished_signal = pyqtSignal(str, object)
    progress_signal = pyqtSignal(str, str, int, int)

    def __init__(
        self,
        session_id: str,
        slice_index: int,
        slice_data: Any,
        inference_service: InferenceService,
        cluster_params: ClusteringParams,
        recognize_params: RecognitionParams,
        extract_params: ExtractParams | None = None,
        parent: QObject | None = None,
    ) -> None:
        """初始化识别（聚类）工作线程。

        Args:
            session_id [str]: 当前流程所属的会话 ID，仅用于日志和回调归属。
            slice_index [int]: 需要进行识别聚类的切片索引。
            slice_data [Any]: 需要执行聚类与识别的单切片数据对象。
            inference_service [InferenceService]: 注入的防腐层推理服务。
            cluster_params [ClusteringParams]: 当前 session 的聚类参数快照。
            recognize_params [RecognitionParams]: 当前 session 的识别参数快照。
            extract_params [ExtractParams | None]: 当前 session 的参数提取快照；为 None 时使用默认值。
            parent [QObject | None]: 挂载的 Qt 父节点。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self._session_id = session_id
        self._slice_index = slice_index
        self._slice_data = slice_data
        self._inference_service = inference_service
        self._cluster_params = cluster_params
        self._recognize_params = recognize_params
        self._extract_params = extract_params or ExtractParams()
        # 缓存流程上下文，异常时供上层读取失败阶段。
        self._pipeline_context = IdentifyPipelineContext(
            on_recognition_started=self._emit_recognition_progress,
        )

    def run(self) -> None:
        """执行当前切片的聚类与识别线程任务。

        功能描述：
            校验切片输入、发射聚类阶段起始进度，调用 core 层的
            ``SliceIdentifyPipeline`` 完成级联聚类与识别，并根据流程上下文的
            当前阶段决定成功或失败信号的载荷。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            RuntimeError: 当切片数据为空时抛出，并由本方法捕获后发出失败信号。
            ValueError: 当目标切片索引越界时抛出，并由本方法捕获后发出失败信号。

        Example:
            >>> hasattr(IdentifyWorker, "finished_signal")
            True
        """
        session_id = self._session_id
        # 绑定会话日志上下文，使本线程内 clustering/recognition/onnx_service 日志自动带上 session_id
        log_token = bind_session_log_context(session_id)
        try:
            # 校验切片数据存在，避免线程空跑。
            if self._slice_data is None:
                raise RuntimeError("目标切片数据为空，无法进行聚类/识别")
            # 校验切片索引合法，避免后续日志和结果落位错乱。
            if self._slice_index < 0:
                raise ValueError(f"切片索引 {self._slice_index} 无效或越界")

            LOGGER.info(
                "开始聚类处理，当前切片: %d",
                self._slice_index + 1,
                extra={"session_id": session_id},
            )
            # 记录聚类参数快照，便于问题排查与回放分析。
            self._log_pipeline_params()

            # 标记进入聚类阶段并发射流程起始进度，通知 workflow 已进入聚类阶段。
            self._pipeline_context.enter_clustering()
            self.progress_signal.emit(session_id, "clustering", 0, 2)

            # 构造切片识别编排器，线程只负责调度与信号发射。
            pipeline = SliceIdentifyPipeline(
                inference_service=self._inference_service,
                cluster_params=self._cluster_params,
                recognize_params=self._recognize_params,
                extract_params=self._extract_params,
                context=self._pipeline_context,
            )
            # 调用 core 层完成级联聚类与识别。
            slice_cluster_res, slice_recognition_res = pipeline.run(self._slice_data)
            # 记录聚类阶段输出规模，便于观察不同参数下的聚类密度。
            LOGGER.info(
                "切片 %d 聚类完成，产生 %d 个簇",
                self._slice_index + 1,
                len(slice_cluster_res.clusters),
                extra={"session_id": session_id},
            )
            # 记录最终有效簇数量，便于和 UI 展示及 session 结果核对。
            LOGGER.info(
                "切片 %d 聚类与识别处理完成，产生 %d 个有效簇",
                self._slice_index + 1,
                len(slice_recognition_res.valid_clusters),
                extra={"session_id": session_id},
            )

            # 发射完成进度，通知 workflow 可以进入写回与阶段推进。
            self.progress_signal.emit(session_id, "done", 2, 2)
            self.finished_signal.emit(
                session_id,
                IdentifyWorkerResult(
                    success=True,
                    cluster_result=slice_cluster_res,
                    recognition_result=slice_recognition_res,
                ),
            )

        except Exception as e:
            LOGGER.error(
                "聚类与识别过程失败: %s",
                e,
                exc_info=True,
                extra={"session_id": session_id},
            )
            self.finished_signal.emit(
                session_id,
                IdentifyWorkerResult(
                    success=False,
                    failed_phase=self._resolve_failed_phase(),
                    error_message=str(e),
                ),
            )
        finally:
            # 复位会话日志上下文，防止线程复用导致 session_id 泄漏
            unbind_session_log_context(log_token)

    def _emit_recognition_progress(self) -> None:
        """由流程上下文触发的识别阶段进度回调。"""
        # 首次进入识别阶段时发一次进度，避免多轮 DOA 复检重复刷状态。
        self.progress_signal.emit(self._session_id, "recognition", 1, 2)

    def _log_pipeline_params(self) -> None:
        """记录聚类与识别参数快照。"""
        clustering_params = self._cluster_params
        recognition_params = self._recognize_params
        LOGGER.info(
            "参数: eps_cf=%.4f, min_pts_cf=%d, eps_pw=%.4f, min_pts_pw=%d, "
            "eps_doa=%.4f, min_pts_doa=%d, clip_doa=%.2f, min_cluster_size=%d, "
            "tol=%.2f, min_conf=%.2f, slice_index=%d",
            clustering_params.eps_cf,
            clustering_params.min_pts_cf,
            clustering_params.eps_pw,
            clustering_params.min_pts_pw,
            clustering_params.eps_doa,
            clustering_params.min_pts_doa,
            clustering_params.clip_threshold_doa,
            clustering_params.min_cluster_size,
            recognition_params.tolerance,
            recognition_params.min_confidence,
            self._slice_index,
            extra={"session_id": self._session_id},
        )

    def _resolve_failed_phase(self) -> str:
        """获取当前流程上下文中记录的失败阶段名。"""
        # 校验阶段异常时上下文尚未推进，此时用 clustering 兜底以匹配旧行为。
        return self._pipeline_context.current_phase or PHASE_CLUSTERING
