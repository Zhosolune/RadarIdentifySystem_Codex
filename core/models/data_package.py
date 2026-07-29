"""数据池中的只读数据包模型。

数据包是解析与预处理结果的唯一所有者。交互式处理 Session 和全速处理
Session 只引用数据包，不再分别复制或持久化同一份输入数据。

Example:
    >>> import numpy as np
    >>> from core.models.pulse_batch import PulseBatch
    >>> from core.models.slice_result import PreprocessResult
    >>> batch = PulseBatch(np.empty((0, 6)), "demo.xlsx", "excel", 0)
    >>> package = DataPackage(
    ...     raw_batch=batch,
    ...     preprocess_result=PreprocessResult(np.empty((0, 6))),
    ... )
    >>> bool(package.package_id)
    True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import uuid

from core.models.dashboard_info import FileDashboardInfo
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult


@dataclass
class DataPackage:
    """保存一包已解析、预处理并冻结的雷达脉冲数据。

    Attributes:
        package_id: 数据包全局唯一标识。
        display_name: 数据池中展示的名称。
        source_path: 原始文件路径。
        source_type: 原始文件类型，例如 ``excel``。
        created_at: 数据包创建时间。
        data_format: 来源文件的显式格式，例如 Excel 的 ``old`` 或 ``new``。
        raw_batch: 解析器归一化后的六列原始脉冲批次。
        preprocess_result: 清洗和 TOA 修正后的预处理结果。
        dashboard_info: 数据包摘要信息。
    """

    raw_batch: PulseBatch
    preprocess_result: PreprocessResult
    dashboard_info: FileDashboardInfo | None = None
    package_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    display_name: str = ""
    source_path: str = ""
    source_type: str = "unknown"
    created_at: datetime = field(default_factory=datetime.now)
    data_format: str | None = None

    def __post_init__(self) -> None:
        """补齐来源信息并冻结输入数组。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 数据包 ID 为空时抛出。
        """
        if not isinstance(self.package_id, str) or not self.package_id.strip():
            raise ValueError("package_id 不能为空")

        # 以归一化批次的来源信息作为数据包缺省来源，避免调用方重复传值。
        self.source_path = self.source_path or self.raw_batch.source_path
        if not self.source_type or self.source_type == "unknown":
            self.source_type = self.raw_batch.source_type
        if not self.display_name:
            self.display_name = (
                Path(self.source_path).name
                if self.source_path
                else f"数据包 {self.package_id[:8]}"
            )
        if self.dashboard_info is None:
            self.dashboard_info = self.preprocess_result.dashboard_info

        # 数据池输入一经注册即只读；不同 Session 可以安全共享同一数组引用。
        self.raw_batch.data.flags.writeable = False
        self.preprocess_result.data.flags.writeable = False

    @property
    def pulse_count(self) -> int:
        """返回预处理后的有效脉冲数量。

        Returns:
            int: 有效脉冲行数。
        """
        return self.preprocess_result.remaining_pulses

    @property
    def band(self) -> str | None:
        """返回预处理识别出的频段。

        Returns:
            str | None: 频段名称，无法判断时返回 None。
        """
        return self.preprocess_result.band
