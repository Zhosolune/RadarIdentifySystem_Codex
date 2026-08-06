# -*- coding: utf-8 -*-
"""core/models/processing_session.py — 单次处理会话数据容器。

ProcessingSession 是随行数据背包（Data Carrier），而非管理者：
  - 各阶段算法的输出结果依次写入对应字段
  - 可以同时存在多个独立实例（天然支持并行处理不同数据包）
  - 不持有任何 Qt/UI/线程引用

各阶段结果字段填充时机：
  ┌──────────────┬──────────────────────────────────────────────────┐
  │ 字段          │ 由哪个工作流填入                                   │
  ├──────────────┼──────────────────────────────────────────────────┤
  │ raw_batch    │ import_workflow（P07/P08）                        │
  │ preprocess.. │ slice_workflow → preprocess()                    │
  │ slice_result │ slice_workflow → slice_by_toa()                  │
  │ cluster_..   │ identify_workflow → run_clustering()（P04）       │
  │ recognition..│ identify_workflow → evaluate_cluster()（P05）    │
  │ merge_result │ merge_workflow → execute_merge_plan()（P06）      │
  └──────────────┴──────────────────────────────────────────────────┘
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional
import threading

from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult, SliceResult
from core.models.dashboard_info import FileDashboardInfo
from core.models.cluster_result import ClusteringResult
from core.models.recognition_result import RecognitionResult
from core.models.merge_result import MergePlan, MergeResult
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.data_package import DataPackage


# -------------------------------------------------------------------
# 处理阶段枚举
# -------------------------------------------------------------------

class ProcessingStage(Enum):
    """处理流程阶段枚举。

    功能描述：
        表示一个 ProcessingSession 在“全局范围内”已完成到哪个阶段，
        仅用于工作流驱动逻辑中的门槛判定。
        当聚类、识别、合并按切片独立执行时，局部进度由切片级状态单独表达。
    """
    CREATED = auto()       # 刚创建，无任何数据
    IMPORTED = auto()      # 已导入原始数据（raw_batch 有效）
    PREPROCESSED = auto()  # 已完成 PA 清洗与 TOA 翻折修复
    SLICED = auto()        # 已完成时间切片（slice_result 有效）
    CLUSTERED = auto()     # 已完成 CF/PW 聚类（cluster_result 有效）
    RECOGNIZED = auto()    # 已完成识别与参数提取（recognition_result 有效）
    MERGED = auto()        # 已完成合并（merge_result 有效）
    EXPORTED = auto()      # 已导出结果文件


class ProcessingMode(Enum):
    """Session 处理模式。

    Attributes:
        SLICE_INTERACTIVE: 由用户逐切片操作的交互式处理模式。
        FULL_SPEED: 自动连续完成切片、识别、合并和保存的全速模式。
    """

    SLICE_INTERACTIVE = "slice_interactive"
    FULL_SPEED = "full_speed"


class SliceProcessStatus(Enum):
    """切片级处理状态枚举。

    功能描述：
        表示单个切片在聚类、识别、合并等局部流程中的执行状态。
    """

    NOT_STARTED = auto()  # 尚未开始
    RUNNING = auto()      # 正在执行
    SUCCEEDED = auto()    # 执行成功
    FAILED = auto()       # 执行失败


@dataclass
class SliceProcessingState:
    """单个切片的局部处理状态。

    功能描述：
        聚合记录单个切片在聚类、识别、合并三个局部阶段的执行状态，
        供工作流推进与 UI 判定统一读取。

    Attributes:
        cluster_status (SliceProcessStatus): 当前切片的聚类状态。
        recognition_status (SliceProcessStatus): 当前切片的识别状态。
        merge_status (SliceProcessStatus): 当前切片的合并状态。
        merge_judgment_suppressed (bool): 是否保持在人工重置后的未判别状态。
        last_cluster_error (str | None): 最近一次聚类失败消息。
        last_recognition_error (str | None): 最近一次识别失败消息。
        last_merge_error (str | None): 最近一次合并失败消息。
    """

    cluster_status: SliceProcessStatus = SliceProcessStatus.NOT_STARTED
    recognition_status: SliceProcessStatus = SliceProcessStatus.NOT_STARTED
    merge_status: SliceProcessStatus = SliceProcessStatus.NOT_STARTED
    merge_judgment_suppressed: bool = False
    last_cluster_error: str | None = None
    last_recognition_error: str | None = None
    last_merge_error: str | None = None


# -------------------------------------------------------------------
# 会话数据容器
# -------------------------------------------------------------------

@dataclass
class ProcessingSession:
    """单次处理的数据容器（随行背包模式）。

    功能描述：
        将一次完整处理流程（导入→预处理→切片→聚类→识别→合并→导出）
        产生的所有中间产物打包在同一个对象中。
        每次处理实例化一份新的 ProcessingSession，多个实例之间完全独立，
        天然支持并行处理不同数据包（无共享可变状态）。

    属性：
        session_id (str): 会话唯一标识（8位 UUID 前缀），用于日志与事件 payload 区分。
        data_package_id (str | None): 来源数据池数据包 ID。
        processing_mode (ProcessingMode): Session 处理模式。
        source_path (str): 数据文件路径。
        source_type (str): 数据来源类型，"excel" / "bin" / "mat"。
        data_format (str | None): 来源数据格式，例如 Excel 的 ``old`` / ``new``。
        created_at (datetime): 会话创建时间戳。
        display_name (str): 会话展示名称，默认使用源文件名或 session_id。
        remark (str): 会话备注信息，未填写时使用“无”。
        last_opened_at (datetime): 最近打开时间戳。
        restored_from_store (bool): 是否由持久化存储恢复。
        config_snapshot (SessionConfigSnapshot): 当前 session 的子配置快照。
        model_selection (SessionModelSelection): 当前 session 的模型选择快照。
        stage (ProcessingStage): 当前已完成的最高阶段。
        raw_batch (PulseBatch | None): 导入并归一化列顺序后的原始脉冲数据。
        preprocess_result (PreprocessResult | None): PA 清洗 + TOA 翻折修复结果。
        dashboard_info (FileDashboardInfo | None): 文件仪表盘摘要信息。
        slice_result (SliceResult | None): TOA 时间切片结果。
        cluster_result (Any | None): CF/PW 聚类结果（P04 落地后替换为具体类型）。
        slice_processing_states (dict[int, SliceProcessingState]): 切片级局部状态映射。
        recognition_result (Any | None): 识别与参数提取结果（P05 落地后替换）。
        merge_plan (MergePlan | None): 用户点击合并后按当前策略生成的切片计划。
        merge_result (MergeResult | None): 与识别结果独立保存的合并结果。
        full_speed_locked (bool): 全速任务是否已经启动并冻结配置。
        exported_file_path (str): 全速任务成功写出的 Excel 文件路径。

    参数说明：
        source_path (str): 文件路径，默认空串。
        source_type (str): 来源类型，默认 "unknown"。

    注意：
        - 写入权限仅属于 app/workflows/ 中的工作流，其他模块只读。
        - 不持有任何 Qt/UI/线程引用，可在无 Qt 环境构造与传递。
    """

    # ── 元信息 ──────────────────────────────────────────────────────
    session_id: str = field(
        default_factory=lambda: uuid.uuid4().hex[:8]
    )
    data_package_id: str | None = None
    processing_mode: ProcessingMode = ProcessingMode.SLICE_INTERACTIVE
    source_path: str = ""
    source_type: str = "unknown"
    data_format: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    display_name: str = ""
    remark: str = "无"
    last_opened_at: datetime = field(default_factory=datetime.now)
    restored_from_store: bool = False
    config_snapshot: SessionConfigSnapshot = field(default_factory=SessionConfigSnapshot.default)
    model_selection: SessionModelSelection = field(default_factory=SessionModelSelection)

    # ── 流程状态 ─────────────────────────────────────────────────────
    stage: ProcessingStage = field(default=ProcessingStage.CREATED)

    # ── P03：导入与预处理产物 ─────────────────────────────────────────
    raw_batch: Optional[PulseBatch] = field(default=None)
    preprocess_result: Optional[PreprocessResult] = field(default=None)
    dashboard_info: Optional[FileDashboardInfo] = field(default=None)
    slice_result: Optional[SliceResult] = field(default=None)

    # ── P04：聚类产物（待 P04 完成后替换 Any 为具体类型） ────────────────
    cluster_result: Optional[ClusteringResult] = field(default=None)
    slice_processing_states: dict[int, SliceProcessingState] = field(default_factory=dict)

    # ── P05：识别与参数产物 ──────────────────────────
    recognition_result: Optional[RecognitionResult] = field(default=None)

    # ── P06：合并判别计划与独立合并产物 ──────────────────────────────────
    merge_plan: Optional[MergePlan] = field(default=None)
    merge_result: Optional[MergeResult] = field(default=None)

    # ── 全速处理持久化状态 ─────────────────────────────────────────────
    # 一旦开始执行就保持锁定；失败、取消和重启后的重试仍使用同一份参数快照。
    full_speed_locked: bool = False
    exported_file_path: str = ""

    # ── 线程安全锁 ───────────────────────────────────────────────────
    lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        """补齐 session 展示名称。"""
        if not self.display_name and self.source_path:
            self.display_name = Path(self.source_path).name
        elif not self.display_name:
            self.display_name = f"Session {self.session_id}"

    @classmethod
    def from_data_package(
        cls,
        package: DataPackage,
        *,
        processing_mode: ProcessingMode = ProcessingMode.SLICE_INTERACTIVE,
        display_name: str = "",
        remark: str = "无",
    ) -> "ProcessingSession":
        """从数据池数据包创建共享只读输入的独立 Session。

        Args:
            package [DataPackage]: 已注册并冻结输入数组的数据包。
            processing_mode [ProcessingMode]: 新 Session 的处理模式。
            display_name [str]: Session 展示名称，留空时沿用数据包名称。
            remark [str]: Session 备注，默认使用“无”。

        Returns:
            ProcessingSession: 拥有独立配置和结果槽位、共享数据包输入的 Session。

        Raises:
            无显式抛出异常。

        Example:
            >>> import numpy as np
            >>> from core.models.data_package import DataPackage
            >>> from core.models.pulse_batch import PulseBatch
            >>> from core.models.slice_result import PreprocessResult
            >>> package = DataPackage(
            ...     PulseBatch(np.empty((0, 6))),
            ...     PreprocessResult(np.empty((0, 6))),
            ... )
            >>> ProcessingSession.from_data_package(package).data_package_id == package.package_id
            True
        """
        return cls(
            data_package_id=package.package_id,
            processing_mode=processing_mode,
            source_path=package.source_path,
            source_type=package.source_type,
            data_format=package.data_format,
            display_name=display_name.strip() or package.display_name,
            remark=remark.strip() or "无",
            stage=ProcessingStage.PREPROCESSED,
            raw_batch=package.raw_batch,
            preprocess_result=package.preprocess_result,
            dashboard_info=package.dashboard_info,
        )

    # -------------------------------------------------------------------
    # 只读属性（便捷查询，不允许外部赋值）
    # -------------------------------------------------------------------

    @property
    def is_imported(self) -> bool:
        """是否已完成数据导入（raw_batch 有效）。

        返回值说明：
            bool: raw_batch 不为 None 则为 True。
        """
        return self.raw_batch is not None

    @property
    def is_sliced(self) -> bool:
        """是否已完成切片（slice_result 有效）。

        返回值说明：
            bool: slice_result 不为 None 则为 True。
        """
        return self.slice_result is not None

    @property
    def is_clustered(self) -> bool:
        """是否已完成全量聚类。

        返回值说明：
            bool: 所有切片均聚类成功则为 True。
        """
        return self.are_all_slices_clustered()

    @property
    def is_recognized(self) -> bool:
        """是否已完成识别（recognition_result 有效）。

        返回值说明：
            bool: recognition_result 不为 None 则为 True。
        """
        return self.recognition_result is not None

    @property
    def is_merged(self) -> bool:
        """是否已完成合并（merge_result 有效）。

        返回值说明：
            bool: merge_result 不为 None 则为 True。
        """
        return self.merge_result is not None

    @property
    def slice_count(self) -> int:
        """当前切片数量，未切片时返回 0。

        返回值说明：
            int: 切片总数。
        """
        return self.slice_result.slice_count if self.slice_result else 0

    @property
    def band(self) -> str | None:
        """预处理推断的频段，未预处理时返回 None。

        返回值说明：
            str | None: 频段名称（如 "C波段"）或 None。
        """
        return self.preprocess_result.band if self.preprocess_result else None

    def reset_slice_processing_states(self, slice_count: int) -> None:
        """重置切片级状态映射。

        功能描述：
            在切片结果发生整体变化后，按新的切片数量初始化全部局部状态，
            同时清空过期的下游阶段状态。

        Args:
            slice_count (int): 当前有效切片数量。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片数量为负数时抛出。
        """
        if slice_count < 0:
            raise ValueError("slice_count 不能为负数")

        # 重建切片状态映射
        self.slice_processing_states = {
            index: SliceProcessingState()
            for index in range(slice_count)
        }

        # 清空下游结果对象
        self.cluster_result = None
        self.recognition_result = None
        self.merge_plan = None
        self.merge_result = None

    def reset_to_preprocessed_state(self) -> None:
        """重置到预处理完成状态，清空所有下游产物。

        功能描述：
            保留 raw_batch、preprocess_result 和 dashboard_info，清空切片及
            之后的所有阶段产物，
            将 stage 回退到 PREPROCESSED。用于 session 关闭再启用时避免旧产物残留。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> session = ProcessingSession()
            >>> session.stage = ProcessingStage.CLUSTERED
            >>> session.reset_to_preprocessed_state()
            >>> session.stage.name
            'PREPROCESSED'
        """
        # 数据池输入保持不变，只清空每个 Session 独占的计算产物。
        self.slice_result = None
        self.cluster_result = None
        self.slice_processing_states = {}
        self.recognition_result = None
        self.merge_plan = None
        self.merge_result = None
        # 回退阶段到预处理完成。
        self.stage = ProcessingStage.PREPROCESSED

    def get_slice_processing_state(self, slice_index: int) -> SliceProcessingState:
        """获取指定切片的局部状态。

        功能描述：
            当状态不存在时按需补建，确保调用方总能拿到可写状态对象。

        Args:
            slice_index (int): 切片索引。

        Returns:
            SliceProcessingState: 指定切片的局部状态对象。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")

        # 按需补建切片状态
        if slice_index not in self.slice_processing_states:
            self.slice_processing_states[slice_index] = SliceProcessingState()
        return self.slice_processing_states[slice_index]

    def is_slice_clustered(self, slice_index: int) -> bool:
        """判断指定切片是否已完成聚类。

        Args:
            slice_index (int): 切片索引。

        Returns:
            bool: 当前切片聚类成功则返回 True。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        return (
            self.get_slice_processing_state(slice_index).cluster_status
            == SliceProcessStatus.SUCCEEDED
        )

    def is_slice_recognized(self, slice_index: int) -> bool:
        """判断指定切片是否已完成识别。

        Args:
            slice_index (int): 切片索引。

        Returns:
            bool: 当前切片识别成功则返回 True。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        return (
            self.get_slice_processing_state(slice_index).recognition_status
            == SliceProcessStatus.SUCCEEDED
        )

    def mark_slice_cluster_running(self, slice_index: int) -> None:
        """标记指定切片正在执行聚类。

        Args:
            slice_index (int): 切片索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        slice_state = self.get_slice_processing_state(slice_index)

        # 更新聚类运行状态
        slice_state.cluster_status = SliceProcessStatus.RUNNING
        slice_state.last_cluster_error = None

    def mark_slice_cluster_succeeded(self, slice_index: int) -> None:
        """标记指定切片聚类成功。

        Args:
            slice_index (int): 切片索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        slice_state = self.get_slice_processing_state(slice_index)

        # 更新聚类成功状态
        slice_state.cluster_status = SliceProcessStatus.SUCCEEDED
        slice_state.last_cluster_error = None

    def mark_slice_cluster_failed(self, slice_index: int, error_msg: str) -> None:
        """标记指定切片聚类失败。

        Args:
            slice_index (int): 切片索引。
            error_msg (str): 失败原因。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        slice_state = self.get_slice_processing_state(slice_index)

        # 更新聚类失败状态
        slice_state.cluster_status = SliceProcessStatus.FAILED
        slice_state.last_cluster_error = error_msg

    def mark_slice_recognition_running(self, slice_index: int) -> None:
        """标记指定切片正在执行识别。

        Args:
            slice_index (int): 切片索引。
        """
        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.recognition_status = SliceProcessStatus.RUNNING
        slice_state.last_recognition_error = None

    def mark_slice_recognition_pending(self, slice_index: int) -> None:
        """标记指定切片识别尚未开始。

        Args:
            slice_index (int): 切片索引。
        """
        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.recognition_status = SliceProcessStatus.NOT_STARTED
        slice_state.last_recognition_error = None

    def mark_slice_recognition_succeeded(self, slice_index: int) -> None:
        """标记指定切片识别成功。

        Args:
            slice_index (int): 切片索引。
        """
        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.recognition_status = SliceProcessStatus.SUCCEEDED
        slice_state.last_recognition_error = None

    def mark_slice_recognition_failed(self, slice_index: int, error_msg: str) -> None:
        """标记指定切片识别失败。

        Args:
            slice_index (int): 切片索引。
            error_msg (str): 失败原因。
        """
        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.recognition_status = SliceProcessStatus.FAILED
        slice_state.last_recognition_error = error_msg

    def reset_slice_identification_results(self, slice_index: int) -> None:
        """重置指定切片的聚类、识别及其派生合并结果。

        该操作只移除目标切片的数据，保留其它切片结果，并将目标切片恢复为
        尚未识别状态，以便使用更新后的参数或配置重新执行完整识别流程。

        Args:
            slice_index [int]: 需要重置的 0-based 切片索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
            IndexError: 当切片结果不存在或索引超出当前切片范围时抛出。

        Example:
            >>> import numpy as np
            >>> from core.models.processing_session import ProcessingSession
            >>> from core.models.slice_result import SingleSlice, SliceResult
            >>> session = ProcessingSession()
            >>> empty_slice = SingleSlice(0, np.empty((0, 6)), (0.0, 1.0))
            >>> session.slice_result = SliceResult([empty_slice])
            >>> session.mark_slice_recognition_succeeded(0)
            >>> session.reset_slice_identification_results(0)
            >>> session.is_slice_recognized(0)
            False
        """
        if slice_index < 0:
            raise ValueError("slice_index 不能为负数")
        if self.slice_result is None or slice_index >= self.slice_result.slice_count:
            raise IndexError("slice_index 超出当前切片范围")

        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.cluster_status = SliceProcessStatus.NOT_STARTED
        slice_state.recognition_status = SliceProcessStatus.NOT_STARTED
        slice_state.last_cluster_error = None
        slice_state.last_recognition_error = None

        # 聚类和识别结果按切片独立存储，只移除当前目标，保留其它切片缓存。
        if self.cluster_result is not None:
            self.cluster_result.slice_results.pop(slice_index, None)
            if not self.cluster_result.slice_results:
                self.cluster_result = None
        if self.recognition_result is not None:
            self.recognition_result.slice_results.pop(slice_index, None)
            if not self.recognition_result.slice_results:
                self.recognition_result = None

        # 合并计划和结果依赖本轮识别来源，重置识别时必须同步失效。
        self.clear_slice_merge_results(slice_index)
        self.stage = ProcessingStage.SLICED

    def mark_slice_merge_running(self, slice_index: int) -> None:
        """标记指定切片正在执行合并。

        Args:
            slice_index [int]: 目标切片的 0-based 索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.merge_status = SliceProcessStatus.RUNNING
        slice_state.last_merge_error = None

    def mark_slice_merge_succeeded(self, slice_index: int) -> None:
        """标记指定切片合并成功。

        Args:
            slice_index [int]: 目标切片的 0-based 索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.merge_status = SliceProcessStatus.SUCCEEDED
        slice_state.last_merge_error = None

    def mark_slice_merge_failed(self, slice_index: int, error_msg: str) -> None:
        """标记指定切片合并失败并记录原因。

        Args:
            slice_index [int]: 目标切片的 0-based 索引。
            error_msg [str]: 合并失败原因。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        slice_state = self.get_slice_processing_state(slice_index)
        slice_state.merge_status = SliceProcessStatus.FAILED
        slice_state.last_merge_error = error_msg

    def clear_slice_merge_results(self, slice_index: int) -> None:
        """清除指定切片依赖旧识别结果生成的合并计划与结果。

        Args:
            slice_index [int]: 需要失效合并结果的 0-based 切片索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        slice_state = self.get_slice_processing_state(slice_index)

        # 合并计划与结果均依赖当前识别代次；识别重跑或策略切换时必须同时失效。
        slice_state.merge_status = SliceProcessStatus.NOT_STARTED
        slice_state.merge_judgment_suppressed = False
        slice_state.last_merge_error = None
        if self.merge_plan is not None:
            self.merge_plan.slice_plans.pop(slice_index, None)

            # 容器不再含任何切片计划时恢复None，保持is_merged等状态判断语义清晰。
            if not self.merge_plan.slice_plans:
                self.merge_plan = None
        if self.merge_result is None:
            return
        self.merge_result.slice_results.pop(slice_index, None)

        # 清理合并派生数据不会触碰cluster_result或recognition_result。
        if not self.merge_result.slice_results:
            self.merge_result = None

    def reset_slice_merge_state(self, slice_index: int) -> None:
        """重置指定切片并保持在尚未执行合并判别的状态。

        Args:
            slice_index [int]: 需要重置的 0-based 切片索引。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 当切片索引为负数时抛出。
        """
        self.clear_slice_merge_results(slice_index)
        # 人工重置与识别失效不同：普通界面刷新不得立即重新生成合并计划。
        self.get_slice_processing_state(slice_index).merge_judgment_suppressed = True

    def are_all_slices_clustered(self) -> bool:
        """判断全部切片是否已完成聚类。

        Returns:
            bool: 全部切片均聚类成功时返回 True。
        """
        if self.slice_count <= 0:
            return False

        # 校验全部切片状态
        return all(
            self.is_slice_clustered(slice_index)
            for slice_index in range(self.slice_count)
        )

    @property
    def clustered_slice_count(self) -> int:
        """返回已完成聚类的切片数量。

        Returns:
            int: 聚类成功的切片总数。
        """
        return sum(
            1
            for slice_index in range(self.slice_count)
            if self.is_slice_clustered(slice_index)
        )

    def __repr__(self) -> str:
        """简洁的会话摘要字符串，便于日志输出。

        返回值说明：
            str: 摘要字符串。
        """
        return (
            f"ProcessingSession("
            f"id={self.session_id}, "
            f"stage={self.stage.name}, "
            f"band={self.band}, "
            f"slices={self.slice_count}, "
            f"src={self.source_path!r}"
            f")"
        )
