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
