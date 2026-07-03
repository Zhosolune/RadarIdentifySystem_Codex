"""识别与特征预测算法。

功能描述：
    对聚类结果进行 PA 与 DTOA 维度的特征预测，计算联合概率，
    并判定簇的有效性。本模块为纯业务逻辑，不直接依赖 ONNX 或绘图库，
    通过依赖注入（回调或接口）调用外部推理能力。

标签体系（严格遵循旧版定义）：
    PA  (6 类): 0=完整包络, 1=残缺包络, 2=部分包络, 3=相扫, 4=旁瓣, 5=非雷达信号
    DTOA(6 类): 0=常规, 1=脉间参差, 2=脉组参差, 3=脉间脉组参差, 4=组变脉间, 5=非雷达信号

DTOA 长短类别合并规则（模型输出 7+ 类 → 6 类）：
    原始: 0=常规_短, 1=常规_长, 2=脉间参差, 3=脉组参差_短, 4=脉组参差_长, 5=脉间脉组参差, 6=组变脉间, 7+=非雷达信号
    合并: 0←0+1, 1←2, 2←3+4, 3←5, 4←6, 5←sum(7:)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import inspect
import logging
import os
from typing import Protocol
from core.models.algorithm_params import RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState
from core.models.recognition_result import ClusterRecognition

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TraceLogEntry:
    """日志回放条目。"""

    logger_name: str
    pathname: str
    func_name: str
    message: str
    level: int = logging.INFO


@dataclass(frozen=True, slots=True)
class _ClusterRecognitionOutcome:
    """单簇识别中间结果。"""

    cluster: ClusterItem
    pa_label: int
    pa_confidence: float
    pa_conf_dict: dict[int, float]
    dtoa_label: int
    dtoa_confidence: float
    dtoa_conf_dict: dict[int, float]
    joint_prob: float
    is_valid: bool
    pa_trace_messages: list[TraceLogEntry]
    dtoa_trace_messages: list[TraceLogEntry]


class InferenceService(Protocol):
    """推理服务协议。
    
    由 infra 层实现此协议，封装 ONNX 模型调用和绘图过程。
    """
    def predict_pa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """预测 PA 特征，返回 (类别标签, 置信度, 各类别置信度字典)"""
        ...

    def predict_dtoa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """预测 DTOA 特征，返回 (类别标签, 置信度, 各类别置信度字典)"""
        ...


def _method_supports_parameter(method: object, parameter_name: str) -> bool:
    """判断预测方法是否支持指定参数。"""
    try:
        return parameter_name in inspect.signature(method).parameters
    except (TypeError, ValueError):
        return False


def _predict_with_optional_log_control(
    method,
    cluster: ClusterItem,
    write_log: bool,
    trace_messages: list[TraceLogEntry] | None = None,
) -> tuple[int, float, dict[int, float]]:
    """按能力调用预测方法，并在支持时传入日志开关。"""
    kwargs = {}
    if _method_supports_parameter(method, "write_log"):
        kwargs["write_log"] = write_log
    if trace_messages is not None and _method_supports_parameter(
        method,
        "trace_messages",
    ):
        kwargs["trace_messages"] = trace_messages
    if kwargs:
        return method(cluster, **kwargs)
    return method(cluster)


def _evaluate_cluster(
    cluster: ClusterItem,
    inference_service: InferenceService,
    params: RecognitionParams,
    write_log: bool,
) -> _ClusterRecognitionOutcome:
    """执行单个簇的识别预测与有效性判定。"""
    del params
    pa_weight = 0.6
    dtoa_weight = 0.4
    pa_trace_messages: list[TraceLogEntry] = []
    dtoa_trace_messages: list[TraceLogEntry] = []
    pa_label, pa_conf, pa_conf_dict = _predict_with_optional_log_control(
        inference_service.predict_pa,
        cluster,
        write_log=write_log,
        trace_messages=pa_trace_messages,
    )
    dtoa_label, dtoa_conf, dtoa_conf_dict = _predict_with_optional_log_control(
        inference_service.predict_dtoa,
        cluster,
        write_log=write_log,
        trace_messages=dtoa_trace_messages,
    )
    joint_prob = pa_conf * pa_weight + dtoa_conf * dtoa_weight
    is_valid = pa_label != 5 or dtoa_label != 5
    return _ClusterRecognitionOutcome(
        cluster=cluster,
        pa_label=pa_label,
        pa_confidence=pa_conf,
        pa_conf_dict=pa_conf_dict,
        dtoa_label=dtoa_label,
        dtoa_confidence=dtoa_conf,
        dtoa_conf_dict=dtoa_conf_dict,
        joint_prob=joint_prob,
        is_valid=is_valid,
        pa_trace_messages=pa_trace_messages,
        dtoa_trace_messages=dtoa_trace_messages,
    )


def _log_cluster_recognition(outcome: _ClusterRecognitionOutcome) -> None:
    """连续输出单个簇的识别日志。"""
    for trace_message in outcome.pa_trace_messages:
        _replay_trace_log(trace_message)
    for trace_message in outcome.dtoa_trace_messages:
        _replay_trace_log(trace_message)
    _replay_trace_log(
        TraceLogEntry(
            logger_name=LOGGER.name,
            pathname=__file__,
            func_name="recognize_clusters",
            message=(
                f"簇 {outcome.cluster.cluster_idx} ({outcome.cluster.dim_name}) "
                f"预测结果: PA={outcome.pa_label}({outcome.pa_confidence:.4f}), "
                f"DTOA={outcome.dtoa_label}({outcome.dtoa_confidence:.4f})"
            ),
        )
    )


def _replay_trace_log(trace_log: TraceLogEntry) -> None:
    """按原始日志头信息回放日志记录。"""
    logger = logging.getLogger(trace_log.logger_name)
    record = logging.LogRecord(
        name=trace_log.logger_name,
        level=trace_log.level,
        pathname=trace_log.pathname,
        lineno=0,
        msg=trace_log.message,
        args=(),
        exc_info=None,
        func=trace_log.func_name,
    )
    logger.handle(record)


def _materialize_recognition_outcomes(
    outcomes: list[_ClusterRecognitionOutcome],
    start_valid_idx: int,
    write_summary_log: bool,
) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
    """按既定顺序固化识别结果并分配有效簇序号。"""
    valid_clusters = []
    invalid_clusters = []
    recognitions = []
    current_valid_idx = start_valid_idx

    for outcome in outcomes:
        if write_summary_log:
            # 顺序回放单簇日志，避免并发识别时多簇日志交错。
            _log_cluster_recognition(outcome)

        valid_cluster_idx = None
        if outcome.is_valid:
            valid_cluster_idx = current_valid_idx
            current_valid_idx += 1

        rec_info = ClusterRecognition(
            slice_index=outcome.cluster.slice_idx,
            dim_name=outcome.cluster.dim_name,
            cluster_index=outcome.cluster.cluster_idx,
            valid_cluster_index=valid_cluster_idx,
            pa_label=outcome.pa_label,
            pa_confidence=outcome.pa_confidence,
            dtoa_label=outcome.dtoa_label,
            dtoa_confidence=outcome.dtoa_confidence,
            is_valid=outcome.is_valid,
            joint_prob=outcome.joint_prob,
            pa_conf_dict=outcome.pa_conf_dict,
            dtoa_conf_dict=outcome.dtoa_conf_dict,
        )
        recognitions.append(rec_info)

        if outcome.is_valid:
            outcome.cluster.state = ClusterState.VALID
            outcome.cluster.pa_label = outcome.pa_label
            outcome.cluster.dtoa_label = outcome.dtoa_label
            outcome.cluster.joint_prob = outcome.joint_prob
            outcome.cluster.valid_cluster_idx = valid_cluster_idx
            valid_clusters.append(outcome.cluster)
        else:
            outcome.cluster.state = ClusterState.INVALID
            invalid_clusters.append(outcome.cluster)

    return valid_clusters, invalid_clusters, recognitions, current_valid_idx


def _resolve_parallel_workers(cluster_count: int, max_workers: int | None) -> int:
    """解析簇级并发线程数。"""
    if cluster_count <= 1:
        return 1
    if max_workers is not None:
        return max(1, min(cluster_count, max_workers))
    cpu_count = os.cpu_count() or 1
    return max(1, min(cluster_count, min(cpu_count, 4)))


def recognize_clusters(
    clusters: list[ClusterItem],
    inference_service: InferenceService,
    params: RecognitionParams,
    start_valid_idx: int,
    write_summary_log: bool = True,
) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
    """对一组簇执行识别。
    
    功能描述：
        调用推理服务获取预测结果，根据配置参数进行判定。
        为通过判定的有效簇分配全局递增的 valid_cluster_idx。

    Args:
        clusters: 待识别的簇列表。
        inference_service: 注入的推理服务。
        params: 识别判定参数。
        start_valid_idx: 当前有效簇的起始索引。
        write_summary_log: 是否输出内置的“簇 X (维度) 预测结果”汇总日志，
            默认 True；DOA 复检等由上层重排缩进日志的场景可传 False 关闭。

    Returns:
        (有效簇列表, 无效簇列表, 识别记录列表, 下一个可用的有效簇索引)
    """
    outcomes = [
        _evaluate_cluster(
            cluster,
            inference_service,
            params,
            write_log=False,
        )
        for cluster in clusters
    ]
    return _materialize_recognition_outcomes(
        outcomes,
        start_valid_idx=start_valid_idx,
        write_summary_log=write_summary_log,
    )


def recognize_clusters_parallel(
    clusters: list[ClusterItem],
    inference_service: InferenceService,
    params: RecognitionParams,
    start_valid_idx: int,
    max_workers: int | None = None,
    write_summary_log: bool = True,
) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
    """并发识别一组簇，并按输入顺序稳定汇总结果。

    功能描述：
        使用线程池并发执行单簇识别预测，但在汇总阶段仍按输入顺序
        分配有效簇序号和输出日志，保证结果顺序与日志可读性稳定。

    Args:
        clusters: 待识别的簇列表。
        inference_service: 注入的推理服务。
        params: 识别判定参数。
        start_valid_idx: 当前有效簇的起始索引。
        max_workers: 并发线程数上限；为 None 时自动按簇数量与 CPU 数推导。
        write_summary_log: 是否输出内置的“簇 X (维度) 预测结果”汇总日志，
            默认 True；DOA 复检等由上层重排缩进日志的场景可传 False 关闭。

    Returns:
        tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
        有效簇、无效簇、识别记录及下一个有效簇序号。

    Raises:
        Exception: 当任一簇识别任务失败时向上抛出原始异常。
    """
    worker_count = _resolve_parallel_workers(len(clusters), max_workers)
    if worker_count <= 1:
        return recognize_clusters(
            clusters,
            inference_service,
            params,
            start_valid_idx,
            write_summary_log=write_summary_log,
        )

    ordered_outcomes: list[_ClusterRecognitionOutcome | None] = [None] * len(clusters)
    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="cluster-recognizer",
    ) as executor:
        future_to_order = {
            executor.submit(
                _evaluate_cluster,
                cluster,
                inference_service,
                params,
                False,
            ): order
            for order, cluster in enumerate(clusters)
        }
        for future in as_completed(future_to_order):
            order = future_to_order[future]
            ordered_outcomes[order] = future.result()

    return _materialize_recognition_outcomes(
        [outcome for outcome in ordered_outcomes if outcome is not None],
        start_valid_idx=start_valid_idx,
        write_summary_log=write_summary_log,
    )
