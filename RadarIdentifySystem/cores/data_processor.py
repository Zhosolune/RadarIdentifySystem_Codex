import numpy as np
import pandas as pd
from typing import Tuple
from .log_manager import LogManager
from .plot_manager import SignalPlotter


class DataProcessor:
    """数据处理器

    负责雷达信号数据的加载、预处理和切片操作。

    Attributes:
        slice_length (int): 切片长度，单位为ms，默认250ms
        slice_dim (int): 切片维度，默认为4（TOA维度）
        data (Optional[NDArray]): 原始数据数组
        sliced_data (Optional[List[NDArray]]): 切片后的数据列表
        time_ranges (List[Tuple[float, float]]): 每个切片的时间范围列表
        plotter (SignalPlotter): 信号绘图器实例
        logger (LogManager): 日志管理器实例
    """

    def __init__(self):
        # 基础参数设置
        self.slice_length = 250  # 250ms
        self.slice_dim = 4  # TOA维度
        self.data: np.ndarray = None
        self.sliced_data: list[np.ndarray] = None
        self.time_ranges: list[tuple[float, float]] = []
        self.plotter = SignalPlotter()
        self.logger = LogManager()

    def load_excel_file(self, file_path: str) -> tuple[bool, str, dict]:
        """加载Excel文件并进行初始预处理

        读取Excel文件中的雷达信号数据，进行单位转换和数据清洗，
        并更新绘图配置。

        Args:
            file_path (str): Excel文件路径

        Returns:
            tuple[bool, str, dict]:
                - bool: 是否加载成功
                - str: 处理信息或错误信息
                - dict: 处理结果信息（总脉冲数、时间范围、剔除数、波段、切片数）

        Notes:
            数据格式要求：
            - CF (列1): 载频，单位MHz
            - PW (列2): 脉宽，单位us
            - DOA (列4): 到达角，单位度
            - PA (列5): 脉冲幅度，单位dB
            - TOA (列7): 到达时间，单位0.1us，将转换为ms
        """
        try:
            self.logger.info(f"开始加载Excel文件: {file_path}")

            # 读取Excel文件
            df = pd.read_excel(file_path)
            self.logger.debug(f"Excel文件读取成功，原始数据形状: {df.shape}")

            # 数据格式重排和单位转换
            data_tmp = df.values
            CF = data_tmp[:, 1]  # MHz
            PW = data_tmp[:, 2]  # us
            DOA = data_tmp[:, 4]  # 度
            PA = data_tmp[:, 5]  # dB
            TOA = data_tmp[:, 7] / 1e4  # 转换为ms

            # 组合原始数据
            raw_data = np.column_stack((CF, PW, DOA, PA, TOA))

            # 调用公共数据处理方法（纯处理，不修改状态）
            processed_data, result = self.process_raw_data(raw_data)

            if result["success"]:
                # Excel文件只有一个波段，直接激活数据
                band = self.activate_band_data(processed_data)
                result["band"] = band  # 更新为plotter返回的波段名
                return True, "数据加载成功", result
            else:
                return False, result["message"], result

        except Exception as e:
            self.logger.error(f"数据加载失败: {str(e)}")
            return False, f"数据加载失败: {str(e)}", {
                "success": False,
                "total_pulses": 0,
                "filtered_pulses": 0,
                "time_range": 0,
                "slice_count": 0,
                "band": None
            }

    def process_raw_data(self, raw_data: np.ndarray) -> Tuple[np.ndarray, dict]:
        """处理原始数据的公共方法（纯处理，不修改状态）

        处理步骤：
        1. 剔除PA无效值（=255）
        2. 处理时间翻折
        3. 计算时间范围
        4. 根据载频判断波段

        Args:
            raw_data: 原始数据数组，格式为 [CF, PW, DOA, PA, TOA]

        Returns:
            Tuple[np.ndarray, dict]: 处理后的数据和结果字典
                - processed_data: 处理后的数据数组
                - result: {
                    "success": bool,
                    "message": str,
                    "total_pulses": int,
                    "filtered_pulses": int,
                    "time_range": float (ms),
                    "slice_count": int,
                    "band": str
                }
        """
        try:
            self.logger.debug(f"开始处理原始数据，形状: {raw_data.shape}")

            # 复制数据，不修改原始数据
            data = raw_data.copy()
            original_length = len(data)

            # 剔除错误数据（PA无效值）
            data = data[data[:, 3] != 255]
            filtered_length = len(data)
            filtered_count = original_length - filtered_length
            self.logger.info(f"剔除无效PA值后，数据量从{original_length}减少到{filtered_length}")

            # 处理由于数据溢出导致的时间翻折情况
            time_data = data[:, self.slice_dim].copy()
            flip_indices = np.where(np.diff(time_data) < -6e4)[0]

            if len(flip_indices) > 0:
                self.logger.warning(f"检测到{len(flip_indices)}个时间翻折点，将进行修正")

                for idx in flip_indices:
                    delta_time = time_data[idx] - time_data[idx + 1]
                    time_data[idx + 1:] += delta_time

                time_data = time_data - time_data[0]
                data[:, self.slice_dim] = time_data

            # 计算时间范围
            time_range = max(time_data) - min(time_data) if len(time_data) > 0 else 0
            slice_count = int(np.ceil(time_range / self.slice_length)) if time_range > 0 else 0
            self.logger.info(f"时间范围: {time_range:.2f}ms, 预计切片数量: {slice_count}")

            # 根据载频判断波段（不更新plotter配置）
            cf_mean = np.mean(data[:, 0]) if len(data) > 0 else 0
            band = self._get_band_name(cf_mean)

            result = {
                "success": True,
                "message": "数据处理成功",
                "total_pulses": original_length,
                "filtered_pulses": filtered_count,
                "time_range": time_range,
                "slice_count": slice_count,
                "band": band
            }

            return data, result

        except Exception as e:
            self.logger.error(f"数据处理失败: {str(e)}")
            return np.array([]), {
                "success": False,
                "message": f"数据处理失败: {str(e)}",
                "total_pulses": 0,
                "filtered_pulses": 0,
                "time_range": 0,
                "slice_count": 0,
                "band": None
            }

    def _get_band_name(self, cf_mean: float) -> str:
        """根据平均载频获取波段名称

        Args:
            cf_mean: 平均载频 (MHz)

        Returns:
            str: 波段名称
        """
        if cf_mean < 1000:
            return None  # 丢弃
        elif cf_mean < 2000:
            return "L波段"
        elif cf_mean < 4000:
            return "S波段"
        elif cf_mean < 8000:
            return "C波段"
        else:
            return "X波段"

    def activate_band_data(self, data: np.ndarray) -> str:
        """激活波段数据，加载到processor并更新绘图配置

        在用户选择某一波段后调用此方法，将数据挂载到self.data
        并更新plotter绑定配置，使后续处理流程可正常使用。

        Args:
            data: 处理后的数据数组 [CF, PW, DOA, PA, TOA]

        Returns:
            str: 波段名称
        """
        self.data = data
        band = self.plotter.update_configs(data)
        self.logger.info(f"已激活波段数据，数据量: {len(data)}，波段: {band}")
        return band

    def start_slice(self):
        """开始数据切片处理

        调用内部的_slice_data方法进行数据切片，并更新sliced_data属性。
        切片结果将存储在实例的sliced_data属性中。
        """
        self.logger.info("开始数据切片处理")
        self.sliced_data = self._slice_data()
        if self.sliced_data:
            self.logger.info(f"切片完成，共生成{len(self.sliced_data)}个切片")
        else:
            self.logger.warning("切片处理未生成有效数据")

    def _slice_data(self) -> list:
        """将数据按时间切片

        根据预设的slice_length对数据进行时间维度的切片，
        同时记录每个切片的时间范围。

        Returns:
            list: 切片后的数据列表，每个元素为一个numpy数组，
                 表示一个时间窗口内的数据点。
                 如果没有有效数据，返回空列表。

        Notes:
            - 切片基于TOA（到达时间）维度进行
            - 空切片会被跳过
            - 每个切片的时间范围会被记录在time_ranges属性中
        """
        if self.data is None:
            self.logger.warning("没有可用的数据进行切片")
            return []

        # 获取时间维度的数据
        time_data = self.data[:, self.slice_dim]

        # 计算时间范围
        time_min = np.min(time_data)
        time_max = np.max(time_data)

        # 计算切片边界
        slice_boundaries = np.arange(time_min, time_max + self.slice_length, self.slice_length)

        # 存储切片结果和时间范围
        sliced_data = []

        # 进行切片
        for i in range(len(slice_boundaries) - 1):
            start_time = slice_boundaries[i]
            end_time = slice_boundaries[i + 1]

            # 提取当前时间窗口内的数据
            mask = (time_data >= start_time) & (time_data < end_time)
            current_slice = self.data[mask]

            if len(current_slice) == 0:
                continue

            sliced_data.append(current_slice)

            # start_toa = current_slice[0][self.slice_dim]
            # end_toa = current_slice[-1][self.slice_dim]
            # self.time_ranges.append((start_toa, end_toa))

            self.time_ranges.append((start_time, end_time))

        return sliced_data
