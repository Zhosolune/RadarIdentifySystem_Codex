from PyQt5.QtCore import QThread, pyqtSignal
from cores.log_manager import LogManager
from cores.data_processor import DataProcessor
from typing import Tuple, List, Dict, Callable

import pandas as pd
import os

import numpy as np


class DataWorker(QThread):
    """数据加载工作线程。

    负责在独立线程中执行Excel文件的加载和数据预处理。
    """

    # finished信号：success, message, result_dict, data
    finished = pyqtSignal(bool, str, object, object)

    def __init__(self, file_path: str):
        """初始化数据工作线程。

        Args:
            file_path: Excel文件路径
        """
        super().__init__()
        self.file_path = file_path
        self.processor = DataProcessor()
        self.logger = LogManager()

    def run(self):
        """执行数据处理。

        加载Excel文件并进行预处理，完成后发送finished信号。
        """
        try:
            self.logger.info("工作线程开始处理数据...")
            success, message, result = self.processor.load_excel_file(self.file_path)
            self.finished.emit(success, message, result, self.processor.data)
            self.logger.info("处理数据线程关闭...")
        except Exception as e:
            self.logger.error(f"工作线程处理异常: {str(e)}")
            self.finished.emit(False, f"处理出错: {str(e)}", {}, None)


class BinWorker(QThread):
    """Bin文件解析工作线程。

    负责在独立线程中执行Bin文件的解析和波段分流。
    """

    # finished信号：success, result_dict
    finished = pyqtSignal(bool, object)

    def __init__(self, file_path: str, strategy: str = "amplitude"):
        """初始化Bin文件工作线程。

        Args:
            file_path: Bin文件路径
            strategy: 解析策略 ('amplitude' 比幅 或 'interferometer' 干涉仪)
        """
        super().__init__()
        self.file_path = file_path
        self.strategy = strategy
        self.logger = LogManager()

    def run(self):
        """执行Bin文件解析。

        解析Bin文件并按波段分流，完成后发送finished信号。
        """
        try:
            self.logger.info("Bin文件工作线程开始解析...")
            from cores.bin_parser import BinFileParser

            parser = BinFileParser()
            # 设置解析策略
            parser.set_strategy(self.strategy)
            result = parser.parse(self.file_path)
            self.finished.emit(result.get("success", False), result)
            self.logger.info("Bin文件解析线程关闭...")
        except Exception as e:
            self.logger.error(f"Bin文件工作线程异常: {str(e)}")
            self.finished.emit(False, {"success": False, "error": str(e)})


class ExportWorker(QThread):
    """Excel导出工作线程
    
    负责在独立线程中执行仪表盘数据的导出。
    """
    
    progress = pyqtSignal(int)  # 进度信号 0-100
    status = pyqtSignal(str)  # 状态信号，显示当前操作
    finished = pyqtSignal(bool, str)  # 成功/失败，消息
    
    def __init__(self, data: dict, export_config: dict, source_file_name: str = ""):
        """初始化导出工作线程
        
        Args:
            data: 待导出的仪表盘数据（按波段分组）
            export_config: 导出配置字典
            source_file_name: 源文件名（不含扩展名）
        """
        super().__init__()
        self.data = data
        self.export_config = export_config
        self.source_file_name = source_file_name or "export"
        self.logger = LogManager()
        self._last_progress = -1  # 用于控制进度更新频率
    
    def run(self):
        """执行导出处理"""
        try:
            self.logger.info("导出工作线程开始...")
            
            export_path = self.export_config.get("export_path", "")
            band_export_mode = self.export_config.get("band_export_mode", 0)
            file_split_mode = self.export_config.get("file_split_mode", 2)
            
            if not export_path or not os.path.exists(export_path):
                self.finished.emit(False, "导出路径无效")
                return
            
            bands = self.data.get("bands", {})
            if not bands:
                self.finished.emit(False, "没有可导出的波段数据")
                return
            
            # 获取用户选中的波段
            selected_bands = self.export_config.get("selected_bands", [])
            
            # 获取有效波段，并根据用户选择过滤
            valid_bands = []
            for k, v in bands.items():
                if v is None:
                    continue
                # selected_bands 格式为 ["L波段", "S波段", "C波段"]
                # 需要匹配波段 key（如 "L", "S", "C"）
                band_label = f"{k}波段"
                if selected_bands and band_label not in selected_bands:
                    continue
                valid_bands.append((k, v))
            
            total_bands = len(valid_bands)
            
            if total_bands == 0:
                self.finished.emit(False, "没有有效的波段数据")
                return
            
            self.progress.emit(0)
            self.status.emit("正在准备导出...")
            
            if band_export_mode == 0:
                # 分别导出为独立的Excel文件
                success = self._export_to_separate_files(valid_bands, export_path, file_split_mode)
            else:
                # 导出为一个Excel文件内不同的sheet
                success = self._export_to_single_file(valid_bands, export_path)
            
            if success:
                self.progress.emit(100)
                self.finished.emit(True, "导出完成")
            else:
                self.finished.emit(False, "导出过程中发生错误")
                
        except Exception as e:
            self.logger.error(f"导出工作线程异常: {str(e)}")
            self.finished.emit(False, f"导出失败: {str(e)}")
    
    def _export_to_separate_files(self, valid_bands: list, export_path: str, file_split_mode: int) -> bool:
        """导出为独立的Excel文件
        
        Args:
            valid_bands: 有效波段列表
            export_path: 导出路径
            file_split_mode: 切分方式 (0=按大小, 1=按数量, 2=不切分)
        """
        try:
            import tempfile
            
            file_split_size_mb = self.export_config.get("file_split_size_mb", 100)
            file_split_count = self.export_config.get("file_split_count", 10)
            
            # 先计算所有波段的总行数
            total_rows_all = 0
            band_data_list = []
            
            for band_key, band_info in valid_bands:
                temp_file = band_info.get("temp_file")
                if not temp_file or not os.path.exists(temp_file):
                    continue
                
                data = np.load(temp_file)
                total_rows_all += len(data)
                band_data_list.append((band_key, data))
            
            if total_rows_all == 0:
                return True
            
            # 计算每1%对应的行数
            rows_per_percent = max(1, total_rows_all // 100)
            rows_written = 0
            
            for band_key, data in band_data_list:
                df = pd.DataFrame(data, columns=["CF", "PW", "DOA", "PA", "TOA"])
                # 将TOA单位从ms转换为us
                df["TOA"] = df["TOA"] * 1000
                df.rename(columns={"TOA": "TOA(us)"}, inplace=True)
                
                total_rows = len(df)
                
                self.status.emit(f"正在导出 {band_key} 波段...")
                
                if file_split_mode == 3 or total_rows == 0:
                    # 不切分：使用分块写入单个文件，实现1%粒度进度
                    file_name = f"{self.source_file_name}_{band_key}.xlsx"
                    file_path = os.path.join(export_path, file_name)
                    
                    # 设定进度步长
                    chunk_size = max(rows_per_percent, 1000)
                    chunk_size = min(chunk_size, 20000)
                    
                    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                        chunks_count = max(1, (total_rows + chunk_size - 1) // chunk_size)
                        
                        for j in range(chunks_count):
                            chunk_start = j * chunk_size
                            chunk_end = min((j + 1) * chunk_size, total_rows)
                            small_chunk = df.iloc[chunk_start:chunk_end]
                            
                            is_first_chunk = (j == 0)
                            
                            if is_first_chunk:
                                small_chunk.to_excel(
                                    writer, index=False, header=True,
                                    startrow=0, sheet_name=f"{band_key}波段"
                                )
                            else:
                                small_chunk.to_excel(
                                    writer, index=False, header=False,
                                    startrow=chunk_start + 1,
                                    sheet_name=f"{band_key}波段"
                                )
                            
                            rows_written += len(small_chunk)
                            progress = int(rows_written / total_rows_all * 100)
                            progress = min(99, progress)
                            
                            if progress != self._last_progress:
                                self._last_progress = progress
                                self.progress.emit(progress)
                    
                elif file_split_mode == 0:
                    # 按大小切分
                    sample_size = min(1000, total_rows)
                    sample_df = df.iloc[:sample_size]
                    
                    tmp_path = tempfile.mktemp(suffix='.xlsx')
                    try:
                        sample_df.to_excel(tmp_path, index=False)
                        actual_size = os.path.getsize(tmp_path)
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    
                    excel_overhead = 5 * 1024
                    bytes_per_row = max(50, (actual_size - excel_overhead) / sample_size)
                    target_bytes = file_split_size_mb * 1024 * 1024
                    rows_per_file = max(1, int((target_bytes - excel_overhead) / bytes_per_row))
                    
                    rows_written = self._write_split_files_by_rows(
                        df, export_path, band_key, rows_per_file,
                        rows_written, total_rows_all, rows_per_percent
                    )
                    
                elif file_split_mode == 1:
                    # 按数量平均切分
                    rows_per_file = max(1, (total_rows + file_split_count - 1) // file_split_count)
                    
                    rows_written = self._write_split_files_by_rows(
                        df, export_path, band_key, rows_per_file,
                        rows_written, total_rows_all, rows_per_percent
                    )
                
                elif file_split_mode == 2:
                    # 按数据条数切分
                    file_split_rows = self.export_config.get("file_split_rows", 100000)
                    rows_per_file = max(1, file_split_rows)
                    
                    rows_written = self._write_split_files_by_rows(
                        df, export_path, band_key, rows_per_file,
                        rows_written, total_rows_all, rows_per_percent
                    )
            
            return True
        except Exception as e:
            self.logger.error(f"导出独立文件失败: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def _emit_progress_by_rows(self, rows_written: int, total_rows: int, rows_per_percent: int):
        """按行数发送进度信号，1%步长
        
        根据已写入行数计算当前进度百分比
        """
        progress = int(rows_written / total_rows * 100) if total_rows > 0 else 0
        progress = min(99, progress)
        
        if progress != self._last_progress:
            self._last_progress = progress
            self.progress.emit(progress)
    
    def _write_split_files_by_rows(self, df: pd.DataFrame, export_path: str, 
                                    band_key: str, rows_per_file: int,
                                    rows_written: int, total_rows_all: int,
                                    rows_per_percent: int) -> int:
        """按行数切分写入并更新进度
        
        使用 ExcelWriter + startrow 分块写入，每写入约 1% 的数据发射一次进度信号
        
        Args:
            df: 要写入的数据
            export_path: 导出路径
            band_key: 波段标识
            rows_per_file: 每个文件的行数
            rows_written: 当前已写入的总行数
            total_rows_all: 所有数据的总行数
            rows_per_percent: 每1%对应的行数
        
        Returns:
            int: 更新后的已写入行数
        """
        total_rows = len(df)
        file_index = 1
        file_start_row = 0
        
        # 设定进度步长：每次写入 rows_per_percent 行
        # 限制 chunk_size 范围，防止过小（IO太慢）或过大（进度跳跃）
        chunk_size = max(rows_per_percent, 1000)
        chunk_size = min(chunk_size, 20000)
        
        while file_start_row < total_rows:
            file_end_row = min(file_start_row + rows_per_file, total_rows)
            file_df = df.iloc[file_start_row:file_end_row]
            file_total_rows = len(file_df)
            
            file_name = f"{self.source_file_name}_{band_key}_{file_index}.xlsx"
            file_path = os.path.join(export_path, file_name)
            
            self.status.emit(f"正在导出 {band_key} 波段 ({file_index})...")
            
            # 使用 ExcelWriter 分块写入同一个文件
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                chunks_in_file = max(1, (file_total_rows + chunk_size - 1) // chunk_size)
                
                for j in range(chunks_in_file):
                    chunk_start = j * chunk_size
                    chunk_end = min((j + 1) * chunk_size, file_total_rows)
                    small_chunk = file_df.iloc[chunk_start:chunk_end]
                    
                    is_first_chunk = (j == 0)
                    
                    # startrow: 第一块从0开始（含表头），后续块从对应行开始（无表头）
                    if is_first_chunk:
                        small_chunk.to_excel(
                            writer, index=False, header=True,
                            startrow=0, sheet_name=f"{band_key}波段"
                        )
                    else:
                        small_chunk.to_excel(
                            writer, index=False, header=False,
                            startrow=chunk_start + 1,  # +1 为表头预留
                            sheet_name=f"{band_key}波段"
                        )
                    
                    # 更新进度
                    rows_written += len(small_chunk)
                    progress = int(rows_written / total_rows_all * 100)
                    progress = min(99, progress)
                    
                    if progress != self._last_progress:
                        self._last_progress = progress
                        self.progress.emit(progress)
            
            file_start_row = file_end_row
            file_index += 1
        
        return rows_written
    
    def _export_to_single_file(self, valid_bands: list, export_path: str) -> bool:
        """导出为单个Excel文件的不同sheet，使用分块写入实现1%粒度进度"""
        try:
            file_path = os.path.join(export_path, f"{self.source_file_name}.xlsx")
            self.status.emit("正在导出到 Excel...")
            
            # 先计算总行数
            total_rows_all = 0
            band_data_list = []
            for band_key, band_info in valid_bands:
                temp_file = band_info.get("temp_file")
                if not temp_file or not os.path.exists(temp_file):
                    continue
                data = np.load(temp_file)
                total_rows_all += len(data)
                band_data_list.append((band_key, data))
            
            if total_rows_all == 0:
                return True
            
            # 计算每1%对应的行数
            rows_per_percent = max(1, total_rows_all // 100)
            chunk_size = max(rows_per_percent, 1000)
            chunk_size = min(chunk_size, 20000)
            
            rows_written = 0
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                for band_key, data in band_data_list:
                    df = pd.DataFrame(data, columns=["CF", "PW", "DOA", "PA", "TOA"])
                    # 将TOA单位从ms转换为us
                    df["TOA"] = df["TOA"] * 1000
                    df.rename(columns={"TOA": "TOA(us)"}, inplace=True)
                    
                    total_rows = len(df)
                    
                    self.status.emit(f"正在导出 {band_key} 波段...")
                    
                    # 分块写入同一个 sheet
                    chunks_count = max(1, (total_rows + chunk_size - 1) // chunk_size)
                    
                    for j in range(chunks_count):
                        chunk_start = j * chunk_size
                        chunk_end = min((j + 1) * chunk_size, total_rows)
                        small_chunk = df.iloc[chunk_start:chunk_end]
                        
                        is_first_chunk = (j == 0)
                        
                        if is_first_chunk:
                            small_chunk.to_excel(
                                writer, index=False, header=True,
                                startrow=0, sheet_name=f"{band_key}波段"
                            )
                        else:
                            small_chunk.to_excel(
                                writer, index=False, header=False,
                                startrow=chunk_start + 1,
                                sheet_name=f"{band_key}波段"
                            )
                        
                        rows_written += len(small_chunk)
                        progress = int(rows_written / total_rows_all * 100)
                        progress = min(99, progress)
                        
                        if progress != self._last_progress:
                            self._last_progress = progress
                            self.progress.emit(progress)
            
            return True
        except Exception as e:
            self.logger.error(f"导出单一文件失败: {str(e)}")
            return False


class IdentifyWorker(QThread):
    """识别处理工作线程。

    负责在独立线程中执行雷达信号的识别处理。
    """

    identify_started = pyqtSignal()  # 识别开始信号
    identify_finished = pyqtSignal(bool, int, bool)

    def __init__(self, data_controller):
        """初始化识别工作线程。

        Args:
            data_controller: 数据控制器实例
        """
        super().__init__()
        self.data_controller = data_controller
        self.logger = LogManager()

    def run(self):
        """执行识别处理。

        对当前切片进行识别处理，完成后发送识别结果信号。
        """
        try:
            # 发送识别开始信号
            self.identify_started.emit()
            self.logger.info("开始识别线程...")

            # 执行识别处理
            success, can_merge = self.data_controller._process_identify_current_slice()

            # 获取有效类别数量
            cluster_count = len(self.data_controller.valid_clusters) if success else 0

            # 发送识别完成信号
            self.identify_finished.emit(success, cluster_count, can_merge)
            self.data_controller.process_finished.emit()
            self.logger.info("识别线程关闭...")

        except Exception as e:
            self.logger.error(f"识别处理线程出错: {str(e)}")
            self.identify_finished.emit(False, 0, False)


class SliceWorker(QThread):
    """切片处理工作线程。

    负责在独立线程中执行雷达信号数据的切片处理。
    """

    slice_finished = pyqtSignal(bool)  # 切片完成信号

    def __init__(self, data_controller):
        """初始化切片工作线程。

        Args:
            data_controller: 数据控制器实例
        """
        super().__init__()
        self.data_controller = data_controller
        self.logger = LogManager()

    def run(self):
        """执行切片处理。

        将雷达信号数据按时间窗口进行切片，并处理第一片数据。
        """
        try:
            self.logger.info("开始切片线程...")

            # 开始切片
            self.data_controller.processor.start_slice()
            self.data_controller.sliced_data = self.data_controller.processor.sliced_data
            self.data_controller.sliced_data_count = len(self.data_controller.processor.sliced_data)

            # 更新切片信息
            if self.data_controller.sliced_data_count_tmp != self.data_controller.sliced_data_count:
                empty_slice_count = self.data_controller.sliced_data_count_tmp - self.data_controller.sliced_data_count
                self.data_controller.slice_info_updated2.emit(
                    f"共获得{self.data_controller.sliced_data_count}个250ms切片，以及<span style='color: red;'>{empty_slice_count}</span>个空切片"
                )
            else:
                self.data_controller.slice_info_updated2.emit(f"共获得{self.data_controller.sliced_data_count}个250ms切片")
            # print(f"sliced_data_count: {self.data_controller.sliced_data_count}, sliced_data_count_tmp: {self.data_controller.sliced_data_count_tmp}")

            success = False
            if self.data_controller.sliced_data and len(self.data_controller.sliced_data) > 0:
                # 处理第一片
                success = self.data_controller.process_first_slice()
                if not success:
                    self.logger.error("处理第一片数据失败")

            self.slice_finished.emit(success)
            self.logger.info("切片线程关闭...")

        except Exception as e:
            self.logger.error(f"切片处理线程出错: {str(e)}")
            self.slice_finished.emit(False)


class FullSpeedWorker(QThread):
    # 信号声明
    slice_started = pyqtSignal()
    slice_finished = pyqtSignal(bool, int)
    current_slice_finished = pyqtSignal(int)
    start_save = pyqtSignal()
    process_finished = pyqtSignal(bool)

    def __init__(self, data_controller):
        super().__init__()
        self.data_controller = data_controller
        self.processor = self.data_controller.processor
        self.cluster_processor = self.data_controller.cluster_processor
        self.logger = LogManager()
        self.predictor = self.data_controller.predictor

        # 获取处理参数
        self.epsilon_CF = self.data_controller.epsilon_CF
        self.epsilon_PW = self.data_controller.epsilon_PW
        self.min_pts = self.data_controller.min_pts
        self.pa_threshold = self.data_controller.pa_threshold
        self.dtoa_threshold = self.data_controller.dtoa_threshold
        self.pa_weight = self.data_controller.pa_weight
        self.dtoa_weight = self.data_controller.dtoa_weight
        self.threshold = self.data_controller.threshold
        self.pri_equal_doa_tolerance = self.data_controller.pri_equal_doa_tolerance
        self.pri_different_doa_tolerance = self.data_controller.pri_different_doa_tolerance
        self.pri_different_cf_tolerance = self.data_controller.pri_different_cf_tolerance
        self.pri_none_doa_tolerance = self.data_controller.pri_none_doa_tolerance

        # 获取标签映射表
        self.PA_LABEL_NAMES = self.data_controller.PA_LABEL_NAMES
        self.DTOA_LABEL_NAMES = self.data_controller.DTOA_LABEL_NAMES

        # 其他必要数据
        self.save_dir = self.data_controller.get_save_dir()  # 使用getter方法获取保存目录
        self.last_file_path = self.data_controller.last_file_path if hasattr(self.data_controller, "last_file_path") else None
        self.current_param_fingerprint = self.data_controller._generate_param_fingerprint()
        self.only_show_identify_result = self.data_controller.only_show_identify_result

        # 数据初始化
        self.slice_data = []
        self.slice_count = 0
        self.valid_clusters = []
        self.merged_clusters = []
        self.merged_pulse_data_by_slice = {}
        self.all_pulse_data_by_slice = {}

    def run(self):
        # 切片
        self._on_slice_fs()

        # 聚类、识别、提取参数
        all_valid_clusters, all_merged_clusters = self._on_cluster_identify_fs()

        # 所有切片处理完成后，一次性保存所有结果
        save_success = False
        if all_valid_clusters or all_merged_clusters:
            # 发射开始保存信号
            self.start_save.emit()
            self.logger.info("开始保存识别结果...")
            self.valid_clusters = all_valid_clusters
            self.merged_clusters = all_merged_clusters
            save_success, _ = self._on_save_result_fs(only_valid=True)
            if self.all_pulse_data_by_slice:  # 检查脉冲数据是否存在
                self._on_save_pulse_data_fs()  # 保存脉冲数据
            else:
                self.logger.warning("没有脉冲数据可保存，跳过保存脉冲数据步骤。")

            # 保存合并脉冲数据
            if self.merged_pulse_data_by_slice:  # 检查合并脉冲数据是否存在
                self._on_save_merged_pulse_data_fs()  # 保存合并脉冲数据
            else:
                self.logger.warning("没有合并脉冲数据可保存，跳过保存合并脉冲数据步骤。")
        else:
            self.logger.warning("没有有效的聚类结果，跳过保存步骤。")

        # 发送处理完成信号 (根据主要结果保存是否成功)
        self.logger.info("全速处理完成所有切片")
        self.process_finished.emit(save_success)  # 以概要结果保存成功与否为准

    def _on_slice_fs(self):
        """执行切片处理。

        将雷达信号数据按时间窗口进行切片，并处理第一片数据。
        """
        try:
            self.logger.info("开始切片...")
            self.slice_started.emit()

            # 开始切片
            self.processor.start_slice()
            self.slice_data = self.processor.sliced_data
            self.slice_count = len(self.processor.sliced_data)

            # 发送切片完成信号
            if self.slice_data is not None and len(self.slice_data) > 0:
                self.slice_finished.emit(True, self.slice_count)
            else:
                self.slice_finished.emit(False, 0)

            self.logger.info("切片完成...")

        except Exception as e:
            self.logger.error(f"切片处理出错: {str(e)}")

    def _on_cluster_identify_fs(self):
        """执行聚类处理。

        对当前切片进行聚类、识别处理。
        """
        try:
            # 用于存储所有切片的有效聚类结果
            all_valid_clusters = []
            all_merged_clusters = []  # 存储所有切片的合并结果
            self.all_pulse_data_by_slice = {}

            # 开始逐片聚类
            for slice_idx in range(len(self.slice_data)):
                # 开始处理第slice_idx+1个切片，向UI发送当前slice_idx，表示已经完成了slice_idx片，以刷新进度条
                self.current_slice_finished.emit(slice_idx)

                try:
                    # 获取当前切片
                    current_slice = self.slice_data[slice_idx]

                    # 数据完整性检查
                    if current_slice is None or len(current_slice) == 0:
                        self.logger.debug(f"切片 {slice_idx + 1} 数据无效")
                        continue

                    # 设置当前切片数据和时间范围
                    self.cluster_processor.set_data(current_slice, slice_idx)
                    self.cluster_processor.set_slice_time_ranges(self.processor.time_ranges)

                    # 初始化处理数据
                    self.valid_clusters = []
                    current_data = current_slice
                    recycled_data = []
                    dim_idx = {"CF": 0, "PW": 0}
                    cluster_count = 0
                    cluster_count_by_save = 0
                    dimensions = ["CF", "PW"]
                    current_slice_pulse_data_valid = []
                    current_slice_pulse_data_invalid = []
                    current_slice_pulse_data_remaining = []
                    current_slice_pulse_data_merged = []
                    current_slice_merged_clusters = []
                    count_valid = 1
                    count_invalid = 1

                    # 按顺序处理每个维度
                    for dimension in dimensions:
                        success, cluster_result = self.cluster_processor.process_dimension(dimension, current_data)

                        if success and cluster_result:
                            # 处理聚类结果
                            for cluster in cluster_result["clusters"]:
                                # 确保cluster包含必要的字段
                                cluster_data = {
                                    "points": cluster["points"],
                                    "time_ranges": self.cluster_processor.time_ranges,
                                    "slice_idx": slice_idx,
                                    "dim_name": dimension,
                                    "cluster_idx": cluster_count + 1,
                                }

                                # 预测
                                success, pa_conf, dtoa_conf, pa_label, dtoa_label, pa_conf_dict, dtoa_conf_dict = self.predictor.predict(
                                    cluster_data, self.pa_threshold, self.dtoa_threshold
                                )

                                if success:
                                    # 提取有效雷达标签对应概率
                                    pa_conf_tmp = pa_conf if pa_label != 5 else 0.0
                                    dtoa_conf_tmp = dtoa_conf if dtoa_label != 4 else 0.0

                                    # 计算联合概率
                                    joint_prob = (pa_conf_tmp * self.pa_weight + dtoa_conf_tmp * self.dtoa_weight) / (self.pa_weight + self.dtoa_weight)

                                    # 判断是否为有效雷达信号（贪婪策略）
                                    is_valid = pa_label != 5 or dtoa_label != 4

                                    # 雷达有效时，对于脉间参差类别的特殊判别
                                    # if is_valid and dtoa_label == 1:
                                    #     # 计算dtoa的集中度
                                    #     dtoa = np.diff(cluster['points'][:, 4]) * 1000  # 转换为us

                                    #     # 计算统计指标
                                    #     dtoa_median = np.median(dtoa)
                                    #     dtoa_min = np.min(dtoa)
                                    #     dtoa_max = np.max(dtoa)

                                    #     # 判断条件：
                                    #     # 1. 数据范围不能超过1000us
                                    #     # 2. 大部分数据应该在中位数/均值附近
                                    #     data_range = dtoa_max - dtoa_min
                                    #     is_range_valid = data_range <= 1000  # 范围阈值可调

                                    #     # 计算在中位数一定范围内的数据比例
                                    #     center_range_ratio = 0.35  # 可调35%
                                    #     in_center_count = np.sum(np.abs(dtoa - dtoa_median) <= center_range_ratio * dtoa_median)
                                    #     center_ratio = in_center_count / len(dtoa)
                                    #     is_centered = center_ratio >= 0.7  # 比例阈值可调

                                    #     # 综合判断
                                    #     if not (is_range_valid or is_centered):
                                    #         is_valid = False

                                    # 创建聚类信息
                                    cluster_info = {
                                        "dim_name": dimension,
                                        "cluster_dim_idx": dim_idx[dimension] + 1,  # 每个维度下的类别索引
                                        "cluster_idx": len(self.valid_clusters) + 1,  # 通过识别的聚类索引
                                        "total_cluster_count": cluster_count + 1,  # 整体聚类结果中的索引
                                        "cluster_data": cluster,
                                        "is_valid": is_valid,  # 保存是否为有效雷达信号
                                        "prediction": {
                                            "pa_label": pa_label,
                                            "pa_conf": pa_conf,
                                            "dtoa_label": dtoa_label,
                                            "dtoa_conf": dtoa_conf,
                                            "joint_prob": joint_prob,
                                            "pa_dict": pa_conf_dict,
                                            "dtoa_dict": dtoa_conf_dict,
                                        },
                                        "CF": [],
                                        "PW": [],
                                        "PRI": [],
                                        "DOA": [],
                                    }
                                    # 提取并更新参数
                                    self.data_controller._extract_cluster_parameters(cluster_info)

                                    # 微观保存脉冲数据：收集脉冲数据
                                    last_toa = None
                                    cluster_points = cluster["points"]
                                    for point in cluster_points:
                                        if last_toa is None:
                                            last_toa = point[4]
                                        pulse_data = {
                                            "类别": "valid" if is_valid else "invalid",
                                            "聚类维度": dimension,
                                            "序号": count_valid if is_valid else count_invalid,
                                            "切片内序号": cluster_info["total_cluster_count"],
                                            "载频": point[0],
                                            "脉宽": point[1],
                                            "方位角": point[2],
                                            "幅度": point[3],
                                            "到达时间": point[4],
                                            "到达时间差": (point[4] - last_toa) * 1000,
                                        }
                                        last_toa = point[4]
                                        if is_valid:
                                            current_slice_pulse_data_valid.append(pulse_data)
                                        else:
                                            # 仅在PW维度下收集无效脉冲数据，避免重复收集脉冲
                                            if dimension == "PW":
                                                current_slice_pulse_data_invalid.append(pulse_data)

                                    # 递增聚类序号
                                    cluster_count += 1

                                    # 宏观保存识别结果：收集所有结果
                                    if is_valid:
                                        cluster_count_by_save += 1
                                        # 将当前切片索引添加到cluster_info
                                        cluster_info["current_slice_idx"] = slice_idx
                                        cluster_info["cluster_idx_per_slice_to_save"] = cluster_count_by_save
                                        all_valid_clusters.append(cluster_info)
                                        current_slice_merged_clusters.append(cluster_info)  # 添加到当前切片的有效聚类
                                        count_valid += 1

                                    # 处理无效数据
                                    if not is_valid:
                                        recycled_data.extend(cluster["points"].tolist())
                                        if dimension == "PW":
                                            count_invalid += 1

                                    # 保存聚类结果
                                    # if not self.only_show_identify_result or is_valid:
                                    #     dim_idx[dimension] += 1
                                    #     self.valid_clusters.append(cluster_info)

                            # 更新待处理数据
                            unprocessed_data = cluster_result.get("unprocessed_points", [])
                            if not isinstance(unprocessed_data, list):
                                unprocessed_data = unprocessed_data.tolist()

                            # 合并回收数据和未聚类数据
                            # 对于CF维度，无效数据和未聚类数据合并，对于PW维度，只保留未聚类数据（因为无效数据已经保存过了）
                            if dimension == "CF":
                                if recycled_data and unprocessed_data:
                                    current_data = np.vstack((recycled_data, unprocessed_data))
                                elif recycled_data:
                                    current_data = recycled_data
                                else:
                                    current_data = unprocessed_data
                            elif dimension == "PW":
                                current_data = unprocessed_data

                    # 合并
                    merged_clusters = self._merge_valid_clusters(current_slice_merged_clusters)
                    if merged_clusters:
                        self.logger.info(f"切片 {slice_idx + 1} 合并数: {len(merged_clusters)}")
                        for cluster in merged_clusters:
                            cluster["current_slice_index"] = slice_idx

                        # 将当前切片的合并结果添加到总的合并结果中
                        all_merged_clusters.extend(merged_clusters)

                    # 处理当前切片最终的剩余脉冲
                    last_toa = None
                    if current_data is not None and len(current_data) > 0:
                        # 确保 current_data 是 NumPy 数组
                        if not isinstance(current_data, np.ndarray):
                            try:
                                current_data = np.array(current_data)
                            except ValueError as ve:
                                self.logger.error(f"切片 {slice_idx + 1} 剩余数据无法转换为Numpy数组: {ve}")
                                current_data = None  # 标记为无法处理

                        # 检查数据维度是否正确
                        if current_data.ndim == 2 and current_data.shape[1] >= 5:
                            for point in current_data:
                                if last_toa is None:
                                    last_toa = point[4]
                                current_slice_pulse_data_remaining.append(
                                    {
                                        "类别": "remaining",
                                        "聚类维度": "——",
                                        "序号": "——",
                                        "切片内序号": "——",
                                        "载频": point[0],
                                        "脉宽": point[1],
                                        "方位角": point[2],
                                        "幅度": point[3],
                                        "到达时间": point[4],
                                        "到达时间差": (point[4] - last_toa) * 1000,
                                    }
                                )
                                last_toa = point[4]
                        elif current_data.ndim == 1 and len(current_data) >= 5:  # 单个脉冲数据
                            point = current_data
                            current_slice_pulse_data_remaining.append(
                                {
                                    "类别": "remaining",
                                    "聚类维度": "——",
                                    "序号": "——",
                                    "切片内序号": "——",
                                    "载频": point[0],
                                    "脉宽": point[1],
                                    "方位角": point[2],
                                    "幅度": point[3],
                                    "到达时间": point[4],
                                    "到达时间差": 0,
                                }
                            )
                        else:
                            self.logger.warning(f"切片 {slice_idx + 1} 的剩余脉冲数据格式不正确，无法保存。Shape: {current_data.shape}")

                    # 存储当前切片的脉冲数据
                    if current_slice_pulse_data_valid or current_slice_pulse_data_invalid or current_slice_pulse_data_remaining:
                        self.logger.info(f"切片 {slice_idx + 1} 存在脉冲数据")
                        self.all_pulse_data_by_slice[slice_idx] = (
                            current_slice_pulse_data_valid + current_slice_pulse_data_invalid + current_slice_pulse_data_remaining
                        )
                    else:
                        self.logger.info(f"切片 {slice_idx + 1} 没有脉冲数据")

                    # 存储当前切片的合并后脉冲数据
                    if merged_clusters:
                        for cluster in merged_clusters:
                            points_merged = cluster["cluster_data"]
                            last_toa = None
                            for point_idx, point in enumerate(points_merged):
                                if last_toa is None:
                                    last_toa = point[4]

                                pulse_data = {
                                    "类别": "merged",
                                    "合并序号": cluster["index_merge"],
                                    "载频": point[0],
                                    "脉宽": point[1],
                                    "方位角": point[2],
                                    "幅度": point[3],
                                    "到达时间": point[4],
                                    "到达时间差": (point[4] - last_toa) * 1000,
                                }
                                last_toa = point[4]
                                current_slice_pulse_data_merged.append(pulse_data)

                    # 存储当前切片的合并后脉冲数据
                    if current_slice_pulse_data_merged:
                        self.merged_pulse_data_by_slice[slice_idx] = current_slice_pulse_data_merged

                except Exception as e:
                    self.logger.error(f"处理切片数据时出错: {str(e)}")
                    continue

            return all_valid_clusters, all_merged_clusters

        except Exception as e:
            self.logger.error(f"聚类处理出错: {str(e)}")
            self.process_finished.emit(False)

    def _can_merge_clusters_pri_equal(self, cluster1: Dict, cluster2: Dict) -> bool:
        """判断两个聚类是否可以基于PRI相同条件合并

        合并条件：PRI可以提取且存在相同值，DOA在指定范围内

        Args:
            cluster1 (dict): 第一个聚类
            cluster2 (dict): 第二个聚类
            merge_params (dict, optional): 合并参数

        Returns:
            bool: 是否可以合并
        """
        try:
            # 获取聚类参数
            pri1 = cluster1.get("PRI", [])
            pri2 = cluster2.get("PRI", [])
            doa1_list = cluster1.get("DOA", [])
            doa2_list = cluster2.get("DOA", [])
            cf1 = cluster1.get("CF", [])
            cf2 = cluster2.get("CF", [])

            # 检查PRI是否都存在
            if not (pri1 and pri2):
                return False

            # 计算DOA差值
            doa_diff = abs(np.mean(doa1_list) - np.mean(doa2_list))

            # 检查CF列表间所有值的差是否都小于指定容差
            cf_tolerance = self.data_controller.pri_different_cf_tolerance
            cf_diff = False
            for var1 in cf1:
                for var2 in cf2:
                    if abs(var1 - var2) <= cf_tolerance:
                        cf_diff = True
                        break
                if cf_diff:
                    break

            if not cf_diff:
                return False

            # 检查是否有相同的PRI值
            pri_set1 = set(np.round(pri1, 1))  # 保留1位小数进行比较
            pri_set2 = set(np.round(pri2, 1))

            # 规则1: PRI相同且DOA在指定范围内，且时间交叠
            if pri_set1.intersection(pri_set2):
                doa_tolerance = self.data_controller.pri_equal_doa_tolerance
                if (doa_diff <= doa_tolerance) and self._check_toa_intersection(cluster1, cluster2):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"判断PRI相同合并条件时出错: {str(e)}")
            return False

    def _can_merge_clusters_pri_different(self, cluster1: Dict, cluster2: Dict) -> bool:
        """判断两个聚类是否可以基于PRI不同条件合并

        合并条件：PRI可以提取但不存在相同值，DOA和CF在指定范围内

        Args:
            cluster1 (dict): 第一个聚类
            cluster2 (dict): 第二个聚类
            merge_params (dict, optional): 合并参数

        Returns:
            bool: 是否可以合并
        """
        try:
            # 若输入的两个类别的DTOA识别结果都是常规雷达（即类别0），则不合并
            dtoa_label1 = cluster1.get("prediction", {}).get("dtoa_label", -1)
            dtoa_label2 = cluster2.get("prediction", {}).get("dtoa_label", -1)
            if dtoa_label1 == 0 and dtoa_label2 == 0:
                return False

            # 获取聚类参数
            pri1 = cluster1.get("PRI", [])
            pri2 = cluster2.get("PRI", [])
            doa1_list = cluster1.get("DOA", [])
            doa2_list = cluster2.get("DOA", [])
            cf1 = cluster1.get("CF", [])
            cf2 = cluster2.get("CF", [])

            # 检查PRI是否都存在
            if not (pri1 and pri2):
                return False

            # 计算DOA差值
            doa_diff = abs(np.mean(doa1_list) - np.mean(doa2_list))

            # 检查CF列表间所有值的差是否都小于指定容差
            cf_tolerance = self.data_controller.pri_different_cf_tolerance
            cf_diff = False
            for var1 in cf1:
                for var2 in cf2:
                    if abs(var1 - var2) <= cf_tolerance:
                        cf_diff = True
                        break
                if cf_diff:
                    break

            if not cf_diff:
                return False

            # 检查是否有相同的PRI值
            pri_set1 = set(np.round(pri1, 1))  # 保留1位小数进行比较
            pri_set2 = set(np.round(pri2, 1))

            # 规则2: PRI不同但DOA和CF在指定范围内，且时间交叠
            if not pri_set1.intersection(pri_set2):
                doa_tolerance = self.data_controller.pri_different_doa_tolerance
                if (doa_diff <= doa_tolerance) and self._check_toa_intersection(cluster1, cluster2):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"判断PRI不同合并条件时出错: {str(e)}")
            return False

    def _can_merge_clusters_pri_none(self, cluster1: Dict, cluster2: Dict) -> bool:
        """判断两个聚类是否可以基于PRI无法提取条件合并

        合并条件：PRI无法提取，DOA在指定范围内，且TOA有相交部分

        Args:
            cluster1 (dict): 第一个聚类
            cluster2 (dict): 第二个聚类
            merge_params (dict, optional): 合并参数

        Returns:
            bool: 是否可以合并
        """
        try:
            # 获取聚类参数
            pri1 = cluster1.get("PRI", [])
            pri2 = cluster2.get("PRI", [])
            doa1_list = cluster1.get("DOA", [])
            doa2_list = cluster2.get("DOA", [])
            cf1 = cluster1.get("CF", [])
            cf2 = cluster2.get("CF", [])

            # 检查PRI是否都不存在
            if pri1 or pri2:
                return False

            # 计算DOA差值
            doa_diff = abs(np.mean(doa1_list) - np.mean(doa2_list))

            # 检查CF列表间所有值的差是否都小于指定容差
            cf_tolerance = self.data_controller.pri_different_cf_tolerance
            cf_diff = False
            for var1 in cf1:
                for var2 in cf2:
                    if abs(var1 - var2) <= cf_tolerance:
                        cf_diff = True
                        break
                if cf_diff:
                    break

            if not cf_diff:
                return False

            # 规则3：PRI不全都存在但DOA在指定范围内，且它们的TOA有相交部分
            doa_tolerance = self.data_controller.pri_none_doa_tolerance
            if doa_diff <= doa_tolerance:
                # 检查TOA是否有相交部分
                if self._check_toa_intersection(cluster1, cluster2):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"判断PRI无法提取合并条件时出错: {str(e)}")
            return False

    def _merge_valid_clusters(self, all_valid_data: List[Dict]) -> List[Dict]:
        """合并有效聚类结果

        采用分层次合并策略：
        1. 先对所有类别执行合并条件一的判断：PRI可以提取且存在相同值
        2. 然后对剩余类别执行合并条件二的判断：PRI可以提取但不存在相同值
        3. 再对剩余类别执行合并条件三的判断：PRI无法提取

        Args:
            merge_params (dict, optional): 合并参数，包含三个规则的参数设置

        合并依据：
        1. PRI相同且DOA在指定范围内
        2. PRI不同但DOA和CF在指定范围内
        3. PRI不存在但DOA在指定范围内
        """
        try:
            if not all_valid_data:
                self.logger.info("没有有效聚类需要合并")
                return

            # 清空之前的合并结果
            self.merged_clusters = []

            # 创建聚类副本用于合并处理
            clusters_to_merge = all_valid_data.copy()
            merged_groups = []  # 存储合并组

            # 第一层：PRI相同条件合并
            self.logger.info("开始第一层合并：PRI相同条件")
            clusters_to_merge, level1_groups = self._merge_clusters_by_condition(clusters_to_merge, self._can_merge_clusters_pri_equal)
            merged_groups.extend(level1_groups)

            # 第二层：PRI不同条件合并
            self.logger.info("开始第二层合并：PRI不同条件")
            clusters_to_merge, level2_groups = self._merge_clusters_by_condition(clusters_to_merge, self._can_merge_clusters_pri_different)
            merged_groups.extend(level2_groups)

            # 第三层：PRI无法提取条件合并
            self.logger.info("开始第三层合并：PRI无法提取条件")
            clusters_to_merge, level3_groups = self._merge_clusters_by_condition(clusters_to_merge, self._can_merge_clusters_pri_none)
            merged_groups.extend(level3_groups)

            # 处理合并组，生成合并后数据
            merge_index = 1
            merged_clusters = []
            for group in merged_groups:
                if len(group) > 1:  # 只处理需要合并的组
                    merged_data = self._create_merged_cluster(group, merge_index)
                    if merged_data:
                        merged_clusters.append(merged_data)
                        merge_index += 1

                        self.logger.info(f"合并了 {len(group)} 个聚类，合并索引: {merge_index - 1}")

            self.logger.info(f"聚类合并完成，共生成 {len(merged_clusters)} 个合并结果")
            return merged_clusters

        except Exception as e:
            self.logger.error(f"聚类合并过程中出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")

    def _merge_clusters_by_condition(self, clusters_to_merge: List[dict], merge_condition_func: Callable) -> Tuple[List[dict], List[List[dict]]]:
        """根据指定条件合并聚类

        Args:
            clusters_to_merge (list): 待合并的聚类列表
            merge_condition_func: 合并条件判断函数
            merge_params (dict, optional): 合并参数

        Returns:
            tuple: (剩余未合并的聚类列表, 合并组列表)
        """
        try:
            remaining_clusters = clusters_to_merge.copy()
            merged_groups = []

            # 贪婪合并策略
            while remaining_clusters:
                # 弹出第一个聚类作为种子
                seed_cluster = remaining_clusters.pop(0)
                current_group = [seed_cluster]

                # 贪婪扩展：重复查找可合并的聚类直到没有新的可加入
                found_new = True
                while found_new:
                    found_new = False
                    i = 0

                    # 遍历剩余聚类
                    while i < len(remaining_clusters):
                        candidate_cluster = remaining_clusters[i]

                        # 检查候选聚类是否可以与当前组中的任一聚类合并
                        can_merge_with_group = False
                        for group_cluster in current_group:
                            if merge_condition_func(group_cluster, candidate_cluster):
                                can_merge_with_group = True
                                break

                        # 如果可以合并，加入组并从待处理列表中移除
                        if can_merge_with_group:
                            current_group.append(candidate_cluster)
                            remaining_clusters.pop(i)
                            found_new = True  # 标记找到新的可合并聚类
                            # 不增加i，因为列表长度已减少
                            self.logger.info("合并成功。")
                        else:
                            i += 1

                # 将完成的合并组加入结果
                merged_groups.append(current_group)

            # 提取未合并的聚类（长度为1的组）作为下一层的输入
            unmerged_clusters = []
            for group in merged_groups:
                if len(group) == 1:
                    unmerged_clusters.append(group[0])

            return unmerged_clusters, merged_groups

        except Exception as e:
            self.logger.error(f"按条件合并聚类时出错: {str(e)}")
            return clusters_to_merge, []

    def _check_toa_intersection(self, cluster1: Dict, cluster2: Dict) -> bool:
        """检查两个聚类的TOA时间范围是否有相交部分

        Args:
            cluster1 (dict): 第一个聚类数据
            cluster2 (dict): 第二个聚类数据

        Returns:
            bool: TOA时间范围是否有相交部分
        """
        try:
            # 获取聚类数据中的points数组
            cluster_data1 = cluster1.get("cluster_data", {})
            cluster_data2 = cluster2.get("cluster_data", {})

            points1 = cluster_data1.get("points", np.array([]))
            points2 = cluster_data2.get("points", np.array([]))

            if len(points1) == 0 or len(points2) == 0:
                return False

            # 提取TOA数据（第4列，索引为4）
            toa1 = points1[:, 4]
            toa2 = points2[:, 4]

            # 计算TOA时间范围
            toa1_min, toa1_max = np.min(toa1), np.max(toa1)
            toa2_min, toa2_max = np.min(toa2), np.max(toa2)

            # 检查时间范围是否有相交
            # 两个时间段相交的条件：max(start1, start2) < min(end1, end2)
            intersection_exists = max(toa1_min, toa2_min) < min(toa1_max, toa2_max)

            return intersection_exists

        except Exception as e:
            self.logger.error(f"检查TOA相交时出错: {str(e)}")
            return False

    def _create_merged_cluster(self, cluster_group, merge_index):
        """创建合并后的聚类数据

        Args:
            cluster_group: 要合并的聚类组
            merge_index: 合并索引

        Returns:
            dict: 合并后的数据结构
        """
        try:
            # 合并脉冲数据
            merged_pulse_data = []
            dim_list = []
            dim_idx_list = []

            for cluster in cluster_group:
                # 获取脉冲数据
                cluster_data = cluster.get("cluster_data", {})
                points = cluster_data.get("points", np.array([]))
                dim = cluster.get("dim_name", "unknown")
                dim_cluster_idx = cluster.get("total_cluster_count", "unknown")
                if len(points) > 0:
                    merged_pulse_data.append(points)
                    dim_list.append(dim)
                    dim_idx_list.append(dim_cluster_idx)

            # 提取参数
            self.logger.info(f"形状：{[np.shape(data) for data in merged_pulse_data]}")
            pulse_data = np.vstack([data for data in merged_pulse_data])
            self.logger.info(f"拼接后数据形状：{np.shape(pulse_data)}")
            pulse_data = pulse_data[np.argsort(pulse_data[:, 4])]
            merged_cf, merged_pw, merged_pri, merged_doa = self.data_controller._extract_parameters_after_merge(pulse_data)

            # 创建合并后数据结构
            merged_data = {
                "cluster_data": pulse_data,  # np.array
                "CF": f"{', '.join([f'{v:.0f}' for v in merged_cf])}",
                "PW": f"{', '.join([f'{v:.1f}' for v in merged_pw])}",
                "DOA": f"{np.mean(merged_doa):.0f}",  # DOA取均值
                "DTOA": f"{', '.join([f'{v:.1f}' for v in merged_pri])}",  # 脉宽，多值用逗号分隔
                "index_merge": merge_index,
                "merge_count": len(cluster_group),
                "dim_name": dim_list,
                "dim_cluster_idx": dim_idx_list,
                "time_ranges": self.cluster_processor.time_ranges,
            }

            return merged_data

        except Exception as e:
            self.logger.error(f"创建合并聚类数据时出错: {str(e)}")
            return None

    def _on_save_result_fs(self, only_valid: bool = False) -> Tuple[bool, str]:
        """保存识别结果到Excel文件

        Args:
            only_valid (bool, optional): 是否只保存有效的雷达信号结果。默认为False。

        Returns:
            Tuple[bool, str]: 是否成功，以及相关消息
        """
        try:
            self.logger.info(f"开始保存全速处理识别结果到目录: {self.save_dir}")

            # 创建保存目录
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir, exist_ok=True)

            # 从原始文件路径提取数据包名称
            if self.last_file_path:
                # 提取文件名并去掉扩展名
                data_package_name = os.path.splitext(os.path.basename(self.last_file_path))[0]
                # 包含参数指纹的文件名
                file_name = f"{data_package_name}_{self.current_param_fingerprint}_result.xlsx"
            else:
                # 如果没有原始文件路径，使用默认名称
                file_name = f"result_{self.current_param_fingerprint}.xlsx"

            file_path = os.path.join(self.save_dir, file_name)

            # 准备数据
            results_data = []
            result_merged_data = []

            # 遍历所有切片的识别结果
            for cluster_idx, cluster_result in enumerate(self.valid_clusters):
                # 提取需要保存的数据
                dim_name = cluster_result.get("dim_name", "")
                prediction = cluster_result.get("prediction", {})

                row_data = {
                    "切片索引": cluster_result.get("current_slice_idx", 0) + 1,
                    "雷达序号": cluster_result.get("cluster_idx_per_slice_to_save", 0),
                    # '雷达序号': cluster_idx + 1,
                    "聚类ID": cluster_result.get("total_cluster_count", 0),
                    "聚类维度": dim_name,
                    "载频/MHz": f"{', '.join([f'{v:.0f}' for v in cluster_result.get('CF', [])])}",  # 载频，多值用逗号分隔
                    "脉宽/us": f"{', '.join([f'{v:.1f}' for v in cluster_result.get('PW', [])])}",  # 脉宽，多值用逗号分隔
                    "DOA/°": f"{np.mean(cluster_result.get('DOA', [])):.0f}",  # DOA取均值
                    "PRI/us": f"{', '.join([f'{v:.1f}' for v in cluster_result.get('PRI', [])])}",  # PRI，多值用逗号分隔
                    "PA预测结果": self.PA_LABEL_NAMES.get(prediction.get("pa_label", 5), "未知"),
                    "PA预测概率": f"{'\n'.join([f'{self.PA_LABEL_NAMES[label]}: {conf:.4f}' for label, conf in prediction.get('pa_dict', {}).items()])}",
                    "DTOA预测结果": self.DTOA_LABEL_NAMES.get(prediction.get("dtoa_label", 4), "未知"),
                    "DTOA预测概率": f"{'\n'.join([f'{self.DTOA_LABEL_NAMES[label]}: {conf:.4f}' for label, conf in prediction.get('dtoa_dict', {}).items()])}",
                }

                results_data.append(row_data)

            for cluster_idx, cluster_result in enumerate(self.merged_clusters):
                # 提取需要保存的数据
                row_data = {
                    "切片索引": cluster_result.get("current_slice_index", 0) + 1,
                    "雷达序号": cluster_result.get("index_merge", 0),
                    "原聚类索引": cluster_result.get("dim_cluster_idx", 0),
                    "载频/MHz": cluster_result.get("CF", "未知"),
                    "脉宽/us": cluster_result.get("PW", "未知"),
                    "DOA/°": cluster_result.get("DOA", "未知"),
                    "PRI/us": cluster_result.get("DTOA", "未知"),
                }

                result_merged_data.append(row_data)

            # 创建DataFrame并保存
            if results_data:
                df = pd.DataFrame(results_data)
                df_merged = pd.DataFrame(result_merged_data)

                # 准备参数信息表
                params_info = {
                    "参数名": [
                        "epsilon_CF",
                        "epsilon_PW",
                        "min_pts",
                        "pa_threshold",
                        "dtoa_threshold",
                        "pa_weight",
                        "dtoa_weight",
                        "threshold",
                        "pri_equal_doa_tolerance",
                        "pri_different_doa_tolerance",
                        "pri_different_cf_tolerance",
                        "pri_none_doa_tolerance",
                    ],
                    "参数值": [
                        self.epsilon_CF,
                        self.epsilon_PW,
                        self.min_pts,
                        self.pa_threshold,
                        self.dtoa_threshold,
                        self.pa_weight,
                        self.dtoa_weight,
                        self.threshold,
                        self.pri_equal_doa_tolerance,
                        self.pri_different_doa_tolerance,
                        self.pri_different_cf_tolerance,
                        self.pri_none_doa_tolerance,
                    ],
                }
                params_df = pd.DataFrame(params_info)

                # 直接创建或覆盖文件，不使用追加模式
                with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name="识别结果", index=False)
                    df_merged.to_excel(writer, sheet_name="合并结果", index=False)
                    params_df.to_excel(writer, sheet_name="参数信息", index=False)

                self.logger.info(f"全速处理识别结果已保存到: {file_path}")
                return True, f"成功保存{len(results_data)}条识别结果和{len(result_merged_data)}条合并结果"
            else:
                return False, "没有有效的识别结果可保存"

        except Exception as e:
            self.logger.error(f"保存识别结果出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return False, f"保存失败: {str(e)}"

    def _on_save_pulse_data_fs(self):
        """保存每个切片的详细脉冲数据到Excel文件

        Returns:
            Tuple[bool, str]: 是否成功，以及相关消息
        """
        try:
            self.logger.info(f"开始保存全速处理脉冲数据到目录: {self.save_dir}")

            # 创建保存目录
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir, exist_ok=True)

            # 从原始文件路径提取数据包名称
            if self.last_file_path:
                # 提取文件名并去掉扩展名
                data_package_name = os.path.splitext(os.path.basename(self.last_file_path))[0]
                # 包含参数指纹的文件名
                file_name = f"{data_package_name}_{self.current_param_fingerprint}_pulse_data.xlsx"
            else:
                # 如果没有原始文件路径，使用默认名称
                file_name = f"pulse_data_{self.current_param_fingerprint}.xlsx"

            file_path = os.path.join(self.save_dir, file_name)

            # 检查是否有脉冲数据可保存
            if not hasattr(self, "all_pulse_data_by_slice") or not self.all_pulse_data_by_slice:
                self.logger.warning("没有收集到脉冲数据可供保存。")
                return False, "没有脉冲数据可保存"

            # 使用 ExcelWriter 写入多个sheet
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                # 按照切片索引排序写入
                sorted_slice_indices = sorted(self.all_pulse_data_by_slice.keys())
                for slice_idx in sorted_slice_indices:
                    pulse_data_list = self.all_pulse_data_by_slice[slice_idx]
                    if pulse_data_list:  # 确保列表不为空
                        # 创建DataFrame
                        df = pd.DataFrame(pulse_data_list)
                        # 确保列顺序
                        column_order = ["类别", "聚类维度", "序号", "切片内序号", "载频", "脉宽", "方位角", "幅度", "到达时间", "到达时间差"]
                        # 检查DataFrame是否包含所有必须列
                        if all(col in df.columns for col in column_order):
                            # 重新排列列顺序
                            df = df[column_order]
                        else:
                            missing_cols = [col for col in column_order if col not in df.columns]
                            self.logger.warning(f"切片 {slice_idx + 1} 的脉冲数据DataFrame缺少列: {missing_cols}")
                        # 写入空列
                        sheet_name = f"Slice_{slice_idx + 1}"
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    else:
                        self.logger.debug(f"切片 {slice_idx + 1} 没有脉冲数据可保存。")

            self.logger.info(f"全速处理脉冲数据已保存到: {file_path}")
            return True, "成功保存脉冲数据"

        except Exception as e:
            self.logger.error(f"保存脉冲数据出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return False, f"保存脉冲数据失败: {str(e)}"

    def _on_save_merged_pulse_data_fs(self):
        """保存每个切片的合并脉冲数据到Excel文件

        Returns:
            Tuple[bool, str]: 是否成功，以及相关消息
        """
        try:
            self.logger.info(f"开始保存全速处理合并脉冲数据到目录: {self.save_dir}")

            # 创建保存目录
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir, exist_ok=True)

            # 从原始文件路径提取数据包名称
            if self.last_file_path:
                # 提取文件名并去掉扩展名
                data_package_name = os.path.splitext(os.path.basename(self.last_file_path))[0]
                # 包含参数指纹的文件名
                file_name = f"{data_package_name}_{self.current_param_fingerprint}_merged_pulse_data.xlsx"
            else:
                # 如果没有原始文件路径，使用默认名称
                file_name = f"merged_pulse_data_{self.current_param_fingerprint}.xlsx"

            file_path = os.path.join(self.save_dir, file_name)

            # 检查是否有合并脉冲数据可保存
            if not hasattr(self, "merged_pulse_data_by_slice") or not self.merged_pulse_data_by_slice:
                self.logger.warning("没有收集到合并脉冲数据可供保存。")
                return False, "没有合并脉冲数据可保存"

            # 使用 ExcelWriter 写入多个sheet
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                # 按照切片索引排序写入
                sorted_slice_indices = sorted(self.merged_pulse_data_by_slice.keys())
                for slice_idx in sorted_slice_indices:
                    merged_pulse_data_list = self.merged_pulse_data_by_slice[slice_idx]
                    if merged_pulse_data_list:  # 确保列表不为空
                        # 创建DataFrame
                        df = pd.DataFrame(merged_pulse_data_list)
                        # 确保列顺序
                        column_order = ["类别", "合并序号", "载频", "脉宽", "方位角", "幅度", "到达时间", "到达时间差"]
                        # 检查DataFrame是否包含所有必须列
                        if all(col in df.columns for col in column_order):
                            # 重新排列列顺序
                            df = df[column_order]
                        else:
                            missing_cols = [col for col in column_order if col not in df.columns]
                            self.logger.warning(f"切片 {slice_idx + 1} 的合并脉冲数据DataFrame缺少列: {missing_cols}")
                        # 写入sheet
                        sheet_name = f"Merged_Slice_{slice_idx + 1}"
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    else:
                        self.logger.debug(f"切片 {slice_idx + 1} 没有合并脉冲数据可保存。")

            self.logger.info(f"全速处理合并脉冲数据已保存到: {file_path}")
            return True, "成功保存合并脉冲数据"

        except Exception as e:
            self.logger.error(f"保存合并脉冲数据出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return False, f"保存合并脉冲数据失败: {str(e)}"
