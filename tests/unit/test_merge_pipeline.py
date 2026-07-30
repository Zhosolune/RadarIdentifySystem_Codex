"""合并流程链路单元测试。"""

from __future__ import annotations

from dataclasses import replace
import logging
from types import SimpleNamespace

import numpy as np
from PyQt6 import sip
from PyQt6.QtCore import QObject, QThread, Qt
from PyQt6.QtWidgets import QApplication
from pytest import LogCaptureFixture, MonkeyPatch, raises
from qfluentwidgets import CheckBox

import core.merge as merge_module
from core.merge import MergePipeline
from core.merge_strategy import DefaultMergeStrategy
from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import (
    ClusterItem,
    ClusterState,
    ClusteringResult,
    SliceClusterResult,
)
from core.models.extraction_result import ExtractedClusterParams
from core.models.merge_result import MergeGroup, SliceMergePlan, SliceMergeResult
from core.models.processing_session import (
    ProcessingSession,
    ProcessingStage,
    SliceProcessStatus,
)
from core.models.pulse_batch import COL_TOA
from core.models.recognition_result import (
    ClusterRecognition,
    RecognitionResult,
    SliceRecognitionResult,
)
from infra.plotting.facades import render_merge_images, resolve_merge_source_colors
from runtime.workflows.merge_workflow import MergeWorkflow
from ui.components.merge_image_column import MergeImageColumn
from ui.controllers.merge_controller import MergeController
from ui.interfaces.slice_interface import SliceInterface


_APP: QApplication | None = None


def _app() -> QApplication:
    """获取或创建测试用 QApplication。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _slice_interface(session: ProcessingSession) -> SliceInterface:
    """创建显式绑定 Session 的切片页面。"""
    return SliceInterface(session=session)


def _wait_for_merge_workflow(workflow: MergeWorkflow) -> None:
    """等待合并线程结束并处理主线程完成回调。"""
    worker = workflow._worker
    assert worker is not None
    assert worker.wait(10_000)
    for _index in range(100):
        QApplication.processEvents()
        if not workflow.is_running():
            break
    assert not workflow.is_running()


def _wait_for_merge_plan(workflow: MergeWorkflow) -> None:
    """等待当前及事件回调续接的合并候选判别线程。"""
    for _task_index in range(10):
        worker = workflow._plan_worker
        if worker is None:
            break
        assert worker.wait(10_000)
        QApplication.processEvents()
    assert not workflow.is_judging()


def _execute_merge_and_wait(
    workflow: MergeWorkflow,
    session: ProcessingSession,
    slice_index: int = 0,
) -> bool:
    """启动合并线程并等待主线程完成结果写回。"""
    _app()
    if not workflow.has_prepared_merge_plan(session, slice_index):
        judging_started = workflow.request_merge_plan(session, slice_index)
        if judging_started:
            _wait_for_merge_plan(workflow)
    started = workflow.execute_merge_plan(session, slice_index)
    if started:
        _wait_for_merge_workflow(workflow)
    return started


def _cluster(cluster_index: int, points: np.ndarray) -> ClusterItem:
    """构造已识别通过的测试簇。"""
    return ClusterItem(
        cluster_idx=cluster_index,
        dim_name="CF",
        points=points,
        points_indices=np.arange(len(points)) + cluster_index * 10,
        slice_idx=0,
        time_ranges=(
            float(points[:, COL_TOA].min()),
            float(points[:, COL_TOA].max()),
        ),
        state=ClusterState.VALID,
        valid_cluster_idx=cluster_index - 1,
    )


def _recognition(cluster_index: int) -> ClusterRecognition:
    """构造保留原模型输出的测试识别记录。"""
    return ClusterRecognition(
        slice_index=0,
        dim_name="CF",
        cluster_index=cluster_index,
        valid_cluster_index=cluster_index - 1,
        pa_label=cluster_index,
        pa_confidence=0.9,
        dtoa_label=cluster_index + 1,
        dtoa_confidence=0.8,
        is_valid=True,
        joint_prob=0.72,
        pa_conf_dict={cluster_index: 0.9},
        dtoa_conf_dict={cluster_index + 1: 0.8},
        extracted_params=ExtractedClusterParams(cf_values=[float(cluster_index)]),
    )


def _source_results() -> tuple[SliceClusterResult, SliceRecognitionResult]:
    """构造包含两个有效识别类的切片结果。"""
    first_points = np.array(
        [
            [5000.0, 1.0, 20.0, 50.0, 50.0, 100.0],
            [5001.0, 1.1, 21.0, 51.0, 51.0, 200.0],
        ]
    )
    second_points = np.array(
        [
            [6000.0, 2.0, 30.0, 60.0, 60.0, 300.0],
            [6001.0, 2.1, 31.0, 61.0, 61.0, 400.0],
        ]
    )
    return (
        SliceClusterResult(
            slice_idx=0,
            clusters=[_cluster(1, first_points), _cluster(2, second_points)],
        ),
        SliceRecognitionResult(
            slice_index=0,
            valid_clusters=[_recognition(1), _recognition(2)],
        ),
    )


def _session_with_source_results() -> ProcessingSession:
    """构造已经完成两个类识别的测试 session。"""
    slice_clusters, slice_recognitions = _source_results()
    session = ProcessingSession()
    session.reset_slice_processing_states(1)
    session.cluster_result = ClusteringResult(slice_results={0: slice_clusters})
    session.recognition_result = RecognitionResult(
        slice_results={0: slice_recognitions}
    )
    session.mark_slice_cluster_succeeded(0)
    session.mark_slice_recognition_succeeded(0)
    return session


def _session_with_four_source_results() -> ProcessingSession:
    """构造包含四个识别通过类的测试session。"""
    clusters: list[ClusterItem] = []
    recognitions: list[ClusterRecognition] = []
    for cluster_index in range(1, 5):
        base_cf = 4500.0 + cluster_index * 300.0
        base_toa = 100.0 + cluster_index * 300.0
        points = np.array(
            [
                [base_cf, cluster_index, 20.0, 40.0, 50.0, base_toa],
                [
                    base_cf + 1.0,
                    cluster_index + 0.1,
                    21.0,
                    41.0,
                    51.0,
                    base_toa + 100.0,
                ],
            ]
        )
        clusters.append(_cluster(cluster_index, points))
        recognitions.append(_recognition(cluster_index))
    session = ProcessingSession()
    session.reset_slice_processing_states(1)
    session.cluster_result = ClusteringResult(
        slice_results={
            0: SliceClusterResult(slice_idx=0, clusters=clusters),
        }
    )
    session.recognition_result = RecognitionResult(
        slice_results={
            0: SliceRecognitionResult(
                slice_index=0,
                valid_clusters=recognitions,
            ),
        }
    )
    session.mark_slice_cluster_succeeded(0)
    session.mark_slice_recognition_succeeded(0)
    return session


class _FixedBatchStrategy:
    """把四个测试类固定划分为两个互斥合并组。"""

    strategy_id = "fixed_batch_v1"

    def build_plan(
        self,
        slice_cluster_result: SliceClusterResult,
        _slice_recognition_result: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """返回两组固定合并计划。"""
        slice_index = slice_cluster_result.slice_idx
        return SliceMergePlan(
            slice_index=slice_index,
            strategy_id=self.strategy_id,
            groups=(
                MergeGroup(slice_index, (1, 2)),
                MergeGroup(slice_index, (3, 4)),
            ),
        )


class _FixedSingleStrategy:
    """把两个测试类固定为一个合并结果。"""

    strategy_id = "fixed_single_v1"

    def build_plan(
        self,
        slice_cluster_result: SliceClusterResult,
        _slice_recognition_result: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """返回单组固定合并计划。"""
        slice_index = slice_cluster_result.slice_idx
        return SliceMergePlan(
            slice_index=slice_index,
            strategy_id=self.strategy_id,
            groups=(MergeGroup(slice_index, (1, 2)),),
        )


class _ConfigurableStrategy:
    """使用同一策略ID和可变分组模拟未来的参数化合并策略。"""

    strategy_id = "configurable_v1"

    def __init__(self, groups: tuple[tuple[int, ...], ...]) -> None:
        """保存本次策略参数对应的固定分组。"""
        self.groups: tuple[tuple[int, ...], ...] = groups
        self.build_count: int = 0

    def build_plan(
        self,
        slice_cluster_result: SliceClusterResult,
        _slice_recognition_result: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """按当前实例参数生成计划并记录判别次数。"""
        self.build_count += 1
        slice_index = slice_cluster_result.slice_idx
        return SliceMergePlan(
            slice_index=slice_index,
            strategy_id=self.strategy_id,
            groups=tuple(
                MergeGroup(slice_index, cluster_indices)
                for cluster_indices in self.groups
            ),
        )


class _SliceAwareStrategy:
    """仅为第一个切片返回可合并分组。"""

    strategy_id = "slice_aware_v1"

    def build_plan(
        self,
        slice_cluster_result: SliceClusterResult,
        _slice_recognition_result: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """按切片索引返回不同的完整合并计划。"""
        slice_index = slice_cluster_result.slice_idx
        groups = (
            (MergeGroup(slice_index, (1, 2)),)
            if slice_index == 0
            else ()
        )
        return SliceMergePlan(
            slice_index=slice_index,
            strategy_id=self.strategy_id,
            groups=groups,
        )


def test_merge_chain_does_not_expose_manual_source_selection_entrypoints() -> None:
    """合并链路不得再暴露任何人工提交来源簇的兼容入口。"""
    assert not hasattr(merge_module, "MergeTarget")
    assert not hasattr(DefaultMergeStrategy, "build_targets")
    assert not hasattr(MergePipeline, "run")
    assert not hasattr(MergeWorkflow, "find_merge_candidates")
    assert not hasattr(MergeWorkflow, "start_merge_by_indices")
    assert not hasattr(MergeWorkflow, "start_strategy_merge_by_indices")
    assert not hasattr(MergeWorkflow, "start_merge")
    assert not hasattr(MergeController, "merge_clusters")


def test_merge_workflow_runs_strategy_pipeline_and_rendering_off_gui_thread(
    monkeypatch: MonkeyPatch,
) -> None:
    """策略判别、批量计算和绘图验证都应在合并子线程执行。"""
    _app()
    session = _session_with_source_results()
    strategy = _FixedSingleStrategy()
    workflow = MergeWorkflow(strategy=strategy)
    main_thread_id = int(QThread.currentThreadId())
    execution_thread_ids: list[int] = []

    original_build_plan = strategy.build_plan
    original_run_plan = MergePipeline.run_plan
    original_render = render_merge_images

    def record_build_plan(
        slice_cluster_result: SliceClusterResult,
        slice_recognition_result: SliceRecognitionResult,
    ) -> SliceMergePlan:
        """记录策略判别所在线程并执行原逻辑。"""
        execution_thread_ids.append(int(QThread.currentThreadId()))
        return original_build_plan(slice_cluster_result, slice_recognition_result)

    def record_run_plan(
        pipeline: MergePipeline,
        *args: object,
        **kwargs: object,
    ) -> object:
        """记录批量合并所在线程并执行原逻辑。"""
        execution_thread_ids.append(int(QThread.currentThreadId()))
        return original_run_plan(pipeline, *args, **kwargs)

    def record_render(*args: object, **kwargs: object) -> object:
        """记录绘图验证所在线程并执行原逻辑。"""
        execution_thread_ids.append(int(QThread.currentThreadId()))
        return original_render(*args, **kwargs)

    monkeypatch.setattr(strategy, "build_plan", record_build_plan)
    monkeypatch.setattr(MergePipeline, "run_plan", record_run_plan)
    monkeypatch.setattr(
        "runtime.threading.merge_worker.render_merge_images",
        record_render,
    )

    judging_started = workflow.request_merge_plan(session, 0)

    assert judging_started
    assert workflow.is_judging()
    assert session.merge_plan is None
    _wait_for_merge_plan(workflow)

    started = workflow.execute_merge_plan(session, 0)

    assert started
    assert workflow.is_running()
    assert session.merge_result is None
    assert (
        session.get_slice_processing_state(0).merge_status
        is SliceProcessStatus.RUNNING
    )
    _wait_for_merge_workflow(workflow)

    assert len(execution_thread_ids) == 3
    assert all(thread_id != main_thread_id for thread_id in execution_thread_ids)
    assert session.merge_result is not None
    presentation = workflow.render_result(session, 0, 0)
    assert presentation.images
    assert len(execution_thread_ids) == 3


def test_merge_pipeline_concatenates_points_and_only_reextracts_parameters(
    monkeypatch: MonkeyPatch,
) -> None:
    """合并流程应复用原识别记录，仅对拼接点云重新提取参数。"""
    slice_clusters, slice_recognitions = _source_results()
    extracted = ExtractedClusterParams(cf_values=[1050.0], pw_values=[1.5])
    extraction_inputs: list[np.ndarray] = []

    def fake_extract(
        points: np.ndarray,
        _params: ExtractParams,
    ) -> ExtractedClusterParams:
        """记录合并后参数提取输入。"""
        extraction_inputs.append(points.copy())
        return extracted

    monkeypatch.setattr("core.merge.extract_cluster_params", fake_extract)
    pipeline = MergePipeline(extract_params=ExtractParams())

    plan = SliceMergePlan(
        slice_index=0,
        strategy_id="test_strategy_v1",
        groups=(MergeGroup(slice_index=0, cluster_indices=(1, 2)),),
    )
    result = pipeline.run_plan(
        plan=plan,
        slice_cluster_result=slice_clusters,
        slice_recognition_result=slice_recognitions,
    )[0]

    expected_points = np.concatenate(
        [cluster.points for cluster in slice_clusters.clusters],
        axis=0,
    )
    assert len(extraction_inputs) == 1
    assert np.array_equal(extraction_inputs[0], expected_points)
    assert np.array_equal(result.merged_points, expected_points)
    assert result.source_cluster_indices == (1, 2)
    assert result.source_recognitions == tuple(slice_recognitions.valid_clusters)
    assert result.merged_recognition is None
    assert result.extracted_params is extracted
    assert result.source_point_clouds[0] is slice_clusters.clusters[0].points
    assert result.source_point_clouds[1] is slice_clusters.clusters[1].points


def test_merge_plan_rejects_ambiguous_or_invalid_strategy_sources() -> None:
    """策略计划应拒绝来源不足、重复或未识别通过的簇。"""
    slice_clusters, slice_recognitions = _source_results()

    with raises(ValueError, match="至少需要两个"):
        MergeGroup(slice_index=0, cluster_indices=(1,))
    with raises(ValueError, match="重复"):
        MergeGroup(slice_index=0, cluster_indices=(1, 1))
    with raises(ValueError, match="大于等于 1"):
        MergeGroup(slice_index=0, cluster_indices=(0, 1))
    with raises(ValueError, match="未找到来源簇"):
        MergePipeline().run_plan(
            plan=SliceMergePlan(
                slice_index=0,
                strategy_id="invalid_test_strategy_v1",
                groups=(MergeGroup(slice_index=0, cluster_indices=(1, 99)),),
            ),
            slice_cluster_result=slice_clusters,
            slice_recognition_result=slice_recognitions,
        )


def test_merge_workflow_logs_session_config_plan_and_atomic_writeback(
    caplog: LogCaptureFixture,
) -> None:
    """工作流日志应记录Session配置、完整计划、执行参数及原子写回结果。"""
    session = _session_with_four_source_results()
    workflow = MergeWorkflow(strategy=_FixedBatchStrategy())
    caplog.set_level(logging.INFO, logger="runtime.workflows.merge_workflow")

    plan = workflow.prepare_merge_plan(session, 0)
    started = _execute_merge_and_wait(workflow, session)

    assert plan is not None
    assert started
    workflow_records = [
        record
        for record in caplog.records
        if record.name == "runtime.workflows.merge_workflow"
    ]
    messages = "\n".join(record.getMessage() for record in workflow_records)
    assert "session合并参数快照={placeholder_value=0.0" in messages
    assert "当前字段为占位且不参与判别=True" in messages
    assert "strategy_id=fixed_batch_v1" in messages
    assert "groups=((1, 2), (3, 4))" in messages
    assert "参数提取配置=ExtractParams(" in messages
    assert "合并线程完成并已原子写回" in messages
    assert "结果来源=((1, 2), (3, 4))" in messages
    assert all(
        getattr(record, "session_id", None) == session.session_id
        for record in workflow_records
    )


def test_merge_workflow_records_failure_without_overwriting_results() -> None:
    """自动策略返回不可用来源时工作流应失败且不写入合并结果。"""
    session = _session_with_source_results()
    workflow = MergeWorkflow(strategy=_ConfigurableStrategy(((1, 99),)))

    started = _execute_merge_and_wait(workflow, session)

    state = session.get_slice_processing_state(0)
    assert started
    assert session.merge_result is None
    assert state.merge_status is SliceProcessStatus.FAILED
    assert state.last_merge_error is not None
    assert "未找到来源簇 99" in state.last_merge_error


def test_reidentify_invalidation_clears_only_target_slice_merge_results() -> None:
    """重新识别前应同时清除目标切片的合并计划和独立结果。"""
    session = _session_with_four_source_results()
    workflow = MergeWorkflow(strategy=_FixedBatchStrategy())
    plan = workflow.prepare_merge_plan(session, 0)
    started = _execute_merge_and_wait(workflow, session)

    assert plan is not None
    assert started
    assert session.merge_plan is not None
    assert session.merge_result is not None

    # 构造另一个切片的独立计划与结果，验证目标切片失效不会误删相邻切片。
    session.merge_plan.slice_plans[1] = SliceMergePlan(
        slice_index=1,
        strategy_id="other_slice_v1",
        groups=(MergeGroup(1, (1, 2)),),
    )
    session.merge_result.slice_results[1] = SliceMergeResult(
        slice_index=1,
        merged_clusters=[
            replace(result, slice_index=1)
            for result in session.merge_result.slice_results[0].merged_clusters
        ],
    )

    session.clear_slice_merge_results(0)

    assert session.merge_plan is not None
    assert set(session.merge_plan.slice_plans) == {1}
    assert session.merge_result is not None
    assert set(session.merge_result.slice_results) == {1}
    state = session.get_slice_processing_state(0)
    assert state.merge_status is SliceProcessStatus.NOT_STARTED
    assert state.last_merge_error is None


def test_merge_controller_executes_full_plan_and_browses_results() -> None:
    """控制器应一次执行完整计划，并用上一类下一类浏览结果。"""
    session = _session_with_four_source_results()
    image_updates: list[tuple[dict[str, np.ndarray], str]] = []
    table_updates: list[tuple[tuple[str, str], ...]] = []

    class FakeSignal:
        """提供控制器连接所需的最小信号接口。"""

        def __init__(self) -> None:
            """初始化槽函数列表。"""
            self.slots: list[object] = []

        def connect(self, slot: object) -> None:
            """记录一个待调用槽函数。"""
            self.slots.append(slot)

        def emit(self, *args: object) -> None:
            """同步调用全部槽函数。"""
            for slot in self.slots:
                slot(*args)

    class FakeButton:
        """提供控制器状态同步所需的最小按钮接口。"""

        def __init__(self) -> None:
            """初始化点击信号、勾选状态和启用状态。"""
            self.clicked = FakeSignal()
            self._checked = False
            self.enabled = True

        def isChecked(self) -> bool:
            """返回当前勾选状态。"""
            return self._checked

        def setChecked(self, checked: bool) -> None:
            """更新当前勾选状态。"""
            self._checked = checked

        def setEnabled(self, enabled: bool) -> None:
            """更新当前启用状态。"""
            self.enabled = enabled

        def isEnabled(self) -> bool:
            """返回当前启用状态。"""
            return self.enabled

    class FakeCategoryCard:
        """记录动态类别与显隐状态。"""

        def __init__(self) -> None:
            """初始化伪类别卡。"""
            self.visibility_changed = FakeSignal()
            self.category_checkboxes: dict[int, FakeButton] = {}

        def set_categories(
            self,
            categories: tuple[tuple[int, tuple[int, int, int]], ...],
            checked_indices: tuple[int, ...],
        ) -> None:
            """保存当前来源类别。"""
            checked_set = set(checked_indices)
            self.category_checkboxes = {
                index: FakeButton() for index, _color in categories
            }
            for index, checkbox in self.category_checkboxes.items():
                checkbox.setChecked(index in checked_set)

        def clear_categories(self) -> None:
            """清空当前来源类别。"""
            self.category_checkboxes.clear()

        def set_all_visible(self, visible: bool) -> None:
            """统一更新全部来源类别状态。"""
            for checkbox in self.category_checkboxes.values():
                checkbox.setChecked(visible)

    class FakeOperationCard:
        """提供控制器所需的操作卡片接口。"""

        def __init__(
            self,
            button_bar: SimpleNamespace,
            category_card: FakeCategoryCard,
        ) -> None:
            """初始化按钮、类别卡和界面状态。"""
            self.button_bar = button_bar
            self.category_display_card = category_card
            self.global_visibility_changed = FakeSignal()
            self.result_count: int | None = None

        def set_result_count(self, result_count: int | None) -> None:
            """记录当前合并结果数量。"""
            self.result_count = result_count

        def set_categories(
            self,
            categories: tuple[tuple[int, tuple[int, int, int]], ...],
            checked_indices: tuple[int, ...],
        ) -> None:
            """转发来源类别更新。"""
            self.category_display_card.set_categories(
                categories,
                checked_indices,
            )

        def clear_categories(self) -> None:
            """清空来源类别。"""
            self.category_display_card.clear_categories()

    class FakeResultTable:
        """记录当前结果表格内容。"""

        def update_rows(self, rows: tuple[tuple[str, str], ...]) -> None:
            """保存表格行。"""
            table_updates.append(rows)

        def clear_rows(self) -> None:
            """清空表格行。"""
            table_updates.clear()

    class FakeView(QObject):
        """提供合并控制器所需最小页面接口。"""

        def __init__(self) -> None:
            """初始化伪页面依赖。"""
            super().__init__()
            self._session = session
            self._slice_controller = SimpleNamespace(current_slice_index=0)
            button_bar = SimpleNamespace(
                merge_button=FakeButton(),
                prev_cluster_button=FakeButton(),
                next_cluster_button=FakeButton(),
                reset_button=FakeButton(),
            )
            category_card = FakeCategoryCard()
            operation_card = FakeOperationCard(button_bar, category_card)
            self.merge_operation_panel = SimpleNamespace(
                operation_card=operation_card,
                result_table_card=FakeResultTable(),
            )
            self.right_panel = SimpleNamespace(
                navigation_control_card=SimpleNamespace(
                    merge_menu_button=FakeButton()
                )
            )
            self.merge_image_column = SimpleNamespace(
                update_images=lambda images, title: image_updates.append(
                    (images, title)
                ),
                clear_images=lambda: image_updates.clear(),
            )

    view = FakeView()
    controller = MergeController(view)

    try:
        _app()
        assert not view.right_panel.navigation_control_card.merge_menu_button.enabled
        _wait_for_merge_plan(controller._workflow)
        controller.set_strategy(_FixedBatchStrategy())
        assert not view.right_panel.navigation_control_card.merge_menu_button.enabled
        _wait_for_merge_plan(controller._workflow)
        assert view.right_panel.navigation_control_card.merge_menu_button.enabled

        controller._execute_merge_plan()
        assert controller._workflow.is_running()
        button_bar = view.merge_operation_panel.operation_card.button_bar
        assert not button_bar.merge_button.enabled
        assert not button_bar.prev_cluster_button.enabled
        assert not button_bar.next_cluster_button.enabled
        assert not button_bar.reset_button.enabled
        _wait_for_merge_workflow(controller._workflow)

        assert session.merge_result is not None
        results = session.merge_result.slice_results[0].merged_clusters
        assert [result.source_cluster_indices for result in results] == [
            (1, 2),
            (3, 4),
        ]
        assert all(result.strategy_id == "fixed_batch_v1" for result in results)
        assert view.right_panel.navigation_control_card.merge_menu_button.enabled
        assert not button_bar.merge_button.enabled
        assert not button_bar.prev_cluster_button.enabled
        assert button_bar.next_cluster_button.enabled
        assert view.merge_operation_panel.operation_card.result_count == 2
        assert "第1/2组" in image_updates[-1][1]

        controller._show_next_result()

        assert button_bar.prev_cluster_button.enabled
        assert not button_bar.next_cluster_button.enabled
        assert "第2/2组" in image_updates[-1][1]
        assert set(
            view.merge_operation_panel.operation_card.category_display_card.category_checkboxes
        ) == {3, 4}
        assert table_updates

        controller._reset_merge_state()

        assert session.merge_plan is None
        assert session.merge_result is None
        assert (
            session.get_slice_processing_state(0).merge_judgment_suppressed
            is True
        )
        assert view.merge_operation_panel.operation_card.result_count is None
        assert view.right_panel.navigation_control_card.merge_menu_button.enabled
        assert button_bar.merge_button.enabled
    finally:
        sip.delete(view)


def test_merge_workflow_executes_full_plan_without_mutating_recognition() -> None:
    """runtime应一次执行全部分组，并保持识别结果对象与内容不变。"""
    session = _session_with_four_source_results()
    workflow = MergeWorkflow(strategy=_FixedBatchStrategy())
    recognition_result = session.recognition_result
    assert recognition_result is not None
    recognition_slice = recognition_result.slice_results[0]
    recognition_items = tuple(recognition_slice.valid_clusters)

    assert workflow.strategy_id == "fixed_batch_v1"
    assert workflow.get_merge_groups(session, 0) == ((1, 2), (3, 4))

    # 识别失败时即使旧对象仍在session，也不得暴露旧计划。
    session.mark_slice_recognition_failed(0, "测试识别失败")
    assert workflow.get_merge_groups(session, 0) == ()
    session.mark_slice_recognition_succeeded(0)

    started = _execute_merge_and_wait(workflow, session)

    assert started
    assert session.recognition_result is recognition_result
    assert tuple(recognition_slice.valid_clusters) == recognition_items
    assert workflow.get_merge_groups(session, 0) == ((1, 2), (3, 4))

    duplicate_started = workflow.execute_merge_plan(session, 0)
    assert not duplicate_started
    assert session.merge_result is not None
    assert len(session.merge_result.slice_results[0].merged_clusters) == 2

    workflow.reset_merge_state(session, 0)

    slice_state = session.get_slice_processing_state(0)
    assert session.merge_plan is None
    assert session.merge_result is None
    assert session.stage is ProcessingStage.RECOGNIZED
    assert slice_state.merge_status is SliceProcessStatus.NOT_STARTED
    assert slice_state.merge_judgment_suppressed is True
    assert workflow.get_merge_groups(session, 0) == ()
    assert workflow.get_merge_groups(session, 0, force=True) == (
        (1, 2),
        (3, 4),
    )
    assert slice_state.merge_judgment_suppressed is False


def test_batch_merge_failure_does_not_write_partial_results(
    monkeypatch: MonkeyPatch,
) -> None:
    """整批执行任一步失败时不应写入半完成结果。"""
    session = _session_with_four_source_results()
    workflow = MergeWorkflow(strategy=_FixedBatchStrategy())
    workflow.prepare_merge_plan(session, 0)

    def fail_run_plan(*_args: object, **_kwargs: object) -> object:
        """模拟批量执行中途失败。"""
        raise ValueError("模拟第二组合并失败")

    monkeypatch.setattr(MergePipeline, "run_plan", fail_run_plan)

    started = _execute_merge_and_wait(workflow, session)

    assert started
    assert session.merge_result is None
    state = session.get_slice_processing_state(0)
    assert state.merge_status is SliceProcessStatus.FAILED
    assert state.last_merge_error is not None
    assert "模拟第二组合并失败" in state.last_merge_error


def test_batch_merge_discards_results_when_recognition_changes(
    monkeypatch: MonkeyPatch,
) -> None:
    """批量执行期间来源识别失效时不得写回旧计划结果。"""
    session = _session_with_four_source_results()
    workflow = MergeWorkflow(strategy=_FixedBatchStrategy())
    workflow.prepare_merge_plan(session, 0)
    original_run_plan = MergePipeline.run_plan

    def invalidate_after_run(
        pipeline: MergePipeline,
        *args: object,
        **kwargs: object,
    ) -> object:
        """先生成结果，再模拟目标切片进入重新识别。"""
        results = original_run_plan(pipeline, *args, **kwargs)
        session.mark_slice_recognition_running(0)
        session.clear_slice_merge_results(0)
        return results

    monkeypatch.setattr(MergePipeline, "run_plan", invalidate_after_run)

    started = _execute_merge_and_wait(workflow, session)

    assert started
    assert session.merge_result is None
    assert (
        session.get_slice_processing_state(0).merge_status
        is SliceProcessStatus.NOT_STARTED
    )


def test_merge_image_column_displays_rgb_bundle_from_workflow() -> None:
    """合并图像列应显示runtime呈现数据中的五维RGB图像。"""
    _app()
    session = _session_with_four_source_results()
    workflow = MergeWorkflow(strategy=_FixedBatchStrategy())
    workflow.prepare_merge_plan(session, 0)
    started = _execute_merge_and_wait(workflow, session)
    presentation = workflow.render_result(session, 0, 0)
    column = MergeImageColumn()

    try:
        assert started
        column.update_images(presentation.images, presentation.title)

        assert column.title_label.text() == "合并结果 第1/2组（原第1+2类）"
        assert all(
            card._source_image is not None for card in column.dimension_cards
        )
        assert all(
            card.image_label._source_image is not None
            for card in column.dimension_cards
        )
    finally:
        sip.delete(column)


def test_merge_presentation_formats_pri_like_right_panel() -> None:
    """合并呈现模型应与右侧表格一致保留一位小数并交由UI分行。"""
    session = _session_with_source_results()
    workflow = MergeWorkflow(strategy=_FixedSingleStrategy())
    workflow.prepare_merge_plan(session, 0)
    started = _execute_merge_and_wait(workflow, session)
    assert started
    assert session.merge_result is not None

    slice_result = session.merge_result.slice_results[0]
    merged = slice_result.merged_clusters[0]
    slice_result.merged_clusters[0] = replace(
        merged,
        extracted_params=replace(
            merged.extracted_params,
            pri_values=[float(value) for value in range(1, 9)],
        ),
    )

    presentation = workflow.render_result(session, 0, 0)

    assert presentation.table_rows[2] == (
        "PRI",
        "1.0、2.0、3.0、4.0、5.0、6.0、7.0、8.0",
    )


def test_hiding_merge_source_updates_parameters_and_preserves_color() -> None:
    """隐藏来源后参数应按可见点云更新，且其余来源颜色不得重分配。"""
    session = _session_with_source_results()
    workflow = MergeWorkflow(strategy=_FixedSingleStrategy())
    workflow.prepare_merge_plan(session, 0)
    started = _execute_merge_and_wait(workflow, session)
    assert started

    full = workflow.render_result(session, 0, 0)
    hidden = workflow.render_result(session, 0, 0, visible_cluster_indices=(2,))
    empty = workflow.render_result(session, 0, 0, visible_cluster_indices=())

    assert [category.color for category in full.categories] == [
        category.color for category in hidden.categories
    ]
    second_color = np.asarray(full.categories[1].color, dtype=np.uint8)
    assert np.any(np.all(full.images["CF"] == second_color, axis=2))
    assert np.any(np.all(hidden.images["CF"] == second_color, axis=2))
    first_color = np.asarray(full.categories[0].color, dtype=np.uint8)
    assert not np.any(np.all(hidden.images["CF"] == first_color, axis=2))
    assert hidden.categories[0].visible is False
    assert hidden.categories[1].visible is True
    assert full.table_rows[3] == ("DOA", "55.5")
    assert hidden.table_rows[3] == ("DOA", "60.5")
    assert all(value == "——" for _label, value in empty.table_rows)


def test_merge_palette_assigns_distinct_colors_beyond_default_capacity() -> None:
    """来源超过默认色板容量时仍应为每类分配不同颜色。"""
    colors = resolve_merge_source_colors(12)

    assert len(colors) == 12
    assert len(set(colors)) == 12


def test_visibility_controls_update_merge_parameter_table(
    monkeypatch: MonkeyPatch,
) -> None:
    """类别及全局复选框变化时应按当前选中点云刷新参数表格。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    interface = _slice_interface(_session_with_source_results())

    try:
        interface.resize(1500, 900)
        interface.show()
        QApplication.processEvents()
        controller = interface._merge_controller
        controller.set_strategy(_FixedSingleStrategy())
        _wait_for_merge_plan(controller._workflow)
        controller._execute_merge_plan()
        _wait_for_merge_workflow(controller._workflow)

        operation_card = interface.merge_operation_panel.operation_card
        category_card = operation_card.category_display_card
        result_table = interface.merge_operation_panel.result_table_card.table
        global_checkbox = operation_card.global_visibility_checkbox
        assert result_table.item(3, 1).text() == "55.5"

        category_card.category_checkboxes[1].setChecked(False)
        QApplication.processEvents()
        assert category_card.visible_cluster_indices() == (2,)
        assert result_table.item(3, 1).text() == "60.5"

        global_checkbox.click()
        QApplication.processEvents()
        assert category_card.visible_cluster_indices() == (1, 2)
        assert result_table.item(3, 1).text() == "55.5"

        global_checkbox.click()
        QApplication.processEvents()
        assert category_card.visible_cluster_indices() == ()
        assert all(
            result_table.item(row, 1).text() == "——"
            for row in range(result_table.rowCount())
        )
    finally:
        sip.delete(interface)


def test_reset_allows_rejudgment_with_same_strategy_id_and_new_parameters(
    monkeypatch: MonkeyPatch,
) -> None:
    """重置后应后台重判，并按同ID的新策略参数执行新计划。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    session = _session_with_four_source_results()
    interface = _slice_interface(session)

    try:
        controller = interface._merge_controller
        operation_card = interface.merge_operation_panel.operation_card
        menu_button = interface.right_panel.navigation_control_card.merge_menu_button
        first_strategy = _ConfigurableStrategy(((1, 2),))
        controller.set_strategy(first_strategy)

        # 策略在后台完成候选判别前，菜单和执行按钮必须保持禁用。
        assert session.merge_plan is None
        assert not menu_button.isEnabled()
        _wait_for_merge_plan(controller._workflow)
        assert menu_button.isEnabled()
        assert operation_card.button_bar.merge_button.isEnabled()
        controller._execute_merge_plan()
        _wait_for_merge_workflow(controller._workflow)
        assert first_strategy.build_count == 1
        assert session.merge_result is not None
        assert (
            session.merge_result.slice_results[0]
            .merged_clusters[0]
            .source_cluster_indices
            == (1, 2)
        )

        menu_button.click()
        QApplication.processEvents()
        controller._reset_merge_state()
        _wait_for_merge_plan(controller._workflow)
        assert session.merge_plan is not None
        assert session.merge_result is None
        assert menu_button.isEnabled()
        assert operation_card.button_bar.merge_button.isEnabled()
        assert operation_card.button_bar.reset_button.isEnabled()
        assert "？" in operation_card.result_count_label.text()

        # 新实例保持相同strategy_id但模拟参数变化，旧ID不得导致计划被错误复用。
        second_strategy = _ConfigurableStrategy(((3, 4),))
        controller.set_strategy(second_strategy)
        _wait_for_merge_plan(controller._workflow)
        controller._execute_merge_plan()
        _wait_for_merge_workflow(controller._workflow)
        assert second_strategy.build_count == 1
        assert session.merge_result is not None
        assert (
            session.merge_result.slice_results[0]
            .merged_clusters[0]
            .source_cluster_indices
            == (3, 4)
        )
    finally:
        sip.delete(interface)


def test_empty_rejudgment_keeps_merge_menu_disabled_after_reset(
    monkeypatch: MonkeyPatch,
) -> None:
    """无候选计划应显示0，重置重判后仍不得激活合并菜单。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    session = _session_with_source_results()
    interface = _slice_interface(session)

    try:
        controller = interface._merge_controller
        operation_card = interface.merge_operation_panel.operation_card
        menu_button = interface.right_panel.navigation_control_card.merge_menu_button
        strategy = _ConfigurableStrategy(())
        controller.set_strategy(strategy)
        _wait_for_merge_plan(controller._workflow)

        assert strategy.build_count == 1
        assert session.merge_plan is not None
        assert session.merge_plan.slice_plans[0].groups == ()
        assert session.merge_result is None
        assert "0" in operation_card.result_count_label.text()
        assert not menu_button.isEnabled()
        assert not operation_card.button_bar.merge_button.isEnabled()
        assert operation_card.button_bar.reset_button.isEnabled()

        controller._reset_merge_state()
        _wait_for_merge_plan(controller._workflow)
        assert session.merge_plan is not None
        assert "0" in operation_card.result_count_label.text()
        assert not menu_button.isEnabled()
        assert not operation_card.button_bar.merge_button.isEnabled()
        assert operation_card.button_bar.reset_button.isEnabled()
    finally:
        sip.delete(interface)


def test_single_result_uses_global_visibility_and_resets_merge_state(
    monkeypatch: MonkeyPatch,
) -> None:
    """单结果合并后应支持全局显隐，并可重置后后台重判。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    interface = _slice_interface(_session_with_source_results())

    try:
        interface.resize(1500, 900)
        interface.show()
        QApplication.processEvents()
        interface.image_workspace.setScrollAnimation(Qt.Orientation.Horizontal, 0)
        interface._merge_controller.set_strategy(_FixedSingleStrategy())
        _wait_for_merge_plan(interface._merge_controller._workflow)
        menu_button = (
            interface.right_panel.navigation_control_card.merge_menu_button
        )
        button_bar = interface.merge_operation_panel.operation_card.button_bar

        assert menu_button.isEnabled()
        menu_button.click()
        QApplication.processEvents()
        assert menu_button.isChecked()
        assert interface.image_workspace.is_merge_active()

        button_bar.merge_button.click()
        _wait_for_merge_workflow(interface._merge_controller._workflow)

        assert menu_button.isEnabled()
        assert menu_button.isChecked()
        assert interface.image_workspace.is_merge_active()
        assert interface.image_workspace.current_pair_index() == 2
        assert not button_bar.merge_button.isEnabled()
        assert not button_bar.prev_cluster_button.isEnabled()
        assert not button_bar.next_cluster_button.isEnabled()
        operation_card = interface.merge_operation_panel.operation_card
        assert operation_card.result_count_label.text() == "共获得1个合并结果"
        category_card = (
            operation_card.category_display_card
        )
        assert set(category_card.category_checkboxes) == {1, 2}
        assert all(
            isinstance(checkbox, CheckBox) and not checkbox.isTristate()
            for checkbox in category_card.category_checkboxes.values()
        )
        assert len(set(category_card.category_colors.values())) == 2
        global_checkbox = operation_card.global_visibility_checkbox
        assert global_checkbox.isTristate()
        assert global_checkbox.isEnabled()
        assert global_checkbox.checkState() == Qt.CheckState.Checked
        assert category_card.height() == category_card.sizeHint().height()
        assert all(
            checkbox.parentWidget() is not None
            and checkbox.parentWidget().height() > 0
            for checkbox in category_card.category_checkboxes.values()
        )

        category_card.category_checkboxes[1].setChecked(False)
        QApplication.processEvents()
        assert category_card.visible_cluster_indices() == (2,)
        assert global_checkbox.checkState() == Qt.CheckState.PartiallyChecked

        global_checkbox.click()
        QApplication.processEvents()
        assert category_card.visible_cluster_indices() == (1, 2)
        assert global_checkbox.checkState() == Qt.CheckState.Checked

        global_checkbox.click()
        QApplication.processEvents()
        assert category_card.visible_cluster_indices() == ()
        assert global_checkbox.checkState() == Qt.CheckState.Unchecked

        global_checkbox.click()
        QApplication.processEvents()
        assert category_card.visible_cluster_indices() == (1, 2)
        assert global_checkbox.checkState() == Qt.CheckState.Checked

        recognition_result = interface._session.recognition_result
        button_bar.reset_button.click()
        _wait_for_merge_plan(interface._merge_controller._workflow)

        assert interface._session.recognition_result is recognition_result
        assert interface._session.merge_plan is not None
        assert interface._session.merge_result is None
        assert (
            interface._session.get_slice_processing_state(
                0
            ).merge_judgment_suppressed
            is False
        )
        assert menu_button.isEnabled()
        assert menu_button.isChecked()
        assert interface.image_workspace.is_merge_active()
        assert interface.image_workspace.current_pair_index() == 2
        assert button_bar.merge_button.isEnabled()
        assert button_bar.reset_button.isEnabled()
        assert operation_card.result_count_label.text() == "共获得？个合并结果"
        assert not operation_card.global_visibility_checkbox.isEnabled()
        assert not category_card.category_checkboxes
        assert category_card.skeleton.isVisible()
    finally:
        sip.delete(interface)


def test_merge_menu_activation_follows_current_slice_candidates(
    monkeypatch: MonkeyPatch,
) -> None:
    """切换切片后，菜单应只按当前切片的策略候选状态激活。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    first_clusters, first_recognitions = _source_results()
    second_clusters = SliceClusterResult(
        slice_idx=1,
        clusters=[
            replace(cluster, slice_idx=1)
            for cluster in first_clusters.clusters
        ],
    )
    second_recognitions = SliceRecognitionResult(
        slice_index=1,
        valid_clusters=[
            replace(recognition, slice_index=1)
            for recognition in first_recognitions.valid_clusters
        ],
    )
    session = ProcessingSession()
    session.reset_slice_processing_states(2)
    session.cluster_result = ClusteringResult(
        slice_results={0: first_clusters, 1: second_clusters}
    )
    session.recognition_result = RecognitionResult(
        slice_results={0: first_recognitions, 1: second_recognitions}
    )
    for slice_index in range(2):
        session.mark_slice_cluster_succeeded(slice_index)
        session.mark_slice_recognition_succeeded(slice_index)
    interface = _slice_interface(session)

    try:
        controller = interface._merge_controller
        menu_button = (
            interface.right_panel.navigation_control_card.merge_menu_button
        )
        _wait_for_merge_plan(controller._workflow)
        controller.set_strategy(_SliceAwareStrategy())
        _wait_for_merge_plan(controller._workflow)

        assert controller._workflow.get_prepared_merge_groups(session, 0) == (
            (1, 2),
        )
        assert menu_button.isEnabled()

        interface._slice_controller._current_slice_index = 1
        controller.refresh_current_slice_state(reset_index=True)
        assert not menu_button.isEnabled()
        _wait_for_merge_plan(controller._workflow)

        assert controller._workflow.has_prepared_merge_plan(session, 1)
        assert controller._workflow.get_prepared_merge_groups(session, 1) == ()
        assert not menu_button.isEnabled()
        assert not menu_button.isChecked()
    finally:
        sip.delete(interface)


def test_identify_finished_does_not_prepare_plan_for_non_current_slice(
    monkeypatch: MonkeyPatch,
) -> None:
    """识别完成事件不应提前判定非当前切片的可合并类。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    session = _session_with_source_results()
    interface = _slice_interface(session)

    try:
        _wait_for_merge_plan(interface._merge_controller._workflow)
        interface._merge_controller._workflow.set_strategy(_FixedSingleStrategy())
        session.merge_plan = None
        interface._slice_controller._current_slice_index = 1

        interface._merge_controller._on_stage_finished(
            session.session_id,
            "identifying",
            0,
        )

        assert session.merge_plan is None
    finally:
        sip.delete(interface)


def test_identify_finished_logs_merge_menu_activation_judgment(
    monkeypatch: MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    """识别完成后应记录合并菜单激活判别的输入、规则和最终状态。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    session = _session_with_source_results()
    interface = _slice_interface(session)

    try:
        _wait_for_merge_plan(interface._merge_controller._workflow)
        interface._merge_controller.set_strategy(_FixedSingleStrategy())
        _wait_for_merge_plan(interface._merge_controller._workflow)
        caplog.set_level(logging.INFO, logger="ui.controllers.merge_controller")
        caplog.clear()

        interface._merge_controller._on_stage_finished(
            session.session_id,
            "identifying",
            0,
        )

        records = [
            record
            for record in caplog.records
            if record.name == "ui.controllers.merge_controller"
        ]
        messages = "\n".join(record.getMessage() for record in records)
        assert "收到阶段完成事件并开始合并菜单激活判别" in messages
        assert "识别完成事件通过合并菜单激活前置校验" in messages
        assert "开始合并菜单可用性判别" in messages
        assert "规则=has_candidates OR has_results" in messages
        assert "is_recognized=True" in messages
        assert "has_candidates=True" in messages
        assert "activation_reason=当前切片存在策略判定的可合并类" in messages
        assert "enabled=True" in messages
        assert "识别完成后的合并菜单激活流程结束" in messages
        assert all(
            getattr(record, "session_id", None) == session.session_id
            for record in records
        )
    finally:
        sip.delete(interface)
