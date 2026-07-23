"""合并流程链路单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PyQt6 import sip
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch, raises

from core.merge import MergePipeline, MergeTarget
from core.models.algorithm_params import ExtractParams
from core.models.cluster_result import (
    ClusterItem,
    ClusterState,
    ClusteringResult,
    SliceClusterResult,
)
from core.models.extraction_result import ExtractedClusterParams
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
from runtime.workflows.merge_workflow import MergeWorkflow
from ui.components.merge_image_column import MergeImageColumn
from ui.controllers.merge_controller import MergeController


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
    """重新识别前应只清除目标切片依赖旧识别结果的合并产物。"""
    session = _session_with_source_results()
    execution = MergeWorkflow().start_merge(
        session,
        MergeTarget(slice_index=0, cluster_indices=(1, 2)),
    )
    assert execution.success

    session.clear_slice_merge_results(0)

    assert session.merge_result is None
    state = session.get_slice_processing_state(0)
    assert state.merge_status is SliceProcessStatus.NOT_STARTED
    assert state.last_merge_error is None


def test_merge_controller_is_explicit_target_boundary_and_updates_image_column() -> None:
    """控制器应接收明确簇编号并把成功结果交给合并图像列。"""
    session = _session_with_source_results()
    updates: list[tuple[object, object]] = []

    class FakeSignal:
        """提供控制器连接所需的最小信号接口。"""

        def __init__(self) -> None:
            """初始化槽函数列表。"""
            self.slots: list[object] = []

        def connect(self, slot: object) -> None:
            """记录一个待调用槽函数。"""
            self.slots.append(slot)

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
            self.merge_operation_panel = SimpleNamespace(
                operation_card=SimpleNamespace(button_bar=button_bar)
            )
            self.right_panel = SimpleNamespace(
                navigation_control_card=SimpleNamespace(
                    merge_menu_button=FakeButton()
                )
            )
            self.merge_image_column = SimpleNamespace(
                update_from_merge=lambda bundle, result: updates.append(
                    (bundle, result)
                )
            )

    view = FakeView()
    controller = MergeController(view)

    class ControllerFixedStrategy:
        """为控制器提供固定候选的测试准则。"""

        strategy_id = "controller_fixed_v1"

        def build_targets(
            self,
            slice_cluster_result: SliceClusterResult,
            _slice_recognition_result: SliceRecognitionResult,
        ) -> tuple[MergeTarget, ...]:
            """返回固定的第1、2类合并目标。"""
            return (
                MergeTarget(
                    slice_index=slice_cluster_result.slice_idx,
                    cluster_indices=(1, 2),
                ),
            )

    try:
        assert not view.right_panel.navigation_control_card.merge_menu_button.enabled
        controller.set_strategy(ControllerFixedStrategy())
        assert view.right_panel.navigation_control_card.merge_menu_button.enabled

        controller._merge_current_candidate()

        assert session.merge_result is not None
        merged_result = session.merge_result.slice_results[0].merged_clusters[0]
        assert merged_result.strategy_id == "controller_fixed_v1"
        assert len(updates) == 1
        assert updates[0][1] is merged_result
        assert not view.right_panel.navigation_control_card.merge_menu_button.enabled
    finally:
        sip.delete(view)


def test_merge_workflow_supports_strategy_switch_and_filters_completed_target() -> None:
    """runtime应允许替换准则，并过滤已经执行的同来源候选。"""
    session = _session_with_source_results()

    class FixedStrategy:
        """始终返回第1、2类作为候选的测试准则。"""

        strategy_id = "fixed_test_v1"

        def build_targets(
            self,
            slice_cluster_result: SliceClusterResult,
            _slice_recognition_result: SliceRecognitionResult,
        ) -> tuple[MergeTarget, ...]:
            """返回固定来源目标。"""
            return (
                MergeTarget(
                    slice_index=slice_cluster_result.slice_idx,
                    cluster_indices=(1, 2),
                ),
            )

    workflow = MergeWorkflow(strategy=FixedStrategy())

    assert workflow.strategy_id == "fixed_test_v1"
    assert workflow.find_merge_candidates(session, 0) == ((1, 2),)

    # 识别失败时旧结果仍在session，但runtime不得重新暴露陈旧候选。
    session.mark_slice_recognition_failed(0, "测试识别失败")
    assert workflow.find_merge_candidates(session, 0) == ()
    session.mark_slice_recognition_succeeded(0)

    execution = workflow.start_strategy_merge_by_indices(session, 0, (1, 2))

    assert execution.success
    assert execution.merge_result is not None
    assert execution.merge_result.strategy_id == "fixed_test_v1"
    assert workflow.find_merge_candidates(session, 0) == ()

    duplicate = workflow.start_strategy_merge_by_indices(session, 0, (2, 1))
    assert not duplicate.success
    assert "不能重复执行" in duplicate.error_message
    assert session.merge_result is not None
    assert len(session.merge_result.slice_results[0].merged_clusters) == 1


def test_merge_image_column_displays_rgb_bundle_from_workflow() -> None:
    """合并图像列应显示工作流生成的五维 RGB 图像。"""
    _app()
    session = _session_with_source_results()
    execution = MergeWorkflow().start_merge(
        session,
        MergeTarget(slice_index=0, cluster_indices=(1, 2)),
    )
    column = MergeImageColumn()

    try:
        assert execution.merge_result is not None
        assert execution.rendered_bundle is not None
        column.update_from_merge(
            execution.rendered_bundle,
            execution.merge_result,
        )

        assert column.title_label.text() == "合并结果 第1组（原第1+2类）"
        assert all(
            card._source_image is not None for card in column.dimension_cards
        )
        assert all(
            card.image_label._source_image is not None
            for card in column.dimension_cards
        )
    finally:
        sip.delete(column)
