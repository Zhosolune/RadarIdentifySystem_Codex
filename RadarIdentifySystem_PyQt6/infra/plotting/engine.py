"""核心渲染引擎。"""

from __future__ import annotations

import numpy as np

from core.models.pulse_batch import COL_TOA
from .types import MergePalette, PlotProfile, PlotSpec
from .utils import extract_dimension_series, _DEFAULT_MERGE_PALETTE


def rasterize_dimension(
    xdata: np.ndarray,
    ydata: np.ndarray,
    spec: PlotSpec,
    time_range: tuple[float, float],
) -> np.ndarray:
    """将单维度数据栅格化为二值图像。

    通过指定的横纵坐标缩放规则与边界范围，计算每个输入数据点应该投影到
    指定高宽画布的哪个像素位置，并在全黑矩阵背景下以白色（255）标记命中位置。
    此过程会自动剔除不在限定时间与纵向范围内的离群点。

    Args:
        xdata (np.ndarray): 用于确定 X 轴位置的数据序列。
        ydata (np.ndarray): 用于确定 Y 轴位置的特征数值序列。
        spec (PlotSpec): 描述输出画布大小与纵轴范围极值的配置规格。
        time_range (tuple[float, float]): 指定当前绘图区域的横轴上下界。

    Returns:
        np.ndarray: 生成的高和宽对应传入规格的二维 uint8 格式灰度图像。

    Raises:
        ValueError: 当参数类型、数组长宽比例异常，或指定的坐标边界发生倒挂时报错。
    """

    # 统一将入参转为浮点型的一维数组
    x = np.asarray(xdata, dtype=np.float64)
    y = np.asarray(ydata, dtype=np.float64)
    # 校验输入结构
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("xdata 和 ydata 必须为等长一维数组")
    if spec.img_height <= 0 or spec.img_width <= 0:
        raise ValueError("图像尺寸必须为正整数")
        
    # 读取时间范围界限并防止除零错
    x_min, x_max = float(time_range[0]), float(time_range[1])
    if x_max <= x_min:
        x_max = x_min + 1.0
        
    # 计算Y轴跨度并校验合法性
    y_span = spec.y_max - spec.y_min
    if y_span <= 0:
        raise ValueError("y_max 必须大于 y_min")

    # 按比例缩放 Y 坐标到图像高度范围（翻转 Y 轴以适配图像左上角原点）
    scaled_y = spec.img_height - np.round(
        (y - spec.y_min) / y_span * (spec.img_height - 1)
    ).astype(np.int32)
    # 按比例缩放 X 坐标到图像宽度范围
    scaled_x = np.round(
        (x - x_min) / (x_max - x_min) * (spec.img_width - 1)
    ).astype(np.int32) + 1

    # 初始化一张全黑图像
    image = np.zeros((spec.img_height, spec.img_width), dtype=np.uint8)
    
    # 过滤掉落在画布外的点
    valid_mask = (
        (scaled_x > 0)
        & (scaled_x <= spec.img_width)
        & (scaled_y > 0)
        & (scaled_y <= spec.img_height)
    )
    
    # 将合法的散点映射到像素点，赋值 255 (白色)
    if np.any(valid_mask):
        image[scaled_y[valid_mask] - 1, scaled_x[valid_mask] - 1] = 255
    return image


def rasterize_merge_dimension(
    cluster_data_list: list[np.ndarray],
    dim_name: str,
    profile: PlotProfile,
    time_range: tuple[float, float],
    visible_cluster_indices: list[int] | None = None,
    palette: MergePalette | None = None,
) -> np.ndarray:
    """将合并聚类栅格化为颜色索引图。

    依次提取多组脉冲数据指定特征的数据序列，计算点坐标后投影到一张画布上；
    每个类别依照预先配置的颜色编号进行索引标记，可由传入可见类别列表动态过滤特定类别。
    索引图为二维单通道形式。

    Args:
        cluster_data_list (list[np.ndarray]): 各个类别对应的多列原始脉冲数据矩阵。
        dim_name (str): 请求渲染的目标维度代号名称。
        profile (PlotProfile): 当前所用的全局绘图配置组合信息。
        time_range (tuple[float, float]): 指定画布横轴显示的起止时间。
        visible_cluster_indices (list[int] | None, optional): 指定需要被渲染的类别组索引下标列表，为 None 时表示全部显示。
        palette (MergePalette | None, optional): 渲染所采用的调色板配置字典对象。

    Returns:
        np.ndarray: 生成的二维灰度图数据（像素点存为类别颜色字典对应的整数值索引），作为单通道数据等待转码。

    Raises:
        ValueError: 当参数类型非法或计算边界导致极值不合法时抛出异常。
    """

    # 获取对应的绘图规格并初始化空图像
    spec = profile.get_spec(dim_name)
    image = np.zeros((spec.img_height, spec.img_width), dtype=np.uint8)
    
    # 准备调色板和非零颜色编号池
    palette_obj = palette or _DEFAULT_MERGE_PALETTE
    color_indices = sorted([k for k in palette_obj.colors if k > 0]) or [1]
    
    # 确定要绘制的 cluster 列表索引（支持外部指定可见集）
    target_indices = (
        list(range(len(cluster_data_list)))
        if visible_cluster_indices is None
        else visible_cluster_indices
    )
    
    # 解析时间与 Y 轴跨度界限
    x_min, x_max = float(time_range[0]), float(time_range[1])
    if x_max <= x_min:
        x_max = x_min + 1.0
    y_span = spec.y_max - spec.y_min
    if y_span <= 0:
        raise ValueError("y_max 必须大于 y_min")

    # 按传入的顺序逐个 cluster 绘制
    for order_idx, cluster_idx in enumerate(target_indices):
        # 越界保护
        if cluster_idx < 0 or cluster_idx >= len(cluster_data_list):
            continue
            
        # 转为规范浮点数组并做格式兜底
        points = np.asarray(cluster_data_list[cluster_idx], dtype=np.float64)
        if points.ndim != 2 or points.shape[1] <= COL_TOA or len(points) == 0:
            continue
            
        # 提取当前类别 X/Y 轴数据
        xdata, ydata = extract_dimension_series(points, dim_name)
        if len(xdata) == 0 or len(ydata) == 0:
            continue
            
        # 过滤包含非数字或无穷大等异常值的数据序列
        if np.any(np.isnan(xdata)) or np.any(np.isnan(ydata)):
            continue
        if np.any(np.isinf(xdata)) or np.any(np.isinf(ydata)):
            continue
            
        # 根据当前维度规格缩放数据到像素系
        scaled_y = spec.img_height - np.round(
            (ydata - spec.y_min) / y_span * (spec.img_height - 1)
        ).astype(np.int32)
        scaled_x = np.round(
            (xdata - x_min) / (x_max - x_min) * (spec.img_width - 1)
        ).astype(np.int32) + 1
        
        # 找出落在画布合法区间的点集合
        valid_mask = (
            (scaled_x > 0)
            & (scaled_x <= spec.img_width)
            & (scaled_y > 0)
            & (scaled_y <= spec.img_height)
        )
        
        # 将合法散点写进索引图，根据绘制顺序循环分配不同颜色标号
        if np.any(valid_mask):
            color_value = color_indices[order_idx % len(color_indices)]
            image[scaled_y[valid_mask] - 1, scaled_x[valid_mask] - 1] = color_value
            
    return image


def convert_color_index_to_rgb(
    color_index_image: np.ndarray,
    palette: MergePalette | None = None,
) -> np.ndarray:
    """将颜色索引图转换为 RGB 图。

    接收多类合并生成的二维颜色编码矩阵，根据配置的映射字典，
    借助 Numpy 查找表替换为可直接进行图形渲染的 RGB 三通道图像；
    当输入图片编码存在越界时自动拓展黑色填充处理。

    Args:
        color_index_image (np.ndarray): 一个带有类别数字索引标签的二维数组。
        palette (MergePalette | None, optional): 一个含有颜色RGB值的调色字典配置实例。

    Returns:
        np.ndarray: 生成的高和宽对应传入原图像、包含 RGB 信息的 3 通道三维数组。

    Raises:
        ValueError: 当输入的索引图不是二维结构时抛出错误。
    """

    # 转为整数数组并校验维度
    image = np.asarray(color_index_image, dtype=np.uint8)
    if image.ndim != 2:
        raise ValueError("color_index_image 必须为二维数组")
        
    # 获取查找表（LUT）
    palette_obj = palette or _DEFAULT_MERGE_PALETTE
    lut = palette_obj.to_lut()
    
    # 若图片中的颜色编号超出LUT边界，自动扩充LUT补零
    if image.max(initial=0) >= len(lut):
        expanded = np.zeros((int(image.max()) + 1, 3), dtype=np.uint8)
        expanded[: len(lut)] = lut
        lut = expanded
        
    # 通过NumPy高级索引将单通道颜色映射为RGB三通道
    return lut[image]
