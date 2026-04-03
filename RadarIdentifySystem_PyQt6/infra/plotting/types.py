"""绘图模块数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import numpy as np

# 默认切片长度
_DEFAULT_SLICE_LENGTH_MS: Final[float] = 250.0
_DIMENSION_ORDER: Final[tuple[str, ...]] = ("CF", "PW", "PA", "DTOA", "DOA")


@dataclass(frozen=True)
class PlotSpec:
    """单维度绘图规格。

    描述了某个特定维度（如 PA、PW）在绘制散点图时所需的高度、宽度
    以及其纵向刻度量程范围（y_min ~ y_max）。

    Attributes:
        y_min (float): 该维度对应 Y 轴的最小值界限。
        y_max (float): 该维度对应 Y 轴的最大值界限。
        img_height (int): 目标生成的二值图像素高度。
        img_width (int): 目标生成的二值图像素宽度。
    """

    y_min: float
    y_max: float
    img_height: int
    img_width: int


@dataclass(frozen=True)
class PlotProfile:
    """多维度绘图规格集合。

    聚合了当次切片或聚类任务中所需所有维度（CF, PW, PA 等）的绘图规格，
    并记录了默认的时间切片长度基准。

    Attributes:
        specs (dict[str, PlotSpec]): 各个目标维度名称与其绘图规格的映射字典。
        slice_length_ms (float): 整个集合预设的缺省 X 轴时间基准跨度（微秒）。
    """

    specs: dict[str, PlotSpec]
    slice_length_ms: float = _DEFAULT_SLICE_LENGTH_MS

    def get_spec(self, dim_name: str) -> PlotSpec:
        """获取指定维度绘图规格。

        从当前配置集合中提取对应维度的规格对象。

        Args:
            dim_name (str): 目标维度名称（如 "CF", "PW", "PA" 等）。

        Returns:
            PlotSpec: 指定维度对应的规格对象。

        Raises:
            KeyError: 当传入的维度名称在配置中不存在时抛出。
        """

        # 从字典中读取指定维度配置
        spec = self.specs.get(dim_name)
        # 若规格不存在则抛出异常
        if spec is None:
            raise KeyError(f"未找到维度 {dim_name} 的绘图规格")
        return spec


@dataclass(frozen=True)
class MergePalette:
    """合并图调色板。

    存储将聚类类别索引映射到对应 RGB 颜色的字典关系，支持将其转换为 NumPy 查找表。

    Attributes:
        colors (dict[int, tuple[int, int, int]]): 类别索引到 (R, G, B) 颜色元组的映射字典。
    """

    colors: dict[int, tuple[int, int, int]]

    def to_lut(self) -> np.ndarray:
        """转换为颜色查找表。

        将字典格式的调色板配置转换为 numpy 查找表（LUT）数组，便于后续快速通过高级索引进行颜色映射。

        Returns:
            np.ndarray: 维度为 (N, 3) 的无符号 8 位整型数组，N 为配置中最大的索引号加一，未定义的索引默认为全黑 [0,0,0]。
        """

        # 计算调色板中最大的索引号
        max_index = max(self.colors) if self.colors else 0
        # 初始化默认全黑的查找表
        lut = np.zeros((max_index + 1, 3), dtype=np.uint8)
        # 遍历配置将RGB值填入查找表
        for index, rgb in self.colors.items():
            lut[index] = np.array(rgb, dtype=np.uint8)
        return lut


@dataclass
class RenderedImageBundle:
    """渲染结果集合。

    封装由底层引擎渲染产出的图像集合字典以及关联的附带元数据。

    Attributes:
        images (dict[str, np.ndarray]): 维度标识（如 "CF", "PW"）与其对应图像数组的映射字典。
        metadata (dict[str, object]): 记录生成时的环境变量（如时间窗 time_range、波段 band）的元数据字典。
    """

    images: dict[str, np.ndarray]
    metadata: dict[str, object] = field(default_factory=dict)
