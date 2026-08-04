"""ONNX 单模型 Runtime Session 加载、真实预热与后台复用池。

该模块只管理单个模型文件对应的 ONNX Runtime Session，不感知 PA 与 DTOA
如何组合为一次识别任务。每个模型在加载后立即执行一次与真实推理输入形状
一致的 dummy inference，确保图优化、Provider 初始化和首轮内核执行均在预热
阶段完成。
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import logging
import os
from pathlib import Path
from threading import RLock
import time
from typing import Any

import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from infra.plotting.utils import _BASE_SPECS


LOGGER = logging.getLogger(__name__)
SUPPORTED_MODEL_TYPES = ("PA", "DTOA")
GPU_PROVIDER_PRIORITY = (
    "CUDAExecutionProvider",
    "DmlExecutionProvider",
    "ROCMExecutionProvider",
    "CoreMLExecutionProvider",
    "TensorrtExecutionProvider",
)


@dataclass(frozen=True, slots=True)
class OnnxModelRuntime:
    """保存一个已加载并完成真实预热的单模型运行时。

    Attributes:
        model_type: 模型类型，取值为 PA 或 DTOA。
        model_path: 模型文件的规范化绝对路径。
        session: 已完成 dummy inference 的 ONNX Runtime Session。
        input_name: 模型唯一输入节点名称。
        input_shape: 与真实识别一致的输入张量形状。
        providers: Session 最终实际使用的 Provider 顺序。
    """

    model_type: str
    model_path: str
    session: Any
    input_name: str
    input_shape: tuple[int, int, int, int]
    providers: tuple[str, ...]


def _normalize_model_type(model_type: str) -> str:
    """规范化模型类型并拒绝未知类型。"""
    normalized_type = model_type.upper()
    if normalized_type not in SUPPORTED_MODEL_TYPES:
        raise ValueError(f"不支持的模型类型: {model_type}")
    return normalized_type


def _expected_input_shape(model_type: str) -> tuple[int, int, int, int]:
    """返回与真实绘图推理链路一致的输入张量形状。"""
    normalized_type = _normalize_model_type(model_type)
    spec = _BASE_SPECS[normalized_type]
    return (1, 1, spec.img_height, spec.img_width)


def resolve_execution_providers(device_preference: str) -> list[str]:
    """根据设备偏好解析当前环境实际可用的 Provider 顺序。

    Args:
        device_preference [str]: AUTO、CPU 或 GPU。

    Returns:
        list[str]: 传给 ONNX Runtime 的 Provider 优先级列表。

    Raises:
        RuntimeError: 当前环境没有安装 onnxruntime 时抛出。
        ValueError: 设备偏好不受支持时抛出。
    """
    normalized_preference = device_preference.upper()
    if normalized_preference not in {"AUTO", "CPU", "GPU"}:
        raise ValueError(f"不支持的 ONNX 推理设备偏好: {device_preference}")
    if ort is None:
        raise RuntimeError("未检测到 onnxruntime，推理功能不可用")

    available = set(ort.get_available_providers())
    if normalized_preference == "CPU":
        return ["CPUExecutionProvider"]

    gpu_provider = next(
        (provider for provider in GPU_PROVIDER_PRIORITY if provider in available),
        None,
    )
    if gpu_provider is not None:
        providers = [gpu_provider]
        if "CPUExecutionProvider" in available:
            providers.append("CPUExecutionProvider")
        LOGGER.info("推理将优先使用 GPU Provider: %s", gpu_provider)
        return providers

    if normalized_preference == "GPU":
        LOGGER.warning("未检测到可用 GPU Provider，推理回退到 CPU")
    else:
        LOGGER.info("未检测到可用 GPU Provider，自动使用 CPU")
    return ["CPUExecutionProvider"]


def build_session_options(
    providers: list[str],
    intra_op_num_threads: int | None,
) -> Any | None:
    """按 Provider 与线程限制构造 ONNX Runtime Session 配置。

    Args:
        providers [list[str]]: 目标 Provider 顺序。
        intra_op_num_threads [int | None]: 单次算子内部线程数。

    Returns:
        Any | None: ONNX Runtime SessionOptions；无需定制时返回 None。

    Raises:
        RuntimeError: 当前环境没有安装 onnxruntime 时抛出。
        ValueError: 线程数小于 1 时抛出。
    """
    if ort is None:
        raise RuntimeError("未检测到 onnxruntime，推理功能不可用")
    if intra_op_num_threads is not None and intra_op_num_threads < 1:
        raise ValueError("ONNX 内部线程数必须大于 0")

    uses_directml = bool(providers) and providers[0] == "DmlExecutionProvider"
    if intra_op_num_threads is None and not uses_directml:
        return None

    options = ort.SessionOptions()
    if intra_op_num_threads is not None:
        options.intra_op_num_threads = intra_op_num_threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    if uses_directml:
        # DirectML 要求禁用内存模式并采用顺序执行。
        options.enable_mem_pattern = False
    return options


def _create_session(
    model_path: str,
    model_type: str,
    providers: list[str],
    session_options: Any | None,
) -> Any:
    """创建底层 Session，并在 GPU 初始化失败时回退到 CPU。"""
    try:
        return ort.InferenceSession(
            model_path,
            sess_options=session_options,
            providers=providers,
        )
    except Exception:
        if providers == ["CPUExecutionProvider"]:
            raise
        LOGGER.warning(
            "%s 模型 GPU Provider 初始化失败，正在回退 CPU",
            model_type,
            exc_info=True,
        )
        return ort.InferenceSession(
            model_path,
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )


def _build_dummy_input(
    session: Any,
    model_type: str,
) -> tuple[str, np.ndarray, tuple[int, int, int, int]]:
    """校验输入契约并构造与真实推理一致的零值张量。"""
    input_name, expected_shape = _validate_session_input(
        session,
        model_type,
    )
    return (
        input_name,
        np.zeros(expected_shape, dtype=np.float32),
        expected_shape,
    )


def _validate_session_input(
    session: Any,
    model_type: str,
) -> tuple[str, tuple[int, int, int, int]]:
    """校验 Session 输入节点是否符合指定 PA/DTOA 生产契约。"""
    normalized_type = _normalize_model_type(model_type)
    inputs = session.get_inputs()
    if len(inputs) != 1:
        raise ValueError(f"{normalized_type} 模型必须只有一个输入节点")

    input_meta = inputs[0]
    if input_meta.type != "tensor(float)":
        raise ValueError(
            f"{normalized_type} 模型输入类型必须为 tensor(float)，"
            f"实际为 {input_meta.type}"
        )
    expected_shape = _expected_input_shape(normalized_type)
    actual_shape = tuple(input_meta.shape)
    if len(actual_shape) != len(expected_shape):
        raise ValueError(
            f"{normalized_type} 模型输入维度必须为 4，实际为 {actual_shape}"
        )
    for actual, expected in zip(actual_shape, expected_shape):
        if isinstance(actual, int) and actual > 0 and actual != expected:
            other_type = "DTOA" if normalized_type == "PA" else "PA"
            other_shape = _expected_input_shape(other_type)
            if actual_shape == other_shape:
                raise ValueError(
                    f"模型输入形状为 {actual_shape}，符合 {other_type} 模型，"
                    f"但当前选择的是 {normalized_type} 模型；请检查模型类型是否选错"
                )
            raise ValueError(
                f"{normalized_type} 模型输入形状必须兼容 {expected_shape}，"
                f"实际为 {actual_shape}"
            )
    return input_meta.name, expected_shape


def validate_onnx_model_contract(
    model_type: str,
    model_path: str,
) -> tuple[int, int, int, int]:
    """在不执行推理的情况下校验待导入 ONNX 模型输入契约。

    Args:
        model_type [str]: 用户选择的模型类型，取值为 PA 或 DTOA。
        model_path [str]: 待导入 ONNX 模型文件路径。

    Returns:
        tuple[int, int, int, int]: 校验通过后的生产输入张量形状。

    Raises:
        FileNotFoundError: 模型文件不存在时抛出。
        RuntimeError: 当前环境没有安装 onnxruntime 时抛出。
        ValueError: 文件格式、模型类型或输入契约不合法时抛出。
    """
    normalized_type = _normalize_model_type(model_type)
    normalized_path = os.path.normcase(os.path.abspath(model_path))
    if not os.path.isfile(normalized_path):
        raise FileNotFoundError(f"找不到待导入模型文件: {model_path}")
    if Path(normalized_path).suffix.lower() != ".onnx":
        raise ValueError("当前 PA/DTOA 推理服务仅支持导入 .onnx 模型")
    if ort is None:
        raise RuntimeError("未检测到 onnxruntime，无法校验模型")

    try:
        # 只读取模型和输入元数据，不执行 run，避免在 UI 导入阶段做重复预热。
        session = ort.InferenceSession(
            normalized_path,
            providers=["CPUExecutionProvider"],
        )
    except Exception as error:
        raise ValueError(
            f"无法读取 ONNX 模型，请确认文件完整且格式正确：{error}"
        ) from error

    _, input_shape = _validate_session_input(session, normalized_type)
    return input_shape


def load_onnx_model_runtime(
    model_type: str,
    model_path: str,
    *,
    device_preference: str = "CPU",
    intra_op_num_threads: int | None = None,
) -> OnnxModelRuntime:
    """加载单个模型并执行一次真实 ONNX dummy inference。

    Args:
        model_type [str]: PA 或 DTOA。
        model_path [str]: 模型文件路径。
        device_preference [str]: AUTO、CPU 或 GPU，默认 CPU。
        intra_op_num_threads [int | None]: ONNX 算子内部线程数。

    Returns:
        OnnxModelRuntime: 已完成 Session 创建和首次 `run()` 的模型运行时。

    Raises:
        FileNotFoundError: 模型文件不存在时抛出。
        RuntimeError: 未安装 onnxruntime 时抛出。
        ValueError: 模型类型、设备、线程或输入契约不合法时抛出。
        Exception: ONNX Runtime 创建 Session 或执行 dummy inference 失败时透传。
    """
    normalized_type = _normalize_model_type(model_type)
    normalized_path = os.path.normcase(os.path.abspath(model_path))
    if not os.path.isfile(normalized_path):
        raise FileNotFoundError(f"找不到 {normalized_type} 模型文件: {model_path}")

    providers = resolve_execution_providers(device_preference)
    session_options = build_session_options(providers, intra_op_num_threads)
    started_at = time.perf_counter()
    session = _create_session(
        normalized_path,
        normalized_type,
        providers,
        session_options,
    )
    input_name, dummy_input, input_shape = _build_dummy_input(
        session,
        normalized_type,
    )
    # 真实执行一次 run，消除图优化、Provider 和首轮内核冷启动延迟。
    session.run(None, {input_name: dummy_input})
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    actual_providers = tuple(session.get_providers())
    LOGGER.info(
        "%s 模型加载并预热完成: path=%s, shape=%s, providers=%s, elapsed=%.1fms",
        normalized_type,
        normalized_path,
        input_shape,
        actual_providers,
        elapsed_ms,
    )
    return OnnxModelRuntime(
        model_type=normalized_type,
        model_path=normalized_path,
        session=session,
        input_name=input_name,
        input_shape=input_shape,
        providers=actual_providers,
    )


class OnnxModelRuntimePool:
    """后台加载并复用单模型 ONNX Runtime Session。

    同一模型类型和规范化路径只会创建一个 Future。识别任务、启动预热和模型
    启用事件共享该 Future，因此并发请求不会重复加载或重复执行 dummy inference。

    Attributes:
        device_preference: 该池使用的设备偏好。
        intra_op_num_threads: 该池使用的 ONNX 内部线程限制。
    """

    def __init__(
        self,
        *,
        device_preference: str = "CPU",
        intra_op_num_threads: int | None = None,
        max_workers: int = 1,
    ) -> None:
        """初始化后台单模型加载池。

        Args:
            device_preference [str]: AUTO、CPU 或 GPU。
            intra_op_num_threads [int | None]: ONNX 算子内部线程数。
            max_workers [int]: 后台并行加载数，默认 1 以保持分级顺序。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 设备偏好、线程数或后台线程数不合法时抛出。
        """
        normalized_preference = device_preference.upper()
        if normalized_preference not in {"AUTO", "CPU", "GPU"}:
            raise ValueError(f"不支持的 ONNX 推理设备偏好: {device_preference}")
        if intra_op_num_threads is not None and intra_op_num_threads < 1:
            raise ValueError("ONNX 内部线程数必须大于 0")
        if max_workers < 1:
            raise ValueError("模型预热线程数必须大于 0")

        self.device_preference = normalized_preference
        self.intra_op_num_threads = intra_op_num_threads
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="onnx-model-preload",
        )
        self._futures: dict[tuple[str, str], Future[OnnxModelRuntime]] = {}
        self._evict_when_done: set[tuple[str, str]] = set()
        self._lock = RLock()
        self._closed = False

    def preload(self, model_type: str, model_path: str) -> Future[OnnxModelRuntime]:
        """提交单模型后台预热并复用同键的现有任务。

        Args:
            model_type [str]: PA 或 DTOA。
            model_path [str]: 模型文件路径。

        Returns:
            Future[OnnxModelRuntime]: 可由识别线程等待的共享加载任务。

        Raises:
            RuntimeError: 运行池已关闭时抛出。
            ValueError: 模型类型不受支持时抛出。
        """
        normalized_type = _normalize_model_type(model_type)
        normalized_path = os.path.normcase(os.path.abspath(model_path))
        key = (normalized_type, normalized_path)
        with self._lock:
            if self._closed:
                raise RuntimeError("ONNX 模型运行池已关闭")
            existing = self._futures.get(key)
            if existing is not None:
                self._evict_when_done.discard(key)
                return existing
            future = self._executor.submit(
                load_onnx_model_runtime,
                normalized_type,
                normalized_path,
                device_preference=self.device_preference,
                intra_op_num_threads=self.intra_op_num_threads,
            )
            self._futures[key] = future
            future.add_done_callback(
                lambda completed, completed_key=key: self._on_future_done(
                    completed_key,
                    completed,
                )
            )
            return future

    def is_ready(self, model_type: str, model_path: str) -> bool:
        """返回指定模型是否已成功完成真实预热。

        Args:
            model_type [str]: PA 或 DTOA。
            model_path [str]: 模型文件路径。

        Returns:
            bool: Future 已成功完成时返回 True。
        """
        key = (
            _normalize_model_type(model_type),
            os.path.normcase(os.path.abspath(model_path)),
        )
        with self._lock:
            future = self._futures.get(key)
        return (
            future is not None
            and future.done()
            and not future.cancelled()
            and future.exception() is None
        )

    def retain_enabled(self, model_type: str, model_paths: list[str]) -> None:
        """仅保留指定类型仍启用的缓存，并安全处理正在加载的任务。

        Args:
            model_type [str]: PA 或 DTOA。
            model_paths [list[str]]: 当前仍启用的模型路径。

        Returns:
            None: 无返回值。
        """
        normalized_type = _normalize_model_type(model_type)
        retained_paths = {
            os.path.normcase(os.path.abspath(path)) for path in model_paths
        }
        with self._lock:
            for key, future in list(self._futures.items()):
                if key[0] != normalized_type or key[1] in retained_paths:
                    continue
                if future.cancel() or future.done():
                    self._futures.pop(key, None)
                else:
                    # 正在执行的任务无法取消，完成后再从池索引移除。
                    self._evict_when_done.add(key)

    def shutdown(self, *, wait: bool = True) -> None:
        """停止接收新任务并关闭后台执行器。

        Args:
            wait [bool]: 是否等待正在执行的预热任务结束，默认 True。

        Returns:
            None: 无返回值。
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _on_future_done(
        self,
        key: tuple[str, str],
        future: Future[OnnxModelRuntime],
    ) -> None:
        """记录后台任务结果并完成延迟淘汰。"""
        if not future.cancelled():
            try:
                future.result()
            except Exception:
                LOGGER.error(
                    "模型后台预热失败: type=%s, path=%s",
                    key[0],
                    key[1],
                    exc_info=True,
                )
        with self._lock:
            if key in self._evict_when_done:
                self._evict_when_done.discard(key)
                self._futures.pop(key, None)
