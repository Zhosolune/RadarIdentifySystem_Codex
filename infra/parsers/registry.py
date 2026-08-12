"""脉冲文件解析器静态注册表。"""

from __future__ import annotations

from collections.abc import Callable

from infra.parsers.base import PulseSourceParser
from infra.parsers.bin_parser import BinPulseParser
from infra.parsers.excel_parser import ExcelPulseParser


_PARSER_FACTORIES: dict[str, Callable[[], PulseSourceParser]] = {
    "excel": ExcelPulseParser,
    "bin": BinPulseParser,
}


def create_pulse_parser(source_type: str) -> PulseSourceParser:
    """按来源类型创建无状态解析器。

    Args:
        source_type [str]: 来源类型键，如 ``excel`` 或 ``bin``。

    Returns:
        PulseSourceParser: 对应格式的解析器实例。

    Raises:
        ValueError: 来源类型尚未注册时抛出。

    Example:
        >>> type(create_pulse_parser("excel")).__name__
        'ExcelPulseParser'
    """
    normalized_type = source_type.strip().lower()
    factory = _PARSER_FACTORIES.get(normalized_type)
    if factory is None:
        raise ValueError(f"暂不支持解析 {source_type} 文件")
    return factory()


def supports_source_type(source_type: str) -> bool:
    """判断来源类型是否已经注册解析器。

    Args:
        source_type [str]: 来源类型键。

    Returns:
        bool: 已注册返回 True，否则返回 False。

    Example:
        >>> supports_source_type("bin")
        True
    """
    return source_type.strip().lower() in _PARSER_FACTORIES

