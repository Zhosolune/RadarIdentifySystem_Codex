"""基于 ONNX 的推理服务防腐层。

功能描述：
    实现 `core.clustering.InferenceService` 协议。
    封装 ONNX Runtime 模型的加载、执行，以及绘图引擎的无边框张量转换逻辑，
    避免算法核心层污染任何底层 AI 框架或 UI 画图组件依赖。
"""

import os
import logging
import time
from concurrent.futures import Future
from typing import Optional, Any
import numpy as np

from core.recognition import InferenceService
from core.recognition import TraceLogEntry
from core.models.cluster_result import ClusterItem
from core.models.pulse_batch import COL_TOA, COL_PA
from core.models.recognition_result import NON_RADAR_LABEL, RECOGNITION_CLASS_COUNT
from infra.plotting.engine import rasterize_dimension
from infra.plotting.utils import _BASE_SPECS, build_dtoa_series, resolve_dtoa_spec
from infra.onnx_runtime_pool import (
    OnnxModelRuntime,
    OnnxModelRuntimePool,
    load_onnx_model_runtime,
)


LOGGER = logging.getLogger(__name__)


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
        runtime_pool: OnnxModelRuntimePool | None = None,
    ) -> None:
        """初始化 ONNX 推理服务。

        Args:
            dtoa_model_path: DTOA 模型的文件绝对路径。
            pa_model_path: PA 模型的文件绝对路径。
            temp_dir: 用于存放临时中间图片的目录（如果使用文件系统转换）。
            device_preference: 推理设备偏好，取值为 AUTO、CPU 或 GPU。
            intra_op_num_threads: 单次 ONNX 算子内部线程数；为 None 时使用运行时默认值。
            runtime_pool: 交互式后台单模型运行池；未传入时同步加载并真实预热。

        Raises:
            ValueError: 推理设备偏好不受支持或线程数小于 1 时抛出。
        """
        LOGGER.debug("正在初始化 ONNX 推理服务: PA=%s, DTOA=%s", pa_model_path, dtoa_model_path)
        self._dtoa_model_path = dtoa_model_path
        self._pa_model_path = pa_model_path
        self._temp_dir = temp_dir
        self._device_preference = device_preference.upper()
        if self._device_preference not in {"AUTO", "CPU", "GPU"}:
            raise ValueError(f"不支持的 ONNX 推理设备偏好: {device_preference}")
        if intra_op_num_threads is not None and intra_op_num_threads < 1:
            raise ValueError("ONNX 内部线程数必须大于 0")
        self._intra_op_num_threads = intra_op_num_threads
        self._runtime_pool = runtime_pool

        # 预测阈值（旧版保留，当前不参与标签判定，供后续扩展使用）
        self.th_pa = 0.9
        self.th_dtoa = 0.91

        self._dtoa_model: Optional[Any] = None
        self._pa_model: Optional[Any] = None
        self._dtoa_runtime_future: Future[OnnxModelRuntime] | None = None
        self._pa_runtime_future: Future[OnnxModelRuntime] | None = None
        os.makedirs(self._temp_dir, exist_ok=True)
        self._load_models()

    def _load_models(self) -> None:
        """加载模型，或绑定后台运行池中的共享加载任务。"""
        model_specs = (
            ("DTOA", self._dtoa_model_path),
            ("PA", self._pa_model_path),
        )
        for model_type, model_path in model_specs:
            if not os.path.isfile(model_path):
                LOGGER.error("找不到 %s 模型文件: %s", model_type, model_path)
                continue
            try:
                if self._runtime_pool is not None:
                    # 仅保存共享 Future，不在创建轻量组合服务时阻塞 UI 线程。
                    future = self._runtime_pool.preload(model_type, model_path)
                    if model_type == "PA":
                        self._pa_runtime_future = future
                    else:
                        self._dtoa_runtime_future = future
                    continue

                # 全速任务未使用共享池，在线程内同步完成加载与真实预热。
                runtime = load_onnx_model_runtime(
                    model_type,
                    model_path,
                    device_preference=self._device_preference,
                    intra_op_num_threads=self._intra_op_num_threads,
                )
                if model_type == "PA":
                    self._pa_model = runtime.session
                else:
                    self._dtoa_model = runtime.session
            except Exception as error:
                LOGGER.error(
                    "%s 模型加载失败: %s",
                    model_type,
                    error,
                    exc_info=True,
                )

    def _resolve_model_session(self, model_type: str) -> Any | None:
        """解析已预热 Session，必要时在当前识别线程等待共享 Future。"""
        if model_type == "PA":
            if self._pa_model is not None:
                return self._pa_model
            future = self._pa_runtime_future
        else:
            if self._dtoa_model is not None:
                return self._dtoa_model
            future = self._dtoa_runtime_future

        if future is None:
            return None
        try:
            # 等待只发生在识别工作线程；Future 内已经执行过真实 dummy inference。
            runtime = future.result()
        except Exception as error:
            LOGGER.error(
                "%s 模型后台预热失败，无法执行预测: %s",
                model_type,
                error,
                exc_info=True,
            )
            return None

        if model_type == "PA":
            self._pa_model = runtime.session
        else:
            self._dtoa_model = runtime.session
        return runtime.session

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
        pa_model = self._resolve_model_session("PA")
        if pa_model is None:
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
            input_name = pa_model.get_inputs()[0].name
            t0 = time.perf_counter()
            raw_output = pa_model.run(None, {input_name: img_tensor})[0]
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
        dtoa_model = self._resolve_model_session("DTOA")
        if dtoa_model is None:
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
            input_name = dtoa_model.get_inputs()[0].name
            t0 = time.perf_counter()
            raw_output = dtoa_model.run(None, {input_name: img_tensor})[0]
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
