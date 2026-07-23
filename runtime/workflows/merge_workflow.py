"""显式合并目标的运行时工作流。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import logging

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from core.merge import (
    DefaultMergeStrategy,
    MergePipeline,
    MergeStrategy,
    MergeTarget,
)
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

    def __init__(
        self,
        parent: QObject | None = None,
        strategy: MergeStrategy | None = None,
    ) -> None:
        """初始化合并工作流并注入当前使用的合并准则。

        Args:
            parent [QObject | None]: Qt父对象，默认不挂载。
            strategy [MergeStrategy | None]: 可替换的合并准则；为空时使用默认准则。

        Returns:
            None: 无返回值。

        Raises:
            TypeError: 注入准则未提供非空标识或候选构建方法时抛出。

        Example:
            >>> workflow = MergeWorkflow()
            >>> workflow.strategy_id
            'hybrid_parameter_v1'
        """
        super().__init__(parent)
        self._strategy: MergeStrategy = (
            DefaultMergeStrategy() if strategy is None else strategy
        )
        self._validate_strategy(self._strategy)

    @property
    def strategy_id(self) -> str:
        """返回当前合并准则的稳定标识。

        Returns:
            str: 当前准则标识，用于日志和运行时切换确认。

        Raises:
            无显式抛出异常。
        """
        return self._strategy.strategy_id

    def set_strategy(self, strategy: MergeStrategy) -> None:
        """在运行时替换后续候选计算使用的合并准则。

        已生成的合并结果不会被自动删除；切换后重新查询候选即可使用新准则。

        Args:
            strategy [MergeStrategy]: 新的合并准则实现。

        Returns:
            None: 无返回值。

        Raises:
            TypeError: 准则未提供非空标识或候选构建方法时抛出。

        Example:
            >>> workflow = MergeWorkflow()
            >>> workflow.set_strategy(DefaultMergeStrategy())
            >>> workflow.strategy_id
            'hybrid_parameter_v1'
        """
        self._validate_strategy(strategy)
        self._strategy = strategy

    @staticmethod
    def _validate_strategy(strategy: MergeStrategy) -> None:
        """校验运行时注入的合并准则最小接口。"""
        strategy_id = getattr(strategy, "strategy_id", None)
        if (
            not isinstance(strategy_id, str)
            or not strategy_id.strip()
            or not callable(getattr(strategy, "build_targets", None))
        ):
            raise TypeError("合并准则必须提供非空 strategy_id 和 build_targets()")

    def find_merge_candidates(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> tuple[tuple[int, ...], ...]:
        """计算当前切片尚未执行的规则合并候选组。

        Args:
            session [ProcessingSession]: 包含聚类和识别结果的目标会话。
            slice_index [int]: 目标切片的0-based索引。

        Returns:
            tuple[tuple[int, ...], ...]: 候选组的簇编号，只包含至少两个来源的组。

        Raises:
            ValueError: 切片索引为负数时抛出。

        Example:
            >>> isinstance(MergeWorkflow().find_merge_candidates(ProcessingSession(), 0), tuple)
            True
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        # 识别失败或重新识别尚未完成时，即使session仍保留旧对象也不得复用旧候选。
        if not session.is_slice_recognized(slice_index):
            return ()
        source_results = self._find_source_results(session, slice_index)
        if source_results is None:
            return ()
        slice_clusters, slice_recognitions = source_results
        targets = self._strategy.build_targets(
            slice_clusters,
            slice_recognitions,
        )

        # 已执行的同一来源集合不再作为候选返回，避免重复点击产生重复结果。
        completed_sources = self._completed_source_sets(session, slice_index)
        return tuple(
            target.cluster_indices
            for target in targets
            if frozenset(target.cluster_indices) not in completed_sources
        )

    def start_merge_by_indices(
        self,
        session: ProcessingSession,
        slice_index: int,
        cluster_indices: Iterable[int],
    ) -> MergeWorkflowResult:
        """根据runtime入口参数构造核心目标并执行合并。

        Args:
            session [ProcessingSession]: 目标处理会话。
            slice_index [int]: 目标切片的0-based索引。
            cluster_indices [Iterable[int]]: 需要合并的来源簇编号。

        Returns:
            MergeWorkflowResult: 合并、写回和绘图的完整结果。

        Raises:
            ValueError: 目标来源数量、编号或重复性不合法时抛出。

        Example:
            >>> hasattr(MergeWorkflow, "start_merge_by_indices")
            True
        """
        target = MergeTarget(
            slice_index=slice_index,
            cluster_indices=tuple(int(index) for index in cluster_indices),
        )
        return self.start_merge(session, target, strategy_id="explicit")

    def start_strategy_merge_by_indices(
        self,
        session: ProcessingSession,
        slice_index: int,
        cluster_indices: Iterable[int],
    ) -> MergeWorkflowResult:
        """执行由当前可插拔准则生成的簇编号目标。

        Args:
            session [ProcessingSession]: 目标处理会话。
            slice_index [int]: 目标切片的0-based索引。
            cluster_indices [Iterable[int]]: 当前准则生成的来源簇编号。

        Returns:
            MergeWorkflowResult: 带当前 ``strategy_id`` 的合并执行结果。

        Raises:
            ValueError: 目标来源数量、编号或重复性不合法时抛出。

        Example:
            >>> hasattr(MergeWorkflow, "start_strategy_merge_by_indices")
            True
        """
        target = MergeTarget(
            slice_index=slice_index,
            cluster_indices=tuple(int(index) for index in cluster_indices),
        )
        return self.start_merge(
            session,
            target,
            strategy_id=self.strategy_id,
        )

    def start_merge(
        self,
        session: ProcessingSession,
        target: MergeTarget,
        strategy_id: str = "explicit",
    ) -> MergeWorkflowResult:
        """执行显式目标合并并写回当前 session。

        Args:
            session [ProcessingSession]: 包含聚类与识别结果的目标会话。
            target [MergeTarget]: 上层已经确定的来源簇集合。
            strategy_id [str]: 目标来源准则标识，人工显式目标默认为 ``explicit``。

        Returns:
            MergeWorkflowResult: 合并领域结果、五维图像或失败信息。

        Raises:
            无显式抛出异常；执行异常会转换为失败结果并发送生命周期信号。
        """
        session_id = session.session_id
        if frozenset(target.cluster_indices) in self._completed_source_sets(
            session,
            target.slice_index,
        ):
            error_message = "同一来源簇集合已经完成合并，不能重复执行"
            LOGGER.warning(
                error_message,
                extra={"session_id": session_id},
            )
            return MergeWorkflowResult(
                success=False,
                error_message=error_message,
            )
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
                strategy_id=strategy_id,
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
        source_results = MergeWorkflow._find_source_results(
            session,
            target.slice_index,
        )
        if source_results is None:
            raise ValueError("目标切片尚未完成识别")
        return source_results

    @staticmethod
    def _find_source_results(
        session: ProcessingSession,
        slice_index: int,
    ) -> tuple[SliceClusterResult, SliceRecognitionResult] | None:
        """尝试读取指定切片的聚类和识别结果。"""
        if session.cluster_result is None or session.recognition_result is None:
            return None
        slice_clusters = session.cluster_result.slice_results.get(slice_index)
        slice_recognitions = session.recognition_result.slice_results.get(slice_index)
        if slice_clusters is None or slice_recognitions is None:
            return None
        return slice_clusters, slice_recognitions

    @staticmethod
    def _completed_source_sets(
        session: ProcessingSession,
        slice_index: int,
    ) -> set[frozenset[int]]:
        """返回指定切片已经写回的来源簇集合。"""
        if session.merge_result is None:
            return set()
        slice_result = session.merge_result.slice_results.get(slice_index)
        if slice_result is None:
            return set()
        return {
            frozenset(result.source_cluster_indices)
            for result in slice_result.merged_clusters
        }

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
