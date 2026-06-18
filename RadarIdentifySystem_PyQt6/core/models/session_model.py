# -*- coding: utf-8 -*-
"""Session 级模型选择数据契约。

该模块只定义 session 内部持有的模型路径快照和候选展示对象，不依赖 UI、
全局配置或持久化层。

Example:
    >>> selection = SessionModelSelection.from_dict({"pa_model_path": "E:/m/pa.pt"})
    >>> selection.pa_model_path
    'E:/m/pa.pt'
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


def _normalize_model_path(value: object) -> str | None:
    """将外部模型路径值归一化为有效字符串或 None。"""
    if not isinstance(value, str):
        return None
    stripped_value = value.strip()
    return stripped_value or None


@dataclass
class SessionModelSelection:
    """Session 级模型选择快照。

    Attributes:
        pa_model_path: 当前 session 选择的 PA 模型路径，未选择时为 None。
        dtoa_model_path: 当前 session 选择的 DTOA 模型路径，未选择时为 None。
    """

    pa_model_path: str | None = None
    dtoa_model_path: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "SessionModelSelection":
        """从字典恢复 session 模型选择快照。

        Args:
            payload [Mapping[str, Any] | None]: 外部传入的模型选择字典，仅识别已定义字段。

        Returns:
            SessionModelSelection: 恢复后的模型选择快照，非法或缺失路径按 None 处理。

        Raises:
            无显式抛出异常。

        Example:
            >>> selection = SessionModelSelection.from_dict({"dtoa_model_path": "E:/m/dtoa.pt"})
            >>> selection.dtoa_model_path
            'E:/m/dtoa.pt'
        """
        data = payload if isinstance(payload, Mapping) else {}
        pa_model_path = data.get("pa_model_path")
        dtoa_model_path = data.get("dtoa_model_path")

        # 只接受非空字符串路径，避免外部载荷把非法对象带入纯数据模型。
        return cls(
            pa_model_path=_normalize_model_path(pa_model_path),
            dtoa_model_path=_normalize_model_path(dtoa_model_path),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。

        Returns:
            dict[str, Any]: 包含 PA 与 DTOA 模型路径的纯字典。

        Raises:
            无显式抛出异常。

        Example:
            >>> SessionModelSelection(pa_model_path="E:/m/pa.pt").to_dict()["pa_model_path"]
            'E:/m/pa.pt'
        """
        return asdict(self)


@dataclass(frozen=True)
class ActiveModelCandidate:
    """可供 session 选择的激活模型候选项。

    Attributes:
        model_type: 模型类型标识，例如 "pa" 或 "dtoa"。
        path: 模型文件路径。
        display_name: 面向 UI 展示的模型名称。

    Example:
        >>> ActiveModelCandidate("pa", "E:/m/pa.pt", "PA 模型").display_name
        'PA 模型'
    """

    model_type: str
    path: str
    display_name: str
