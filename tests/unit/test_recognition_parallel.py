"""并发簇识别测试。"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.models.algorithm_params import RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState
from core.models.recognition_result import NON_RADAR_LABEL
from core.recognition import recognize_clusters_parallel
from core.recognition import TraceLogEntry


class _FakeInferenceService:
    """测试用推理服务。"""

    def __init__(self, delays: dict[int, float]) -> None:
        """初始化簇级延迟映射。"""
        self._delays = delays

    def predict_pa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """返回预设 PA 预测结果。"""
        time.sleep(self._delays.get(cluster.cluster_idx, 0.0))
        if write_log:
            logging.getLogger("test.parallel").info(
                "簇 %d PA 内部日志",
                cluster.cluster_idx,
            )
        elif trace_messages is not None:
            trace_messages.extend(
                [
                    TraceLogEntry(
                        logger_name="infra.onnx_service",
                        pathname="e:/myProjects_Trae/RadarIdentifySystem_Codex/infra/onnx_service.py",
                        func_name="predict_pa",
                        message=f"PA ONNX 原始输出 (logits): [cluster={cluster.cluster_idx}]",
                    ),
                    TraceLogEntry(
                        logger_name="infra.onnx_service",
                        pathname="e:/myProjects_Trae/RadarIdentifySystem_Codex/infra/onnx_service.py",
                        func_name="predict_pa",
                        message=f"PA Softmax 概率: [cluster={cluster.cluster_idx}]",
                    ),
                    TraceLogEntry(
                        logger_name="infra.onnx_service",
                        pathname="e:/myProjects_Trae/RadarIdentifySystem_Codex/infra/onnx_service.py",
                        func_name="predict_pa",
                        message=(
                            f"PA 预测完成: label={cluster.cluster_idx}, conf=0.9000, "
                            f"各类别概率={cluster.cluster_idx}=0.9000, 耗时=10.0ms"
                        ),
                    ),
                ]
            )
        if cluster.cluster_idx == 2:
            return 5, 0.21, {5: 0.21}
        return cluster.cluster_idx, 0.90 - cluster.cluster_idx * 0.05, {
            cluster.cluster_idx: 0.90 - cluster.cluster_idx * 0.05,
        }

    def predict_dtoa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """返回预设 DTOA 预测结果。"""
        time.sleep(self._delays.get(cluster.cluster_idx, 0.0) / 2)
        if write_log:
            logging.getLogger("test.parallel").info(
                "簇 %d DTOA 内部日志",
                cluster.cluster_idx,
            )
        elif trace_messages is not None:
            trace_messages.extend(
                [
                    TraceLogEntry(
                        logger_name="infra.onnx_service",
                        pathname="e:/myProjects_Trae/RadarIdentifySystem_Codex/infra/onnx_service.py",
                        func_name="predict_dtoa",
                        message=f"DTOA ONNX 原始输出 (logits): [cluster={cluster.cluster_idx}]",
                    ),
                    TraceLogEntry(
                        logger_name="infra.onnx_service",
                        pathname="e:/myProjects_Trae/RadarIdentifySystem_Codex/infra/onnx_service.py",
                        func_name="predict_dtoa",
                        message=f"DTOA Softmax 概率: [cluster={cluster.cluster_idx}]",
                    ),
                    TraceLogEntry(
                        logger_name="infra.onnx_service",
                        pathname="e:/myProjects_Trae/RadarIdentifySystem_Codex/infra/onnx_service.py",
                        func_name="predict_dtoa",
                        message=(
                            f"DTOA 预测完成: label={cluster.cluster_idx}, conf=0.8000, "
                            f"各类别概率={cluster.cluster_idx}=0.8000, 耗时=8.0ms"
                        ),
                    ),
                ]
            )
        if cluster.cluster_idx == 2:
            return 5, 0.18, {5: 0.18}
        return cluster.cluster_idx, 0.80 - cluster.cluster_idx * 0.05, {
            cluster.cluster_idx: 0.80 - cluster.cluster_idx * 0.05,
        }


class _FixedInferenceService:
    """返回固定PA和DTOA结果的识别服务桩。"""

    def __init__(
        self,
        pa_result: tuple[int, float, dict[int, float]],
        dtoa_result: tuple[int, float, dict[int, float]],
    ) -> None:
        """初始化固定预测结果。"""
        self._pa_result = pa_result
        self._dtoa_result = dtoa_result

    def predict_pa(
        self,
        _cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """返回固定PA预测结果。"""
        del write_log, trace_messages
        return self._pa_result

    def predict_dtoa(
        self,
        _cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """返回固定DTOA预测结果。"""
        del write_log, trace_messages
        return self._dtoa_result


def _make_cluster(cluster_idx: int) -> ClusterItem:
    """构造测试簇对象。"""
    return ClusterItem(
        cluster_idx=cluster_idx,
        dim_name="CF",
        points=np.array(
            [
                [1000.0 + cluster_idx, 1.0, 10.0, 80.0, 80.0, 0.0],
                [2000.0 + cluster_idx, 2.0, 11.0, 81.0, 81.0, 1000.0],
            ]
        ),
        points_indices=np.array([0, 1]),
        slice_idx=0,
        time_ranges=(0.0, 1.0),
    )


def test_greedy_recognition_uses_only_non_radar_labels() -> None:
    """贪婪策略应忽略门限和权重，并且不计算联合概率。"""
    params = RecognitionParams(
        greedy_strategy=True,
        pa_confidence_threshold=1.0,
        pa_confidence_weight=0.0,
        dtoa_confidence_threshold=1.0,
        dtoa_confidence_weight=0.0,
        joint_confidence_threshold=1.0,
    )
    service = _FixedInferenceService(
        pa_result=(1, 0.01, {1: 0.01}),
        dtoa_result=(NON_RADAR_LABEL, 0.01, {NON_RADAR_LABEL: 0.01}),
    )

    valid, invalid, recognitions, _ = recognize_clusters_parallel(
        [_make_cluster(1)],
        service,
        params,
        start_valid_idx=0,
    )

    assert len(valid) == 1
    assert invalid == []
    assert recognitions[0].is_valid is True
    assert recognitions[0].joint_prob == 0.0


def test_greedy_recognition_rejects_two_non_radar_labels() -> None:
    """贪婪策略应在PA和DTOA均为非雷达标签时判为无效。"""
    service = _FixedInferenceService(
        pa_result=(NON_RADAR_LABEL, 0.99, {NON_RADAR_LABEL: 0.99}),
        dtoa_result=(NON_RADAR_LABEL, 0.99, {NON_RADAR_LABEL: 0.99}),
    )

    valid, invalid, recognitions, _ = recognize_clusters_parallel(
        [_make_cluster(1)],
        service,
        RecognitionParams(),
        start_valid_idx=0,
    )

    assert valid == []
    assert len(invalid) == 1
    assert recognitions[0].is_valid is False
    assert recognitions[0].joint_prob == 0.0


def test_strict_recognition_accepts_threshold_boundaries() -> None:
    """严格策略应接受PA、DTOA及联合概率恰好等于门限的结果。"""
    params = RecognitionParams(
        greedy_strategy=False,
        pa_confidence_threshold=0.7,
        pa_confidence_weight=3.0,
        dtoa_confidence_threshold=0.5,
        dtoa_confidence_weight=1.0,
        joint_confidence_threshold=0.65,
    )
    service = _FixedInferenceService(
        pa_result=(1, 0.7, {1: 0.7}),
        dtoa_result=(2, 0.5, {2: 0.5}),
    )

    valid, invalid, recognitions, _ = recognize_clusters_parallel(
        [_make_cluster(1)],
        service,
        params,
        start_valid_idx=0,
    )

    assert len(valid) == 1
    assert invalid == []
    assert recognitions[0].is_valid is True
    assert recognitions[0].joint_prob == pytest.approx(0.65)


@pytest.mark.parametrize(
    ("pa_label", "dtoa_label"),
    [
        (NON_RADAR_LABEL, 2),
        (1, NON_RADAR_LABEL),
        (NON_RADAR_LABEL, NON_RADAR_LABEL),
    ],
)
def test_strict_recognition_rejects_non_radar_before_probability_calculation(
    monkeypatch: pytest.MonkeyPatch,
    pa_label: int,
    dtoa_label: int,
) -> None:
    """严格策略遇到任一非雷达标签时应直接拒绝并跳过联合概率计算。"""
    params = RecognitionParams(
        greedy_strategy=False,
        pa_confidence_threshold=0.0,
        pa_confidence_weight=0.6,
        dtoa_confidence_threshold=0.0,
        dtoa_confidence_weight=0.4,
        joint_confidence_threshold=0.0,
    )
    service = _FixedInferenceService(
        pa_result=(pa_label, 0.99, {pa_label: 0.99}),
        dtoa_result=(dtoa_label, 0.99, {dtoa_label: 0.99}),
    )

    def fail_if_calculated(
        _pa_confidence: float,
        _dtoa_confidence: float,
        _params: RecognitionParams,
    ) -> float:
        """在非雷达分支误算联合概率时立即使测试失败。"""
        raise AssertionError("非雷达标签不应计算联合概率")

    monkeypatch.setattr(
        "core.recognition._calculate_joint_probability",
        fail_if_calculated,
    )

    valid, invalid, recognitions, _ = recognize_clusters_parallel(
        [_make_cluster(1)],
        service,
        params,
        start_valid_idx=0,
    )

    assert valid == []
    assert len(invalid) == 1
    assert recognitions[0].is_valid is False
    assert recognitions[0].joint_prob == 0.0


def test_strict_recognition_requires_each_threshold_and_joint_threshold() -> None:
    """严格策略应同时满足PA、DTOA和加权联合概率三个门限条件。"""
    params = RecognitionParams(
        greedy_strategy=False,
        pa_confidence_threshold=0.6,
        pa_confidence_weight=0.5,
        dtoa_confidence_threshold=0.6,
        dtoa_confidence_weight=0.5,
        joint_confidence_threshold=0.7,
    )
    cases = [
        ((1, 0.59, {1: 0.59}), (2, 0.9, {2: 0.9})),
        ((1, 0.9, {1: 0.9}), (2, 0.59, {2: 0.59})),
        ((1, 0.69, {1: 0.69}), (2, 0.69, {2: 0.69})),
    ]

    for cluster_idx, (pa_result, dtoa_result) in enumerate(cases, start=1):
        service = _FixedInferenceService(pa_result, dtoa_result)
        valid, invalid, recognitions, _ = recognize_clusters_parallel(
            [_make_cluster(cluster_idx)],
            service,
            params,
            start_valid_idx=0,
        )

        assert valid == []
        assert len(invalid) == 1
        assert recognitions[0].is_valid is False


def test_strict_recognition_handles_zero_total_weight() -> None:
    """严格策略权重和为零时联合概率应安全回退为零。"""
    params = RecognitionParams(
        greedy_strategy=False,
        pa_confidence_threshold=0.5,
        pa_confidence_weight=0.0,
        dtoa_confidence_threshold=0.5,
        dtoa_confidence_weight=0.0,
        joint_confidence_threshold=0.1,
    )
    service = _FixedInferenceService(
        pa_result=(1, 0.9, {1: 0.9}),
        dtoa_result=(2, 0.9, {2: 0.9}),
    )

    valid, invalid, recognitions, _ = recognize_clusters_parallel(
        [_make_cluster(1)],
        service,
        params,
        start_valid_idx=0,
    )

    assert valid == []
    assert len(invalid) == 1
    assert recognitions[0].joint_prob == 0.0


def test_parallel_recognition_keeps_input_order_and_valid_indices() -> None:
    """并发识别后应保持输入顺序并稳定分配有效簇编号。"""
    clusters = [_make_cluster(1), _make_cluster(2), _make_cluster(3)]
    service = _FakeInferenceService({1: 0.03, 2: 0.01, 3: 0.02})

    valid, invalid, recognitions, next_valid_idx = recognize_clusters_parallel(
        clusters,
        service,
        RecognitionParams(),
        start_valid_idx=5,
        max_workers=3,
    )

    assert [recognition.cluster_index for recognition in recognitions] == [1, 2, 3]
    assert [cluster.cluster_idx for cluster in valid] == [1, 3]
    assert [cluster.cluster_idx for cluster in invalid] == [2]
    assert [cluster.valid_cluster_idx for cluster in valid] == [5, 6]
    assert next_valid_idx == 7
    assert clusters[0].state is ClusterState.VALID
    assert clusters[1].state is ClusterState.INVALID
    assert clusters[2].state is ClusterState.VALID


def test_parallel_recognition_replays_detailed_logs_in_cluster_order(caplog) -> None:
    """并发识别后应按簇顺序连续输出完整日志块。"""
    clusters = [_make_cluster(1), _make_cluster(2), _make_cluster(3)]
    service = _FakeInferenceService({1: 0.03, 2: 0.01, 3: 0.02})

    with caplog.at_level(logging.DEBUG):
        recognize_clusters_parallel(
            clusters,
            service,
            RecognitionParams(),
            start_valid_idx=0,
            max_workers=3,
        )

    messages = [record.getMessage() for record in caplog.records]
    cluster_1_start = messages.index("PA ONNX 原始输出 (logits): [cluster=1]")
    cluster_1_end = messages.index("簇 1 (CF) 预测结果: PA=1(0.8500), DTOA=1(0.7500)")
    cluster_2_start = messages.index("PA ONNX 原始输出 (logits): [cluster=2]")
    cluster_2_end = messages.index("簇 2 (CF) 预测结果: PA=5(0.2100), DTOA=5(0.1800)")
    cluster_3_start = messages.index("PA ONNX 原始输出 (logits): [cluster=3]")
    cluster_3_end = messages.index("簇 3 (CF) 预测结果: PA=3(0.7500), DTOA=3(0.6500)")

    assert cluster_1_start < cluster_1_end < cluster_2_start < cluster_2_end < cluster_3_start < cluster_3_end
    assert not any("内部日志" in record.getMessage() for record in caplog.records)
    pa_records = [
        record for record in caplog.records
        if "PA ONNX 原始输出" in record.getMessage()
    ]
    summary_records = [
        record for record in caplog.records
        if "预测结果" in record.getMessage()
    ]
    assert all(record.name == "infra.onnx_service" for record in pa_records)
    assert all(record.funcName == "predict_pa" for record in pa_records)
    assert all(record.name == "core.recognition" for record in summary_records)
    assert all(record.funcName == "recognize_clusters" for record in summary_records)


def test_single_cluster_path_uses_same_detailed_log_structure(caplog) -> None:
    """单簇识别回退串行时也应保持与并发分支一致的日志结构。"""
    clusters = [_make_cluster(1)]
    service = _FakeInferenceService({1: 0.0})

    with caplog.at_level(logging.DEBUG):
        recognize_clusters_parallel(
            clusters,
            service,
            RecognitionParams(),
            start_valid_idx=0,
            max_workers=1,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert "PA ONNX 原始输出 (logits): [cluster=1]" in messages
    assert "DTOA ONNX 原始输出 (logits): [cluster=1]" in messages
    assert "簇 1 (CF) 预测结果: PA=1(0.8500), DTOA=1(0.7500)" in messages
    assert not any("内部日志" in record.getMessage() for record in caplog.records)
    assert any(
        record.name == "infra.onnx_service" and record.funcName == "predict_pa"
        for record in caplog.records
    )
    assert any(
        record.name == "core.recognition" and record.funcName == "recognize_clusters"
        for record in caplog.records
    )
