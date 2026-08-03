"""合并计划判别与批量执行后台线程。

本模块在子线程中完成合并策略判别、点云合并、参数重提取和绘图可用性
验证。线程只返回不可变执行结果，不直接写入 Session 或操作界面。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.logger import bind_session_log_context, unbind_session_log_context
from core.merge import MergePipeline
from core.merge_strategy import MergeStrategy
from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import SliceClusterResult
from core.models.merge_result import MergedClusterResult, SliceMergePlan
from core.models.recognition_result import SliceRecognitionResult
from infra.plotting.facades import build_merge_palette, render_merge_images
from infra.plotting.types import RenderedImageBundle


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MergePlanWorkerResult:
    """合并候选判别线程结果。

    Attributes:
        success [bool]: 策略是否成功生成完整计划。
        plan [SliceMergePlan | None]: 当前切片的完整合并计划。
        error_message [str]: 失败原因，成功时为空字符串。
    """

    success: bool
    plan: SliceMergePlan | None = None
    error_message: str = ""


class MergePlanWorker(QThread):
    """合并候选计划后台判别线程。

    Attributes:
        finished_signal [pyqtSignal]: 完成信号，参数为 session_id 和
            :class:`MergePlanWorkerResult`。
    """

    finished_signal = pyqtSignal(str, object)

    def __init__(
        self,
        session_id: str,
        slice_index: int,
        strategy: MergeStrategy,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
        parent: QObject | None = None,
    ) -> None:
        """初始化合并候选判别线程。

        Args:
            session_id [str]: 当前任务所属 Session 标识。
            slice_index [int]: 目标切片的 0-based 索引。
            strategy [MergeStrategy]: 本次判别冻结的合并策略实例。
            slice_cluster_result [SliceClusterResult]: 本次判别冻结的聚类结果。
            slice_recognition_result [SliceRecognitionResult]: 本次判别冻结的识别结果。
            parent [QObject | None]: Qt 父对象，默认不挂载。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self._session_id = session_id
        self._slice_index = slice_index
        self._strategy = strategy
        self._slice_cluster_result = slice_cluster_result
        self._slice_recognition_result = slice_recognition_result

    def run(self) -> None:
        """在线程中生成当前切片完整合并计划。

        Returns:
            None: 结果通过 ``finished_signal`` 发出。

        Raises:
            无。所有异常都会转换为失败结果并通过信号返回。
        """
        log_token = bind_session_log_context(self._session_id)
        try:
            LOGGER.debug(
                "合并候选判别线程启动: slice_index=%d, strategy_id=%s",
                self._slice_index,
                self._strategy.strategy_id,
            )
            plan = self._strategy.build_plan(
                self._slice_cluster_result,
                self._slice_recognition_result,
            )
            if plan.slice_index != self._slice_index:
                raise ValueError("合并准则返回了错误的切片索引")
            if plan.strategy_id != self._strategy.strategy_id:
                raise ValueError("合并计划的策略标识与当前策略不一致")
            self.finished_signal.emit(
                self._session_id,
                MergePlanWorkerResult(success=True, plan=plan),
            )
        except Exception as error:
            LOGGER.error("合并候选判别线程失败: %s", error, exc_info=True)
            self.finished_signal.emit(
                self._session_id,
                MergePlanWorkerResult(success=False, error_message=str(error)),
            )
        finally:
            unbind_session_log_context(log_token)


@dataclass(frozen=True, slots=True)
class MergeWorkerResult:
    """合并线程执行结果。

    Attributes:
        success [bool]: 已判定计划的整批计算是否全部成功。
        plan [SliceMergePlan | None]: 本次执行消费的完整切片计划。
        merged_results [tuple[MergedClusterResult, ...]]: 与计划分组顺序一致的合并结果。
        rendered_bundles [tuple[RenderedImageBundle, ...]]: 各结果的完整来源五维图像。
        error_message [str]: 失败原因，成功时为空字符串。
    """

    success: bool
    plan: SliceMergePlan | None = None
    merged_results: tuple[MergedClusterResult, ...] = ()
    rendered_bundles: tuple[RenderedImageBundle, ...] = ()
    error_message: str = ""


class MergeWorker(QThread):
    """合并计划批量计算后台线程。

    Attributes:
        finished_signal [pyqtSignal]: 完成信号，参数为 session_id 和
            :class:`MergeWorkerResult`。
    """

    finished_signal = pyqtSignal(str, object)

    def __init__(
        self,
        session_id: str,
        slice_index: int,
        plan: SliceMergePlan,
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
        extract_params: ExtractParams,
        band: str | None,
        parent: QObject | None = None,
    ) -> None:
        """初始化合并工作线程。

        Args:
            session_id [str]: 当前任务所属 Session 标识。
            slice_index [int]: 目标切片的 0-based 索引。
            plan [SliceMergePlan]: 后台策略判别生成并冻结的完整合并计划。
            slice_cluster_result [SliceClusterResult]: 本次任务冻结的聚类结果。
            slice_recognition_result [SliceRecognitionResult]: 本次任务冻结的识别结果。
            extract_params [ExtractParams]: Session 参数提取快照。
            band [str | None]: 绘图使用的频段信息。
            parent [QObject | None]: Qt 父对象，默认不挂载。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(parent)
        self._session_id = session_id
        self._slice_index = slice_index
        self._plan = plan
        self._slice_cluster_result = slice_cluster_result
        self._slice_recognition_result = slice_recognition_result
        self._extract_params = extract_params
        self._band = band

    def run(self) -> None:
        """在线程中执行完整合并计划。

        Returns:
            None: 结果通过 ``finished_signal`` 发出。

        Raises:
            无。所有异常都会转换为失败结果并通过信号返回。
        """
        log_token = bind_session_log_context(self._session_id)
        try:
            LOGGER.info(
                "合并执行线程启动: slice_index=%d, strategy_id=%s, groups=%s",
                self._slice_index,
                self._plan.strategy_id,
                tuple(group.cluster_indices for group in self._plan.groups),
            )

            pipeline = MergePipeline(self._extract_params)
            merged_results = pipeline.run_plan(
                self._plan,
                self._slice_cluster_result,
                self._slice_recognition_result,
            )
            if not merged_results:
                raise ValueError("合并计划没有生成任何结果")

            # 在线程内完成五维绘图验证，避免大图栅格化阻塞 GUI 线程。
            rendered_bundles: list[RenderedImageBundle] = []
            for merged in merged_results:
                LOGGER.debug(
                    "合并线程验证结果绘图: slice_index=%d, merge_index=%d, "
                    "source_cluster_indices=%s, band=%s",
                    self._slice_index,
                    merged.merge_index,
                    merged.source_cluster_indices,
                    self._band,
                )
                rendered_bundles.append(
                    render_merge_images(
                        list(merged.source_point_clouds),
                        band=self._band,
                        time_range=merged.time_range,
                        palette=build_merge_palette(
                            len(merged.source_point_clouds)
                        ),
                    )
                )

            self.finished_signal.emit(
                self._session_id,
                MergeWorkerResult(
                    success=True,
                    plan=self._plan,
                    merged_results=merged_results,
                    rendered_bundles=tuple(rendered_bundles),
                ),
            )
        except Exception as error:
            LOGGER.error("合并线程执行失败: %s", error, exc_info=True)
            self.finished_signal.emit(
                self._session_id,
                MergeWorkerResult(success=False, error_message=str(error)),
            )
        finally:
            unbind_session_log_context(log_token)
