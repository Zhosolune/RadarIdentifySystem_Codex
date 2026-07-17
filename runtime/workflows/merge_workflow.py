"""显式合并目标的运行时工作流。"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from core.merge import MergePipeline, MergeTarget
from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import SliceClusterResult
from core.models.merge_result import (
    MergeResult,
    MergedClusterResult,
    SliceMergeResult,
)
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.recognition_result import SliceRecognitionResult
from infra.plotting.facades import render_merge_images
from infra.plotting.types import RenderedImageBundle


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MergeWorkflowResult:
    """一次合并工作流的执行结果。

    Attributes:
        success [bool]: 合并与绘图是否全部成功。
        merge_result [MergedClusterResult | None]: 成功时的领域结果。
        rendered_bundle [RenderedImageBundle | None]: 成功时的五维多颜色图像。
        error_message [str]: 失败消息，成功时为空字符串。
    """

    success: bool
    merge_result: MergedClusterResult | None = None
    rendered_bundle: RenderedImageBundle | None = None
    error_message: str = ""


class MergeWorkflow(QObject):
    """连接 session 识别结果、核心合并流程和多颜色绘图。"""

    def start_merge(
        self,
        session: ProcessingSession,
        target: MergeTarget,
    ) -> MergeWorkflowResult:
        """执行显式目标合并并写回当前 session。

        Args:
            session [ProcessingSession]: 包含聚类与识别结果的目标会话。
            target [MergeTarget]: 上层已经确定的来源簇集合。

        Returns:
            MergeWorkflowResult: 合并领域结果、五维图像或失败信息。

        Raises:
            无显式抛出异常；执行异常会转换为失败结果并发送生命周期信号。
        """
        session_id = session.session_id
        signal_bus.stage_started.emit(session_id, "merging", target.slice_index)
        with session.lock:
            session.mark_slice_merge_running(target.slice_index)

        try:
            slice_clusters, slice_recognitions = self._get_source_results(
                session,
                target,
            )
            merge_index = self._next_merge_index(session, target.slice_index)
            pipeline = MergePipeline(self._build_extract_params(session))
            merged = pipeline.run(
                target=target,
                slice_cluster_result=slice_clusters,
                slice_recognition_result=slice_recognitions,
                merge_index=merge_index,
            )
            # 保留各来源点云分别着色，合并点云仅用于参数提取和后续业务消费。
            bundle = render_merge_images(
                list(merged.source_point_clouds),
                band=session.band,
                time_range=merged.time_range,
            )
            with session.lock:
                self._write_result(session, merged)
                session.mark_slice_merge_succeeded(target.slice_index)
                session.stage = ProcessingStage.MERGED
            signal_bus.stage_finished.emit(
                session_id,
                "merging",
                target.slice_index,
            )
            return MergeWorkflowResult(
                success=True,
                merge_result=merged,
                rendered_bundle=bundle,
            )
        except Exception as error:
            LOGGER.error(
                "合并流程失败: %s",
                error,
                exc_info=True,
                extra={"session_id": session_id},
            )
            with session.lock:
                session.mark_slice_merge_failed(target.slice_index, str(error))
            signal_bus.stage_failed.emit(
                session_id,
                "merging",
                target.slice_index,
                str(error),
            )
            return MergeWorkflowResult(success=False, error_message=str(error))

    @staticmethod
    def _get_source_results(
        session: ProcessingSession,
        target: MergeTarget,
    ) -> tuple[SliceClusterResult, SliceRecognitionResult]:
        """读取目标切片的聚类和识别结果。"""
        if session.cluster_result is None or session.recognition_result is None:
            raise ValueError("当前 session 尚无可用的识别结果")
        slice_clusters = session.cluster_result.slice_results.get(target.slice_index)
        slice_recognitions = session.recognition_result.slice_results.get(
            target.slice_index
        )
        if slice_clusters is None or slice_recognitions is None:
            raise ValueError("目标切片尚未完成识别")
        return slice_clusters, slice_recognitions

    @staticmethod
    def _next_merge_index(session: ProcessingSession, slice_index: int) -> int:
        """返回目标切片下一个 1-based 合并结果序号。"""
        if session.merge_result is None:
            return 1
        slice_result = session.merge_result.slice_results.get(slice_index)
        return 1 if slice_result is None else len(slice_result.merged_clusters) + 1

    @staticmethod
    def _build_extract_params(session: ProcessingSession) -> ExtractParams:
        """根据 session 快照构造参数提取值对象。"""
        config = session.config_snapshot.extract
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

    @staticmethod
    def _write_result(
        session: ProcessingSession,
        merged: MergedClusterResult,
    ) -> None:
        """把单个合并结果追加到 session 对应切片。"""
        if session.merge_result is None:
            session.merge_result = MergeResult()
        slice_result = session.merge_result.slice_results.setdefault(
            merged.slice_index,
            SliceMergeResult(slice_index=merged.slice_index),
        )
        slice_result.merged_clusters.append(merged)
