"""识别工作线程聚类参数传递测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.models.algorithm_params import ClusteringParams, RecognitionParams
from core.models.processing_session import ProcessingSession
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

    def fake_recognize_clusters(clusters, inference_service, recognize_params, start_index):
        """跳过识别逻辑，保持测试聚焦于聚类参数传递。"""
        return [], [], [], start_index

    monkeypatch.setattr(
        "runtime.threading.identify_worker.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "runtime.threading.identify_worker.recognize_clusters",
        fake_recognize_clusters,
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
