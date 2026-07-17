"""识别流程与工作线程契约测试。

功能描述：
    覆盖 core/identify_pipeline 中的级联流程编排、参数提取行为，
    以及 runtime/threading/identify_worker 与 runtime/workflows/identify_workflow
    的调度契约。业务逻辑用例直接调用 core 层公共 API，避免耦合线程私有实现。
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.identify_pipeline import (
    IdentifyPipelineContext,
    SliceIdentifyPipeline,
)
from core.identify_stages import IdentifyStageOps
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import (
    ClusterItem,
    ClusterState,
    ClusteringResult,
    SliceClusterResult,
)
from core.models.processing_session import ProcessingSession, ProcessingStage, SliceProcessStatus
from core.models.pulse_batch import COL_DOA
from core.models.recognition_result import (
    ClusterRecognition,
    RecognitionResult,
    SliceRecognitionResult,
)
from core.params_extract import extract_cluster_params
from runtime.threading.identify_worker import IdentifyWorker, IdentifyWorkerResult
from runtime.workflows.identify_workflow import IdentifyWorkflow


def test_identify_worker_requires_injected_session_params() -> None:
    """识别线程应通过构造函数接收 session 参数。"""
    # 校验构造签名保留三类快照参数入口。
    assert "cluster_params" in IdentifyWorker.__init__.__code__.co_varnames
    assert "recognize_params" in IdentifyWorker.__init__.__code__.co_varnames
    assert "extract_params" in IdentifyWorker.__init__.__code__.co_varnames
    assert isinstance(ClusteringParams(eps_cf=7.0), ClusteringParams)
    assert isinstance(RecognitionParams(tolerance=0.25), RecognitionParams)
    assert isinstance(ExtractParams(eps_cf=1.5), ExtractParams)


def test_slice_identify_pipeline_attaches_extracted_params_to_valid_recognition(
    monkeypatch: MonkeyPatch,
) -> None:
    """最终识别通过的类应携带 CF、PW、PRI、DOA 提取结果。"""
    points = np.array(
        [
            [1000.0, 1.0, 20.0, 10.0, 10.0, 0.0],
            [1000.0, 1.0, 20.0, 20.0, 20.0, 100.0],
            [1000.0, 1.0, 20.0, 30.0, 30.0, 200.0],
            [1100.0, 2.0, 20.0, 20.0, 20.0, 400.0],
            [1100.0, 2.0, 20.0, 30.0, 30.0, 600.0],
            [1100.0, 2.0, 20.0, 40.0, 40.0, 800.0],
        ],
        dtype=float,
    )
    source_cluster = ClusterItem(
        cluster_idx=1,
        dim_name="CF",
        points=points,
        points_indices=np.arange(len(points)),
        slice_idx=0,
        time_ranges=(0.0, 800.0),
    )

    def fake_process_dimension_clustering(
        **kwargs: Any,
    ) -> tuple[list[ClusterItem], np.ndarray]:
        """仅返回一个 CF 有效父簇，DOA 不拆分。"""
        if kwargs["dim_name"] == "CF":
            return [source_cluster], np.array([], dtype=int)
        if kwargs["dim_name"] == "DOA":
            return [], np.array([], dtype=int)
        return [], np.array([], dtype=int)

    def fake_recognize_clusters_parallel(
        clusters: list[ClusterItem],
        inference_service: object,
        recognize_params: RecognitionParams,
        start_index: int,
        max_workers: int | None = None,
    ) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
        """把输入簇全部判定为识别通过。"""
        del inference_service, recognize_params, max_workers
        recognitions = [
            ClusterRecognition(
                slice_index=cluster.slice_idx,
                dim_name=cluster.dim_name,
                cluster_index=cluster.cluster_idx,
                valid_cluster_index=start_index + index,
                pa_label=1,
                pa_confidence=0.9,
                dtoa_label=1,
                dtoa_confidence=0.8,
                is_valid=True,
            )
            for index, cluster in enumerate(clusters)
        ]
        return clusters, [], recognitions, start_index + len(clusters)

    # 打桩 core 层引用的聚类与识别函数，隔离外部依赖。
    monkeypatch.setattr(
        "core.identify_pipeline.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.recognize_clusters_parallel",
        fake_recognize_clusters_parallel,
    )

    slice_data = SimpleNamespace(index=0, data=points, time_range=(0.0, 800.0))
    pipeline = SliceIdentifyPipeline(
        inference_service=object(),
        cluster_params=ClusteringParams(),
        recognize_params=RecognitionParams(),
        extract_params=ExtractParams(
            eps_cf=0.2,
            min_pts_cf=2,
            threshold_ratio_cf=10.0,
            eps_pw=0.2,
            min_pts_pw=2,
            threshold_ratio_pw=10.0,
            eps_pri=0.2,
            min_pts_pri=2,
            threshold_ratio_pri=10.0,
            filter_threshold_pri=2.0,
            harmonic_tolerance_pri=0.0,
        ),
    )
    _, recognition_result = pipeline.run(slice_data)

    extracted_params = recognition_result.valid_clusters[0].extracted_params
    assert extracted_params is not None
    assert sorted(extracted_params.cf_values) == [1000.0, 1100.0]
    assert sorted(extracted_params.pw_values) == [1.0, 2.0]
    assert sorted(extracted_params.pri_values) == [10.0, 20.0]
    assert extracted_params.doa_values == [25.0]


def test_extract_cluster_params_filters_related_pri_values_after_grouping() -> None:
    """PRI 应先提取典型值，再过滤整数倍与和值相关项。"""
    interval_us_values = [10.0, 10.0, 10.0, 15.0, 15.0, 15.0, 25.0, 25.0, 25.0]
    # TOA 内部单位为 0.1us，因此测试数据需要把 us 间隔转换为 0.1us 计数。
    toa_values = np.concatenate(([0.0], np.cumsum(interval_us_values) / 0.1))
    points = np.column_stack(
        (
            np.full(len(toa_values), 1000.0),
            np.full(len(toa_values), 1.0),
            np.full(len(toa_values), 20.0),
            np.full(len(toa_values), 30.0),
            np.full(len(toa_values), 30.0),
            toa_values,
        )
    )
    extract_params = ExtractParams(
        eps_cf=0.2,
        min_pts_cf=1,
        threshold_ratio_cf=10.0,
        eps_pw=0.2,
        min_pts_pw=1,
        threshold_ratio_pw=10.0,
        eps_pri=0.2,
        min_pts_pri=3,
        threshold_ratio_pri=10.0,
        filter_threshold_pri=2.0,
        harmonic_tolerance_pri=0.2,
    )

    # 直接调用 core 层参数提取入口，验证 PRI 谐波过滤规则。
    extracted_params = extract_cluster_params(points, extract_params)

    assert sorted(extracted_params.pri_values) == [10.0, 15.0]


def test_extract_cluster_params_extracts_doa_with_trimmed_circular_mean() -> None:
    """DOA 应去除排序两端值后计算循环均值。"""
    doa_values = np.array([1.0, 2.0, 358.0, 359.0])
    points = np.column_stack(
        (
            np.full(len(doa_values), 1000.0),
            np.full(len(doa_values), 1.0),
            np.full(len(doa_values), 20.0),
            doa_values,
            doa_values,
            np.arange(len(doa_values), dtype=float) * 100.0,
        )
    )
    extract_params = ExtractParams(
        eps_cf=0.2,
        min_pts_cf=1,
        threshold_ratio_cf=10.0,
        eps_pw=0.2,
        min_pts_pw=1,
        threshold_ratio_pw=10.0,
        eps_pri=0.2,
        min_pts_pri=3,
        threshold_ratio_pri=10.0,
    )

    # 直接调用 core 层参数提取入口，验证循环均值裁剪规则。
    extracted_params = extract_cluster_params(points, extract_params)

    assert extracted_params.doa_values == [pytest.approx(0.0, abs=0.0001)]


def test_slice_identify_pipeline_passes_split_min_pts_to_cf_and_pw(
    monkeypatch: MonkeyPatch,
) -> None:
    """识别流程应分别向 CF/PW 聚类传递对应的最小点数。"""
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

    # 打桩 core 层聚类与识别函数，聚焦聚类参数传递路径。
    monkeypatch.setattr(
        "core.identify_pipeline.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.recognize_clusters_parallel",
        fake_recognize_clusters_parallel,
    )
    slice_data = SimpleNamespace(
        index=0,
        data=np.array(
            [
                [1000.0, 1.0, 10.0, 90.0, 90.0, 0.0],
                [2000.0, 5.0, 11.0, 91.0, 91.0, 1000.0],
            ]
        ),
        time_range=(0.0, 1.0),
    )

    pipeline = SliceIdentifyPipeline(
        inference_service=object(),
        cluster_params=ClusteringParams(min_pts_cf=3, min_pts_pw=7),
        recognize_params=RecognitionParams(),
    )
    pipeline.run(slice_data)

    assert calls == [("CF", 3), ("PW", 7)]


def test_slice_identify_pipeline_saves_all_clusters_by_cluster_index(
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
            points=np.zeros((len(points_indices), 6), dtype=float),
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
        if kwargs["dim_name"] == "DOA":
            return [], np.array([], dtype=int)
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

        if clusters and clusters[0].dim_name == "DOA":
            recs = []
            for offset, cluster in enumerate(clusters):
                cluster.state = ClusterState.VALID
                cluster.valid_cluster_idx = start_index + offset
                recs.append(make_recognition(cluster, start_index + offset, True))
            return clusters, [], recs, start_index + len(clusters)

        pw_valid.state = ClusterState.VALID
        pw_valid.valid_cluster_idx = start_index
        return (
            [pw_valid],
            [],
            [make_recognition(pw_valid, start_index, True)],
            start_index + 1,
        )

    # 打桩 core 层聚类与识别函数，验证整流程编排结果落位顺序。
    monkeypatch.setattr(
        "core.identify_pipeline.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.recognize_clusters_parallel",
        fake_recognize_clusters_parallel,
    )
    slice_data = SimpleNamespace(
        index=0,
        data=np.zeros((3, 6), dtype=float),
        time_range=(0.0, 1.0),
    )

    pipeline = SliceIdentifyPipeline(
        inference_service=object(),
        cluster_params=ClusteringParams(),
        recognize_params=RecognitionParams(),
    )
    cluster_result, recognition_result = pipeline.run(slice_data)

    assert [cluster.cluster_idx for cluster in cluster_result.clusters] == [1, 2]
    assert [cluster.dim_name for cluster in cluster_result.clusters] == [
        "CF",
        "PW",
    ]
    assert [cluster.state for cluster in cluster_result.clusters] == [
        ClusterState.VALID,
        ClusterState.VALID,
    ]
    assert [
        recognition.cluster_index for recognition in recognition_result.valid_clusters
    ] == [1, 2]
    assert [
        recognition.cluster_index for recognition in recognition_result.invalid_clusters
    ] == []


def test_slice_identify_pipeline_clusters_valid_results_by_doa(
    monkeypatch: MonkeyPatch,
) -> None:
    """CF-DOA 未通过子类应回收到 PW，PW 通过类再执行 DOA 检查。"""
    doa_calls: list[tuple[int, float, int]] = []
    pw_input_doa_values: list[float] = []
    points = np.array(
        [
            [1000.0, 1.0, 20.0, 10.0, 10.0, 0.0],
            [1000.0, 1.0, 20.0, 11.0, 11.0, 1.0],
            [1000.0, 1.0, 20.0, 35.0, 35.0, 2.0],
            [2000.0, 2.0, 20.0, 40.0, 40.0, 3.0],
            [3000.0, 3.0, 20.0, 50.0, 50.0, 4.0],
        ],
        dtype=float,
    )

    def make_cluster(
        cluster_idx: int,
        dim_name: str,
        source_points: np.ndarray,
        points_indices: np.ndarray,
    ) -> ClusterItem:
        """构造测试聚类簇。"""
        return ClusterItem(
            cluster_idx=cluster_idx,
            dim_name=dim_name,
            points=source_points[points_indices],
            points_indices=points_indices,
            slice_idx=0,
            time_ranges=(0.0, 1.0),
        )

    def make_recognition(
        cluster: ClusterItem,
        valid_cluster_index: int | None,
        is_valid: bool,
    ) -> ClusterRecognition:
        """构造测试识别记录。"""
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
        """按流程阶段返回固定聚类结果。"""
        if kwargs["dim_name"] == "CF":
            source_points = kwargs["points"]
            return (
                [
                    make_cluster(1, "CF", source_points, np.array([0, 1, 2])),
                    make_cluster(2, "CF", source_points, np.array([3])),
                ],
                np.array([4], dtype=int),
            )

        if kwargs["dim_name"] == "DOA":
            doa_calls.append((kwargs["dim_idx"], kwargs["epsilon"], kwargs["min_pts"]))
            source_points = kwargs["points"]
            if source_points[:, COL_DOA].tolist() == [10.0, 11.0, 35.0]:
                return (
                    [
                        make_cluster(1, "DOA", source_points, np.array([0, 1])),
                        make_cluster(2, "DOA", source_points, np.array([2])),
                    ],
                    np.array([], dtype=int),
                )
            return [make_cluster(1, "DOA", source_points, np.arange(len(source_points)))], np.array([], dtype=int)

        pw_input_doa_values.extend(kwargs["points"][:, COL_DOA].tolist())
        return (
            [
                make_cluster(3, "PW", kwargs["points"], np.array([0, 1])),
                make_cluster(4, "PW", kwargs["points"], np.array([2])),
            ],
            np.array([], dtype=int),
        )

    def fake_recognize_clusters_parallel(
        clusters: list[ClusterItem],
        inference_service: object,
        recognize_params: RecognitionParams,
        start_index: int,
        max_workers: int | None = None,
    ) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
        """按维度模拟识别结果。"""
        del inference_service, recognize_params, max_workers
        if clusters and clusters[0].dim_name == "CF":
            clusters[0].state = ClusterState.VALID
            clusters[1].state = ClusterState.INVALID
            return (
                [clusters[0]],
                [clusters[1]],
                [
                    make_recognition(clusters[0], start_index, True),
                    make_recognition(clusters[1], None, False),
                ],
                start_index + 1,
            )
        if clusters and clusters[0].dim_name == "DOA":
            clusters[0].state = ClusterState.VALID
            clusters[0].valid_cluster_idx = start_index
            recs = [make_recognition(clusters[0], start_index, True)]
            if len(clusters) > 1:
                clusters[1].state = ClusterState.INVALID
                recs.append(make_recognition(clusters[1], None, False))
                return [clusters[0]], [clusters[1]], recs, start_index + 1
            return [clusters[0]], [], recs, start_index + 1

        clusters[0].state = ClusterState.VALID
        clusters[1].state = ClusterState.INVALID
        return (
            [clusters[0]],
            [clusters[1]],
            [
                make_recognition(clusters[0], start_index, True),
                make_recognition(clusters[1], None, False),
            ],
            start_index + 1,
        )

    # 打桩 core 层依赖，覆盖 CF-DOA 回收到 PW 的完整路径。
    monkeypatch.setattr(
        "core.identify_pipeline.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    monkeypatch.setattr(
        "core.identify_stages.recognize_clusters_parallel",
        fake_recognize_clusters_parallel,
    )

    slice_data = SimpleNamespace(index=0, data=points, time_range=(0.0, 1.0))
    pipeline = SliceIdentifyPipeline(
        inference_service=object(),
        cluster_params=ClusteringParams(eps_doa=16.8, min_pts_doa=2),
        recognize_params=RecognitionParams(),
    )
    cluster_result, recognition_result = pipeline.run(slice_data)

    assert doa_calls == [(2, 16.8, 2), (2, 16.8, 2)]
    assert sorted(pw_input_doa_values) == [35.0, 40.0, 50.0]
    assert [cluster.cluster_idx for cluster in cluster_result.clusters] == [1, 2, 3]
    assert [cluster.dim_name for cluster in cluster_result.clusters] == [
        "DOA",
        "PW",
        "PW",
    ]
    assert [rec.cluster_index for rec in recognition_result.valid_clusters] == [1, 2]
    assert [rec.cluster_index for rec in recognition_result.invalid_clusters] == [3]


def test_cluster_doa_children_keeps_largest_clusters_until_clip_threshold(
    monkeypatch: MonkeyPatch,
) -> None:
    """DOA 子簇应按点数降序保留，累计超过阈值后丢弃剩余小簇。"""

    def make_cluster(
        cluster_idx: int,
        source_points: np.ndarray,
        points_indices: np.ndarray,
    ) -> ClusterItem:
        """构造指定点索引的 DOA 测试簇。"""
        return ClusterItem(
            cluster_idx=cluster_idx,
            dim_name="DOA",
            points=source_points[points_indices],
            points_indices=points_indices,
            slice_idx=0,
            time_ranges=(0.0, 1.0),
        )

    def fake_process_dimension_clustering(
        **kwargs: Any,
    ) -> tuple[list[ClusterItem], np.ndarray]:
        """返回未按规模排序的 DOA 子簇，验证后处理会重新排序裁剪。"""
        source_points = kwargs["points"]
        return (
            [
                make_cluster(1, source_points, np.array([0, 1])),
                make_cluster(2, source_points, np.array([2, 3, 4, 5, 6])),
                make_cluster(3, source_points, np.array([7, 8, 9])),
                make_cluster(4, source_points, np.array([10])),
            ],
            np.array([11], dtype=int),
        )

    # 打桩 core 层聚类函数，聚焦裁剪规则验证。
    monkeypatch.setattr(
        "core.identify_stages.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    parent_points = np.zeros((12, 6), dtype=float)
    parent_cluster = ClusterItem(
        cluster_idx=1,
        dim_name="CF",
        points=parent_points,
        points_indices=np.arange(12),
        slice_idx=0,
        time_ranges=(0.0, 1.0),
    )

    stage_ops = IdentifyStageOps(
        inference_service=object(),
        cluster_params=ClusteringParams(clip_threshold_doa=60.0),
        recognize_params=RecognitionParams(),
        context=IdentifyPipelineContext(),
    )
    doa_clusters = stage_ops.cluster_doa_children(parent_cluster)

    assert [cluster.cluster_size for cluster in doa_clusters] == [5, 3]
    assert [cluster.points_indices.tolist() for cluster in doa_clusters] == [
        [2, 3, 4, 5, 6],
        [7, 8, 9],
    ]


def test_cluster_doa_children_keeps_at_most_three_clusters(
    monkeypatch: MonkeyPatch,
) -> None:
    """DOA 子簇累计未超过阈值时也最多保留点数最多的三类。"""

    def make_cluster(
        cluster_idx: int,
        source_points: np.ndarray,
        points_indices: np.ndarray,
    ) -> ClusterItem:
        """构造指定点索引的 DOA 测试簇。"""
        return ClusterItem(
            cluster_idx=cluster_idx,
            dim_name="DOA",
            points=source_points[points_indices],
            points_indices=points_indices,
            slice_idx=0,
            time_ranges=(0.0, 1.0),
        )

    def fake_process_dimension_clustering(
        **kwargs: Any,
    ) -> tuple[list[ClusterItem], np.ndarray]:
        """返回四个 DOA 子簇，验证最多三类的截断规则。"""
        source_points = kwargs["points"]
        return (
            [
                make_cluster(1, source_points, np.array([0, 1])),
                make_cluster(2, source_points, np.array([2, 3, 4, 5])),
                make_cluster(3, source_points, np.array([6, 7, 8])),
                make_cluster(4, source_points, np.array([9])),
            ],
            np.array([], dtype=int),
        )

    # 打桩 core 层聚类函数，验证三类截断规则。
    monkeypatch.setattr(
        "core.identify_stages.process_dimension_clustering",
        fake_process_dimension_clustering,
    )
    parent_points = np.zeros((10, 6), dtype=float)
    parent_cluster = ClusterItem(
        cluster_idx=1,
        dim_name="PW",
        points=parent_points,
        points_indices=np.arange(10),
        slice_idx=0,
        time_ranges=(0.0, 1.0),
    )

    stage_ops = IdentifyStageOps(
        inference_service=object(),
        cluster_params=ClusteringParams(clip_threshold_doa=100.0),
        recognize_params=RecognitionParams(),
        context=IdentifyPipelineContext(),
    )
    doa_clusters = stage_ops.cluster_doa_children(parent_cluster)

    assert [cluster.cluster_size for cluster in doa_clusters] == [4, 3, 2]
    assert [cluster.points_indices.tolist() for cluster in doa_clusters] == [
        [2, 3, 4, 5],
        [6, 7, 8],
        [0, 1],
    ]


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
    session.slice_result = SimpleNamespace(
        slice_count=3,
        slices=[
            SimpleNamespace(index=0, data=np.zeros((1, 6), dtype=float), time_range=(0.0, 1.0)),
            SimpleNamespace(index=1, data=np.zeros((1, 6), dtype=float), time_range=(1.0, 2.0)),
            SimpleNamespace(index=2, data=np.zeros((1, 6), dtype=float), time_range=(2.0, 3.0)),
        ],
    )
    session.model_selection.pa_model_path = "E:/models/pa.onnx"
    session.model_selection.dtoa_model_path = "E:/models/dtoa.onnx"
    session.config_snapshot.clustering.eps_cf = 7.0
    session.config_snapshot.clustering.min_pts_cf = 4
    session.config_snapshot.clustering.eps_doa = 12.5
    session.config_snapshot.clustering.min_pts_doa = 6
    session.config_snapshot.recognition.tolerance = 0.25
    workflow = IdentifyWorkflow()

    workflow.start_identify(session, slice_index=2)

    cluster_params = captured["cluster_params"]
    recognize_params = captured["recognize_params"]
    assert isinstance(cluster_params, ClusteringParams)
    assert isinstance(recognize_params, RecognitionParams)
    assert captured["session_id"] == "session_params"
    assert captured["slice_data"].index == 2
    assert cluster_params.eps_cf == 7.0
    assert cluster_params.min_pts_cf == 4
    assert cluster_params.eps_doa == 12.5
    assert cluster_params.min_pts_doa == 6
    assert recognize_params.tolerance == 0.25
    assert captured["started"] is True
    service_args = captured["inference_service"]["service_args"]
    assert service_args["pa_path"] == "E:/models/pa.onnx"
    assert service_args["dtoa_path"] == "E:/models/dtoa.onnx"
    assert service_args["temp_dir"]


def test_identify_workflow_injects_extract_params(
    monkeypatch: MonkeyPatch,
) -> None:
    """识别 workflow 应把当前 session 的提取参数快照注入 worker。"""
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

    session = ProcessingSession(session_id="session_extract_params")
    session.slice_result = SimpleNamespace(
        slice_count=1,
        slices=[
            SimpleNamespace(index=0, data=np.zeros((1, 6), dtype=float), time_range=(0.0, 1.0)),
        ],
    )
    session.model_selection.pa_model_path = "E:/models/pa.onnx"
    session.model_selection.dtoa_model_path = "E:/models/dtoa.onnx"
    session.config_snapshot.extract.eps_cf = 1.25
    session.config_snapshot.extract.min_pts_cf = 6
    session.config_snapshot.extract.threshold_ratio_pri = 15.0
    session.config_snapshot.extract.filter_threshold_pri = 3.0
    session.config_snapshot.extract.harmonic_tolerance_pri = 0.2
    workflow = IdentifyWorkflow()

    workflow.start_identify(session, slice_index=0)

    extract_params = captured["extract_params"]
    assert isinstance(extract_params, ExtractParams)
    assert extract_params.eps_cf == 1.25
    assert extract_params.min_pts_cf == 6
    assert extract_params.threshold_ratio_pri == 15.0
    assert extract_params.filter_threshold_pri == 3.0
    assert extract_params.harmonic_tolerance_pri == 0.2
    assert captured["started"] is True


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
            self._session_id = kwargs["session_id"]
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
    session_a.slice_result = SimpleNamespace(
        slice_count=1,
        slices=[SimpleNamespace(index=0, data=np.zeros((1, 6), dtype=float), time_range=(0.0, 1.0))],
    )
    session_a.model_selection.pa_model_path = "E:/models/pa_a.onnx"
    session_a.model_selection.dtoa_model_path = "E:/models/dtoa_a.onnx"
    session_b = ProcessingSession(session_id="session_b")
    session_b.slice_result = SimpleNamespace(
        slice_count=2,
        slices=[
            SimpleNamespace(index=0, data=np.zeros((1, 6), dtype=float), time_range=(0.0, 1.0)),
            SimpleNamespace(index=1, data=np.zeros((1, 6), dtype=float), time_range=(1.0, 2.0)),
        ],
    )
    session_b.model_selection.pa_model_path = "E:/models/pa_b.onnx"
    session_b.model_selection.dtoa_model_path = "E:/models/dtoa_b.onnx"

    workflow_a = IdentifyWorkflow()
    workflow_b = IdentifyWorkflow()

    workflow_a.start_identify(session_a, slice_index=0)
    workflow_b.start_identify(session_b, slice_index=1)

    assert started_sessions == ["session_a", "session_b"]
    assert workflow_a.is_running() is True
    assert workflow_b.is_running() is True


def test_identify_workflow_writes_session_results_on_worker_success() -> None:
    """识别结果应由 workflow 在主线程统一写回 session。"""
    session = ProcessingSession(session_id="session_success")
    session.slice_result = SimpleNamespace(slice_count=1, slices=[SimpleNamespace(index=0)])
    workflow = IdentifyWorkflow()
    workflow._active_session = session
    workflow._active_session_id = session.session_id
    workflow._active_slice_index = 0
    workflow._worker = None

    cluster_result = SliceClusterResult(
        slice_idx=0,
        clusters=[],
        unprocessed_points=np.array([]),
        recycled_points=np.array([]),
    )
    recognition_result = SliceRecognitionResult(
        slice_index=0,
        valid_clusters=[],
        invalid_clusters=[],
    )

    workflow._on_worker_finished(
        session.session_id,
        IdentifyWorkerResult(
            success=True,
            cluster_result=cluster_result,
            recognition_result=recognition_result,
        ),
    )

    assert isinstance(session.cluster_result, ClusteringResult)
    assert isinstance(session.recognition_result, RecognitionResult)
    assert session.cluster_result.slice_results[0] is cluster_result
    assert session.recognition_result.slice_results[0] is recognition_result
    assert session.is_slice_clustered(0) is True
    assert session.is_slice_recognized(0) is True
    assert session.stage is ProcessingStage.RECOGNIZED


def test_identify_workflow_normalizes_worker_result_slice_index() -> None:
    """worker 结果索引漂移时 workflow 应以启动索引统一结果元数据。"""
    session = ProcessingSession(session_id="session_normalize")
    session.slice_result = SimpleNamespace(
        slice_count=2,
        slices=[SimpleNamespace(index=0), SimpleNamespace(index=1)],
    )
    workflow = IdentifyWorkflow()
    workflow._active_session = session
    workflow._active_session_id = session.session_id
    workflow._active_slice_index = 1
    workflow._worker = None

    cluster_result = SliceClusterResult(
        slice_idx=99,
        clusters=[],
        unprocessed_points=np.array([]),
        recycled_points=np.array([]),
    )
    recognition_result = SliceRecognitionResult(
        slice_index=99,
        valid_clusters=[],
        invalid_clusters=[],
    )

    workflow._on_worker_finished(
        session.session_id,
        IdentifyWorkerResult(
            success=True,
            cluster_result=cluster_result,
            recognition_result=recognition_result,
        ),
    )

    assert session.cluster_result is not None
    assert session.recognition_result is not None
    assert session.cluster_result.slice_results[1].slice_idx == 1
    assert session.recognition_result.slice_results[1].slice_index == 1


def test_identify_workflow_marks_recognition_running_only_after_progress() -> None:
    """识别状态应在收到识别阶段进度后再进入运行中。"""
    session = ProcessingSession(session_id="session_progress")
    session.slice_result = SimpleNamespace(slice_count=1, slices=[SimpleNamespace(index=0)])
    workflow = IdentifyWorkflow()
    workflow._active_session = session
    workflow._active_session_id = session.session_id
    workflow._active_slice_index = 0

    with session.lock:
        session.mark_slice_cluster_running(0)
        session.mark_slice_recognition_pending(0)

    workflow._on_worker_progress(session.session_id, "recognition", 1, 2)

    assert session.get_slice_processing_state(0).cluster_status is SliceProcessStatus.RUNNING
    assert (
        session.get_slice_processing_state(0).recognition_status
        is SliceProcessStatus.RUNNING
    )


def test_identify_workflow_keeps_recognition_not_started_when_clustering_fails() -> None:
    """聚类阶段失败时不应把识别状态误记为失败。"""
    session = ProcessingSession(session_id="session_failure")
    session.slice_result = SimpleNamespace(slice_count=1, slices=[SimpleNamespace(index=0)])
    workflow = IdentifyWorkflow()
    workflow._active_session = session
    workflow._active_session_id = session.session_id
    workflow._active_slice_index = 0
    workflow._worker = None

    with session.lock:
        session.mark_slice_cluster_running(0)
        session.mark_slice_recognition_pending(0)

    workflow._on_worker_finished(
        session.session_id,
        IdentifyWorkerResult(
            success=False,
            failed_phase="clustering",
            error_message="cluster failed",
        ),
    )

    state = session.get_slice_processing_state(0)
    assert state.cluster_status is SliceProcessStatus.FAILED
    assert state.recognition_status is SliceProcessStatus.NOT_STARTED
    assert session.stage is ProcessingStage.SLICED
