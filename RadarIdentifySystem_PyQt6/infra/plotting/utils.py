"""绘图辅助工具函数。"""

from __future__ import annotations

from typing import Final

import numpy as np

from core.models.pulse_batch import COL_CF, COL_DOA, COL_PA, COL_PW, COL_TOA
from .types import MergePalette, PlotProfile, PlotSpec, _DEFAULT_SLICE_LENGTH_MS


_BASE_SPECS: Final[dict[str, PlotSpec]] = {
    "PA": PlotSpec(y_min=40, y_max=120, img_height=80, img_width=400),
    "DTOA": PlotSpec(y_min=0, y_max=3000, img_height=250, img_width=500),
    "PW": PlotSpec(y_min=0, y_max=300, img_height=200, img_width=400),
    "DOA": PlotSpec(y_min=0, y_max=360, img_height=120, img_width=400),
}

_CF_BAND_SPECS: Final[dict[str, PlotSpec]] = {
    "L波段": PlotSpec(y_min=1000, y_max=2000, img_height=400, img_width=400),
    "S波段": PlotSpec(y_min=2000, y_max=4000, img_height=400, img_width=400),
    "C波段": PlotSpec(y_min=4000, y_max=8000, img_height=400, img_width=400),
    "X波段": PlotSpec(y_min=8000, y_max=12000, img_height=400, img_width=400),
}

_DEFAULT_CF_SPEC: Final[PlotSpec] = _CF_BAND_SPECS["C波段"]

_DEFAULT_MERGE_PALETTE: Final[MergePalette] = MergePalette(
    colors={
        0: (0, 0, 0),
        1: (255, 0, 0),
        2: (0, 0, 255),
        3: (0, 255, 0),
        4: (255, 165, 0),
        5: (255, 0, 255),
        6: (0, 255, 255),
        7: (255, 255, 0),
        8: (255, 192, 203),
        9: (255, 140, 0),
        10: (200, 200, 200),
    }
)


def build_plot_profile(band: str | None, slice_length_ms: float = _DEFAULT_SLICE_LENGTH_MS) -> PlotProfile:
    """构建绘图规格集合。

    根据传入的频段标识构造全维度的绘图规格集合。如果是特定波段（如X波段），则自动应用局部覆盖。

    Args:
        band (str | None): 当前数据集所属的频段字符串（如 "X波段"），若为空则使用默认配置。
        slice_length_ms (float, optional): 绘图时默认使用的时间切片长度跨度，默认为 250.0。

    Returns:
        PlotProfile: 封装好的当前配置全维度规格对象。
    """

    # 复制基础配置避免污染默认字典
    specs = dict(_BASE_SPECS)
    # 获取波段对应的载频配置
    specs["CF"] = _CF_BAND_SPECS.get(band or "", _DEFAULT_CF_SPEC)
    
    # 针对X波段覆盖脉宽和DTOA规格
    if band == "X波段":
        specs["PW"] = PlotSpec(
            y_min=specs["PW"].y_min,
            y_max=50,
            img_height=specs["PW"].img_height,
            img_width=specs["PW"].img_width,
        )
        specs["DTOA"] = PlotSpec(
            y_min=specs["DTOA"].y_min,
            y_max=100,
            img_height=specs["DTOA"].img_height,
            img_width=specs["DTOA"].img_width,
        )
    return PlotProfile(specs=specs, slice_length_ms=slice_length_ms)


def build_dtoa_series(toa: np.ndarray) -> np.ndarray:
    """根据 TOA 构建 DTOA 序列。

    通过对时间序列做差分并转换单位，计算得出脉冲到达时间间隔序列。
    最后一位使用末尾差值做补齐填充以保证长度一致。

    Args:
        toa (np.ndarray): 一维的到达时间数组（单位：毫秒）。

    Returns:
        np.ndarray: 一维的差分时间数组（单位：微秒），与输入等长。

    Raises:
        ValueError: 当传入的不是一维数组时抛出。
    """

    # 统一转换为一维浮点数组
    toa_array = np.asarray(toa, dtype=np.float64)
    # 校验输入维度是否合法
    if toa_array.ndim != 1:
        raise ValueError(f"TOA 必须为一维数组，实际维度={toa_array.ndim}")
    
    # 判空返回空数组
    if len(toa_array) == 0:
        return np.array([], dtype=np.float64)
        
    # 计算相邻TOA的差值并转为微秒
    dtoa = np.diff(toa_array) * 1000.0
    # 复制最后一个差值填充长度
    fill_value = float(dtoa[-1]) if len(dtoa) > 0 else 0.0
    return np.append(dtoa, fill_value).astype(np.float64)


def validate_points(points: np.ndarray) -> np.ndarray:
    """校验脉冲点数组结构。

    检测传入的数组是否符合至少5列（对应脉冲基础特征列）的二维矩阵结构，
    若不满足则强制抛出异常阻断后续绘制逻辑。

    Args:
        points (np.ndarray): 待校验的二维矩阵，行代表各脉冲点。

    Returns:
        np.ndarray: 经过浮点数类型转换后的规范化二维矩阵。

    Raises:
        ValueError: 当矩阵为空，或者列数不够，或维度不是二维时抛出。
    """

    # 统一转换为二维浮点数组
    array = np.asarray(points, dtype=np.float64)
    
    # 校验输入维度与列数
    if array.ndim != 2 or array.shape[1] <= COL_TOA:
        raise ValueError(f"points 必须为至少 5 列的二维数组，实际 shape={array.shape}")
        
    # 判空抛出异常
    if len(array) == 0:
        raise ValueError("points 不能为空数组")
    return array


def resolve_time_range(
    toa: np.ndarray,
    time_range: tuple[float, float] | None,
    slice_length_ms: float,
) -> tuple[float, float]:
    """解析绘图时间范围。

    尝试从用户指定的参数中确定 X 轴时间基准；
    若未指定则通过遍历实际的时间序列寻找最小值与最大值，
    并应用防除零等兜底机制。

    Args:
        toa (np.ndarray): 包含时间数据的一维数组。
        time_range (tuple[float, float] | None): 外部设定的目标时间区间 (min, max)。
        slice_length_ms (float): 时间跨度容差参数，当区间为零时用以向外扩展宽度。

    Returns:
        tuple[float, float]: 可靠的起始与结束时间基准，保证起始小于结束。
    """

    # 若外部指定了时间范围，则优先使用
    if time_range is not None:
        start, end = float(time_range[0]), float(time_range[1])
        # 防止区间非法为零或负数
        if end <= start:
            end = start + 1.0
        return start, end
        
    # 转为浮点数组计算实际时间界限
    toa_array = np.asarray(toa, dtype=np.float64)
    if len(toa_array) == 0:
        return 0.0, max(slice_length_ms, 1.0)
        
    # 获取起始与结束时间点
    start = float(np.min(toa_array))
    end = float(np.max(toa_array))
    
    # 防止极窄区间导致除零错
    if end <= start:
        end = start + max(slice_length_ms, 1.0)
    return start, end


def resolve_dtoa_spec(base_spec: PlotSpec, dtoa: np.ndarray) -> PlotSpec:
    """根据 DTOA 分布解析绘图规格。

    检测传入的 DTOA 序列数据，当落在 3000~4000 高数值区间的数据量
    达到设定的阈值比例时，自动扩大纵坐标的最高显示范围（从3000扩至4000）。

    Args:
        base_spec (PlotSpec): 包含原始纵轴范围的绘图规格。
        dtoa (np.ndarray): 一维的 DTOA 差分数据序列。

    Returns:
        PlotSpec: 一个经分析处理、可能替换纵坐标量程的新配置规格。
    """

    # 转为浮点数组计算统计量
    dtoa_array = np.asarray(dtoa, dtype=np.float64)
    if len(dtoa_array) == 0:
        return base_spec
        
    # 统计落在大区间 [3000, 4000] 内的个数
    count = int(np.sum((dtoa_array >= 3000) & (dtoa_array <= 4000)))
    
    # 若大值占比较高则将量程扩至 4000
    if count > min(10, int(0.2 * len(dtoa_array))):
        return PlotSpec(
            y_min=base_spec.y_min,
            y_max=4000,
            img_height=base_spec.img_height,
            img_width=base_spec.img_width,
        )
        
    # 否则默认使用 3000 的上限
    return PlotSpec(
        y_min=base_spec.y_min,
        y_max=3000,
        img_height=base_spec.img_height,
        img_width=base_spec.img_width,
    )


def extract_dimension_series(points: np.ndarray, dim_name: str) -> tuple[np.ndarray, np.ndarray]:
    """提取维度对应的 X/Y 数据。

    通过指定的维度名称（如 CF, PW, PA），从二维脉冲特征数组里截取对应的列作为纵坐标数据；
    X 轴默认总是提取对应的到达时间列 (TOA)。其中 DTOA 作为特殊派生维度，
    由 TOA 序列单独构建。

    Args:
        points (np.ndarray): 包含脉冲序列和各项特征数据的多列矩阵。
        dim_name (str): 请求抽取的特征维度名称缩写。

    Returns:
        tuple[np.ndarray, np.ndarray]: 一个元组，包含等长的一维时间序列 (x) 与目标特征序列 (y)。

    Raises:
        ValueError: 当请求了一个未定义的维度名称时报错。
    """

    # 取出作为 X 轴基准的 TOA 列
    toa = points[:, COL_TOA]
    
    # 按照维度名称提取对应的 Y 轴数据
    if dim_name == "CF":
        return toa, points[:, COL_CF]
    if dim_name == "PW":
        return toa, points[:, COL_PW]
    if dim_name == "DOA":
        return toa, points[:, COL_DOA]
    if dim_name == "PA":
        return toa, points[:, COL_PA]
    if dim_name == "DTOA":
        # 针对 DTOA 派生维度动态计算差值序列
        return toa, build_dtoa_series(toa)
        
    # 未知维度抛出异常阻断渲染
    raise ValueError(f"不支持的维度名称：{dim_name}")


def collect_toa(cluster_data_list: list[np.ndarray]) -> np.ndarray:
    """收集合并场景下所有 TOA 数据。

    对于多个分类聚类组的特征数组列表，分别抽取各自包含的时间特征列并拼接成一维超长数组，
    为确定整个合并画布的最佳 X 轴尺度作准备。

    Args:
        cluster_data_list (list[np.ndarray]): 一组分别记录各聚类类别的脉冲二维数据矩阵集合。

    Returns:
        np.ndarray: 由所有组别的 TOA 合并形成的一维浮点序列。
        若传入列表无合规的数据则返回空数组。
    """

    # 遍历所有类别收集有效的 TOA 序列
    toa_series: list[np.ndarray] = []
    for cluster_data in cluster_data_list:
        points = np.asarray(cluster_data, dtype=np.float64)
        # 跳过空数组或列数不足的非法结构
        if points.ndim != 2 or points.shape[1] <= COL_TOA or len(points) == 0:
            continue
        toa_series.append(points[:, COL_TOA])
        
    # 如果全空则返回空数组
    if not toa_series:
        return np.array([], dtype=np.float64)
        
    # 将多个聚类的 TOA 拼成一维大数组以供后续计算极值
    return np.concatenate(toa_series)
