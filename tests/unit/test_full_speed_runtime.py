"""全速处理注册器和连续流水线测试。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.app_config import appConfig
from core.models.cluster_result import (
    ClusterItem,
    ClusterState,
    ClusteringResult,
    SliceClusterResult,
)
from core.models.extraction_result import ExtractedClusterParams
from core.models.merge_result import (
    MergePlan,
    MergeResult,
    SliceMergePlan,
    SliceMergeResult,
)
from core.models.processing_session import (
    ProcessingMode,
    ProcessingSession,
    SliceProcessStatus,
)
from core.models.recognition_result import (
    ClusterRecognition,
    RecognitionResult,
    SliceRecognitionResult,
)
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.slice_result import (
    PreprocessResult,
    SingleSlice,
    SliceResult,
)
from runtime.full_speed_session_registry import (
    FullSpeedSessionRegistry,
    FullSpeedStatus,
)
from runtime.threading.full_speed_worker import (
    FullSpeedExecutionRequest,
    FullSpeedWorker,
    FullSpeedWorkerResult,
)
from runtime.workflows.full_speed_workflow import FullSpeedWorkflow
import runtime.workflows.full_speed_workflow as workflow_module


def _build_full_speed_session(output_dir: Path) -> ProcessingSession:
    """构造具备执行前置条件的全速 Session。"""
    session = ProcessingSession(
        data_package_id="package1",
        processing_mode=ProcessingMode.FULL_SPEED,
        source_path="E:/data/demo.xlsx",
        source_type="excel",
        display_name="测试全速任务",
        preprocess_result=PreprocessResult(
            np.array(
                [
                    [5000.0, 1.0, 90.0, 10.0, 11.0, 0.0],
                    [5000.0, 1.0, 91.0, 10.0, 11.0, 3_000_000.0],
                ]
            )
        ),
    )
    session.config_snapshot.business.export_dir_path = str(output_dir)
    session.model_selection = SessionModelSelection("pa.onnx", "dtoa.onnx")
    return session


def test_registry_freezes_configuration_on_first_start(tmp_path) -> None:
    """首次开始后保存路径不可修改，失败重试仍沿用冻结配置。"""
    registry = FullSpeedSessionRegistry(tmp_path / "sessions")
    session = registry.register(_build_full_speed_session(tmp_path / "out"))

    registry.begin(session.session_id)
    assert session.full_speed_locked
    assert registry.state(session.session_id).status is FullSpeedStatus.RUNNING
    with pytest.raises(RuntimeError, match="已冻结"):
        registry.set_output_dir(session.session_id, str(tmp_path / "other"))

    registry.mark_failed(session.session_id, "test")
    registry.begin(session.session_id)
    assert registry.state(session.session_id).output_dir == str(tmp_path / "out")


def test_registry_persists_session_parameter_snapshot_before_freeze(
    tmp_path,
) -> None:
    """注册器应保存独立算法快照、保留业务配置并拒绝冻结后的修改。"""
    registry = FullSpeedSessionRegistry(tmp_path / "sessions")
    session = registry.register(_build_full_speed_session(tmp_path / "out"))
    session.config_snapshot.plot.scale_mode = "KEEP_RATIO"
    draft = SessionConfigSnapshot.default()
    draft.clustering.eps_cf = 6.75
    draft.recognition.greedy_strategy = False
    draft.business.export_dir_path = str(tmp_path / "stale")
    draft.plot.scale_mode = "STRETCH"

    registry.set_config_snapshot(session.session_id, draft)

    assert session.config_snapshot.clustering.eps_cf == 6.75
    assert not session.config_snapshot.recognition.greedy_strategy
    assert (
        session.config_snapshot.business.export_dir_path
        == str(tmp_path / "out")
    )
    assert session.config_snapshot.plot.scale_mode == "KEEP_RATIO"
    persisted = registry.session_registry.store.load_session(
        session.session_id
    )
    assert persisted.config_snapshot.clustering.eps_cf == 6.75

    registry.begin(session.session_id)
    with pytest.raises(RuntimeError, match="已冻结"):
        registry.set_config_snapshot(session.session_id, draft)


def test_full_speed_worker_reuses_slice_pipeline_for_every_slice(
    tmp_path,
    monkeypatch,
) -> None:
    """全速线程应按现有切片模型逐片识别、合并并保存。"""
    from runtime.threading import full_speed_worker as worker_module
    inference_kwargs: list[dict[str, object]] = []
    pipeline_kwargs: list[dict[str, object]] = []

    class _InferenceStub:
        """替代独立 ONNX 推理服务。"""

        def __init__(self, **kwargs) -> None:
            """记录测试构造参数。"""
            inference_kwargs.append(kwargs)

    class _IdentifyPipelineStub:
        """为每个切片返回一组确定性识别结果。"""

        def __init__(self, **kwargs) -> None:
            """记录测试构造参数。"""
            pipeline_kwargs.append(kwargs)

        def run(self, single_slice):
            """生成与切片索引一致的聚类和识别结果。"""
            cluster = ClusterItem(
                cluster_idx=1,
                dim_name="CF",
                points=single_slice.data,
                points_indices=np.arange(len(single_slice.data)),
                slice_idx=single_slice.index,
                time_ranges=single_slice.time_range,
                state=ClusterState.VALID,
            )
            recognition = ClusterRecognition(
                slice_index=single_slice.index,
                dim_name="CF",
                cluster_index=1,
                valid_cluster_index=0,
                pa_label=1,
                pa_confidence=0.9,
                dtoa_label=1,
                dtoa_confidence=0.8,
                is_valid=True,
                joint_prob=0.72,
                extracted_params=ExtractedClusterParams(cf_values=[5000.0]),
            )
            return (
                SliceClusterResult(
                    slice_idx=single_slice.index,
                    clusters=[cluster],
                ),
                SliceRecognitionResult(
                    slice_index=single_slice.index,
                    valid_clusters=[recognition],
                ),
            )

    class _MergeStrategyStub:
        """返回空合并计划。"""

        def build_plan(self, clusters, _recognitions):
            """按聚类结果切片索引构造空计划。"""
            return SliceMergePlan(
                clusters.slice_idx,
                "test_strategy",
                (),
            )

    class _ExporterStub:
        """记录保存调用并返回确定路径。"""

        def export(self, data, output_dir):
            """返回测试结果文件路径。"""
            assert data.slice_result.slice_count == 2
            return Path(output_dir) / "result.xlsx"

    monkeypatch.setattr(worker_module, "OnnxInferenceService", _InferenceStub)
    monkeypatch.setattr(
        worker_module,
        "SliceIdentifyPipeline",
        _IdentifyPipelineStub,
    )
    monkeypatch.setattr(
        worker_module,
        "HybridParameterMergeStrategy",
        _MergeStrategyStub,
    )
    monkeypatch.setattr(worker_module, "ExcelResultExporter", _ExporterStub)

    session = _build_full_speed_session(tmp_path)
    session.config_snapshot.clustering.eps_cf = 7.75
    session.config_snapshot.recognition.greedy_strategy = False
    session.config_snapshot.extract.eps_pri = 0.65
    request = FullSpeedExecutionRequest(
        session_id=session.session_id,
        data_package_id=session.data_package_id,
        display_name=session.display_name,
        source_path=session.source_path,
        source_type=session.source_type,
        created_at=session.created_at,
        preprocess_result=session.preprocess_result,
        config_snapshot=SessionConfigSnapshot.from_dict(
            session.config_snapshot.to_dict()
        ),
        model_selection=SessionModelSelection("pa.onnx", "dtoa.onnx"),
        output_dir=str(tmp_path),
        temp_dir=str(tmp_path),
        compute_device="GPU",
        recognition_workers=1,
    )
    result = FullSpeedWorker(request)._execute()

    assert result.success
    assert result.slice_result.slice_count == 2
    assert sorted(result.recognition_result.slice_results) == [0, 1]
    assert sorted(result.merge_plan.slice_plans) == [0, 1]
    assert result.output_file.endswith("result.xlsx")
    assert inference_kwargs == [
        {
            "pa_model_path": "pa.onnx",
            "dtoa_model_path": "dtoa.onnx",
            "temp_dir": str(tmp_path),
            "device_preference": "GPU",
            "intra_op_num_threads": 1,
        }
    ]
    assert len(pipeline_kwargs) == 2
    assert all(
        kwargs["recognition_max_workers"] == 1
        for kwargs in pipeline_kwargs
    )
    assert all(
        kwargs["cluster_params"].eps_cf == 7.75
        and kwargs["recognize_params"].greedy_strategy is False
        and kwargs["extract_params"].eps_pri == 0.65
        for kwargs in pipeline_kwargs
    )


def test_full_speed_workflow_rejects_start_at_concurrency_limit(
    tmp_path,
    monkeypatch,
) -> None:
    """达到全速任务并发上限时应拒绝启动新任务。"""
    registry = FullSpeedSessionRegistry(tmp_path / "sessions")
    session = registry.register(_build_full_speed_session(tmp_path / "out"))
    workflow = FullSpeedWorkflow(registry)
    workflow._workers["busy"] = type(
        "_BusyWorker",
        (),
        {"isRunning": lambda self: True},
    )()
    original_get = workflow_module.qconfig.get

    def fake_get(config_item):
        """仅替换全速任务并发上限。"""
        if config_item is appConfig.fullSpeedMaxConcurrentTasks:
            return 1
        return original_get(config_item)

    monkeypatch.setattr(workflow_module.qconfig, "get", fake_get)

    with pytest.raises(RuntimeError, match="并发上限"):
        workflow.start(session.session_id)


def test_full_speed_request_snapshots_global_performance_settings(
    tmp_path,
    monkeypatch,
) -> None:
    """全速请求应冻结独立算法快照、设备偏好和识别线程上限。"""
    registry = FullSpeedSessionRegistry(tmp_path / "sessions")
    session = registry.register(_build_full_speed_session(tmp_path / "out"))
    session.config_snapshot.clustering.eps_cf = 6.25
    session.config_snapshot.recognition.greedy_strategy = False
    workflow = FullSpeedWorkflow(registry)
    original_get = workflow_module.qconfig.get

    def fake_get(config_item):
        """返回当前测试指定的全速性能配置。"""
        if config_item is appConfig.fullSpeedComputeDevice:
            return "GPU"
        if config_item is appConfig.fullSpeedRecognitionWorkers:
            return 3
        return original_get(config_item)

    monkeypatch.setattr(workflow_module.qconfig, "get", fake_get)

    request = workflow._build_request(session)
    session.config_snapshot.clustering.eps_cf = 9.5
    session.config_snapshot.recognition.greedy_strategy = True

    assert request.compute_device == "GPU"
    assert request.recognition_workers == 3
    assert request.config_snapshot is not session.config_snapshot
    assert request.config_snapshot.clustering.eps_cf == 6.25
    assert request.config_snapshot.recognition.greedy_strategy is False


def test_full_speed_workflow_commits_complete_result_atomically(
    tmp_path,
) -> None:
    """工作流成功提交后应同步 Session 结果、阶段和卡片终态。"""
    registry = FullSpeedSessionRegistry(tmp_path / "sessions")
    session = registry.register(_build_full_speed_session(tmp_path / "out"))
    registry.begin(session.session_id)
    single_slice = SingleSlice(
        index=0,
        data=session.preprocess_result.data,
        time_range=(0.0, 3_000_001.0),
    )
    cluster_slice = SliceClusterResult(slice_idx=0)
    recognition_slice = SliceRecognitionResult(slice_index=0)
    plan = SliceMergePlan(0, "test_strategy", ())
    output_file = str(tmp_path / "out" / "result.xlsx")
    result = FullSpeedWorkerResult(
        success=True,
        slice_result=SliceResult([single_slice]),
        clustering_result=ClusteringResult({0: cluster_slice}),
        recognition_result=RecognitionResult({0: recognition_slice}),
        merge_plan=MergePlan({0: plan}),
        merge_result=MergeResult({0: SliceMergeResult(0)}),
        output_file=output_file,
    )

    FullSpeedWorkflow(registry)._commit_success(session.session_id, result)

    assert session.slice_result is result.slice_result
    assert session.is_slice_recognized(0)
    assert (
        session.get_slice_processing_state(0).merge_status
        is SliceProcessStatus.SUCCEEDED
    )
    assert session.exported_file_path == output_file
    assert registry.state(session.session_id).status is FullSpeedStatus.SUCCEEDED
