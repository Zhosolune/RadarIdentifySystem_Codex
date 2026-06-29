"""识别工作线程聚类参数传递测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.models.algorithm_params import ClusteringParams, RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState
from core.models.processing_session import ProcessingSession
from core.models.recognition_result import ClusterRecognition
from runtime.threading.identify_worker import IdentifyWorker
from runtime.workflows.identify_workflow import IdentifyWorkflow


def test_identify_worker_requires_injected_session_params() -> None:
    """识别线程应通过构造函数接收 session 参数。"""
    assert "cluster_params" in IdentifyWorker.__init__.__code__.co_varnames
    assert "recognize_params" in IdentifyWorker.__init__.__code__.co_varnames
    assert isinstance(ClusteringParams(eps_cf=7.0), ClusteringParams)
    assert isinstance(RecognitionParams(tolerance=0.25), RecognitionParams)


def test_identify_worker_passes_split_min_pts_to_cf_and_pw(
    monkeypatch: MonkeyPatch,
) -> None:
    """识别线程应分别向 CF/PW 聚类传递对应的最小点数。"""
    calls: list[tuple[str, int]] = []

    def fake_process_dimension_clustering(**kwargs):
        """记录维度名称和 DBSCAN 最小点数，并触发 PW 分支。"""
        calls.append((kwargs["dim_name"], kwargs["min_pts"]))
        if kwargs["dim_name"] == "CF":
            return [], np.array([0, 1])
        return [], np.array([])

    def fake_recognize_clusters_parallel(
        clusters,
        inference_service,
        recognize_params,
        start_index,
        max_workers=None,
    ):
        """跳过识别逻辑，保持测试聚焦于聚类参数传递。"""
        del clusters, inference_service, recognize_params, max_workers
        return [], [], [], start_index

    monkeypatch.setattr(
        "runtime.threading.identify_worker.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "runtime.threading.identify_worker.recognize_clusters_parallel",
        fake_recognize_clusters_parallel,
    )
    worker = IdentifyWorker(
        session=ProcessingSession(),
        slice_index=0,
        inference_service=object(),
        cluster_params=ClusteringParams(),
        recognize_params=RecognitionParams(),
    )
    slice_data = SimpleNamespace(
        index=0,
        data=np.array(
            [
                [1000.0, 1.0, 90.0, 10.0, 0.0],
                [2000.0, 5.0, 91.0, 11.0, 1000.0],
            ]
        ),
        time_range=(0.0, 1.0),
    )

    worker._cluster_and_recognize_slice(
        slice_data=slice_data,
        inference_service=object(),
        cluster_params=ClusteringParams(min_pts_cf=3, min_pts_pw=7),
        recognize_params=RecognitionParams(),
    )

    assert calls == [("CF", 3), ("PW", 7)]


def test_identify_worker_saves_all_clusters_by_cluster_index(
    monkeypatch: MonkeyPatch,
) -> None:
    """展示全部聚类结果依赖保存顺序，识别后应按簇索引保存全部簇。"""

    def make_cluster(
        cluster_idx: int,
        dim_name: str,
        points_indices: np.ndarray,
    ) -> ClusterItem:
        """构造带指定索引和维度的测试聚类簇。"""
        return ClusterItem(
            cluster_idx=cluster_idx,
            dim_name=dim_name,
            points=np.zeros((len(points_indices), 5), dtype=float),
            points_indices=points_indices,
            slice_idx=0,
            time_ranges=(0.0, 1.0),
        )

    cf_valid = make_cluster(1, "CF", np.array([0]))
    cf_invalid = make_cluster(2, "CF", np.array([1]))
    pw_valid = make_cluster(3, "PW", np.array([0]))

    def make_recognition(
        cluster: ClusterItem,
        valid_cluster_index: int | None,
        is_valid: bool,
    ) -> ClusterRecognition:
        """构造与测试聚类簇对应的识别结果。"""
        return ClusterRecognition(
            slice_index=cluster.slice_idx,
            dim_name=cluster.dim_name,
            cluster_index=cluster.cluster_idx,
            valid_cluster_index=valid_cluster_index,
            pa_label=1 if is_valid else 5,
            pa_confidence=0.9,
            dtoa_label=1 if is_valid else 5,
            dtoa_confidence=0.8,
            is_valid=is_valid,
        )

    def fake_process_dimension_clustering(
        **kwargs: Any,
    ) -> tuple[list[ClusterItem], np.ndarray]:
        """按维度返回固定聚类结果，用于稳定复现保存顺序。"""
        if kwargs["dim_name"] == "CF":
            return [cf_valid, cf_invalid], np.array([], dtype=int)
        return [pw_valid], np.array([], dtype=int)

    def fake_recognize_clusters_parallel(
        clusters: list[ClusterItem],
        inference_service: object,
        recognize_params: RecognitionParams,
        start_index: int,
        max_workers: int | None = None,
    ) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
        """返回固定识别结果，模拟有效簇与无效簇交错的场景。"""
        del inference_service, recognize_params, max_workers
        if clusters and clusters[0].dim_name == "CF":
            cf_valid.state = ClusterState.VALID
            cf_invalid.state = ClusterState.INVALID
            cf_valid.valid_cluster_idx = start_index
            return (
                [cf_valid],
                [cf_invalid],
                [
                    make_recognition(cf_valid, start_index, True),
                    make_recognition(cf_invalid, None, False),
                ],
                start_index + 1,
            )

        pw_valid.state = ClusterState.VALID
        pw_valid.valid_cluster_idx = start_index
        return (
            [pw_valid],
            [],
            [make_recognition(pw_valid, start_index, True)],
            start_index + 1,
        )

    monkeypatch.setattr(
        "runtime.threading.identify_worker.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "runtime.threading.identify_worker.recognize_clusters_parallel",
        fake_recognize_clusters_parallel,
    )
    worker = IdentifyWorker(
        session=ProcessingSession(),
        slice_index=0,
        inference_service=object(),
        cluster_params=ClusteringParams(),
        recognize_params=RecognitionParams(),
    )
    slice_data = SimpleNamespace(
        index=0,
        data=np.zeros((3, 5), dtype=float),
        time_range=(0.0, 1.0),
    )

    cluster_result, recognition_result = worker._cluster_and_recognize_slice(
        slice_data=slice_data,
        inference_service=object(),
        cluster_params=ClusteringParams(),
        recognize_params=RecognitionParams(),
    )

    assert [cluster.cluster_idx for cluster in cluster_result.clusters] == [1, 2, 3]
    assert [cluster.state for cluster in cluster_result.clusters] == [
        ClusterState.VALID,
        ClusterState.INVALID,
        ClusterState.VALID,
    ]
    assert [
        recognition.cluster_index for recognition in recognition_result.valid_clusters
    ] == [1, 3]
    assert [
        recognition.cluster_index for recognition in recognition_result.invalid_clusters
    ] == [2]


def test_identify_workflow_injects_session_params_and_models(
    monkeypatch: MonkeyPatch,
) -> None:
    """识别 workflow 应从当前 session 注入模型路径与算法参数。"""
    captured: dict[str, object] = {}

    class FakeSignal:
        """测试用信号桩。"""

        def connect(self, _slot) -> None:
            """忽略信号连接。"""
            return None

    class FakeWorker:
        """测试用识别线程桩。"""

        progress_signal = FakeSignal()
        finished_signal = FakeSignal()

        def __init__(self, **kwargs) -> None:
            """记录 workflow 传入的构造参数。"""
            captured.update(kwargs)

        def isRunning(self) -> bool:
            """返回线程未运行。"""
            return False

        def start(self) -> None:
            """标记 workflow 已启动线程。"""
            captured["started"] = True

    monkeypatch.setattr(
        "runtime.workflows.identify_workflow.IdentifyWorker",
        FakeWorker,
    )
    monkeypatch.setattr(
        "runtime.workflows.identify_workflow.get_cached_inference_service",
        lambda **kwargs: {"service_args": kwargs},
    )

    session = ProcessingSession(session_id="session_params")
    session.slice_result = object()
    session.model_selection.pa_model_path = "E:/models/pa.onnx"
    session.model_selection.dtoa_model_path = "E:/models/dtoa.onnx"
    session.config_snapshot.clustering.eps_cf = 7.0
    session.config_snapshot.clustering.min_pts_cf = 4
    session.config_snapshot.recognition.tolerance = 0.25
    workflow = IdentifyWorkflow()

    workflow.start_identify(session, slice_index=2)

    cluster_params = captured["cluster_params"]
    recognize_params = captured["recognize_params"]
    assert isinstance(cluster_params, ClusteringParams)
    assert isinstance(recognize_params, RecognitionParams)
    assert cluster_params.eps_cf == 7.0
    assert cluster_params.min_pts_cf == 4
    assert recognize_params.tolerance == 0.25
    assert captured["started"] is True
    service_args = captured["inference_service"]["service_args"]
    assert service_args["pa_path"] == "E:/models/pa.onnx"
    assert service_args["dtoa_path"] == "E:/models/dtoa.onnx"
    assert service_args["temp_dir"]


def test_multiple_identify_workflow_instances_can_start_in_parallel(
    monkeypatch: MonkeyPatch,
) -> None:
    """不同 workflow 实例应可各自启动识别线程。"""
    started_sessions: list[str] = []

    class FakeSignal:
        """测试用信号桩。"""

        def connect(self, _slot) -> None:
            """忽略信号连接。"""
            return None

    class FakeWorker:
        """测试用识别线程桩。"""

        progress_signal = FakeSignal()
        finished_signal = FakeSignal()

        def __init__(self, **kwargs) -> None:
            """记录当前启动的 session。"""
            self._session_id = kwargs["session"].session_id
            self._running = False

        def isRunning(self) -> bool:
            """返回当前线程运行状态。"""
            return self._running

        def start(self) -> None:
            """标记线程已启动。"""
            self._running = True
            started_sessions.append(self._session_id)

    monkeypatch.setattr(
        "runtime.workflows.identify_workflow.IdentifyWorker",
        FakeWorker,
    )
    monkeypatch.setattr(
        "runtime.workflows.identify_workflow.get_cached_inference_service",
        lambda **kwargs: {"service_args": kwargs},
    )

    session_a = ProcessingSession(session_id="session_a")
    session_a.slice_result = object()
    session_a.model_selection.pa_model_path = "E:/models/pa_a.onnx"
    session_a.model_selection.dtoa_model_path = "E:/models/dtoa_a.onnx"
    session_b = ProcessingSession(session_id="session_b")
    session_b.slice_result = object()
    session_b.model_selection.pa_model_path = "E:/models/pa_b.onnx"
    session_b.model_selection.dtoa_model_path = "E:/models/dtoa_b.onnx"

    workflow_a = IdentifyWorkflow()
    workflow_b = IdentifyWorkflow()

    workflow_a.start_identify(session_a, slice_index=0)
    workflow_b.start_identify(session_b, slice_index=1)

    assert started_sessions == ["session_a", "session_b"]
    assert workflow_a.is_running() is True
    assert workflow_b.is_running() is True
