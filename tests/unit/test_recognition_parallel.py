"""并发簇识别测试。"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.models.algorithm_params import RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState
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


def _make_cluster(cluster_idx: int) -> ClusterItem:
    """构造测试簇对象。"""
    return ClusterItem(
        cluster_idx=cluster_idx,
        dim_name="CF",
        points=np.array(
            [
                [1000.0 + cluster_idx, 1.0, 80.0, 10.0, 0.0],
                [2000.0 + cluster_idx, 2.0, 81.0, 11.0, 1000.0],
            ]
        ),
        points_indices=np.array([0, 1]),
        slice_idx=0,
        time_ranges=(0.0, 1.0),
    )


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

    with caplog.at_level(logging.INFO):
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

    with caplog.at_level(logging.INFO):
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
