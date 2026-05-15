"""导入数据后台线程。"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.models.pulse_batch import PulseBatch, COL_CF, COL_PW, COL_DOA, COL_PA, COL_TOA
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.preprocess import preprocess

LOGGER = logging.getLogger(__name__)


class ImportWorker(QThread):
    """Excel数据导入与预处理后台线程。

    功能描述：
        在子线程中读取 Excel 文件，提取指定列数据并组合为 Numpy 数组。
        随后调用 core/preprocess.py 中的纯函数进行数据清洗与修正，
        并将结果装配到指定的 Session 对象中。

    参数说明：
        session (ProcessingSession): 需要写入数据的会话对象。
        file_path (str): Excel 文件路径。
        parent (QObject | None): 挂载的 Qt 父节点。

    属性说明：
        finished_signal (pyqtSignal): 导入完成信号，携带 session_id、成功标志和消息。
    """

    finished_signal = pyqtSignal(str, bool, str)

    def __init__(
        self,
        session: ProcessingSession,
        file_path: str,
        parent: QObject | None = None
    ) -> None:
        """初始化导入工作线程。

        参数说明：
            session (ProcessingSession): 会话实例。
            file_path (str): 文件路径。
            parent (QObject | None): 挂载的 Qt 父节点。
        """
        super().__init__(parent)
        self._session = session
        self._file_path = file_path

    def run(self) -> None:
        """执行导入与预处理任务。

        功能描述：
            读取 Excel，提取 CF/PW/DOA/PA/TOA 列数据，转换 TOA 单位为 ms。
            调用 preprocess() 获取清洗后的 PreprocessResult。
            将结果赋给 Session，并发送完成信号。
        """
        try:
            LOGGER.info("开始导入并预处理数据", extra={"session_id": self._session.session_id})
            df = pd.read_excel(self._file_path)
            data_tmp = df.values

            # 提取需要的列 (与旧版保持一致：CF, PW, DOA, PA, TOA)
            CF = data_tmp[:, 1]
            PW = data_tmp[:, 2]
            DOA = data_tmp[:, 4]
            PA = data_tmp[:, 5]
            TOA = data_tmp[:, 7]  # 保持原始单位 0.1us，不转换

            # 构造按照预定义顺序对齐的数组
            raw_data = np.zeros((len(data_tmp), 5))
            raw_data[:, COL_CF] = CF
            raw_data[:, COL_PW] = PW
            raw_data[:, COL_DOA] = DOA
            raw_data[:, COL_PA] = PA
            raw_data[:, COL_TOA] = TOA
            
            self._session.raw_batch = PulseBatch(raw_data)

            # 调用 core 中的预处理纯函数
            preprocess_res = preprocess(
                data=raw_data,
                source_path=self._file_path,
                source_type="excel",
                slice_length=2_500_000,  # 250ms = 2,500,000 × 0.1us
                session_id=self._session.session_id
            )

            # 将预处理结果写入 Session
            with self._session.lock:
                self._session.raw_batch = PulseBatch(raw_data)
                self._session.preprocess_result = preprocess_res
                # 推进全局阶段
                self._session.stage = ProcessingStage.PREPROCESSED

            LOGGER.info("数据导入与预处理完成", extra={"session_id": self._session.session_id})
            self.finished_signal.emit(self._session.session_id, True, f"导入成功，共 {preprocess_res.total_pulses} 条脉冲")

        except Exception as e:
            LOGGER.error("数据导入失败: %s", str(e), extra={"session_id": self._session.session_id})
            self.finished_signal.emit(self._session.session_id, False, f"导入失败: {str(e)}")
