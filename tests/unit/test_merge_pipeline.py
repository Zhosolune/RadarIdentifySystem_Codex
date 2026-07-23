"""合并流程链路单元测试。"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
from PyQt6 import sip
from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch, raises
from qfluentwidgets import CheckBox

from core.merge import MergePipeline, MergeTarget
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
from infra.plotting.facades import resolve_merge_source_colors
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

    result = pipeline.run(
        target=MergeTarget(slice_index=0, cluster_indices=(1, 2)),
        slice_cluster_result=slice_clusters,
        slice_recognition_result=slice_recognitions,
        merge_index=1,
    )

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


def test_merge_target_rejects_ambiguous_or_invalid_sources() -> None:
    """显式目标应拒绝来源不足、重复或未识别通过的簇。"""
    slice_clusters, slice_recognitions = _source_results()

    with raises(ValueError, match="至少需要两个"):
        MergeTarget(slice_index=0, cluster_indices=(1,))
    with raises(ValueError, match="重复"):
        MergeTarget(slice_index=0, cluster_indices=(1, 1))
    with raises(ValueError, match="大于等于 1"):
        MergeTarget(slice_index=0, cluster_indices=(0, 1))
    with raises(ValueError, match="未找到来源簇"):
        MergePipeline().run(
            target=MergeTarget(slice_index=0, cluster_indices=(1, 99)),
            slice_cluster_result=slice_clusters,
            slice_recognition_result=slice_recognitions,
            merge_index=1,
        )


def test_merge_workflow_writes_session_and_renders_source_clusters_in_colors() -> None:
    """工作流应写回合并结果并生成包含多种来源颜色的五维图像。"""
    session = _session_with_source_results()
    workflow = MergeWorkflow()

    execution = workflow.start_merge(
        session,
        MergeTarget(slice_index=0, cluster_indices=(1, 2)),
    )

    assert execution.success
    assert execution.merge_result is not None
    assert execution.merge_result.strategy_id == "explicit"
    assert execution.rendered_bundle is not None
    assert session.merge_result is not None
    assert session.merge_result.slice_results[0].merged_clusters == [
        execution.merge_result
    ]
    assert session.stage is ProcessingStage.MERGED
    assert (
        session.get_slice_processing_state(0).merge_status
        is SliceProcessStatus.SUCCEEDED
    )
    assert set(execution.rendered_bundle.images) == {
        "CF",
        "PW",
        "PA",
        "DTOA",
        "DOA",
    }
    cf_image = execution.rendered_bundle.images["CF"]
    non_black_colors = np.unique(cf_image.reshape(-1, 3), axis=0)
    non_black_colors = non_black_colors[np.any(non_black_colors != 0, axis=1)]
    assert len(non_black_colors) >= 2


def test_merge_workflow_records_failure_without_overwriting_results() -> None:
    """来源解析失败时工作流应记录失败状态且不写入合并结果。"""
    session = _session_with_source_results()
    workflow = MergeWorkflow()

    execution = workflow.start_merge(
        session,
        MergeTarget(slice_index=0, cluster_indices=(1, 99)),
    )

    state = session.get_slice_processing_state(0)
    assert not execution.success
    assert "未找到来源簇 99" in execution.error_message
    assert session.merge_result is None
    assert state.merge_status is SliceProcessStatus.FAILED
    assert state.last_merge_error == execution.error_message


def test_reidentify_invalidation_clears_only_target_slice_merge_results() -> None:
    """重新识别前应同时清除目标切片的合并计划和独立结果。"""
    session = _session_with_four_source_results()
    workflow = MergeWorkflow(strategy=_FixedBatchStrategy())
    plan = workflow.prepare_merge_plan(session, 0)
    execution = workflow.execute_merge_plan(session, 0)

    assert plan is not None
    assert execution.success
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
        assert not view.right_panel.navigation_control_card.merge_menu_button.enabled
        controller.set_strategy(_FixedBatchStrategy())
        assert view.right_panel.navigation_control_card.merge_menu_button.enabled

        controller._execute_merge_plan()

        assert session.merge_result is not None
        results = session.merge_result.slice_results[0].merged_clusters
        assert [result.source_cluster_indices for result in results] == [
            (1, 2),
            (3, 4),
        ]
        assert all(result.strategy_id == "fixed_batch_v1" for result in results)
        button_bar = view.merge_operation_panel.operation_card.button_bar
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
        assert not view.right_panel.navigation_control_card.merge_menu_button.enabled
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

    execution = workflow.execute_merge_plan(session, 0)

    assert execution.success
    assert execution.result_count == 2
    assert session.recognition_result is recognition_result
    assert tuple(recognition_slice.valid_clusters) == recognition_items
    assert workflow.get_merge_groups(session, 0) == ((1, 2), (3, 4))

    duplicate = workflow.execute_merge_plan(session, 0)
    assert not duplicate.success
    assert "已经执行" in duplicate.error_message
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

    execution = workflow.execute_merge_plan(session, 0)

    assert not execution.success
    assert "模拟第二组合并失败" in execution.error_message
    assert session.merge_result is None
    assert (
        session.get_slice_processing_state(0).merge_status
        is SliceProcessStatus.FAILED
    )


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

    execution = workflow.execute_merge_plan(session, 0)

    assert not execution.success
    assert "来源或计划已变化" in execution.error_message
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
    execution = workflow.execute_merge_plan(session, 0)
    presentation = workflow.render_result(session, 0, 0)
    column = MergeImageColumn()

    try:
        assert execution.success
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
    execution = workflow.execute_merge_plan(session, 0)
    assert execution.success
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
    execution = workflow.execute_merge_plan(session, 0)
    assert execution.success

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
    interface = SliceInterface(session=_session_with_source_results())

    try:
        interface.resize(1500, 900)
        interface.show()
        QApplication.processEvents()
        controller = interface._merge_controller
        controller.set_strategy(_FixedSingleStrategy())
        controller._execute_merge_plan()
        QApplication.processEvents()

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


def test_single_result_uses_global_visibility_and_resets_merge_state(
    monkeypatch: MonkeyPatch,
) -> None:
    """单结果合并后应支持全局显隐，并可重置回未判别状态。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    interface = SliceInterface(session=_session_with_source_results())

    try:
        interface.resize(1500, 900)
        interface.show()
        QApplication.processEvents()
        interface.image_workspace.setScrollAnimation(Qt.Orientation.Horizontal, 0)
        interface._merge_controller.set_strategy(_FixedSingleStrategy())
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
        QApplication.processEvents()

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
        QApplication.processEvents()

        assert interface._session.recognition_result is recognition_result
        assert interface._session.merge_plan is None
        assert interface._session.merge_result is None
        assert (
            interface._session.get_slice_processing_state(
                0
            ).merge_judgment_suppressed
            is True
        )
        assert not menu_button.isEnabled()
        assert not menu_button.isChecked()
        assert not interface.image_workspace.is_merge_active()
        assert interface.image_workspace.current_pair_index() == 0
        assert not button_bar.merge_button.isEnabled()
        assert not button_bar.reset_button.isEnabled()
        assert operation_card.result_count_label.text() == "共获得？个合并结果"
        assert not operation_card.global_visibility_checkbox.isEnabled()
        assert not category_card.category_checkboxes
        assert category_card.skeleton.isVisible()
    finally:
        sip.delete(interface)


def test_identify_finished_prepares_plan_for_non_current_slice(
    monkeypatch: MonkeyPatch,
) -> None:
    """识别完成事件应为非当前切片立即保存合并计划。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda _model_type: [],
    )
    session = _session_with_source_results()
    interface = SliceInterface(session=session)

    try:
        interface._merge_controller._workflow.set_strategy(_FixedSingleStrategy())
        session.merge_plan = None
        interface._slice_controller._current_slice_index = 1

        interface._merge_controller._on_stage_finished(
            session.session_id,
            "identifying",
            0,
        )

        assert session.merge_plan is not None
        assert session.merge_plan.slice_plans[0].strategy_id == "fixed_single_v1"
        assert [
            group.cluster_indices
            for group in session.merge_plan.slice_plans[0].groups
        ] == [(1, 2)]
    finally:
        sip.delete(interface)
