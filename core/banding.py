"""统一脉冲数据的 L/S/C 波段拆分规则。

本模块只处理归一化后的 CF 数值，不关心数据来自 Excel、BIN 或其他格式。
"""

from __future__ import annotations

import numpy as np

from core.models.pulse_batch import COL_CF, PULSE_COLUMN_COUNT


BAND_LABELS: dict[str, str] = {
    "L": "L波段",
    "S": "S波段",
    "C": "C波段",
}
"""稳定波段键到用户可见名称的映射。"""

_BAND_RANGES: tuple[tuple[str, float, float], ...] = (
    ("L", 1000.0, 2000.0),
    ("S", 2000.0, 4000.0),
    ("C", 4000.0, 8000.0),
)


def split_pulse_indices_by_band(data: np.ndarray) -> dict[str, np.ndarray]:
    """按每行 CF 将统一脉冲数据拆成 L/S/C 索引。

    返回索引保持源文件中的行顺序；低于 1000MHz 或不低于 8000MHz 的
    数据不进入任何结果组。

    Args:
        data [np.ndarray]: shape=(N, 6) 的统一脉冲数据。

    Returns:
        dict[str, np.ndarray]: 波段键到一维行索引数组的映射，始终包含 L/S/C。

    Raises:
        ValueError: 输入不是统一六列二维数组时抛出。

    Example:
        >>> rows = np.array([[1500, 1, 1, 1, 1, 1], [5000, 1, 1, 1, 1, 2]])
        >>> {key: value.tolist() for key, value in split_pulse_indices_by_band(rows).items()}
        {'L': [0], 'S': [], 'C': [1]}
    """
    if data.ndim != 2 or data.shape[1] != PULSE_COLUMN_COUNT:
        raise ValueError(
            f"波段拆分输入必须为 shape=(N, {PULSE_COLUMN_COUNT})，"
            f"实际 shape={data.shape}"
        )

    cf_values = data[:, COL_CF]
    return {
        band: np.flatnonzero((cf_values >= low) & (cf_values < high))
        for band, low, high in _BAND_RANGES
    }

