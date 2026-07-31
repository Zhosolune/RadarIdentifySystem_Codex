"""全速处理后台线程。

线程按固定顺序执行切片、逐片聚类识别、逐片合并和 Excel 保存。它只消费
首次启动时冻结的请求快照，并返回完整结果；运行期间不读取 UI 或可变全局配置。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import threading

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.logger import bind_session_log_context, unbind_session_log_context
from core.identify_pipeline import SliceIdentifyPipeline
from core.merge import MergePipeline
from core.merge_strategy import HybridParameterMergeStrategy
from core.models.algorithm_params import (
    ClusteringParams,
    ExtractParams,
    RecognitionParams,
)
from core.models.cluster_result import ClusteringResult
from core.models.merge_result import (
    MergePlan,
    MergeResult,
    SliceMergeResult,
)
from core.models.recognition_result import RecognitionResult
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.slice_result import PreprocessResult, SliceResult
from core.slicing import slice_from_preprocess
from infra.excel_result_exporter import (
    ExcelResultExporter,
    FullSpeedExportData,
)
from infra.onnx_service import OnnxInferenceService


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FullSpeedExecutionRequest:
    """全速线程的冻结输入。

    Attributes:
        session_id: Session 唯一标识。
        data_package_id: 来源数据包 ID。
        display_name: Session 展示名称。
        source_path: 原始文件路径。
        source_type: 原始文件类型。
        created_at: Session 创建时间。
        preprocess_result: 数据池共享的只读预处理结果。
        config_snapshot: 首次启动时冻结的参数快照。
        model_selection: 首次启动时冻结的模型路径。
        output_dir: Excel 保存目录。
        temp_dir: ONNX 推理中间文件目录。
        compute_device: ONNX 推理设备偏好，取值为 AUTO、CPU 或 GPU。
        recognition_workers: 单任务簇级识别并发线程上限。
    """

    session_id: str
    data_package_id: str | None
    display_name: str
    source_path: str
    source_type: str
    created_at: datetime
    preprocess_result: PreprocessResult
    config_snapshot: SessionConfigSnapshot
    model_selection: SessionModelSelection
    output_dir: str
    temp_dir: str
    compute_device: str = "AUTO"
    recognition_workers: int = 2


@dataclass(frozen=True, slots=True)
class FullSpeedWorkerResult:
    """全速线程终态结果。

    Attributes:
        success: 是否完整执行并保存成功。
        cancelled: 是否由用户取消。
        slice_result: 成功时的切片结果。
        clustering_result: 成功时的全量聚类结果。
        recognition_result: 成功时的全量识别结果。
        merge_plan: 成功时的全量合并计划。
        merge_result: 成功时的独立合并结果。
        output_file: 成功生成的 Excel 文件路径。
        error_message: 失败原因。
    """

    success: bool
    cancelled: bool = False
    slice_result: SliceResult | None = None
    clustering_result: ClusteringResult | None = None
    recognition_result: RecognitionResult | None = None
    merge_plan: MergePlan | None = None
    merge_result: MergeResult | None = None
    output_file: str = ""
    error_message: str = ""


class _FullSpeedCancelled(RuntimeError):
    """表示任务在安全检查点响应了取消请求。"""


class FullSpeedWorker(QThread):
    """在独立线程中执行一个完整全速 Session。

    Attributes:
        progress_signal: 进度信号，依次携带 Session ID、阶段、当前切片、
            总切片、百分比、说明和是否处于导出阶段。
        finished_signal: 终态信号，携带 Session ID 与
            :class:`FullSpeedWorkerResult`。
    """

    progress_signal = pyqtSignal(str, str, int, int, int, str, bool)
    finished_signal = pyqtSignal(str, object)

    def __init__(
        self,
        request: FullSpeedExecutionRequest,
        parent: QObject | None = None,
    ) -> None:
        """初始化全速处理线程。

        Args:
            request [FullSpeedExecutionRequest]: 已冻结的执行请求。
            parent [QObject | None]: Qt 父对象，默认不挂载。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self._request = request
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        """请求任务在下一个安全检查点停止。

        Returns:
            None: 无返回值。
        """
        self._cancel_event.set()

    def run(self) -> None:
        """连续执行全速流水线并通过信号返回终态。

        Returns:
            None: 结果通过 ``finished_signal`` 发出。

        Raises:
            无。内部异常统一转换为失败结果。
        """
        request = self._request
        log_token = bind_session_log_context(request.session_id)
        try:
            LOGGER.info(
                "全速任务启动: package_id=%s, source=%s, output_dir=%s, "
                "compute_device=%s, recognition_workers=%d, "
                "onnx_intra_op_threads=1",
                request.data_package_id,
                request.source_path,
                request.output_dir,
                request.compute_device,
                request.recognition_workers,
            )
            result = self._execute()
            self.finished_signal.emit(request.session_id, result)
        except _FullSpeedCancelled:
            LOGGER.info("全速任务已在安全检查点取消")
            self.finished_signal.emit(
                request.session_id,
                FullSpeedWorkerResult(success=False, cancelled=True),
            )
        except Exception as error:
            LOGGER.error("全速任务失败: %s", error, exc_info=True)
            self.finished_signal.emit(
                request.session_id,
                FullSpeedWorkerResult(
                    success=False,
                    error_message=str(error),
                ),
            )
        finally:
            unbind_session_log_context(log_token)

    def _execute(self) -> FullSpeedWorkerResult:
        """执行同步流水线并返回完整结果。"""
        request = self._request
        self._check_cancelled()
        self._emit_progress("切片处理", 0, 0, 1, "正在按 250ms 窗口切片")
        slice_result = slice_from_preprocess(
            request.preprocess_result,
            slice_length=2_500_000,
            session_id=request.session_id,
        )
        total_slices = slice_result.slice_count
        self._emit_progress(
            "切片完成",
            0,
            total_slices,
            5,
            f"生成 {total_slices} 个有效切片",
        )

        clustering_result = ClusteringResult()
        recognition_result = RecognitionResult()
        merge_plan = MergePlan()
        merge_result = MergeResult()

        if total_slices:
            inference_service = self._create_inference_service()
            cluster_params = self._build_cluster_params()
            recognition_params = self._build_recognition_params()
            extract_params = self._build_extract_params()
            merge_strategy = HybridParameterMergeStrategy()
            merge_pipeline = MergePipeline(extract_params)

            for offset, current_slice in enumerate(slice_result.slices):
                self._check_cancelled()
                current_number = offset + 1
                start_progress = 5 + int(85 * offset / total_slices)
                self._emit_progress(
                    "聚类与识别",
                    current_number,
                    total_slices,
                    start_progress,
                    f"正在处理第 {current_number}/{total_slices} 个切片",
                )
                identify_pipeline = SliceIdentifyPipeline(
                    inference_service=inference_service,
                    cluster_params=cluster_params,
                    recognize_params=recognition_params,
                    extract_params=extract_params,
                    recognition_max_workers=(
                        self._request.recognition_workers
                    ),
                )
                cluster_slice, recognition_slice = identify_pipeline.run(
                    current_slice
                )
                clustering_result.slice_results[current_slice.index] = (
                    cluster_slice
                )
                recognition_result.slice_results[current_slice.index] = (
                    recognition_slice
                )

                self._check_cancelled()
                merge_progress = 5 + int(
                    85 * (offset + 0.8) / total_slices
                )
                self._emit_progress(
                    "自动合并",
                    current_number,
                    total_slices,
                    merge_progress,
                    f"正在判别第 {current_number}/{total_slices} 个切片的合并候选",
                )
                slice_plan = merge_strategy.build_plan(
                    cluster_slice,
                    recognition_slice,
                )
                merge_plan.slice_plans[current_slice.index] = slice_plan
                merged_clusters = (
                    merge_pipeline.run_plan(
                        slice_plan,
                        cluster_slice,
                        recognition_slice,
                    )
                    if slice_plan.groups
                    else ()
                )
                merge_result.slice_results[current_slice.index] = (
                    SliceMergeResult(
                        slice_index=current_slice.index,
                        merged_clusters=list(merged_clusters),
                    )
                )
                end_progress = 5 + int(
                    85 * (offset + 1) / total_slices
                )
                self._emit_progress(
                    "切片处理完成",
                    current_number,
                    total_slices,
                    end_progress,
                    f"第 {current_number}/{total_slices} 个切片处理完成",
                )

        self._check_cancelled()
        self._emit_progress(
            "保存 Excel",
            total_slices,
            total_slices,
            92,
            "正在生成结果工作簿",
            exporting=True,
        )
        export_data = FullSpeedExportData(
            session_id=request.session_id,
            display_name=request.display_name,
            source_path=request.source_path,
            source_type=request.source_type,
            data_package_id=request.data_package_id,
            created_at=request.created_at,
            config_snapshot=request.config_snapshot,
            model_selection=request.model_selection,
            slice_result=slice_result,
            clustering_result=clustering_result,
            recognition_result=recognition_result,
            merge_result=merge_result,
        )
        output_path = ExcelResultExporter().export(
            export_data,
            Path(request.output_dir),
        )
        LOGGER.info("全速任务结果已保存: %s", output_path)
        self._emit_progress(
            "保存完成",
            total_slices,
            total_slices,
            100,
            str(output_path),
            exporting=True,
        )
        return FullSpeedWorkerResult(
            success=True,
            slice_result=slice_result,
            clustering_result=clustering_result,
            recognition_result=recognition_result,
            merge_plan=merge_plan,
            merge_result=merge_result,
            output_file=str(output_path),
        )

    def _create_inference_service(self) -> OnnxInferenceService:
        """为当前全速 Session 创建独立 ONNX 推理服务。"""
        selection = self._request.model_selection
        if not selection.pa_model_path or not selection.dtoa_model_path:
            raise ValueError("全速任务缺少 PA 或 DTOA 模型")
        return OnnxInferenceService(
            pa_model_path=selection.pa_model_path,
            dtoa_model_path=selection.dtoa_model_path,
            temp_dir=self._request.temp_dir,
            device_preference=self._request.compute_device,
            intra_op_num_threads=1,
        )

    def _build_cluster_params(self) -> ClusteringParams:
        """从冻结快照构造聚类参数值对象。"""
        config = self._request.config_snapshot.clustering
        return ClusteringParams(
            eps_cf=config.eps_cf,
            min_pts_cf=config.min_pts_cf,
            eps_pw=config.eps_pw,
            min_pts_pw=config.min_pts_pw,
            eps_doa=config.eps_doa,
            min_pts_doa=config.min_pts_doa,
            clip_threshold_doa=config.clip_threshold_doa,
        )

    def _build_recognition_params(self) -> RecognitionParams:
        """从冻结快照构造识别参数值对象。"""
        config = self._request.config_snapshot.recognition
        return RecognitionParams(
            greedy_strategy=config.greedy_strategy,
            pa_confidence_threshold=config.pa_confidence_threshold,
            pa_confidence_weight=config.pa_confidence_weight,
            dtoa_confidence_threshold=config.dtoa_confidence_threshold,
            dtoa_confidence_weight=config.dtoa_confidence_weight,
            joint_confidence_threshold=config.joint_confidence_threshold,
        )

    def _build_extract_params(self) -> ExtractParams:
        """从冻结快照构造参数提取值对象。"""
        config = self._request.config_snapshot.extract
        return ExtractParams(
            eps_cf=config.eps_cf,
            min_pts_cf=config.min_pts_cf,
            threshold_ratio_cf=config.threshold_ratio_cf,
            eps_pw=config.eps_pw,
            min_pts_pw=config.min_pts_pw,
            threshold_ratio_pw=config.threshold_ratio_pw,
            eps_pri=config.eps_pri,
            min_pts_pri=config.min_pts_pri,
            threshold_ratio_pri=config.threshold_ratio_pri,
            filter_threshold_pri=config.filter_threshold_pri,
            harmonic_tolerance_pri=config.harmonic_tolerance_pri,
        )

    def _emit_progress(
        self,
        stage: str,
        current_slice: int,
        total_slices: int,
        progress: int,
        message: str,
        *,
        exporting: bool = False,
    ) -> None:
        """发出归一化进度信号并记录阶段日志。"""
        normalized_progress = max(0, min(100, int(progress)))
        LOGGER.info(
            "全速进度: stage=%s, slice=%d/%d, progress=%d, message=%s",
            stage,
            current_slice,
            total_slices,
            normalized_progress,
            message,
        )
        self.progress_signal.emit(
            self._request.session_id,
            stage,
            current_slice,
            total_slices,
            normalized_progress,
            message,
            exporting,
        )

    def _check_cancelled(self) -> None:
        """在阶段边界检查协作式取消标志。"""
        if self._cancel_event.is_set():
            raise _FullSpeedCancelled()
