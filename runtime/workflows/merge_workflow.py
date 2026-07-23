"""切片合并判别、批量执行与结果呈现工作流。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import logging

import numpy as np
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
    MergePlan,
    MergeResult,
    MergedClusterResult,
    SliceMergePlan,
    SliceMergeResult,
)
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.recognition_result import SliceRecognitionResult
from infra.plotting.facades import (
    build_merge_palette,
    render_merge_images,
    resolve_merge_source_colors,
)
from infra.plotting.types import RenderedImageBundle


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MergeCategoryPresentation:
    """一个合并结果来源类别的界面数据。

    Attributes:
        cluster_index [int]: 原识别类簇编号。
        color [tuple[int, int, int]]: 与合并图一致的RGB颜色。
        visible [bool]: 当前是否参与绘图。
    """

    cluster_index: int
    color: tuple[int, int, int]
    visible: bool


@dataclass(frozen=True, slots=True)
class MergeResultPresentation:
    """当前合并结果的纯界面呈现数据。

    Attributes:
        title [str]: 合并图像列标题。
        result_index [int]: 当前结果的0-based浏览索引。
        result_count [int]: 当前切片合并结果总数。
        categories [tuple[MergeCategoryPresentation, ...]]: 来源类别及颜色。
        images [dict[str, np.ndarray]]: 五维RGB图像。
        table_rows [tuple[tuple[str, str], ...]]: 合并参数表格行。
    """

    title: str
    result_index: int
    result_count: int
    categories: tuple[MergeCategoryPresentation, ...]
    images: dict[str, np.ndarray]
    table_rows: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class MergeBatchWorkflowResult:
    """一次切片级批量合并的执行结果。

    Attributes:
        success [bool]: 完整计划是否全部执行并写回成功。
        result_count [int]: 成功生成的独立合并结果数量。
        error_message [str]: 失败原因，成功时为空字符串。
    """

    success: bool
    result_count: int = 0
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class MergeWorkflowResult:
    """兼容人工单组合并入口的执行结果。

    Attributes:
        success [bool]: 合并与绘图是否全部成功。
        merge_result [MergedClusterResult | None]: 成功时的领域结果。
        rendered_bundle [RenderedImageBundle | None]: 成功时的五维图像。
        error_message [str]: 失败消息，成功时为空字符串。
    """

    success: bool
    merge_result: MergedClusterResult | None = None
    rendered_bundle: RenderedImageBundle | None = None
    error_message: str = ""


class MergeWorkflow(QObject):
    """连接识别结果、可插拔准则、批量合并和多颜色绘图。"""

    def __init__(
        self,
        parent: QObject | None = None,
        strategy: MergeStrategy | None = None,
    ) -> None:
        """初始化合并工作流并注入当前准则。

        Args:
            parent [QObject | None]: Qt父对象，默认不挂载。
            strategy [MergeStrategy | None]: 可替换的合并准则。

        Returns:
            None: 无返回值。

        Raises:
            TypeError: 注入准则缺少稳定标识或计划构建方法时抛出。
        """
        super().__init__(parent)
        self._strategy: MergeStrategy = (
            DefaultMergeStrategy() if strategy is None else strategy
        )
        # 在工作流边界校验最小插件契约，避免错误准则延迟到识别完成后才暴露。
        self._validate_strategy(self._strategy)

    @property
    def strategy_id(self) -> str:
        """返回当前合并准则的稳定标识。

        Returns:
            str: 当前准则标识。
        """
        return self._strategy.strategy_id

    def set_strategy(self, strategy: MergeStrategy) -> None:
        """替换后续判别使用的合并准则。

        Args:
            strategy [MergeStrategy]: 新准则实例。

        Returns:
            None: 无返回值。

        Raises:
            TypeError: 准则不满足最小接口时抛出。
        """
        self._validate_strategy(strategy)
        self._strategy = strategy

    def switch_strategy(
        self,
        session: ProcessingSession,
        slice_index: int,
        strategy: MergeStrategy,
    ) -> bool:
        """切换准则并失效当前切片的旧派生计划和结果。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 需要重新判别的目标切片。
            strategy [MergeStrategy]: 新准则实例。

        Returns:
            bool: 准则标识发生变化并完成失效处理时返回True。

        Raises:
            TypeError: 新准则不满足可插拔接口时抛出。
            ValueError: 切片索引为负数时抛出。
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        self._validate_strategy(strategy)
        previous_strategy_id = self.strategy_id
        if strategy.strategy_id == previous_strategy_id:
            return False
        with session.lock:
            # 计划和结果都是旧准则的派生产物；切换时只清理当前切片，
            # 聚类与识别结果继续保留，随后可直接基于新准则重新判别。
            self._strategy = strategy
            session.clear_slice_merge_results(slice_index)
        return True

    def prepare_merge_plan(
        self,
        session: ProcessingSession,
        slice_index: int,
        *,
        force: bool = False,
    ) -> SliceMergePlan | None:
        """在识别完成后生成并保存当前切片的完整合并计划。

        Args:
            session [ProcessingSession]: 包含聚类和识别结果的会话。
            slice_index [int]: 目标切片的0-based索引。
            force [bool]: 是否忽略同准则旧计划并重新判别。

        Returns:
            SliceMergePlan | None: 已完成识别时返回计划，否则返回None。

        Raises:
            ValueError: 切片索引为负数或准则生成跨切片计划时抛出。
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        if not session.is_slice_recognized(slice_index):
            return None
        slice_state = session.get_slice_processing_state(slice_index)
        if slice_state.merge_judgment_suppressed and not force:
            return None

        # 同一准则的已有计划可直接复用，避免界面刷新时反复执行合并判别。
        existing = (
            session.merge_plan.slice_plans.get(slice_index)
            if session.merge_plan is not None
            else None
        )
        if (
            not force
            and existing is not None
            and existing.strategy_id == self.strategy_id
        ):
            return existing

        source_results = self._find_source_results(session, slice_index)
        if source_results is None:
            return None

        # 准则只读取当前切片的聚类与识别结果，并返回独立的派生计划。
        plan = self._build_plan(*source_results)
        if plan.slice_index != slice_index:
            raise ValueError("合并准则返回了错误的切片索引")
        with session.lock:
            if session.merge_plan is None:
                session.merge_plan = MergePlan()
            # 切片索引是计划唯一槽位；强制重算时原位替换旧派生计划。
            session.merge_plan.slice_plans[slice_index] = plan
            session.get_slice_processing_state(
                slice_index
            ).merge_judgment_suppressed = False
        return plan

    def get_merge_groups(
        self,
        session: ProcessingSession,
        slice_index: int,
        *,
        force: bool = False,
    ) -> tuple[tuple[int, ...], ...]:
        """返回当前切片完整计划中的全部来源分组。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片的0-based索引。
            force [bool]: 是否强制重新判别。

        Returns:
            tuple[tuple[int, ...], ...]: 全部互斥合并分组。

        Raises:
            ValueError: 切片索引为负数或准则返回跨切片计划时抛出。
        """
        plan = self.prepare_merge_plan(session, slice_index, force=force)
        if plan is None:
            return ()
        return tuple(group.cluster_indices for group in plan.groups)

    def find_merge_candidates(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> tuple[tuple[int, ...], ...]:
        """兼容旧调用方并返回完整合并计划。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片的0-based索引。

        Returns:
            tuple[tuple[int, ...], ...]: 全部互斥合并分组。

        Raises:
            ValueError: 切片索引为负数或准则返回跨切片计划时抛出。
        """
        return self.get_merge_groups(session, slice_index)

    def execute_merge_plan(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> MergeBatchWorkflowResult:
        """一次执行当前切片计划中的全部分组并原子写回。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片的0-based索引。

        Returns:
            MergeBatchWorkflowResult: 整批执行结果。
        """
        # 一个切片的完整计划只允许批量执行一次，已有结果时拒绝覆盖。
        existing_count = self.get_result_count(session, slice_index)
        if existing_count:
            return MergeBatchWorkflowResult(
                success=False,
                error_message="当前切片的合并计划已经执行",
            )
        plan = self.prepare_merge_plan(session, slice_index)
        if plan is None or not plan.groups:
            return MergeBatchWorkflowResult(
                success=False,
                error_message="当前切片没有可执行的合并计划",
            )

        session_id = session.session_id
        signal_bus.stage_started.emit(session_id, "merging", slice_index)
        with session.lock:
            session.mark_slice_merge_running(slice_index)

        try:
            # 锁外执行点云拼接和参数提取，避免长时间阻塞其它session状态读取。
            slice_clusters, slice_recognitions = self._get_source_results(
                session,
                slice_index,
            )
            pipeline = MergePipeline(self._build_extract_params(session))
            merged_results = pipeline.run_plan(
                plan,
                slice_clusters,
                slice_recognitions,
            )
            if not merged_results:
                raise ValueError("合并计划没有生成任何结果")

            # 先验证整批每个结果都可绘制；任一失败时一个结果也不写入session。
            for merged in merged_results:
                palette = build_merge_palette(len(merged.source_point_clouds))
                render_merge_images(
                    list(merged.source_point_clouds),
                    band=session.band,
                    time_range=merged.time_range,
                    palette=palette,
                )

            with session.lock:
                # 重新读取来源和计划，并用对象身份检查执行期间是否发生重新识别、
                # 策略切换或计划重建，防止异步旧结果污染新一代数据。
                current_sources = self._find_source_results(session, slice_index)
                current_plan = (
                    session.merge_plan.slice_plans.get(slice_index)
                    if session.merge_plan is not None
                    else None
                )
                if (
                    not session.is_slice_recognized(slice_index)
                    or current_sources is None
                    or current_sources[0] is not slice_clusters
                    or current_sources[1] is not slice_recognitions
                    or current_plan is not plan
                    or current_plan.strategy_id != self.strategy_id
                ):
                    raise ValueError("合并执行期间来源或计划已变化，已放弃旧计划结果")
                if session.merge_result is None:
                    session.merge_result = MergeResult()

                # 全部计算和代次校验成功后一次性替换切片结果，保证批量写回原子性。
                session.merge_result.slice_results[slice_index] = SliceMergeResult(
                    slice_index=slice_index,
                    merged_clusters=list(merged_results),
                )
                session.mark_slice_merge_succeeded(slice_index)
                session.stage = ProcessingStage.MERGED
            signal_bus.stage_finished.emit(session_id, "merging", slice_index)
            return MergeBatchWorkflowResult(
                success=True,
                result_count=len(merged_results),
            )
        except Exception as error:
            LOGGER.error(
                "批量合并流程失败: %s",
                error,
                exc_info=True,
                extra={"session_id": session_id},
            )
            with session.lock:
                # 重新识别已开始时，其工作流拥有当前状态；不得把失效状态覆盖为合并失败。
                if session.is_slice_recognized(slice_index):
                    session.mark_slice_merge_failed(slice_index, str(error))
            signal_bus.stage_failed.emit(
                session_id,
                "merging",
                slice_index,
                str(error),
            )
            return MergeBatchWorkflowResult(
                success=False,
                error_message=str(error),
            )

    def get_result_count(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> int:
        """返回当前切片已有的独立合并结果数量。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片索引。

        Returns:
            int: 合并结果数量。
        """
        if session.merge_result is None:
            return 0
        slice_result = session.merge_result.slice_results.get(slice_index)
        return 0 if slice_result is None else len(slice_result.merged_clusters)

    def reset_merge_state(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> None:
        """清除当前切片计划和结果并保持未进行合并判别状态。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片的0-based索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 切片索引为负数时抛出。
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        with session.lock:
            session.reset_slice_merge_state(slice_index)
            # 当前会话不再包含任何合并结果时，全局阶段同步回退到识别完成。
            if (
                session.merge_result is None
                and session.stage is ProcessingStage.MERGED
            ):
                session.stage = ProcessingStage.RECOGNIZED

    def render_result(
        self,
        session: ProcessingSession,
        slice_index: int,
        result_index: int,
        visible_cluster_indices: Iterable[int] | None = None,
    ) -> MergeResultPresentation:
        """按稳定颜色渲染一个合并结果及其界面数据。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片索引。
            result_index [int]: 需要呈现的0-based结果索引。
            visible_cluster_indices [Iterable[int] | None]: 当前可见的原类簇编号。

        Returns:
            MergeResultPresentation: 图像、颜色、标题和参数表数据。

        Raises:
            ValueError: 当前切片没有合并结果时抛出。
            IndexError: 结果索引越界时抛出。
        """
        if session.merge_result is None:
            raise ValueError("当前会话没有合并结果")
        slice_result = session.merge_result.slice_results.get(slice_index)
        if slice_result is None or not slice_result.merged_clusters:
            raise ValueError("当前切片没有合并结果")
        if not 0 <= result_index < len(slice_result.merged_clusters):
            raise IndexError("合并结果索引越界")

        result = slice_result.merged_clusters[result_index]
        source_indices = result.source_cluster_indices

        # UI传入的是业务簇编号；绘图引擎使用来源点云在结果内的0-based位置。
        visible_set = (
            None
            if visible_cluster_indices is None
            else {int(index) for index in visible_cluster_indices}
        )
        visible_positions = (
            None
            if visible_set is None
            else [
                position
                for position, cluster_index in enumerate(source_indices)
                if cluster_index in visible_set
            ]
        )
        palette = build_merge_palette(len(source_indices))
        # 调色板由完整来源数生成，类别隐藏后其它类别仍使用原位置颜色。
        colors = resolve_merge_source_colors(
            len(source_indices),
            palette=palette,
        )
        bundle = render_merge_images(
            list(result.source_point_clouds),
            band=session.band,
            time_range=result.time_range,
            visible_cluster_indices=visible_positions,
            palette=palette,
        )
        source_text = "+".join(str(index) for index in source_indices)
        title = (
            f"合并结果 第{result_index + 1}/{len(slice_result.merged_clusters)}组"
            f"（原第{source_text}类）"
        )
        categories = tuple(
            MergeCategoryPresentation(
                cluster_index=cluster_index,
                color=colors[position],
                visible=visible_set is None or cluster_index in visible_set,
            )
            for position, cluster_index in enumerate(source_indices)
        )
        params = result.extracted_params
        return MergeResultPresentation(
            title=title,
            result_index=result_index,
            result_count=len(slice_result.merged_clusters),
            categories=categories,
            images=bundle.images,
            table_rows=(
                ("CF", self._format_values(params.cf_values)),
                ("PW", self._format_values(params.pw_values)),
                ("PRI", self._format_values(params.pri_values, decimal_places=1)),
                ("DOA", self._format_values(params.doa_values)),
            ),
        )

    def start_merge_by_indices(
        self,
        session: ProcessingSession,
        slice_index: int,
        cluster_indices: Iterable[int],
    ) -> MergeWorkflowResult:
        """执行一个人工明确指定的来源分组。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片索引。
            cluster_indices [Iterable[int]]: 来源簇编号。

        Returns:
            MergeWorkflowResult: 单组合并结果。

        Raises:
            ValueError: 来源簇数量、编号或切片索引不合法时抛出。
        """
        return self.start_merge(
            session,
            MergeTarget(
                slice_index=slice_index,
                cluster_indices=tuple(int(index) for index in cluster_indices),
            ),
            strategy_id="explicit",
        )

    def start_strategy_merge_by_indices(
        self,
        session: ProcessingSession,
        slice_index: int,
        cluster_indices: Iterable[int],
    ) -> MergeWorkflowResult:
        """兼容旧调用方并执行一个策略来源分组。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片索引。
            cluster_indices [Iterable[int]]: 来源簇编号。

        Returns:
            MergeWorkflowResult: 单组合并结果。

        Raises:
            ValueError: 来源簇数量、编号或切片索引不合法时抛出。
        """
        return self.start_merge(
            session,
            MergeTarget(
                slice_index=slice_index,
                cluster_indices=tuple(int(index) for index in cluster_indices),
            ),
            strategy_id=self.strategy_id,
        )

    def start_merge(
        self,
        session: ProcessingSession,
        target: MergeTarget,
        strategy_id: str = "explicit",
    ) -> MergeWorkflowResult:
        """兼容人工入口并追加一个独立合并结果。

        Args:
            session [ProcessingSession]: 目标会话。
            target [MergeTarget]: 人工明确来源分组。
            strategy_id [str]: 来源标识。

        Returns:
            MergeWorkflowResult: 单组合并和绘图结果。
        """
        # 来源集合按无序集合判重，人工以不同排列提交也不能重复生成相同结果。
        if frozenset(target.cluster_indices) in self._completed_source_sets(
            session,
            target.slice_index,
        ):
            return MergeWorkflowResult(
                success=False,
                error_message="同一来源簇集合已经完成合并，不能重复执行",
            )
        session_id = session.session_id
        signal_bus.stage_started.emit(
            session_id,
            "merging",
            target.slice_index,
        )
        with session.lock:
            session.mark_slice_merge_running(target.slice_index)
        try:
            # 兼容入口仍生成独立合并结果，不会从识别结果中删除任何来源簇。
            slice_clusters, slice_recognitions = self._get_source_results(
                session,
                target.slice_index,
            )
            pipeline = MergePipeline(self._build_extract_params(session))
            merged = pipeline.run(
                target,
                slice_clusters,
                slice_recognitions,
                self._next_merge_index(session, target.slice_index),
                strategy_id,
            )
            bundle = render_merge_images(
                list(merged.source_point_clouds),
                band=session.band,
                time_range=merged.time_range,
                palette=build_merge_palette(len(merged.source_point_clouds)),
            )
            with session.lock:
                self._append_result(session, merged)
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
    def _validate_strategy(strategy: MergeStrategy) -> None:
        """校验可插拔准则的最小运行时接口。"""
        strategy_id = getattr(strategy, "strategy_id", None)
        if (
            not isinstance(strategy_id, str)
            or not strategy_id.strip()
            or not callable(getattr(strategy, "build_plan", None))
        ):
            raise TypeError("合并准则必须提供非空strategy_id和build_plan()")

    def _build_plan(
        self,
        slice_clusters: SliceClusterResult,
        slice_recognitions: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """调用当前可插拔准则生成完整切片计划。"""
        return self._strategy.build_plan(
            slice_clusters,
            slice_recognitions,
        )

    @staticmethod
    def _get_source_results(
        session: ProcessingSession,
        slice_index: int,
    ) -> tuple[SliceClusterResult, SliceRecognitionResult]:
        """读取目标切片聚类与识别结果，缺失时抛出。"""
        source_results = MergeWorkflow._find_source_results(session, slice_index)
        if source_results is None:
            raise ValueError("目标切片尚未完成识别")
        return source_results

    @staticmethod
    def _find_source_results(
        session: ProcessingSession,
        slice_index: int,
    ) -> tuple[SliceClusterResult, SliceRecognitionResult] | None:
        """尝试读取目标切片聚类与识别结果。"""
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
        """返回人工入口已写回的来源簇集合。"""
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
        """返回人工入口的下一个1-based结果序号。"""
        if session.merge_result is None:
            return 1
        slice_result = session.merge_result.slice_results.get(slice_index)
        return 1 if slice_result is None else len(slice_result.merged_clusters) + 1

    @staticmethod
    def _build_extract_params(session: ProcessingSession) -> ExtractParams:
        """根据session快照构造参数提取值对象。"""
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
    def _append_result(
        session: ProcessingSession,
        merged: MergedClusterResult,
    ) -> None:
        """把人工单组合并结果追加到目标切片。"""
        if session.merge_result is None:
            session.merge_result = MergeResult()
        slice_result = session.merge_result.slice_results.setdefault(
            merged.slice_index,
            SliceMergeResult(slice_index=merged.slice_index),
        )
        slice_result.merged_clusters.append(merged)

    @staticmethod
    def _format_values(
        values: Iterable[float],
        *,
        decimal_places: int | None = None,
    ) -> str:
        """把参数值格式化为由界面根据可用列宽分行的结果文本。"""
        formatted: list[str] = []
        for value in values:
            if decimal_places is None:
                formatted.append(f"{float(value):g}")
                continue
            quantizer = (
                Decimal("1")
                if decimal_places == 0
                else Decimal(f"1e-{decimal_places}")
            )
            rounded = Decimal(str(value)).quantize(
                quantizer,
                rounding=ROUND_HALF_UP,
            )
            if rounded == Decimal("0"):
                rounded = Decimal("0")
            formatted.append(f"{rounded:.{decimal_places}f}")
        if not formatted:
            return "——"
        return "、".join(formatted)
