"""参数提取结果数据模型。

本模块只定义识别通过类的参数提取结果契约，不包含任何提取算法或线程调度逻辑。

Example:
    构造一个包含 CF 和 DOA 典型值的参数结果：
    >>> result = ExtractedClusterParams(cf_values=[1000.0], doa_values=[25.0])
    >>> result.cf_values
    [1000.0]
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ExtractedClusterParams:
    """单个识别通过类的参数提取结果。

    该类用于挂载到 `ClusterRecognition.extracted_params`，四类参数均使用列表表达，
    以支持同一识别类内存在多个典型值的情况。

    Attributes:
        cf_values [list[float]]: CF 典型值列表，单位 MHz。
        pw_values [list[float]]: PW 典型值列表，单位 us。
        pri_values [list[float]]: PRI 典型值列表，单位 us。
        doa_values [list[float]]: DOA 典型值列表，单位度；当前由均值形成单元素列表。

    Example:
        >>> params = ExtractedClusterParams(
        ...     cf_values=[1000.0, 1100.0],
        ...     pw_values=[1.0],
        ...     pri_values=[10.0],
        ...     doa_values=[25.0],
        ... )
        >>> params.pri_values
        [10.0]
    """

    cf_values: list[float] = field(default_factory=list)
    pw_values: list[float] = field(default_factory=list)
    pri_values: list[float] = field(default_factory=list)
    doa_values: list[float] = field(default_factory=list)
