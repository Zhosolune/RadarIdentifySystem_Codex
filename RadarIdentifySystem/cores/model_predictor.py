import onnxruntime as ort
import numpy as np
from PIL import Image
import os
from typing import Tuple, Optional, Dict
from .plot_manager import SignalPlotter
from .log_manager import LogManager
from common.paths import Paths

class ModelPredictor:
    """模型预测器

    负责加载和管理深度学习模型，对雷达信号聚类结果进行PA和DTOA特征预测。
    使用 ONNX Runtime 进行推理。

    Attributes:
        model_dtoa (ort.InferenceSession): DTOA预测模型会话
        model_pa (ort.InferenceSession): PA预测模型会话
        temp_dir (str): 临时文件目录
        plotter (SignalPlotter): 信号绘图器实例
        logger (LogManager): 日志管理器实例
        th_dtoa (float): DTOA预测阈值，默认0.91
        th_pa (float): PA预测阈值，默认0.9
        time_ranges (list): 时间范围列表
        dtoa_model_path (str): DTOA模型文件路径
        pa_model_path (str): PA模型文件路径
    """

    def __init__(self):
        """初始化模型预测器"""
        self.dtoa_model = None
        self.pa_model = None
        
        # 使用用户数据目录下的temp文件夹
        temp_path = Paths.get_user_data_dir() / "temp"
        temp_path.mkdir(parents=True, exist_ok=True)
        self.temp_dir = str(temp_path)
        
        self.plotter = SignalPlotter()
        self.logger = LogManager()

        # 添加模型路径属性
        self.dtoa_model_path = None
        self.pa_model_path = None

        # 预测阈值
        self.th_dtoa = 0.91  # DTOA预测阈值
        self.th_pa = 0.9  # PA预测阈值

        self.time_ranges = []  # 初始化时间范围列表
        
        self.logger.info("使用推理引擎: ONNX Runtime (CPU)")

    def set_time_ranges(self, time_ranges: list):
        """设置时间范围列表

        Args:
            time_ranges (list): 时间范围列表，每个元素为(start_time, end_time)元组
        """
        self.time_ranges = time_ranges
        self.logger.debug(f"设置时间范围列表: {self.time_ranges}")

    def load_models(self, dtoa_model_path: str, pa_model_path: str) -> bool:
        """加载深度学习模型

        Args:
            dtoa_model_path: DTOA模型文件路径
            pa_model_path: PA模型文件路径

        Returns:
            bool: 是否成功加载模型
        """
        try:
            self.logger.info("\n=== 开始加载模型 ===")

            if self.load_dtoa_model(dtoa_model_path):
                self.logger.info("DTOA模型加载成功")
            else:
                return False

            if self.load_pa_model(pa_model_path):
                self.logger.info("PA模型加载成功")
            else:
                return False

            return True

        except Exception as e:
            self.logger.error(f"加载模型时出错: {str(e)}")
            return False

    def set_temp_dir(self, temp_dir: str):
        """设置临时文件目录

        Args:
            temp_dir (str): 临时文件目录路径

        Notes:
            同时会更新plotter的临时目录和保存目录
        """
        self.temp_dir = temp_dir
        self.plotter.set_temp_dir(temp_dir)
        self.plotter.set_save_dir(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)

    def predict(self, cluster_data: dict, pa_threshold: float, dtoa_threshold: float) -> Tuple[bool, float, float, int, int, dict, dict]:
        """预测单个聚类结果的PA和DTOA特征

        Args:
            cluster_data (dict): 聚类数据字典，包含：
                - slice_idx: 切片索引
                - time_ranges: 时间范围元组 (start_time, end_time)
                - dim_name: 维度名称
                - cluster_idx: 聚类编号
                - points: 聚类数据点

        Returns:
            Tuple[bool, float, float, int, int]:
                - bool: 预测是否成功
                - float: PA预测置信度
                - float: DTOA预测置信度
                - int: PA预测标签 (0-5，5表示无效)
                - int: DTOA预测标签 (0-4，4表示无效)

        Notes:
            - PA预测使用400x80的图像输入
            - DTOA预测使用500x250的图像输入
            - 预测结果会根据置信度阈值进行后处理
            - 临时生成的图像文件会在预测后删除
        """
        try:
            if not self.pa_model:
                self.logger.error("PA模型未正确初始化")
            if not self.dtoa_model:
                self.logger.error("DTOA模型未正确初始化")
            if not self.temp_dir:
                self.logger.error("临时目录未正确初始化")
            if not self.pa_model or not self.dtoa_model or not self.temp_dir:
                self.logger.error("模型或临时目录未正确初始化")
                return False, 0.0, 0.0, -1, -1, {}, {}

            self.th_dtoa = dtoa_threshold
            self.th_pa = pa_threshold

            self.logger.info(
                f"预测 切片{cluster_data.get('slice_idx', '?') + 1} - {cluster_data.get('dim_name', '?')}维度 - 聚类{cluster_data.get('cluster_idx', '?')}"
            )

            # 使用plot_manager生成图像并获取路径
            image_paths = self.plotter.plot_cluster(cluster_data, for_predict=True)

            # DTOA预测
            dtoa_image_tensor = self._preprocess_image(image_paths["DTOA"])
            
            # ONNX Runtime 推理
            dtoa_inputs = {self.dtoa_model.get_inputs()[0].name: dtoa_image_tensor}
            dtoa_output = self.dtoa_model.run(None, dtoa_inputs)[0]
            
            # Softmax
            dtoa_pred_tensor = np.exp(dtoa_output) / np.sum(np.exp(dtoa_output), axis=1, keepdims=True)
            dtoa_pred = dtoa_pred_tensor

            # 长短类别整合
            if dtoa_pred.shape[1] > 6:
                dtoa_pred[0, 0] = dtoa_pred[0, 0] + dtoa_pred[0, 1]
                dtoa_pred[0, 1] = dtoa_pred[0, 2]
                dtoa_pred[0, 2] = dtoa_pred[0, 3] + dtoa_pred[0, 4]
                dtoa_pred[0, 3] = dtoa_pred[0, 5]
                dtoa_pred[0, 4] = dtoa_pred[0, 6]
                dtoa_pred[0, 5] = np.sum(dtoa_pred[0, 7:])
                dtoa_pred[0, 6:] = 0

            dtoa_label = np.argmax(dtoa_pred[0, :6])
            dtoa_conf = dtoa_pred[0, dtoa_label]

            # 保存DTOA预测结果中置信度大于0的标签及其对应的置信度
            dtoa_conf_dict = {}
            for i, conf in enumerate(dtoa_pred[0, :6]):
                if np.round(conf, 4) > 0:
                    dtoa_conf_dict[i] = float(conf)

            # PA预测
            pa_image_tensor = self._preprocess_image(image_paths["PA"])
            
            # ONNX Runtime 推理
            pa_inputs = {self.pa_model.get_inputs()[0].name: pa_image_tensor}
            pa_output = self.pa_model.run(None, pa_inputs)[0]
            
            # Softmax
            pa_pred_tensor = np.exp(pa_output) / np.sum(np.exp(pa_output), axis=1, keepdims=True)
            pa_pred = pa_pred_tensor
            
            # PA后处理：合并负样本 (5, 6, 7, 8 -> 5)
            if pa_pred.shape[1] > 6:
                pa_pred[0, 5] = np.sum(pa_pred[0, 5:])
                pa_pred[0, 6:] = 0
            
            pa_label = np.argmax(pa_pred[0, :6])
            pa_conf = pa_pred[0, pa_label]

            if pa_label >= 5:
                # 计算组合概率
                prob_comb_0_1 = pa_pred[0, 0] + pa_pred[0, 1]
                prob_comb_0_4 = pa_pred[0, 0] + pa_pred[0, 4]

                if prob_comb_0_1 > pa_conf and prob_comb_0_1 >= prob_comb_0_4:
                    # 完整+残缺 概率高，取其中最大者
                    pa_label = 0 if pa_pred[0, 0] >= pa_pred[0, 1] else 1
                    pa_conf = prob_comb_0_1
                    pa_pred[0, 0] = prob_comb_0_1 if pa_pred[0, 0] >= pa_pred[0, 1] else 0
                    pa_pred[0, 1] = 0 if pa_pred[0, 0] >= pa_pred[0, 1] else prob_comb_0_1
                elif prob_comb_0_4 > pa_conf:
                    # 完整+旁瓣 概率高，取其中最大者
                    pa_label = 0 if pa_pred[0, 0] >= pa_pred[0, 4] else 4
                    pa_conf = prob_comb_0_4
                    pa_pred[0, 0] = prob_comb_0_4 if pa_pred[0, 0] >= pa_pred[0, 4] else 0
                    pa_pred[0, 4] = 0 if pa_pred[0, 0] >= pa_pred[0, 4] else prob_comb_0_4

            # 保存PA预测结果中置信度大于0的标签及其对应的置信度
            pa_conf_dict = {}
            for i, conf in enumerate(pa_pred[0, :6]):
                if np.round(conf, 4) > 0:
                    pa_conf_dict[i] = float(conf)

            # 清理临时文件
            for path in image_paths.values():
                if os.path.exists(path):
                    os.remove(path)

            self.logger.info(f"PA - 标签: {pa_label}, 置信度: {pa_conf:.4f}")
            self.logger.info(f"DTOA - 标签: {dtoa_label}, 置信度: {dtoa_conf:.4f}")

            return True, float(pa_conf), float(dtoa_conf), int(pa_label), int(dtoa_label), pa_conf_dict, dtoa_conf_dict

        except Exception as e:
            self.logger.error(f"预测出错: {str(e)}")
            import traceback

            self.logger.error(f"错误详情:\n{traceback.format_exc()}")
            return False, 0.0, 0.0, -1, -1, {}, {}

    def _preprocess_image(self, image_path: str) -> np.ndarray:
        """预处理图像用于模型输入

        Args:
            image_path (str): 图像文件路径

        Returns:
            np.ndarray: 预处理后的图像张量，形状为(1, 1, height, width)

        Notes:
            - 像素值会被归一化到[0,1]范围
            - 图像会被转换为灰度图（单通道）
            - 返回的张量包含batch维度
        """
        img = Image.open(image_path)
        img = img.convert("L")  # 转换为灰度图 (单通道)
        img_array = np.array(img)
        img_array = img_array.astype("float32")
        img_array = img_array / 255.0  # 归一化
        
        # 灰度图只有 (H, W)，需要扩展为 (C, H, W) 其中 C=1
        img_array = np.expand_dims(img_array, axis=0)
        
        # 转换为 Tensor 并添加 Batch 维度 (1, C, H, W)
        img_array = np.expand_dims(img_array, axis=0)
        
        return img_array

    def load_pa_model(self, model_path: str) -> bool:
        """单独加载PA模型

        Args:
            model_path: PA模型文件路径

        Returns:
            bool: 加载是否成功
        """
        try:
            self.logger.info(f"开始加载PA模型(ONNX): {model_path}")

            # 检查文件是否存在
            if not os.path.exists(model_path):
                self.logger.error(f"PA模型文件不存在: {model_path}")
                return False

            # 加载ONNX模型
            try:
                self.pa_model = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            except Exception as e:
                self.logger.error(f"无法加载模型文件(非ONNX格式?): {e}")
                return False
                
            self.pa_model_path = model_path
            self.logger.info(f"PA模型加载成功")
            return True

        except Exception as e:
            self.logger.error(f"加载PA模型时出错: {str(e)}")
            return False

    def load_dtoa_model(self, model_path: str) -> bool:
        """单独加载DTOA模型

        Args:
            model_path: DTOA模型文件路径

        Returns:
            bool: 加载是否成功
        """
        try:
            self.logger.info(f"开始加载DTOA模型(ONNX): {model_path}")

            # 检查文件是否存在
            if not os.path.exists(model_path):
                self.logger.error(f"DTOA模型文件不存在: {model_path}")
                return False

            # 加载ONNX模型
            try:
                self.dtoa_model = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            except Exception as e:
                self.logger.error(f"无法加载模型文件(非ONNX格式?): {e}")
                return False
                
            self.dtoa_model_path = model_path
            self.logger.info("DTOA模型加载成功")
            return True

        except Exception as e:
            self.logger.error(f"加载DTOA模型时出错: {str(e)}")
            return False
