"""Bin文件解析模块

负责解析二进制PDW文件，支持：
- 分块读取
- PDW记录解码
- 波段自动分流（L/S/C）
- 临时文件缓存
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, Optional
from .log_manager import LogManager
from .data_processor import DataProcessor


class BinFileParser:
    """Bin文件解析器

    解析二进制PDW文件，按波段分流并处理数据。

    Attributes:
        CHUNK_SIZE: 每次读取的PDW记录数
        PDW_RECORD_SIZE: 每条PDW记录的字节数（16个uint16 = 32字节）
    """

    CHUNK_SIZE = 100000  # 每次读取10万条PDW
    PDW_RECORD_SIZE = 32  # 每条PDW记录32字节

    # 波段频率范围 (MHz)
    BAND_RANGES = {
        "L": (1000, 2000),
        "S": (2000, 4000),
        "C": (4000, 8000),
        "X": (8000, float("inf")),
    }

    def __init__(self):
        self.logger = LogManager()
        self.processor = DataProcessor()
        self._temp_files: Dict[str, str] = {}  # 波段 -> 临时文件路径
        self._temp_dir: str = ""  # 临时文件目录
        self._strategy: str = "amplitude"  # 解析策略：amplitude(比幅) / interferometer(干涉仪)

    def set_strategy(self, strategy: str):
        """设置解析策略
        
        Args:
            strategy: 'amplitude' (比幅，使用ACSAOA/ACSPA) 或 
                      'interferometer' (干涉仪，使用PCSAOA/PCSPA)
        """
        if strategy in ("amplitude", "interferometer"):
            self._strategy = strategy
            self.logger.info(f"解析策略已设置为: {'比幅' if strategy == 'amplitude' else '干涉仪'}")

    def parse(self, file_path: str) -> Dict:
        """解析Bin文件

        分块读取并解码bin文件，按波段分流后各自处理，
        将处理后的数据写入临时文件。

        Args:
            file_path: bin文件路径

        Returns:
            Dict: {
                "success": bool,
                "source_file": str,
                "bands": {
                    "L": {"temp_file": str, "result": dict} | None,
                    "S": {...} | None,
                    "C": {...} | None,
                },
                "discarded_count": int,
                "drop_stats": Dict[str, int]
            }
        """
        try:
            self.logger.info(f"开始解析Bin文件: {file_path}")

            # 创建临时文件目录（bin文件所在目录下的Temp文件夹）
            bin_dir = os.path.dirname(file_path)
            self._temp_dir = os.path.join(bin_dir, "Temp")
            if not os.path.exists(self._temp_dir):
                os.makedirs(self._temp_dir)
                self.logger.info(f"创建临时文件目录: {self._temp_dir}")

            # 清理之前的临时文件
            self._cleanup_temp_files()

            # 初始化波段数据缓冲区和统计信息
            # band_valid_buffers: 存储处理后的有效数据块 (只包含最终6列)
            band_valid_buffers: Dict[str, list] = {"L": [], "S": [], "C": []}
            
            # band_stats: 存储流式统计信息
            band_stats = {
                band: {
                    "total_pulses": 0,
                    "drop_f26": 0,
                    "drop_pa": 0,
                    "drop_doa": 0,
                    "time_min": float("inf"),
                    "time_max": float("-inf")
                } for band in ["L", "S", "C"]
            }
            
            discarded_count = 0
            global_drop_stats = {"f26": 0, "pa": 0, "doa": 0}

            # 分块读取并解码
            with open(file_path, "rb") as f:
                while True:
                    # 读取一块数据
                    chunk = f.read(self.CHUNK_SIZE * self.PDW_RECORD_SIZE)
                    if not chunk:
                        break

                    # 解码PDW记录 (返回float32格式的中间数据)
                    pdw_data = self._decode_chunk(chunk)
                    
                    if pdw_data is None or len(pdw_data) == 0:
                        continue

                    # 按波段分流
                    for band, (low, high) in self.BAND_RANGES.items():
                        if band == "X":
                            continue  # X波段暂不支持，丢弃
                        
                        # RF 在第0列
                        mask = (pdw_data[:, 0] >= low) & (pdw_data[:, 0] < high)
                        band_chunk = pdw_data[mask]
                        
                        if len(band_chunk) > 0:
                            stats = band_stats[band]
                            stats["total_pulses"] += len(band_chunk)
                            
                            # 提取列
                            # [RF, PW, TOA, F26, ACSAOA_raw, ACSPA_raw, PCSAOA_raw, PCSPA_raw]
                            RF = band_chunk[:, 0]
                            PW = band_chunk[:, 1]
                            TOA = band_chunk[:, 2]
                            F26 = band_chunk[:, 3]
                            ACSAOA_raw = band_chunk[:, 4]
                            ACSPA_raw = band_chunk[:, 5]
                            PCSAOA_raw = band_chunk[:, 6]
                            PCSPA_raw = band_chunk[:, 7]
                            
                            # 初始化有效性掩码
                            if self._strategy == "amplitude":
                                # 比幅策略
                                acsaoa_valid = (F26 != 1)
                                acspa_valid = (ACSPA_raw != 255 ) & (ACSPA_raw <= 120)
                                
                                drop_f26 = int(np.sum(~acsaoa_valid))
                                drop_pa = int(np.sum(~acspa_valid))
                                
                                stats["drop_f26"] += drop_f26
                                stats["drop_pa"] += drop_pa
                                global_drop_stats["f26"] += drop_f26
                                global_drop_stats["pa"] += drop_pa
                                
                                final_valid_mask = acsaoa_valid & acspa_valid
                                
                                # 计算最终字段
                                DOA = ACSAOA_raw * 1.40625
                                PA = ACSPA_raw
                            else:
                                # 干涉仪策略
                                pcsaoa_valid = (PCSAOA_raw != 65535)
                                pcspa_valid = (PCSPA_raw != 255) & (PCSPA_raw <= 120)
                                
                                drop_doa = int(np.sum(~pcsaoa_valid))
                                drop_pa = int(np.sum(~pcspa_valid))
                                
                                stats["drop_doa"] += drop_doa
                                stats["drop_pa"] += drop_pa
                                global_drop_stats["doa"] += drop_doa
                                global_drop_stats["pa"] += drop_pa
                                
                                final_valid_mask = pcsaoa_valid & pcspa_valid
                                
                                # 计算最终字段
                                DOA = PCSAOA_raw * 0.01
                                PA = PCSPA_raw

                            # 提取并保存有效数据
                            valid_count = np.sum(final_valid_mask)
                            if valid_count > 0:
                                processed_chunk = np.column_stack((
                                    RF[final_valid_mask],
                                    PW[final_valid_mask],
                                    DOA[final_valid_mask],
                                    PA[final_valid_mask],
                                    TOA[final_valid_mask],
                                    F26[final_valid_mask]
                                ))
                                band_valid_buffers[band].append(processed_chunk)

                            # 更新时间统计
                            if len(TOA) > 0:
                                stats["time_min"] = min(stats["time_min"], np.min(TOA[final_valid_mask]))
                                stats["time_max"] = max(stats["time_max"], np.max(TOA[final_valid_mask]))

                    # 统计丢弃的数据（<1000MHz 或 >=8000MHz）
                    discard_mask = (pdw_data[:, 0] < 1000) | (pdw_data[:, 0] >= 8000)
                    discarded_count += np.sum(discard_mask)

            # 处理各波段最终结果
            results = {}
            for band in ["L", "S", "C"]:
                stats = band_stats[band]
                valid_buffers = band_valid_buffers[band]
                
                if stats["total_pulses"] > 0: # 只要有原始脉冲就算有数据
                    
                    # 合并有效数据
                    if valid_buffers:
                        processed_data = np.vstack(valid_buffers)
                    else:
                        processed_data = np.empty((0, 6), dtype=np.float32)
                        
                    self.logger.info(f"{band}波段: 原始脉冲{stats['total_pulses']}, 有效脉冲{len(processed_data)}")

                    # 计算时间范围
                    if stats["time_max"] > stats["time_min"]:
                        time_range = float(stats["time_max"] - stats["time_min"])
                    else:
                        time_range = 0.0

                    # 计算预计切片数
                    slice_length = 250
                    slice_count = int(np.ceil(time_range / slice_length)) if time_range > 0 else 0

                    # 构造 band_drop_stats
                    band_drop_stats = {
                        "f26": stats["drop_f26"],
                        "pa": stats["drop_pa"],
                        "doa": stats["drop_doa"]
                    }

                    # 构造完整的 result 字典
                    result = {
                        "success": True,
                        "message": "解析成功",
                        "total_pulses": stats["total_pulses"],
                        "filtered_pulses": stats["total_pulses"] - len(processed_data),
                        "time_range": time_range,
                        "slice_count": slice_count,
                        "band": f"{band}波段",
                        "clusters": [],
                        "drop_stats": band_drop_stats,
                        "strategy": self._strategy
                    }

                    if len(processed_data) > 0:
                        # 写入临时文件 (只保存前5列标准数据: RF, PW, DOA, PA, TOA)
                        temp_file = self._save_to_temp_file(band, processed_data[:, :5])
                        self._temp_files[band] = temp_file
                        results[band] = {
                            "temp_file": temp_file,
                            "result": result
                        }
                    else:
                        # 有原始脉冲但全被过滤了
                         results[band] = {
                            "temp_file": None,
                            "result": result
                        }
                else:
                    results[band] = None

            self.logger.info(f"Bin文件解析完成，丢弃脉冲数: {discarded_count}")

            return {
                "success": True,
                "source_file": file_path,
                "bands": results,
                "discarded_count": discarded_count,
                "drop_stats": global_drop_stats 
            }

        except Exception as e:
            self.logger.error(f"Bin文件解析失败: {str(e)}")
            # 发生错误时也要尝试清理内存
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                "success": False,
                "source_file": file_path,
                "bands": {},
                "discarded_count": 0,
                "drop_stats": {},
                "error": str(e)
            }

    def _export_to_excel(self, data: np.ndarray, filename: str, desc: str):
        """导出数据到Excel文件（用于调试）

        Args:
            data: 数据数组
            filename: 文件名
            desc: 描述
        """
        try:
            excel_path = os.path.join(self._temp_dir, filename)
            df = pd.DataFrame(data, columns=["CF(MHz)", "PW(us)", "DOA(度)", "PA(dB)", "TOA(us)", "F26", "DTOA(us)"])
            df.to_excel(excel_path, index=False)
            self.logger.info(f"【调试】已导出{desc}到: {excel_path}")
        except Exception as e:
            self.logger.warning(f"导出Excel失败: {str(e)}")

    def _decode_chunk(self, chunk: bytes) -> Optional[np.ndarray]:
        """解码一块二进制数据，返回包含所有必要校验字段的中间数据

        不进行具体的策略过滤，而是提取所有可能需要的字段，供后续分波段处理。

        返回数据列结构 (9列):
        0: RF (MHz)
        1: PW (us)
        2: TOA (ms)
        3: F26 (原始标志)
        4: ACSAOA_raw (低8位)
        5: ACSPA_raw (低8位)
        6: PCSAOA_raw (原始值)
        7: PCSPA_raw (高8位)
        8: Type (原始类型，用于调试)

        Args:
            chunk: 二进制数据块

        Returns:
            Optional[np.ndarray]: 包含原始校验字段的数据矩阵，如果无效则返回None
        """
        try:
            # 转换为大端序uint16数组
            data = np.frombuffer(chunk, dtype=">u2")  # >u2 = big-endian uint16

            # 重塑为 [N, 16] 的记录数组
            num_records = len(data) // 16
            if num_records == 0:
                return None
            data = data[:num_records * 16].reshape(-1, 16)

            # ===== 第一步：基础有效性过滤 =====
            # 1. Type值过滤（取低4位）：只有3、5、6为有效
            record_type = data[:, 0] & 0x0F
            # 2. RF不能为0
            rf = data[:, 2]
            valid_mask = ((record_type == 3) | (record_type == 5) | (record_type == 6)) & (rf != 0)
            data = data[valid_mask]

            if len(data) == 0:
                return None

            # ===== 第二步：提取各字段的原始值 =====
            # Word 3 (索引2): RF 载频, LSB 1MHz
            RF = data[:, 2].astype(np.float32)
            
            # Word 5-6 (索引4-5): TOA = TOAHighWord * 65536 + TOALowWord, LSB 0.1us
            TOA_HIGH = data[:, 4].astype(np.uint32) << 16
            TOA_LOW = data[:, 5].astype(np.uint32)
            TOA = (TOA_HIGH + TOA_LOW).astype(np.float64) * 0.1 / 1000  # TOA保持双精度以防溢出或精度损失
            
            # Word 7 (索引6): PW 脉宽, LSB 0.05us
            PW = data[:, 6].astype(np.float32) * 0.05
            
            # Word 8 (索引7): ACSAOA（取低8位）, LSB 1.40625°
            ACSAOA_raw = data[:, 7] & 0xFF
            
            # Word 12 (索引11): 高8位=PCSPA, 低8位=ACSPA
            ACSPA_raw = data[:, 11] & 0xFF
            PCSPA_raw = (data[:, 11] >> 8) & 0xFF

            # Word 14 (索引13): PCSAOA, LSB 0.01°
            PCSAOA_raw = data[:, 13]
            
            # Word 16 (索引15): F26标志位（取第10位，从第0位开始计数）
            F26 = (data[:, 15] >> 10) & 0x01

            # 组合为中间格式 [RF, PW, TOA, F26, ACSAOA_raw, ACSPA_raw, PCSAOA_raw, PCSPA_raw]
            # 注意：大部分列转为 float32 节省内存，TOA保持 float64
            result = np.column_stack((
                RF, PW, TOA.astype(np.float32), 
                F26.astype(np.float32), 
                ACSAOA_raw.astype(np.float32), 
                ACSPA_raw.astype(np.float32), 
                PCSAOA_raw.astype(np.float32), 
                PCSPA_raw.astype(np.float32)
            ))
            return result

        except Exception as e:
            self.logger.warning(f"解码数据块失败: {str(e)}")
            return None

    def _save_to_temp_file(self, band: str, data: np.ndarray) -> str:
        """将数据保存到临时文件

        Args:
            band: 波段名
            data: 处理后的数据

        Returns:
            str: 临时文件路径
        """
        temp_file = os.path.join(self._temp_dir, f"radar_band_{band}.npy")
        np.save(temp_file, data)
        self.logger.debug(f"已保存{band}波段数据到临时文件: {temp_file}")
        return temp_file

    def load_band_data(self, band: str) -> Optional[np.ndarray]:
        """从临时文件加载波段数据

        Args:
            band: 波段名 (L/S/C)

        Returns:
            np.ndarray: 处理后的数据，如果不存在返回None
        """
        temp_file = self._temp_files.get(band)
        if temp_file and os.path.exists(temp_file):
            data = np.load(temp_file)
            self.logger.info(f"已从临时文件加载{band}波段数据，数据量: {len(data)}")
            return data
        return None

    def _cleanup_temp_files(self):
        """清理临时文件"""
        for band, temp_file in self._temp_files.items():
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    self.logger.debug(f"已删除临时文件: {temp_file}")
            except Exception as e:
                self.logger.warning(f"删除临时文件失败: {str(e)}")
        self._temp_files.clear()

    def cleanup(self):
        """清理所有资源，程序退出时调用"""
        self._cleanup_temp_files()

