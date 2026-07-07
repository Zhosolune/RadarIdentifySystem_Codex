#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""切片识别流程日志开销 Profiling 脚本。

对比「正常日志」与「禁用日志」的 identify_slice 耗时，用于验证日志记录对算法执行效率的影响量级。

用法:
    # 合成负载（默认）
    D:/Miniforge3/envs/pyqt6/python.exe scripts/profile_identify_logging.py

    # 真实环境：使用本地最近打开的 session + 真实 ONNX
    D:/Miniforge3/envs/pyqt6/python.exe scripts/profile_identify_logging.py --real
    D:/Miniforge3/envs/pyqt6/python.exe scripts/profile_identify_logging.py --real --session-id <id> --slice-index 0

    # 列出可用 session
    D:/Miniforge3/envs/pyqt6/python.exe scripts/profile_identify_logging.py --list-sessions
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from app.app_config import appConfig, qconfig
from app.logger import bind_session_log_context, configure_logging, unbind_session_log_context
from app.model_bootstrap import get_cached_inference_service
from core.identify_pipeline import identify_slice
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import ClusterItem
from core.models.processing_session import ProcessingSession
from core.models.recognition_result import ClusterRecognition
from core.recognition import TraceLogEntry, recognize_clusters_parallel
from core.slicing import slice_by_toa
from infra.session_store import SessionIndexEntry, SessionStore
from utils.paths import get_session_config_dir


class _CountingHandler(logging.Handler):
    """统计一次运行中实际落盘的日志条数。"""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1


@dataclass(frozen=True)
class RealWorkload:
    """真实 session 负载描述。"""

    session_id: str
    display_name: str
    slice_index: int
    slice_pulse_count: int
    pa_model_path: str
    dtoa_model_path: str
    slice_data: Any
    inference_service: Any
    cluster_params: ClusteringParams
    recognize_params: RecognitionParams
    extract_params: ExtractParams
    warmup_rounds: int = 1
    measure_rounds: int = 3


@dataclass(frozen=True)
class ProfileConfig:
    """Profiling 合成负载参数。"""

    cf_cluster_count: int = 8
    doa_children_per_parent: int = 3
    inference_delay_ms: float = 12.0
    warmup_rounds: int = 1
    measure_rounds: int = 5
    points_per_cf_cluster: int = 6


@dataclass(frozen=True)
class ProfileResult:
    """单场景 Profiling 结果。"""

    label: str
    seconds: list[float]
    log_records: int

    @property
    def median_s(self) -> float:
        return statistics.median(self.seconds)

    @property
    def mean_s(self) -> float:
        return statistics.mean(self.seconds)


class _SlowInferenceService:
    """模拟 ONNX 推理耗时，并在静默模式下收集 TraceLogEntry。"""

    def __init__(self, delay_ms: float) -> None:
        self._delay_s = max(delay_ms, 0.0) / 1000.0

    def _sleep(self) -> None:
        if self._delay_s > 0:
            time.sleep(self._delay_s)

    @staticmethod
    def _append_trace(
        trace_messages: list[TraceLogEntry] | None,
        message: str,
        func_name: str,
    ) -> None:
        if trace_messages is None:
            return
        trace_messages.append(
            TraceLogEntry(
                logger_name="infra.onnx_service",
                pathname=str(ROOT / "infra" / "onnx_service.py"),
                func_name=func_name,
                message=message,
            )
        )

    def predict_pa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        del write_log
        self._sleep()
        self._append_trace(
            trace_messages,
            f"PA 预测完成: cluster={cluster.cluster_idx}",
            "predict_pa",
        )
        conf_dict = {index: 0.1 for index in range(6)}
        conf_dict[1] = 0.9
        return 1, 0.9, conf_dict

    def predict_dtoa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        del write_log
        self._sleep()
        self._append_trace(
            trace_messages,
            f"DTOA 预测完成: cluster={cluster.cluster_idx}",
            "predict_dtoa",
        )
        conf_dict = {index: 0.1 for index in range(6)}
        conf_dict[1] = 0.8
        return 1, 0.8, conf_dict


def _list_session_entries() -> list[SessionIndexEntry]:
    """列出本地持久化的 session 索引条目。"""
    store = SessionStore(get_session_config_dir())
    return store.list_sessions()


def _pick_recent_session_id(session_id: str | None) -> SessionIndexEntry:
    """解析目标 session；未指定时取最近打开的 session。"""
    entries = _list_session_entries()
    if not entries:
        raise RuntimeError("本地没有可用 session，请先在软件中导入数据并创建 session。")

    if session_id is not None:
        for entry in entries:
            if entry.session_id == session_id:
                return entry
        known_ids = ", ".join(entry.session_id for entry in entries)
        raise RuntimeError(f"未找到 session_id={session_id}，可用列表: {known_ids}")

    return max(entries, key=lambda entry: entry.last_opened_at)


def _build_params_from_session(session: ProcessingSession) -> tuple[
    ClusteringParams,
    RecognitionParams,
    ExtractParams,
]:
    """按 IdentifyWorkflow 规则从 session 快照构造算法参数。"""
    clustering_config = session.config_snapshot.clustering
    recognition_config = session.config_snapshot.recognition
    extract_config = session.config_snapshot.extract
    cluster_params = ClusteringParams(
        eps_cf=clustering_config.eps_cf,
        min_pts_cf=clustering_config.min_pts_cf,
        eps_pw=clustering_config.eps_pw,
        min_pts_pw=clustering_config.min_pts_pw,
        eps_doa=clustering_config.eps_doa,
        min_pts_doa=clustering_config.min_pts_doa,
        clip_threshold_doa=clustering_config.clip_threshold_doa,
    )
    recognize_params = RecognitionParams(
        tolerance=recognition_config.tolerance,
        min_confidence=recognition_config.min_confidence,
        max_candidates=recognition_config.max_candidates,
    )
    extract_params = ExtractParams(
        eps_cf=extract_config.eps_cf,
        min_pts_cf=extract_config.min_pts_cf,
        threshold_ratio_cf=extract_config.threshold_ratio_cf,
        eps_pw=extract_config.eps_pw,
        min_pts_pw=extract_config.min_pts_pw,
        threshold_ratio_pw=extract_config.threshold_ratio_pw,
        eps_pri=extract_config.eps_pri,
        min_pts_pri=extract_config.min_pts_pri,
        threshold_ratio_pri=extract_config.threshold_ratio_pri,
        filter_threshold_pri=extract_config.filter_threshold_pri,
        harmonic_tolerance_pri=extract_config.harmonic_tolerance_pri,
    )
    return cluster_params, recognize_params, extract_params


def _load_real_workload(
    session_id: str | None,
    slice_index: int | None,
    warmup_rounds: int,
    measure_rounds: int,
) -> RealWorkload:
    """加载最近 session 的导入缓存，切片后构造真实识别负载。"""
    entry = _pick_recent_session_id(session_id)
    store = SessionStore(get_session_config_dir())
    session = store.load_session(entry.session_id)
    if not store.load_import_cache(session):
        raise RuntimeError(
            f"session {entry.session_id} 缺少导入缓存，请先在软件中完成导入。"
        )
    if session.preprocess_result is None:
        raise RuntimeError(f"session {entry.session_id} 预处理结果为空。")

    pa_path = session.model_selection.pa_model_path
    dtoa_path = session.model_selection.dtoa_model_path
    if not pa_path or not dtoa_path:
        raise RuntimeError(
            f"session {entry.session_id} 未配置 PA/DTOA 模型路径，请先在软件中选择模型。"
        )

    slice_result = slice_by_toa(
        session.preprocess_result.data,
        session_id=entry.session_id,
    )
    if slice_result.slice_count <= 0:
        raise RuntimeError(f"session {entry.session_id} 切片结果为空。")

    resolved_slice_index = 0 if slice_index is None else slice_index
    if not (0 <= resolved_slice_index < slice_result.slice_count):
        raise RuntimeError(
            f"切片索引越界: {resolved_slice_index}，当前 session 共 {slice_result.slice_count} 片。"
        )

    cluster_params, recognize_params, extract_params = _build_params_from_session(session)
    temp_dir = str(qconfig.get(appConfig.logDir))
    inference_service = get_cached_inference_service(
        pa_path=pa_path,
        dtoa_path=dtoa_path,
        temp_dir=temp_dir,
    )
    slice_data = slice_result.slices[resolved_slice_index]
    return RealWorkload(
        session_id=entry.session_id,
        display_name=entry.display_name,
        slice_index=resolved_slice_index,
        slice_pulse_count=slice_data.pulse_count,
        pa_model_path=pa_path,
        dtoa_model_path=dtoa_path,
        slice_data=slice_data,
        inference_service=inference_service,
        cluster_params=cluster_params,
        recognize_params=recognize_params,
        extract_params=extract_params,
        warmup_rounds=warmup_rounds,
        measure_rounds=measure_rounds,
    )


def _make_points(config: ProfileConfig) -> np.ndarray:
    """构造固定规模的切片点集。"""
    rows: list[list[float]] = []
    for cf_index in range(config.cf_cluster_count):
        cf_value = 1000.0 + cf_index * 100.0
        for point_index in range(config.points_per_cf_cluster):
            rows.append(
                [
                    cf_value,
                    1.0 + (point_index % 2),
                    10.0 + point_index,
                    20.0,
                    float(cf_index * 10 + point_index),
                ]
            )
    return np.array(rows, dtype=float)


def _build_workload_patches(config: ProfileConfig, points: np.ndarray):
    """构造与负载规模联动的聚类/识别打桩。"""

    def make_cluster(
        cluster_idx: int,
        dim_name: str,
        source_points: np.ndarray,
        points_indices: np.ndarray,
    ) -> ClusterItem:
        return ClusterItem(
            cluster_idx=cluster_idx,
            dim_name=dim_name,
            points=source_points[points_indices],
            points_indices=points_indices,
            slice_idx=0,
            time_ranges=(0.0, 1.0),
        )

    cf_clusters = [
        make_cluster(
            cluster_idx=index + 1,
            dim_name="CF",
            source_points=points,
            points_indices=np.arange(
                index * config.points_per_cf_cluster,
                (index + 1) * config.points_per_cf_cluster,
            ),
        )
        for index in range(config.cf_cluster_count)
    ]

    def fake_process_dimension_clustering(
        **kwargs: Any,
    ) -> tuple[list[ClusterItem], np.ndarray]:
        dim_name = kwargs["dim_name"]
        if dim_name == "CF":
            return cf_clusters, np.array([], dtype=int)
        if dim_name == "PW":
            source_points = kwargs["points"]
            if len(source_points) == 0:
                return [], np.array([], dtype=int)
            midpoint = max(1, len(source_points) // 2)
            return (
                [
                    make_cluster(9001, "PW", source_points, np.arange(0, midpoint)),
                    make_cluster(9002, "PW", source_points, np.arange(midpoint, len(source_points))),
                ],
                np.array([], dtype=int),
            )
        if dim_name == "DOA":
            source_points = kwargs["points"]
            child_count = min(config.doa_children_per_parent, len(source_points))
            if child_count <= 0:
                return [], np.array([], dtype=int)
            split_points = np.array_split(np.arange(len(source_points)), child_count)
            return (
                [
                    make_cluster(offset + 1, "DOA", source_points, indices)
                    for offset, indices in enumerate(split_points)
                    if len(indices) > 0
                ],
                np.array([], dtype=int),
            )
        return [], np.array([], dtype=int)

    inference_service = _SlowInferenceService(config.inference_delay_ms)

    def real_recognize(
        clusters: list[ClusterItem],
        _inference_service: object,
        recognize_params: RecognitionParams,
        start_index: int,
        max_workers: int | None = None,
        write_summary_log: bool = True,
    ) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
        del _inference_service
        return recognize_clusters_parallel(
            clusters,
            inference_service,
            recognize_params,
            start_index,
            max_workers=max_workers,
            write_summary_log=write_summary_log,
        )

    return fake_process_dimension_clustering, real_recognize


@contextmanager
def _logging_mode(enabled: bool) -> Iterator[None]:
    """切换全局日志开关。

    注意: core.recognition._replay_trace_log 直接调用 logger.handle()，
    会绕过 logging.disable()，因此在关闭日志时同步打桩该回放函数。
    """
    if enabled:
        logging.disable(logging.NOTSET)
        yield
        return

    logging.disable(logging.CRITICAL)
    with patch("core.recognition._replay_trace_log", lambda _entry: None):
        yield
    logging.disable(logging.NOTSET)


def _run_identify_once(
    *,
    slice_data: Any,
    inference_service: Any,
    cluster_params: ClusteringParams,
    recognize_params: RecognitionParams,
    extract_params: ExtractParams,
    session_id: str,
    logging_enabled: bool,
    synthetic_patches: tuple[Any, Any] | None,
) -> tuple[float, int]:
    """执行一次 identify_slice 并返回耗时与日志条数。"""
    counter = _CountingHandler()
    root_logger = logging.getLogger()
    stream_handlers = [
        handler for handler in root_logger.handlers if isinstance(handler, logging.StreamHandler)
    ]
    for handler in stream_handlers:
        handler.setLevel(logging.CRITICAL + 1)
    root_logger.addHandler(counter)

    token = bind_session_log_context(session_id)
    started = time.perf_counter()
    try:
        patch_cm: Any
        if synthetic_patches is None:
            patch_cm = _logging_mode(logging_enabled)
        else:
            fake_clustering, real_recognize = synthetic_patches
            patch_cm = (
                patch("core.identify_pipeline.process_dimension_clustering", fake_clustering),
                patch("core.identify_stages.process_dimension_clustering", fake_clustering),
                patch("core.identify_stages.recognize_clusters_parallel", real_recognize),
                _logging_mode(logging_enabled),
            )

        with patch_cm:
            identify_slice(
                slice_data=slice_data,
                inference_service=inference_service,
                cluster_params=cluster_params,
                recognize_params=recognize_params,
                extract_params=extract_params,
            )
    finally:
        unbind_session_log_context(token)
        root_logger.removeHandler(counter)
        for handler in stream_handlers:
            handler.setLevel(logging.NOTSET)

    elapsed = time.perf_counter() - started
    return elapsed, counter.count


def _run_synthetic_once(
    config: ProfileConfig,
    points: np.ndarray,
    logging_enabled: bool,
) -> tuple[float, int]:
    """执行一次合成负载 identify_slice。"""
    slice_data = SimpleNamespace(index=0, data=points, time_range=(0.0, 1.0))
    synthetic_patches = _build_workload_patches(config, points)
    return _run_identify_once(
        slice_data=slice_data,
        inference_service=_SlowInferenceService(config.inference_delay_ms),
        cluster_params=ClusteringParams(
            eps_cf=1.0,
            min_pts_cf=2,
            eps_pw=1.0,
            min_pts_pw=2,
            eps_doa=16.8,
            min_pts_doa=2,
            clip_threshold_doa=80.0,
        ),
        recognize_params=RecognitionParams(),
        extract_params=ExtractParams(),
        session_id="PROFILE_SESSION",
        logging_enabled=logging_enabled,
        synthetic_patches=synthetic_patches,
    )


def _run_real_once(workload: RealWorkload, logging_enabled: bool) -> tuple[float, int]:
    """执行一次真实 session 负载 identify_slice。"""
    return _run_identify_once(
        slice_data=workload.slice_data,
        inference_service=workload.inference_service,
        cluster_params=workload.cluster_params,
        recognize_params=workload.recognize_params,
        extract_params=workload.extract_params,
        session_id=workload.session_id,
        logging_enabled=logging_enabled,
        synthetic_patches=None,
    )


def _profile_scenario_runner(
    run_once: Any,
    warmup_rounds: int,
    measure_rounds: int,
    logging_enabled: bool,
) -> ProfileResult:
    """重复测量单场景耗时。"""
    label = "logging_on" if logging_enabled else "logging_off"
    durations: list[float] = []
    last_log_count = 0

    for _ in range(warmup_rounds):
        run_once(logging_enabled)

    for _ in range(measure_rounds):
        elapsed, log_count = run_once(logging_enabled)
        durations.append(elapsed)
        last_log_count = log_count

    return ProfileResult(label=label, seconds=durations, log_records=last_log_count)


def _profile_synthetic_scenario(
    config: ProfileConfig,
    points: np.ndarray,
    logging_enabled: bool,
) -> ProfileResult:
    """重复测量合成负载单场景耗时。"""
    return _profile_scenario_runner(
        lambda enabled: _run_synthetic_once(config, points, enabled),
        config.warmup_rounds,
        config.measure_rounds,
        logging_enabled,
    )


def _profile_real_scenario(workload: RealWorkload, logging_enabled: bool) -> ProfileResult:
    """重复测量真实负载单场景耗时。"""
    return _profile_scenario_runner(
        lambda enabled: _run_real_once(workload, enabled),
        workload.warmup_rounds,
        workload.measure_rounds,
        logging_enabled,
    )


def _format_seconds(value: float) -> str:
    return f"{value * 1000:.1f} ms"


def _print_report(
    enabled: ProfileResult,
    disabled: ProfileResult,
    *,
    title: str,
    workload_lines: list[str],
    footer_lines: list[str],
) -> None:
    """打印对比结果。"""
    delta = enabled.median_s - disabled.median_s
    ratio = (delta / disabled.median_s * 100.0) if disabled.median_s > 0 else 0.0
    compute_estimate = disabled.median_s
    logging_estimate = max(delta, 0.0)

    print("=" * 72)
    print(title)
    print("=" * 72)
    for line in workload_lines:
        print(line)
    print("-" * 72)
    print(f"{'场景':<16} {'中位耗时':>12} {'均值耗时':>12} {'日志条数':>10}")
    print(
        f"{enabled.label:<16} "
        f"{_format_seconds(enabled.median_s):>12} "
        f"{_format_seconds(enabled.mean_s):>12} "
        f"{enabled.log_records:>10}"
    )
    print(
        f"{disabled.label:<16} "
        f"{_format_seconds(disabled.median_s):>12} "
        f"{_format_seconds(disabled.mean_s):>12} "
        f"{disabled.log_records:>10}"
    )
    print("-" * 72)
    print(f"日志额外耗时(中位数): {_format_seconds(logging_estimate)}")
    print(f"相对增量: {ratio:.1f}%")
    if compute_estimate > 0 and enabled.median_s > 0:
        logging_share = logging_estimate / enabled.median_s * 100.0
        print(f"日志占开启日志总耗时比例(估算): {logging_share:.1f}%")
    print("=" * 72)
    print("说明:")
    for line in footer_lines:
        print(f"  - {line}")


def _print_synthetic_report(
    config: ProfileConfig,
    enabled: ProfileResult,
    disabled: ProfileResult,
) -> None:
    _print_report(
        enabled,
        disabled,
        title="切片识别流程日志 Profiling（合成负载）",
        workload_lines=[
            (
                f"负载: CF簇={config.cf_cluster_count}, "
                f"DOA子簇/父簇={config.doa_children_per_parent}, "
                f"模拟推理延迟={config.inference_delay_ms:.1f}ms/次(predict_pa/dtoa 各一次), "
                f"轮次={config.measure_rounds}"
            )
        ],
        footer_lines=[
            "logging_on  使用项目 configure_logging() 的同步控制台+文件 Handler。",
            "logging_off 通过 logging.disable(CRITICAL) 关闭 LOGGER.info，并屏蔽 trace 回放。",
            "推理耗时由 _SlowInferenceService 模拟，聚类结果通过打桩固定，便于复现实验。",
        ],
    )


def _print_real_report(workload: RealWorkload, enabled: ProfileResult, disabled: ProfileResult) -> None:
    _print_report(
        enabled,
        disabled,
        title="切片识别流程日志 Profiling（真实 session）",
        workload_lines=[
            f"session_id: {workload.session_id}",
            f"display_name: {workload.display_name}",
            f"slice_index: {workload.slice_index}（脉冲数={workload.slice_pulse_count}）",
            f"PA模型: {workload.pa_model_path}",
            f"DTOA模型: {workload.dtoa_model_path}",
            f"轮次: warmup={workload.warmup_rounds}, measure={workload.measure_rounds}",
        ],
        footer_lines=[
            "logging_on  使用项目 configure_logging() 的同步控制台+文件 Handler。",
            "logging_off 通过 logging.disable(CRITICAL) 关闭 LOGGER.info，并屏蔽 trace 回放。",
            "使用真实 DBSCAN 聚类、真实 ONNX 推理与 session 配置快照，不经过 UI。",
        ],
    )


def _print_session_list() -> None:
    entries = _list_session_entries()
    if not entries:
        print("当前没有持久化 session。")
        return
    print("可用 session（默认 --real 取 last_opened_at 最新的一条）:")
    for entry in sorted(entries, key=lambda item: item.last_opened_at, reverse=True):
        print(
            f"  {entry.session_id}  {entry.display_name}  "
            f"last_opened={entry.last_opened_at.isoformat(sep=' ', timespec='seconds')}"
        )


@dataclass(frozen=True)
class CliArgs:
    """命令行参数。"""

    list_sessions: bool
    use_real: bool
    session_id: str | None
    slice_index: int | None
    synthetic: ProfileConfig
    real_warmup: int
    real_rounds: int


def parse_args() -> CliArgs:
    parser = argparse.ArgumentParser(description="Profile identify_slice logging overhead.")
    parser.add_argument("--real", action="store_true", help="使用本地最近 session + 真实 ONNX")
    parser.add_argument("--list-sessions", action="store_true", help="列出本地 session 后退出")
    parser.add_argument("--session-id", default=None, help="指定 session_id；默认取最近打开")
    parser.add_argument("--slice-index", type=int, default=None, help="指定切片索引；默认 0")
    parser.add_argument("--cf-clusters", type=int, default=8, help="合成负载: CF 阶段父簇数量")
    parser.add_argument("--doa-children", type=int, default=3, help="合成负载: 每个父簇拆出的 DOA 子簇数")
    parser.add_argument("--inference-ms", type=float, default=12.0, help="合成负载: 单次 predict 模拟延迟")
    parser.add_argument("--rounds", type=int, default=5, help="测量轮次")
    parser.add_argument("--warmup", type=int, default=1, help="预热轮次")
    args = parser.parse_args()
    return CliArgs(
        list_sessions=args.list_sessions,
        use_real=args.real,
        session_id=args.session_id,
        slice_index=args.slice_index,
        synthetic=ProfileConfig(
            cf_cluster_count=max(1, args.cf_clusters),
            doa_children_per_parent=max(2, args.doa_children),
            inference_delay_ms=max(0.0, args.inference_ms),
            warmup_rounds=max(0, args.warmup),
            measure_rounds=max(1, args.rounds),
        ),
        real_warmup=max(0, args.warmup),
        real_rounds=max(1, args.rounds),
    )


def main() -> int:
    args = parse_args()
    if args.list_sessions:
        _print_session_list()
        return 0

    configure_logging()

    if args.use_real:
        workload = _load_real_workload(
            session_id=args.session_id,
            slice_index=args.slice_index,
            warmup_rounds=args.real_warmup,
            measure_rounds=args.real_rounds,
        )
        enabled = _profile_real_scenario(workload, logging_enabled=True)
        disabled = _profile_real_scenario(workload, logging_enabled=False)
        _print_real_report(workload, enabled, disabled)
        return 0

    points = _make_points(args.synthetic)
    enabled = _profile_synthetic_scenario(args.synthetic, points, logging_enabled=True)
    disabled = _profile_synthetic_scenario(args.synthetic, points, logging_enabled=False)
    _print_synthetic_report(args.synthetic, enabled, disabled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
