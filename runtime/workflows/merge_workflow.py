"""切片合并判别、批量执行与结果呈现工作流。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import logging

import numpy as np
from PyQt6.QtCore import QObject, pyqtSlot

from app.logger import bind_session_log_context, unbind_session_log_context
from app.signal_bus import signal_bus
from core.merge import (
    DefaultMergeStrategy,
    MergeStrategy,
)
from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import SliceClusterResult
from core.models.extraction_result import ExtractedClusterParams
from core.models.merge_result import (
    MergePlan,
    MergeResult,
    MergedClusterResult,
    SliceMergePlan,
    SliceMergeResult,
)
from core.models.processing_session import (
    ProcessingSession,
    ProcessingStage,
    SliceProcessStatus,
)
from core.models.recognition_result import SliceRecognitionResult
from core.params_extract import extract_cluster_params
from infra.plotting.facades import (
    build_merge_palette,
    render_merge_images,
    resolve_merge_source_colors,
)
from infra.plotting.types import RenderedImageBundle
from runtime.threading.merge_worker import (
    MergePlanWorker,
    MergePlanWorkerResult,
    MergeWorker,
    MergeWorkerResult,
)


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MergeCategoryPresentation:
    """一个合并结果来源类别的界面数据。

    Attributes:
        cluster_index [int]: 原识别类簇编号。
        color [tuple[int, int, int]]: 与合并图一致的RGB颜色。
        visible [bool]: 当前是否参与绘图和参数计算。
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
        self._worker: MergeWorker | None = None
        self._plan_worker: MergePlanWorker | None = None
        self._active_session: ProcessingSession | None = None
        self._active_slice_index: int | None = None
        self._active_strategy: MergeStrategy | None = None
        self._active_plan: SliceMergePlan | None = None
        self._active_slice_clusters: SliceClusterResult | None = None
        self._active_slice_recognitions: SliceRecognitionResult | None = None
        self._plan_session: ProcessingSession | None = None
        self._plan_slice_index: int | None = None
        self._plan_strategy: MergeStrategy | None = None
        self._plan_slice_clusters: SliceClusterResult | None = None
        self._plan_slice_recognitions: SliceRecognitionResult | None = None
        self._rendered_bundles: dict[
            tuple[str, int],
            tuple[RenderedImageBundle, ...],
        ] = {}

    def is_running(self) -> bool:
        """判断当前工作流是否仍有待完成的合并线程。

        Returns:
            bool: 从线程创建到主线程回调清理完成期间返回 True。

        Raises:
            无显式抛出异常。
        """
        return self._worker is not None

    def is_judging(self) -> bool:
        """判断当前工作流是否正在后台判别可合并类。

        Returns:
            bool: 候选计划线程尚未完成主线程回调时返回 True。

        Raises:
            无显式抛出异常。
        """
        return self._plan_worker is not None

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
        LOGGER.info(
            "替换合并策略: old_strategy_id=%s, new_strategy_id=%s",
            self.strategy_id,
            strategy.strategy_id,
        )
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
            bool: 完成准则替换和旧派生状态失效处理时返回True。

        Raises:
            TypeError: 新准则不满足可插拔接口时抛出。
            ValueError: 切片索引为负数时抛出。
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        self._validate_strategy(strategy)
        old_strategy_id = self.strategy_id
        with session.lock:
            # 同一策略ID或同一实例未来都可能修改参数；显式应用策略时一律
            # 清除旧派生状态，聚类和识别结果继续保留供下次点击合并重新判别。
            self._strategy = strategy
            session.clear_slice_merge_results(slice_index)
            self._rendered_bundles.pop((session.session_id, slice_index), None)
        LOGGER.info(
            "切换Session合并策略并清除旧派生状态: slice_index=%d, "
            "old_strategy_id=%s, new_strategy_id=%s",
            slice_index,
            old_strategy_id,
            strategy.strategy_id,
            extra={"session_id": session.session_id},
        )
        return True

    def request_merge_plan(
        self,
        session: ProcessingSession,
        slice_index: int,
        *,
        force: bool = False,
    ) -> bool:
        """启动当前切片的后台合并候选判别。

        Args:
            session [ProcessingSession]: 包含聚类和识别结果的目标会话。
            slice_index [int]: 目标切片的 0-based 索引。
            force [bool]: 是否忽略重置抑制状态并重新判别。

        Returns:
            bool: 候选判别线程成功启动时返回 True，否则返回 False。

        Raises:
            ValueError: 切片索引为负数时抛出。
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        session_id = session.session_id
        LOGGER.info(
            "请求后台判别合并候选: slice_index=%d, strategy_id=%s, "
            "force=%s, judging=%s, result_count=%d",
            slice_index,
            self.strategy_id,
            force,
            self.is_judging(),
            self.get_result_count(session, slice_index),
            extra={"session_id": session_id},
        )
        if self.is_judging() or self.is_running():
            LOGGER.info(
                "跳过后台合并候选判别: slice_index=%d, 原因=已有合并任务运行",
                slice_index,
                extra={"session_id": session_id},
            )
            return False
        if self.get_result_count(session, slice_index):
            LOGGER.info(
                "跳过后台合并候选判别: slice_index=%d, 原因=已有合并结果",
                slice_index,
                extra={"session_id": session_id},
            )
            return False
        if not session.is_slice_recognized(slice_index):
            LOGGER.info(
                "跳过后台合并候选判别: slice_index=%d, 原因=切片尚未识别完成",
                slice_index,
                extra={"session_id": session_id},
            )
            return False
        slice_state = session.get_slice_processing_state(slice_index)
        if slice_state.merge_judgment_suppressed and not force:
            LOGGER.info(
                "跳过后台合并候选判别: slice_index=%d, "
                "原因=重置后判别被抑制且force=False",
                slice_index,
                extra={"session_id": session_id},
            )
            return False
        existing = self._get_prepared_plan(session, slice_index)
        if existing is not None and not force:
            LOGGER.info(
                "跳过后台合并候选判别: slice_index=%d, "
                "原因=当前策略计划已经存在, group_count=%d",
                slice_index,
                existing.group_count,
                extra={"session_id": session_id},
            )
            return False
        source_results = self._find_source_results(session, slice_index)
        if source_results is None:
            LOGGER.info(
                "跳过后台合并候选判别: slice_index=%d, 原因=来源结果缺失",
                slice_index,
                extra={"session_id": session_id},
            )
            return False

        strategy = self._strategy
        slice_clusters, slice_recognitions = source_results
        if force:
            with session.lock:
                session.clear_slice_merge_results(slice_index)
        self._plan_worker = MergePlanWorker(
            session_id=session_id,
            slice_index=slice_index,
            strategy=strategy,
            slice_cluster_result=slice_clusters,
            slice_recognition_result=slice_recognitions,
            parent=self,
        )
        self._plan_session = session
        self._plan_slice_index = slice_index
        self._plan_strategy = strategy
        self._plan_slice_clusters = slice_clusters
        self._plan_slice_recognitions = slice_recognitions
        self._plan_worker.finished_signal.connect(self._on_plan_worker_finished)
        signal_bus.stage_started.emit(session_id, "merge_judging", slice_index)
        self._plan_worker.start()
        return True

    @pyqtSlot(str, object)
    def _on_plan_worker_finished(
        self,
        session_id: str,
        result: MergePlanWorkerResult,
    ) -> None:
        """校验并保存后台候选判别结果。"""
        session = self._plan_session
        slice_index = self._plan_slice_index
        error_message = result.error_message
        if session is None or slice_index is None:
            error_message = error_message or "合并候选判别缺少活动Session上下文"
        elif session.session_id != session_id:
            error_message = "合并候选判别Session与活动任务不一致"
        elif result.success:
            plan = result.plan
            if plan is None:
                error_message = "合并候选判别线程未返回计划"
            else:
                try:
                    with session.lock:
                        if not self._plan_context_is_current(session, slice_index):
                            raise ValueError("合并候选判别期间来源或策略已变化")
                        if plan.slice_index != slice_index:
                            raise ValueError("合并候选判别返回了错误的切片索引")
                        if self._plan_strategy is None or (
                            plan.strategy_id != self._plan_strategy.strategy_id
                        ):
                            raise ValueError("合并候选判别返回的策略标识已失效")
                        if session.merge_plan is None:
                            session.merge_plan = MergePlan()
                        session.merge_plan.slice_plans[slice_index] = plan
                        session.get_slice_processing_state(
                            slice_index
                        ).merge_judgment_suppressed = False
                    LOGGER.info(
                        "后台合并候选判别完成: slice_index=%d, "
                        "strategy_id=%s, group_count=%d, groups=%s",
                        slice_index,
                        plan.strategy_id,
                        plan.group_count,
                        tuple(group.cluster_indices for group in plan.groups),
                        extra={"session_id": session_id},
                    )
                except Exception as error:
                    error_message = str(error)

        if error_message and session is not None and slice_index is not None:
            with session.lock:
                if self._plan_context_is_current(session, slice_index):
                    session.mark_slice_merge_failed(slice_index, error_message)

        self._cleanup_plan_worker_context()
        if error_message:
            LOGGER.error(
                "后台合并候选判别失败: slice_index=%s, error=%s",
                slice_index,
                error_message,
                extra={"session_id": session_id},
            )
            signal_bus.stage_failed.emit(
                session_id,
                "merge_judging",
                slice_index,
                error_message,
            )
            return
        signal_bus.stage_finished.emit(
            session_id,
            "merge_judging",
            slice_index,
        )

    def _plan_context_is_current(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> bool:
        """判断候选判别来源和策略仍属于当前Session代次。"""
        current_sources = self._find_source_results(session, slice_index)
        return (
            session.is_slice_recognized(slice_index)
            and current_sources is not None
            and current_sources[0] is self._plan_slice_clusters
            and current_sources[1] is self._plan_slice_recognitions
            and self._strategy is self._plan_strategy
        )

    def _cleanup_plan_worker_context(self) -> None:
        """释放候选判别线程及其活动输入引用。"""
        if self._plan_worker is not None:
            self._plan_worker.deleteLater()
        self._plan_worker = None
        self._plan_session = None
        self._plan_slice_index = None
        self._plan_strategy = None
        self._plan_slice_clusters = None
        self._plan_slice_recognitions = None

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
        session_id = session.session_id
        merge_config = session.config_snapshot.merge
        LOGGER.info(
            "请求生成合并判别计划: slice_index=%d, strategy_id=%s, force=%s, "
            "session合并参数快照={placeholder_value=%s, "
            "当前字段为占位且不参与判别=True}",
            slice_index,
            self.strategy_id,
            force,
            merge_config.placeholder_value,
            extra={"session_id": session_id},
        )
        if not session.is_slice_recognized(slice_index):
            LOGGER.info(
                "跳过合并判别计划生成: slice_index=%d, 原因=切片尚未识别完成",
                slice_index,
                extra={"session_id": session_id},
            )
            return None
        slice_state = session.get_slice_processing_state(slice_index)
        if slice_state.merge_judgment_suppressed and not force:
            LOGGER.info(
                "跳过合并判别计划生成: slice_index=%d, "
                "原因=重置后判别被抑制且force=False",
                slice_index,
                extra={"session_id": session_id},
            )
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
            LOGGER.info(
                "复用已有合并判别计划: slice_index=%d, strategy_id=%s, "
                "group_count=%d, groups=%s",
                slice_index,
                existing.strategy_id,
                existing.group_count,
                tuple(group.cluster_indices for group in existing.groups),
                extra={"session_id": session_id},
            )
            return existing

        source_results = self._find_source_results(session, slice_index)
        if source_results is None:
            LOGGER.info(
                "跳过合并判别计划生成: slice_index=%d, "
                "原因=聚类结果或识别结果缺失",
                slice_index,
                extra={"session_id": session_id},
            )
            return None

        # 未来合并准则存在真实可配置参数时，应在本runtime边界显式接收
        # ``MergeParams`` 值对象：识别完成后的基准判别由调用方从
        # ``session.config_snapshot.merge`` 构造；重置后的重新判别则由
        # MergeController 传入当前面板激活周期持有的临时副本。两种来源都
        # 只作为本次策略输入，不允许工作流读取全局qconfig或回写Session快照。
        # 准则只读取当前切片的聚类与识别结果，并返回独立的派生计划。
        LOGGER.info(
            "调用核心合并策略: slice_index=%d, strategy_id=%s, "
            "cluster_count=%d, valid_recognition_count=%d",
            slice_index,
            self.strategy_id,
            len(source_results[0].clusters),
            len(source_results[1].valid_clusters),
            extra={"session_id": session_id},
        )
        log_token = bind_session_log_context(session_id)
        try:
            try:
                plan = self._build_plan(*source_results)
            except Exception as error:
                LOGGER.error(
                    "核心合并策略判别失败: slice_index=%d, strategy_id=%s, "
                    "error=%s",
                    slice_index,
                    self.strategy_id,
                    error,
                    exc_info=True,
                    extra={"session_id": session_id},
                )
                raise
        finally:
            unbind_session_log_context(log_token)
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
        LOGGER.info(
            "合并判别计划已保存: slice_index=%d, strategy_id=%s, "
            "group_count=%d, groups=%s, force=%s",
            slice_index,
            plan.strategy_id,
            plan.group_count,
            tuple(group.cluster_indices for group in plan.groups),
            force,
            extra={"session_id": session_id},
        )
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

    def get_prepared_merge_groups(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> tuple[tuple[int, ...], ...]:
        """只读取当前策略已经保存的合并分组，不触发新的合并判别。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片的0-based索引。

        Returns:
            tuple[tuple[int, ...], ...]: 已保存计划中的全部分组；计划不存在或
            不属于当前策略时返回空元组。

        Raises:
            ValueError: 切片索引为负数时抛出。

        Example:
            >>> session = ProcessingSession()
            >>> session.reset_slice_processing_states(1)
            >>> MergeWorkflow().get_prepared_merge_groups(session, 0)
            ()
        """
        plan = self._get_prepared_plan(session, slice_index)
        if plan is None:
            return ()
        return tuple(group.cluster_indices for group in plan.groups)

    def has_prepared_merge_plan(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> bool:
        """判断当前切片是否已经按当前策略完成合并判别。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片的0-based索引。

        Returns:
            bool: 存在当前策略计划时返回True，空分组计划也视为已判别。

        Raises:
            ValueError: 切片索引为负数时抛出。

        Example:
            >>> session = ProcessingSession()
            >>> session.reset_slice_processing_states(1)
            >>> MergeWorkflow().has_prepared_merge_plan(session, 0)
            False
        """
        return self._get_prepared_plan(session, slice_index) is not None

    def _get_prepared_plan(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> SliceMergePlan | None:
        """返回当前策略已有计划，且不执行合并判别。"""
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        if not session.is_slice_recognized(slice_index):
            return None
        plan = (
            session.merge_plan.slice_plans.get(slice_index)
            if session.merge_plan is not None
            else None
        )
        if plan is None or plan.strategy_id != self.strategy_id:
            return None
        return plan

    def execute_merge_plan(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> bool:
        """启动当前切片的自动判别与批量合并线程。

        Args:
            session [ProcessingSession]: 目标会话。
            slice_index [int]: 目标切片的0-based索引。

        Returns:
            bool: 线程成功启动时返回 True，前置条件不满足时返回 False。

        Raises:
            无显式抛出异常。
        """
        session_id = session.session_id
        LOGGER.info(
            "请求执行切片完整合并计划: slice_index=%d, strategy_id=%s",
            slice_index,
            self.strategy_id,
            extra={"session_id": session_id},
        )
        if self.is_running() or self.is_judging():
            LOGGER.warning(
                "拒绝执行合并计划: slice_index=%d, 原因=合并任务正在运行",
                slice_index,
                extra={"session_id": session_id},
            )
            return False
        existing_count = self.get_result_count(session, slice_index)
        if existing_count:
            LOGGER.info(
                "拒绝执行合并计划: slice_index=%d, 原因=已有合并结果, "
                "existing_result_count=%d",
                slice_index,
                existing_count,
                extra={"session_id": session_id},
            )
            return False
        source_results = self._find_source_results(session, slice_index)
        if not session.is_slice_recognized(slice_index) or source_results is None:
            LOGGER.info(
                "拒绝执行合并计划: slice_index=%d, "
                "原因=当前切片尚未完成识别",
                slice_index,
                extra={"session_id": session_id},
            )
            return False
        plan = self._get_prepared_plan(session, slice_index)
        if plan is None or not plan.groups:
            LOGGER.info(
                "拒绝执行合并计划: slice_index=%d, "
                "原因=%s",
                slice_index,
                "尚未完成候选判别" if plan is None else "当前切片没有可合并类",
                extra={"session_id": session_id},
            )
            return False

        extract_params = self._build_extract_params(session)
        strategy = self._strategy
        slice_clusters, slice_recognitions = source_results
        LOGGER.info(
            "准备启动合并线程: slice_index=%d, strategy_id=%s, "
            "groups=%s, cluster_count=%d, valid_recognition_count=%d, "
            "参数提取配置=%s",
            slice_index,
            strategy.strategy_id,
            tuple(group.cluster_indices for group in plan.groups),
            len(slice_clusters.clusters),
            len(slice_recognitions.valid_clusters),
            extract_params,
            extra={"session_id": session_id},
        )
        with session.lock:
            # 执行必须消费菜单激活时已经判定的同一计划，避免判别与执行来源漂移。
            session.mark_slice_merge_running(slice_index)
            self._rendered_bundles.pop((session_id, slice_index), None)

        self._worker = MergeWorker(
            session_id=session_id,
            slice_index=slice_index,
            plan=plan,
            slice_cluster_result=slice_clusters,
            slice_recognition_result=slice_recognitions,
            extract_params=extract_params,
            band=session.band,
            parent=self,
        )
        self._active_session = session
        self._active_slice_index = slice_index
        self._active_strategy = strategy
        self._active_plan = plan
        self._active_slice_clusters = slice_clusters
        self._active_slice_recognitions = slice_recognitions
        self._worker.finished_signal.connect(self._on_worker_finished)
        signal_bus.stage_started.emit(session_id, "merging", slice_index)
        self._worker.start()
        return True

    @pyqtSlot(str, object)
    def _on_worker_finished(
        self,
        session_id: str,
        result: MergeWorkerResult,
    ) -> None:
        """在主线程校验代次并原子写回合并线程结果。

        Args:
            session_id [str]: 完成任务所属 Session 标识。
            result [MergeWorkerResult]: 子线程返回的完整执行结果。

        Returns:
            None: 无返回值。

        Raises:
            无。失效或计算异常统一转换为阶段失败事件。
        """
        session = self._active_session
        slice_index = self._active_slice_index
        error_message = result.error_message
        result_count = 0
        if session is None or slice_index is None:
            error_message = error_message or "合并线程回调缺少活动Session上下文"
        elif session.session_id != session_id:
            error_message = "合并线程回调Session与活动任务不一致"
        elif result.success:
            try:
                result_count = self._commit_worker_result(session, slice_index, result)
            except Exception as error:
                error_message = str(error)
                LOGGER.error(
                    "合并线程结果写回失败: %s",
                    error,
                    exc_info=True,
                    extra={"session_id": session_id},
                )

        if error_message and session is not None and slice_index is not None:
            with session.lock:
                # 只在来源代次和策略仍属于本任务时记录计算失败；重识别或策略切换
                # 已拥有更新后的状态，旧线程不得覆盖为失败。
                if self._active_context_is_current(session, slice_index):
                    session.mark_slice_merge_failed(slice_index, error_message)
                else:
                    slice_state = session.get_slice_processing_state(slice_index)
                    if slice_state.merge_status is SliceProcessStatus.RUNNING:
                        slice_state.merge_status = SliceProcessStatus.NOT_STARTED
                        slice_state.last_merge_error = None

        self._cleanup_worker_context()
        if error_message:
            signal_bus.stage_failed.emit(
                session_id,
                "merging",
                slice_index,
                error_message,
            )
            return

        LOGGER.info(
            "合并线程完成并已原子写回: slice_index=%d, strategy_id=%s, "
            "result_count=%d, 结果来源=%s",
            slice_index,
            None if result.plan is None else result.plan.strategy_id,
            result_count,
            tuple(
                merged.source_cluster_indices
                for merged in result.merged_results
            ),
            extra={"session_id": session_id},
        )
        signal_bus.stage_finished.emit(session_id, "merging", slice_index)

    def _commit_worker_result(
        self,
        session: ProcessingSession,
        slice_index: int,
        result: MergeWorkerResult,
    ) -> int:
        """校验线程输入代次并原子写回策略计划与合并结果。"""
        plan = result.plan
        if plan is None:
            raise ValueError("合并线程未返回策略计划")
        with session.lock:
            if not self._active_context_is_current(session, slice_index):
                raise ValueError("合并执行期间来源或策略已变化，已放弃旧线程结果")
            if plan.slice_index != slice_index:
                raise ValueError("合并线程返回了错误的切片索引")
            if self._active_strategy is None or (
                plan.strategy_id != self._active_strategy.strategy_id
            ):
                raise ValueError("合并线程返回的策略标识已失效")
            if len(result.merged_results) != plan.group_count:
                raise ValueError("合并线程结果数量与策略计划不一致")
            if len(result.rendered_bundles) != plan.group_count:
                raise ValueError("合并线程图像数量与策略计划不一致")

            if session.merge_result is None:
                session.merge_result = MergeResult()
            session.merge_result.slice_results[slice_index] = SliceMergeResult(
                slice_index=slice_index,
                merged_clusters=list(result.merged_results),
            )
            session.mark_slice_merge_succeeded(slice_index)
            session.stage = ProcessingStage.MERGED
            self._rendered_bundles[(session.session_id, slice_index)] = (
                result.rendered_bundles
            )
        return len(result.merged_results)

    def _active_context_is_current(
        self,
        session: ProcessingSession,
        slice_index: int,
    ) -> bool:
        """判断当前Session仍对应线程启动时冻结的来源和策略。"""
        current_sources = self._find_source_results(session, slice_index)
        return (
            session.is_slice_recognized(slice_index)
            and current_sources is not None
            and current_sources[0] is self._active_slice_clusters
            and current_sources[1] is self._active_slice_recognitions
            and self._strategy is self._active_strategy
            and session.merge_plan is not None
            and session.merge_plan.slice_plans.get(slice_index) is self._active_plan
        )

    def _cleanup_worker_context(self) -> None:
        """释放合并线程对象及其活动输入引用。"""
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._active_session = None
        self._active_slice_index = None
        self._active_strategy = None
        self._active_plan = None
        self._active_slice_clusters = None
        self._active_slice_recognitions = None

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
        previous_plan = (
            session.merge_plan.slice_plans.get(slice_index)
            if session.merge_plan is not None
            else None
        )
        previous_result_count = self.get_result_count(session, slice_index)
        LOGGER.info(
            "开始重置合并状态: slice_index=%d, previous_strategy_id=%s, "
            "previous_groups=%s, previous_result_count=%d",
            slice_index,
            None if previous_plan is None else previous_plan.strategy_id,
            (
                ()
                if previous_plan is None
                else tuple(
                    group.cluster_indices for group in previous_plan.groups
                )
            ),
            previous_result_count,
            extra={"session_id": session.session_id},
        )
        with session.lock:
            session.reset_slice_merge_state(slice_index)
            self._rendered_bundles.pop((session.session_id, slice_index), None)
            # 当前会话不再包含任何合并结果时，全局阶段同步回退到识别完成。
            if (
                session.merge_result is None
                and session.stage is ProcessingStage.MERGED
            ):
                session.stage = ProcessingStage.RECOGNIZED
        LOGGER.info(
            "合并状态重置完成: slice_index=%d, "
            "merge_judgment_suppressed=%s, session_stage=%s",
            slice_index,
            session.get_slice_processing_state(
                slice_index
            ).merge_judgment_suppressed,
            session.stage,
            extra={"session_id": session.session_id},
        )

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
        cached_bundles = self._rendered_bundles.get(
            (session.session_id, slice_index),
            (),
        )
        if visible_positions is None and result_index < len(cached_bundles):
            # 初次呈现及结果浏览直接复用Worker产出的图像，避免回到GUI线程重复栅格化。
            bundle = cached_bundles[result_index]
        else:
            bundle = render_merge_images(
                list(result.source_point_clouds),
                band=session.band,
                time_range=result.time_range,
                visible_cluster_indices=visible_positions,
                palette=palette,
            )
        title = (
            f"合并结果 第{result_index + 1}/{len(slice_result.merged_clusters)}类"
        )
        categories = tuple(
            MergeCategoryPresentation(
                cluster_index=cluster_index,
                color=colors[position],
                visible=visible_set is None or cluster_index in visible_set,
            )
            for position, cluster_index in enumerate(source_indices)
        )
        # 参数与图像使用同一组选中来源；全选时复用已保存的合并参数，
        # 部分选择时对可见来源点云即时重提取，且不修改持久化合并结果。
        params = self._extract_visible_params(
            session,
            result,
            visible_positions,
        )
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

    def _extract_visible_params(
        self,
        session: ProcessingSession,
        result: MergedClusterResult,
        visible_positions: list[int] | None,
    ) -> ExtractedClusterParams:
        """按当前可见来源点云返回参数提取结果。"""
        if (
            visible_positions is None
            or len(visible_positions) == len(result.source_point_clouds)
        ):
            return result.extracted_params
        if not visible_positions:
            return ExtractedClusterParams()

        # 来源点云在合并执行阶段已经完成结构校验，此处仅按稳定位置顺序拼接。
        visible_points = np.concatenate(
            [
                result.source_point_clouds[position]
                for position in visible_positions
            ],
            axis=0,
        )
        return extract_cluster_params(
            visible_points,
            self._build_extract_params(session),
        )

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
