"""基于 ONNX 的推理服务防腐层。

功能描述：
    实现 `core.clustering.InferenceService` 协议。
    封装 ONNX Runtime 模型的加载、执行，以及绘图引擎的无边框张量转换逻辑，
    避免算法核心层污染任何底层 AI 框架或 UI 画图组件依赖。
"""

import os
import logging
import time
from threading import RLock
from typing import Optional, Tuple, Any
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from core.recognition import InferenceService
from core.recognition import TraceLogEntry
from core.models.cluster_result import ClusterItem
from core.models.pulse_batch import COL_TOA, COL_PA
from core.models.recognition_result import NON_RADAR_LABEL, RECOGNITION_CLASS_COUNT
from infra.plotting.engine import rasterize_dimension
from infra.plotting.utils import _BASE_SPECS, build_dtoa_series, resolve_dtoa_spec


LOGGER = logging.getLogger(__name__)
GPU_PROVIDER_PRIORITY = (
    "CUDAExecutionProvider",
    "DmlExecutionProvider",
    "ROCMExecutionProvider",
    "CoreMLExecutionProvider",
    "TensorrtExecutionProvider",
)
_SHARED_MODEL_SESSION_CACHE: dict[
    tuple[str, tuple[str, ...], int | None],
    Any,
] = {}
_SHARED_MODEL_SESSION_CACHE_LOCK = RLock()


def clear_shared_model_session_cache() -> None:
    """清空交互式预热使用的底层 ONNX 模型 Session 缓存。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    with _SHARED_MODEL_SESSION_CACHE_LOCK:
        _SHARED_MODEL_SESSION_CACHE.clear()


def _emit_or_collect_message(
    message: str,
    *args,
    logger_name: str,
    pathname: str,
    func_name: str,
    write_log: bool,
    trace_messages: list[TraceLogEntry] | None,
) -> None:
    """输出或收集预测日志。"""
    rendered_message = message % args if args else message
    if write_log:
        LOGGER.debug(rendered_message)
        return
    if trace_messages is not None:
        trace_messages.append(
            TraceLogEntry(
                logger_name=logger_name,
                pathname=pathname,
                func_name=func_name,
                message=rendered_message,
            )
        )


class OnnxInferenceService(InferenceService):
    """基于 ONNX Runtime 的推理服务实现。"""

    def __init__(
        self,
        dtoa_model_path: str,
        pa_model_path: str,
        temp_dir: str,
        device_preference: str = "CPU",
        intra_op_num_threads: int | None = None,
        reuse_model_sessions: bool = False,
    ) -> None:
        """初始化 ONNX 推理服务。

        Args:
            dtoa_model_path: DTOA 模型的文件绝对路径。
            pa_model_path: PA 模型的文件绝对路径。
            temp_dir: 用于存放临时中间图片的目录（如果使用文件系统转换）。
            device_preference: 推理设备偏好，取值为 AUTO、CPU 或 GPU。
            intra_op_num_threads: 单次 ONNX 算子内部线程数；为 None 时使用运行时默认值。
            reuse_model_sessions: 是否按模型路径复用底层 ONNX Session，交互式预热场景使用。

        Raises:
            ValueError: 推理设备偏好不受支持或线程数小于 1 时抛出。
        """
        LOGGER.debug("正在初始化 ONNX 推理服务: PA=%s, DTOA=%s", pa_model_path, dtoa_model_path)
        self._dtoa_model_path = dtoa_model_path
        self._pa_model_path = pa_model_path
        self._temp_dir = temp_dir
        self._device_preference = device_preference.upper()
        if self._device_preference not in {"AUTO", "CPU", "GPU"}:
            raise ValueError(
                f"不支持的 ONNX 推理设备偏好: {device_preference}"
            )
        if intra_op_num_threads is not None and intra_op_num_threads < 1:
            raise ValueError("ONNX 内部线程数必须大于 0")
        self._intra_op_num_threads = intra_op_num_threads
        self._reuse_model_sessions = reuse_model_sessions

        # 预测阈值（旧版保留，当前不参与标签判定，供后续扩展使用）
        self.th_pa = 0.9
        self.th_dtoa = 0.91

        self._dtoa_model: Optional[Any] = None
        self._pa_model: Optional[Any] = None

        if ort is None:
            LOGGER.warning("未检测到 onnxruntime，推理功能将不可用！")

        self._providers = self._resolve_execution_providers()
        self._session_options = self._build_session_options()
        os.makedirs(self._temp_dir, exist_ok=True)
        self._load_models()

    def _build_session_options(self) -> Any | None:
        """按线程限制构造 ONNX Runtime Session 配置。"""
        if ort is None:
            return None
        uses_directml = (
            bool(self._providers)
            and self._providers[0] == "DmlExecutionProvider"
        )
        if self._intra_op_num_threads is None and not uses_directml:
            return None
        options = ort.SessionOptions()
        if self._intra_op_num_threads is not None:
            options.intra_op_num_threads = self._intra_op_num_threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        if uses_directml:
            # DirectML 要求禁用内存模式并采用顺序执行。
            options.enable_mem_pattern = False
        return options

    def _resolve_execution_providers(self) -> list[str]:
        """根据设备偏好选择当前环境实际可用的执行 Provider。"""
        if ort is None:
            return []
        available = set(ort.get_available_providers())
        if self._device_preference == "CPU":
            return ["CPUExecutionProvider"]

        gpu_provider = next(
            (
                provider
                for provider in GPU_PROVIDER_PRIORITY
                if provider in available
            ),
            None,
        )
        if gpu_provider is not None:
            providers = [gpu_provider]
            if "CPUExecutionProvider" in available:
                providers.append("CPUExecutionProvider")
            LOGGER.info(
                "全速推理将优先使用 GPU Provider: %s",
                gpu_provider,
            )
            return providers

        if self._device_preference == "GPU":
            LOGGER.warning(
                "未检测到可用 GPU Provider，全速推理回退到 CPU"
            )
        else:
            LOGGER.info("未检测到可用 GPU Provider，自动使用 CPU")
        return ["CPUExecutionProvider"]

    def _create_session(self, model_path: str, model_name: str) -> Any:
        """创建模型 Session，并在 GPU 初始化失败时回退到 CPU。"""
        if not self._reuse_model_sessions:
            return self._create_uncached_session(model_path, model_name)

        cache_key = (
            os.path.normcase(os.path.abspath(model_path)),
            tuple(self._providers),
            self._intra_op_num_threads,
        )
        with _SHARED_MODEL_SESSION_CACHE_LOCK:
            cached_session = _SHARED_MODEL_SESSION_CACHE.get(cache_key)
            if cached_session is not None:
                LOGGER.debug("复用已预热的 %s 模型 Session: %s", model_name, model_path)
                return cached_session
            session = self._create_uncached_session(model_path, model_name)
            _SHARED_MODEL_SESSION_CACHE[cache_key] = session
            return session

    def _create_uncached_session(self, model_path: str, model_name: str) -> Any:
        """创建不经过共享缓存的底层 ONNX Session。"""
        try:
            session = ort.InferenceSession(
                model_path,
                sess_options=self._session_options,
                providers=self._providers,
            )
        except Exception:
            if self._providers == ["CPUExecutionProvider"]:
                raise
            LOGGER.warning(
                "%s 模型 GPU Provider 初始化失败，正在回退 CPU",
                model_name,
                exc_info=True,
            )
            session = ort.InferenceSession(
                model_path,
                sess_options=self._session_options,
                providers=["CPUExecutionProvider"],
            )
        LOGGER.info(
            "%s 模型加载成功: %s, providers=%s",
            model_name,
            model_path,
            session.get_providers(),
        )
        return session

    def _load_models(self) -> None:
        """加载 PA 和 DTOA 的 ONNX 模型。"""
        if ort is None:
            return

        # 加载 DTOA
        if os.path.exists(self._dtoa_model_path):
            try:
                self._dtoa_model = self._create_session(
                    self._dtoa_model_path,
                    "DTOA",
                )
            except Exception as e:
                LOGGER.error(f"DTOA 模型加载失败: {e}")
        else:
            LOGGER.error(f"找不到 DTOA 模型文件: {self._dtoa_model_path}")

        # 加载 PA
        if os.path.exists(self._pa_model_path):
            try:
                self._pa_model = self._create_session(
                    self._pa_model_path,
                    "PA",
                )
            except Exception as e:
                LOGGER.error(f"PA 模型加载失败: {e}")
        else:
            LOGGER.error(f"找不到 PA 模型文件: {self._pa_model_path}")

    def predict_pa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """预测 PA 特征。
        
        Args:
            cluster: 待预测的簇对象。
            write_log: 是否立即输出预测日志。
            trace_messages: 静默模式下用于收集日志消息的列表。
            
        Returns:
            (类别标签, 置信度, 各类别置信度字典)
        """
        if self._pa_model is None:
            LOGGER.debug("PA 模型未加载，跳过预测")
            return -1, 0.0, {}

        try:
            # 1. 从 cluster 中提取 TOA 和 PA 序列
            points = cluster.points
            toa = points[:, COL_TOA]
            pa = points[:, COL_PA]
            slice_start, slice_end = cluster.time_ranges

            # 2. 使用绘图引擎栅格化为二值图像
            spec = _BASE_SPECS["PA"]
            raw_img = rasterize_dimension(toa, pa, spec, (slice_start, slice_end))
            img_tensor = np.expand_dims(
                raw_img.astype(np.float32) / 255.0, axis=(0, 1)
            )

            # 3. ONNX 推理
            input_name = self._pa_model.get_inputs()[0].name
            t0 = time.perf_counter()
            raw_output = self._pa_model.run(None, {input_name: img_tensor})[0]
            t1 = time.perf_counter()

            _emit_or_collect_message(
                "PA ONNX 原始输出 (logits): [%s]",
                ", ".join(f"{v:.4f}" for v in raw_output[0]),
                logger_name=LOGGER.name,
                pathname=__file__,
                func_name="predict_pa",
                write_log=write_log,
                trace_messages=trace_messages,
            )

            # 4. Softmax 与后处理
            pred = np.exp(raw_output) / np.sum(np.exp(raw_output), axis=1, keepdims=True)

            _emit_or_collect_message(
                "PA Softmax 概率: [%s]",
                ", ".join(f"{p:.4f}" for p in pred[0]),
                logger_name=LOGGER.name,
                pathname=__file__,
                func_name="predict_pa",
                write_log=write_log,
                trace_messages=trace_messages,
            )

            # 将扩展负样本类别统一合并到非雷达标签。
            if pred.shape[1] > RECOGNITION_CLASS_COUNT:
                pred[0, NON_RADAR_LABEL] = np.sum(
                    pred[0, NON_RADAR_LABEL:]
                )
                pred[0, RECOGNITION_CLASS_COUNT:] = 0

            label = int(np.argmax(pred[0, :RECOGNITION_CLASS_COUNT]))
            conf = float(pred[0, label])

            # 特殊组合概率处理 (复用旧版逻辑)
            if label >= NON_RADAR_LABEL:
                prob_comb_0_1 = pred[0, 0] + pred[0, 1]
                prob_comb_0_4 = pred[0, 0] + pred[0, 4]

                if prob_comb_0_1 > conf and prob_comb_0_1 >= prob_comb_0_4:
                    label = 0 if pred[0, 0] >= pred[0, 1] else 1
                    conf = float(prob_comb_0_1)
                elif prob_comb_0_4 > conf:
                    label = 0 if pred[0, 0] >= pred[0, 4] else 4
                    conf = float(prob_comb_0_4)

            conf_dict = {i: float(c) for i, c in enumerate(pred[0, :6]) if np.round(c, 4) > 0}

            _emit_or_collect_message(
                "PA 预测完成: label=%d, conf=%.4f, 各类别概率=%s, 耗时=%.1fms",
                label,
                conf,
                ", ".join(f"{k}={v:.4f}" for k, v in sorted(conf_dict.items())),
                (t1 - t0) * 1000,
                logger_name=LOGGER.name,
                pathname=__file__,
                func_name="predict_pa",
                write_log=write_log,
                trace_messages=trace_messages,
            )
            return label, conf, conf_dict

        except Exception as e:
            LOGGER.error(f"PA 预测异常: {e}", exc_info=True)
            return -1, 0.0, {}

    def predict_dtoa(
        self,
        cluster: ClusterItem,
        write_log: bool = True,
        trace_messages: list[TraceLogEntry] | None = None,
    ) -> tuple[int, float, dict[int, float]]:
        """预测 DTOA 特征。

        Args:
            cluster: 待预测的簇对象。
            write_log: 是否立即输出预测日志。
            trace_messages: 静默模式下用于收集日志消息的列表。

        Returns:
            tuple[int, float, dict[int, float]]: 预测标签、置信度与置信度字典。

        Raises:
            无显式抛出异常。
        """
        if self._dtoa_model is None:
            LOGGER.debug("DTOA 模型未加载，跳过预测")
            return -1, 0.0, {}

        try:
            points = cluster.points
            toa = points[:, COL_TOA]
            slice_start, slice_end = cluster.time_ranges

            # 使用绘图模块已有方法计算 DTOA 并解析规格
            dtoa = build_dtoa_series(toa)
            spec = resolve_dtoa_spec(_BASE_SPECS["DTOA"], dtoa)

            # 使用绘图引擎栅格化为二值图像
            raw_img = rasterize_dimension(toa, dtoa, spec, (slice_start, slice_end))
            img_tensor = np.expand_dims(
                raw_img.astype(np.float32) / 255.0, axis=(0, 1)
            )

            # ONNX 推理
            input_name = self._dtoa_model.get_inputs()[0].name
            t0 = time.perf_counter()
            raw_output = self._dtoa_model.run(None, {input_name: img_tensor})[0]
            t1 = time.perf_counter()

            _emit_or_collect_message(
                "DTOA ONNX 原始输出 (logits): [%s]",
                ", ".join(f"{v:.4f}" for v in raw_output[0]),
                logger_name=LOGGER.name,
                pathname=__file__,
                func_name="predict_dtoa",
                write_log=write_log,
                trace_messages=trace_messages,
            )

            # Softmax 与后处理
            pred = np.exp(raw_output) / np.sum(np.exp(raw_output), axis=1, keepdims=True)

            _emit_or_collect_message(
                "DTOA Softmax 概率: [%s]",
                ", ".join(f"{p:.4f}" for p in pred[0]),
                logger_name=LOGGER.name,
                pathname=__file__,
                func_name="predict_dtoa",
                write_log=write_log,
                trace_messages=trace_messages,
            )

            if pred.shape[1] > RECOGNITION_CLASS_COUNT:
                pred[0, 0] = pred[0, 0] + pred[0, 1]
                pred[0, 1] = pred[0, 2]
                pred[0, 2] = pred[0, 3] + pred[0, 4]
                pred[0, 3] = pred[0, 5]
                pred[0, 4] = pred[0, 6]
                pred[0, NON_RADAR_LABEL] = np.sum(pred[0, 7:])
                pred[0, RECOGNITION_CLASS_COUNT:] = 0

            label = int(np.argmax(pred[0, :RECOGNITION_CLASS_COUNT]))
            conf = float(pred[0, label])

            conf_dict = {i: float(c) for i, c in enumerate(pred[0, :6]) if np.round(c, 4) > 0}

            _emit_or_collect_message(
                "DTOA 预测完成: label=%d, conf=%.4f, 各类别概率=%s, 耗时=%.1fms",
                label,
                conf,
                ", ".join(f"{k}={v:.4f}" for k, v in sorted(conf_dict.items())),
                (t1 - t0) * 1000,
                logger_name=LOGGER.name,
                pathname=__file__,
                func_name="predict_dtoa",
                write_log=write_log,
                trace_messages=trace_messages,
            )
            return label, conf, conf_dict

        except Exception as e:
            LOGGER.error(f"DTOA 预测异常: {e}", exc_info=True)
            return -1, 0.0, {}
