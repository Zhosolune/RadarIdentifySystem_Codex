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
  │ merge_result │ merge_workflow → merge_clusters()（P06）          │
  └──────────────┴──────────────────────────────────────────────────┘
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional
import threading

from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult, SliceResult
from core.models.cluster_result import ClusteringResult


# -------------------------------------------------------------------
# 处理阶段枚举
# -------------------------------------------------------------------

class ProcessingStage(Enum):
    """处理流程阶段枚举。

    功能描述：
        表示一个 ProcessingSession 当前已完成到哪个阶段，
        用于工作流驱动逻辑中的合法性判定（例如：未切片前禁止聚类）。
    """
    CREATED = auto()       # 刚创建，无任何数据
    IMPORTED = auto()      # 已导入原始数据（raw_batch 有效）
    PREPROCESSED = auto()  # 已完成 PA 清洗与 TOA 翻折修复
    SLICED = auto()        # 已完成时间切片（slice_result 有效）
    CLUSTERED = auto()     # 已完成 CF/PW 聚类（cluster_result 有效）
    RECOGNIZED = auto()    # 已完成识别与参数提取（recognition_result 有效）
    MERGED = auto()        # 已完成合并（merge_result 有效）
    EXPORTED = auto()      # 已导出结果文件


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
        source_path (str): 数据文件路径。
        source_type (str): 数据来源类型，"excel" / "bin" / "mat"。
        created_at (datetime): 会话创建时间戳。
        stage (ProcessingStage): 当前已完成的最高阶段。
        raw_batch (PulseBatch | None): 导入并归一化列顺序后的原始脉冲数据。
        preprocess_result (PreprocessResult | None): PA 清洗 + TOA 翻折修复结果。
        slice_result (SliceResult | None): TOA 时间切片结果。
        cluster_result (Any | None): CF/PW 聚类结果（P04 落地后替换为具体类型）。
        recognition_result (Any | None): 识别与参数提取结果（P05 落地后替换）。
        merge_result (Any | None): 合并结果（P06 落地后替换）。

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
    source_path: str = ""
    source_type: str = "unknown"
    created_at: datetime = field(default_factory=datetime.now)

    # ── 流程状态 ─────────────────────────────────────────────────────
    stage: ProcessingStage = field(default=ProcessingStage.CREATED)

    # ── P03：导入与预处理产物 ─────────────────────────────────────────
    raw_batch: Optional[PulseBatch] = field(default=None)
    preprocess_result: Optional[PreprocessResult] = field(default=None)
    slice_result: Optional[SliceResult] = field(default=None)

    # ── P04：聚类产物（待 P04 完成后替换 Any 为具体类型） ────────────────
    cluster_result: Optional[ClusteringResult] = field(default=None)

    # ── P05：识别与参数产物（待 P05 完成后替换） ──────────────────────────
    # TODO(P05): 替换为 RecognitionResult
    recognition_result: Optional[Any] = field(default=None)

    # ── P06：合并产物（待 P06 完成后替换） ────────────────────────────────
    # TODO(P06): 替换为 MergeResult
    merge_result: Optional[Any] = field(default=None)

    # ── 线程安全锁 ───────────────────────────────────────────────────
    lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

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
        """是否已完成聚类（cluster_result 有效）。

        返回值说明：
            bool: cluster_result 不为 None 则为 True。
        """
        return self.cluster_result is not None

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
