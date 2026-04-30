"""基于 ONNX 的推理服务防腐层。

功能描述：
    实现 `core.clustering.InferenceService` 协议。
    封装 ONNX Runtime 模型的加载、执行，以及绘图引擎的无边框张量转换逻辑，
    避免算法核心层污染任何底层 AI 框架或 UI 画图组件依赖。
"""

import os
import logging
import time
from typing import Optional, Tuple, Any
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from core.recognition import InferenceService
from core.models.cluster_result import ClusterItem
from core.models.pulse_batch import COL_TOA, COL_PA
from infra.plotting.engine import rasterize_dimension
from infra.plotting.utils import _BASE_SPECS, build_dtoa_series, resolve_dtoa_spec


LOGGER = logging.getLogger(__name__)


class OnnxInferenceService(InferenceService):
    """基于 ONNX Runtime 的推理服务实现。"""

    def __init__(self, dtoa_model_path: str, pa_model_path: str, temp_dir: str):
        """初始化 ONNX 推理服务。

        Args:
            dtoa_model_path: DTOA 模型的文件绝对路径。
            pa_model_path: PA 模型的文件绝对路径。
            temp_dir: 用于存放临时中间图片的目录（如果使用文件系统转换）。
        """
        LOGGER.info("正在初始化 ONNX 推理服务: PA=%s, DTOA=%s", pa_model_path, dtoa_model_path)
        self._dtoa_model_path = dtoa_model_path
        self._pa_model_path = pa_model_path
        self._temp_dir = temp_dir

        # 预测阈值（旧版保留，当前不参与标签判定，供后续扩展使用）
        self.th_pa = 0.9
        self.th_dtoa = 0.91

        self._dtoa_model: Optional[Any] = None
        self._pa_model: Optional[Any] = None

        if ort is None:
            LOGGER.warning("未检测到 onnxruntime，推理功能将不可用！")

        os.makedirs(self._temp_dir, exist_ok=True)
        self._load_models()

    def _load_models(self) -> None:
        """加载 PA 和 DTOA 的 ONNX 模型。"""
        if ort is None:
            return

        # 加载 DTOA
        if os.path.exists(self._dtoa_model_path):
            try:
                self._dtoa_model = ort.InferenceSession(self._dtoa_model_path, providers=['CPUExecutionProvider'])
                LOGGER.info(f"DTOA 模型加载成功: {self._dtoa_model_path}")
            except Exception as e:
                LOGGER.error(f"DTOA 模型加载失败: {e}")
        else:
            LOGGER.error(f"找不到 DTOA 模型文件: {self._dtoa_model_path}")

        # 加载 PA
        if os.path.exists(self._pa_model_path):
            try:
                self._pa_model = ort.InferenceSession(self._pa_model_path, providers=['CPUExecutionProvider'])
                LOGGER.info(f"PA 模型加载成功: {self._pa_model_path}")
            except Exception as e:
                LOGGER.error(f"PA 模型加载失败: {e}")
        else:
            LOGGER.error(f"找不到 PA 模型文件: {self._pa_model_path}")

    def predict_pa(self, cluster: ClusterItem) -> tuple[int, float, dict[int, float]]:
        """预测 PA 特征。
        
        Args:
            cluster: 待预测的簇对象。
            
        Returns:
            (类别标签, 置信度, 各类别置信度字典)
        """
        if self._pa_model is None:
            LOGGER.warning("PA 模型未加载，跳过预测")
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

            LOGGER.info(
                "PA ONNX 原始输出 (logits): [%s]",
                ", ".join(f"{v:.4f}" for v in raw_output[0]),
            )

            # 4. Softmax 与后处理
            pred = np.exp(raw_output) / np.sum(np.exp(raw_output), axis=1, keepdims=True)

            LOGGER.info(
                "PA Softmax 概率: [%s]",
                ", ".join(f"{p:.4f}" for p in pred[0]),
            )

            # 合并负样本 (5, 6, 7, 8 -> 5)
            if pred.shape[1] > 6:
                pred[0, 5] = np.sum(pred[0, 5:])
                pred[0, 6:] = 0

            label = int(np.argmax(pred[0, :6]))
            conf = float(pred[0, label])

            # 特殊组合概率处理 (复用旧版逻辑)
            if label >= 5:
                prob_comb_0_1 = pred[0, 0] + pred[0, 1]
                prob_comb_0_4 = pred[0, 0] + pred[0, 4]

                if prob_comb_0_1 > conf and prob_comb_0_1 >= prob_comb_0_4:
                    label = 0 if pred[0, 0] >= pred[0, 1] else 1
                    conf = float(prob_comb_0_1)
                elif prob_comb_0_4 > conf:
                    label = 0 if pred[0, 0] >= pred[0, 4] else 4
                    conf = float(prob_comb_0_4)

            conf_dict = {i: float(c) for i, c in enumerate(pred[0, :6]) if np.round(c, 4) > 0}

            LOGGER.info(
                "PA 预测完成: label=%d, conf=%.4f, 各类别概率=%s, 耗时=%.1fms",
                label, conf,
                ", ".join(f"{k}={v:.4f}" for k, v in sorted(conf_dict.items())),
                (t1 - t0) * 1000,
            )
            return label, conf, conf_dict

        except Exception as e:
            LOGGER.error(f"PA 预测异常: {e}", exc_info=True)
            return -1, 0.0, {}

    def predict_dtoa(self, cluster: ClusterItem) -> tuple[int, float, dict[int, float]]:
        """预测 DTOA 特征。"""
        if self._dtoa_model is None:
            LOGGER.warning("DTOA 模型未加载，跳过预测")
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

            LOGGER.info(
                "DTOA ONNX 原始输出 (logits): [%s]",
                ", ".join(f"{v:.4f}" for v in raw_output[0]),
            )

            # Softmax 与后处理
            pred = np.exp(raw_output) / np.sum(np.exp(raw_output), axis=1, keepdims=True)

            LOGGER.info(
                "DTOA Softmax 概率: [%s]",
                ", ".join(f"{p:.4f}" for p in pred[0]),
            )

            if pred.shape[1] > 6:
                pred[0, 0] = pred[0, 0] + pred[0, 1]
                pred[0, 1] = pred[0, 2]
                pred[0, 2] = pred[0, 3] + pred[0, 4]
                pred[0, 3] = pred[0, 5]
                pred[0, 4] = pred[0, 6]
                pred[0, 5] = np.sum(pred[0, 7:])
                pred[0, 6:] = 0

            label = int(np.argmax(pred[0, :6]))
            conf = float(pred[0, label])

            conf_dict = {i: float(c) for i, c in enumerate(pred[0, :6]) if np.round(c, 4) > 0}

            LOGGER.info(
                "DTOA 预测完成: label=%d, conf=%.4f, 各类别概率=%s, 耗时=%.1fms",
                label, conf,
                ", ".join(f"{k}={v:.4f}" for k, v in sorted(conf_dict.items())),
                (t1 - t0) * 1000,
            )
            return label, conf, conf_dict

        except Exception as e:
            LOGGER.error(f"DTOA 预测异常: {e}", exc_info=True)
            return -1, 0.0, {}
