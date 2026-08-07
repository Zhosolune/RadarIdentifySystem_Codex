"""场景绘图门面。"""

from __future__ import annotations

from colorsys import hsv_to_rgb

import numpy as np

from core.models.pulse_batch import COL_CF, COL_DOA, COL_PA, COL_PW, COL_TOA
from .types import MergePalette, PlotProfile, RenderedImageBundle, _DIMENSION_ORDER
from .utils import (
    _DEFAULT_MERGE_PALETTE,
    build_dtoa_series,
    build_plot_profile,
    collect_toa,
    resolve_dtoa_spec,
    resolve_time_range,
    validate_points,
)
from .engine import (
    convert_color_index_to_rgb,
    rasterize_dimension,
    rasterize_merge_dimension,
    rasterize_recomputed_merge_dtoa,
)


def resolve_merge_source_colors(
    source_count: int,
    palette: MergePalette | None = None,
) -> tuple[tuple[int, int, int], ...]:
    """按完整合并结果中的来源位置返回稳定RGB颜色。

    Args:
        source_count [int]: 来源类簇数量，必须大于等于0。
        palette [MergePalette | None]: 可选调色板，默认使用合并图调色板。

    Returns:
        tuple[tuple[int, int, int], ...]: 与来源位置一一对应的RGB颜色。

    Raises:
        ValueError: 来源数量为负数或调色板没有非黑颜色时抛出。

    Example:
        >>> len(resolve_merge_source_colors(2))
        2
    """
    if source_count < 0:
        raise ValueError("source_count 不能为负数")
    # 颜色按完整结果中的来源位置解析，不受当前可见子集的顺序影响。
    palette_obj = palette or build_merge_palette(source_count)
    color_indices = sorted(index for index in palette_obj.colors if index > 0)
    if not color_indices and source_count:
        raise ValueError("合并调色板至少需要一个非黑颜色")
    return tuple(
        palette_obj.colors[color_indices[position % len(color_indices)]]
        for position in range(source_count)
    )


def build_merge_palette(source_count: int) -> MergePalette:
    """为完整合并结果构造足量且稳定的来源颜色。

    默认沿用项目既有颜色；来源超过默认容量时，以黄金分割步长生成额外颜色，
    保证支持范围内每个来源位置拥有不同RGB值。

    Args:
        source_count [int]: 来源类簇数量，允许范围为0到255。

    Returns:
        MergePalette: 包含黑色背景和足量来源颜色的调色板。

    Raises:
        ValueError: 来源数量不在0到255范围内时抛出。

    Example:
        >>> len(set(resolve_merge_source_colors(12)))
        12
    """
    if not 0 <= source_count <= 255:
        raise ValueError("source_count 必须位于0到255之间")
    # 优先沿用项目默认颜色，保证常见少类别场景的视觉风格保持不变。
    base_colors = [
        _DEFAULT_MERGE_PALETTE.colors[index]
        for index in sorted(_DEFAULT_MERGE_PALETTE.colors)
        if index > 0
    ]
    colors: dict[int, tuple[int, int, int]] = {0: (0, 0, 0)}
    used_colors = set(base_colors[:source_count])
    for position in range(source_count):
        if position < len(base_colors):
            rgb = base_colors[position]
        else:
            # 黄金分割步长可将新增颜色均匀散布在色相环上，并保持确定性。
            hue = (position * 0.618033988749895) % 1.0
            red, green, blue = hsv_to_rgb(hue, 0.72, 1.0)
            rgb = (
                int(round(red * 255)),
                int(round(green * 255)),
                int(round(blue * 255)),
            )
            # 极少数取整碰撞时按位置确定性扰动蓝色通道。
            while rgb in used_colors:
                rgb = (rgb[0], rgb[1], (rgb[2] + 1) % 256)
        used_colors.add(rgb)
        colors[position + 1] = rgb
    return MergePalette(colors=colors)


def render_slice_images(
    slice_data: np.ndarray,
    *,
    band: str | None = None,
    profile: PlotProfile | None = None,
    time_range: tuple[float, float] | None = None,
) -> RenderedImageBundle:
    """渲染切片的五维图像。

    通过调用引擎底层，以统一的时间基准一次性完成单个切片结果对应的 CF, PW, PA, DTOA, DOA
    这五张二维散点图绘制，同时将绘图所用波段、时间范围附在元数据。

    Args:
        slice_data (np.ndarray): 表示单个切片的原始特征点数据，包含各字段列的多行二维数组。
        band (str | None, optional): 供动态推导配置用（例如 "C波段"），不传默认。
        profile (PlotProfile | None, optional): 指定该次渲染依赖的数据图配置实例，为空时重新构建。
        time_range (tuple[float, float] | None, optional): 如果被提供则以此定为横轴的时间标尺起止极值。

    Returns:
        RenderedImageBundle: 封装完成的一个图片结果字典及其相关的波段等附属信息字典。

    Raises:
        ValueError: 当切片点数组行列数据不满足基础规范时抛出。
    """

    # 校验输入并准备绘图规格
    points = validate_points(slice_data)
    profile_obj = profile or build_plot_profile(band)
    
    # 提取时间基准并解析固定时间窗
    toa = points[:, COL_TOA]
    target_time_range = resolve_time_range(
        toa=toa,
        time_range=time_range,
        slice_length=profile_obj.slice_length,
    )
    
    # 计算DTOA派生序列
    dtoa = build_dtoa_series(toa)
    
    # 逐个维度渲染并组装成字典
    images = {
        "CF": rasterize_dimension(toa, points[:, COL_CF], profile_obj.get_spec("CF"), target_time_range),
        "PW": rasterize_dimension(toa, points[:, COL_PW], profile_obj.get_spec("PW"), target_time_range),
        "PA": rasterize_dimension(toa, points[:, COL_PA], profile_obj.get_spec("PA"), target_time_range),
        "DTOA": rasterize_dimension(
            toa,
            dtoa,
            resolve_dtoa_spec(profile_obj.get_spec("DTOA"), dtoa),
            target_time_range,
        ),
        "DOA": rasterize_dimension(toa, points[:, COL_DOA], profile_obj.get_spec("DOA"), target_time_range),
    }
    
    # 封装渲染包返回
    return RenderedImageBundle(images=images, metadata={"time_range": target_time_range, "band": band})


def render_cluster_images(
    cluster_points: np.ndarray,
    *,
    band: str | None = None,
    profile: PlotProfile | None = None,
    time_range: tuple[float, float] | None = None,
) -> RenderedImageBundle:
    """渲染单聚类展示图像。

    生成用于界面回显查看的一个单独类别（聚类结果）的所有图像视图。
    它直接委托调用给底层的切片渲染门面。

    Args:
        cluster_points (np.ndarray): 表示单个识别类别的原始特征点数据，包含各字段列的多行二维数组。
        band (str | None, optional): 供动态推导配置用。
        profile (PlotProfile | None, optional): 指定该次渲染依赖的数据图配置实例，为空时重新构建。
        time_range (tuple[float, float] | None, optional): 如果被提供则以此定为横轴的时间标尺起止极值。

    Returns:
        RenderedImageBundle: 包含五张图及相关描述的结果数据对象。
    """

    # 聚类结果在数据结构上与切片等同，直接复用切片渲染逻辑
    return render_slice_images(
        cluster_points,
        band=band,
        profile=profile,
        time_range=time_range,
    )


def render_predict_images(
    cluster_points: np.ndarray,
    *,
    band: str | None = None,
    profile: PlotProfile | None = None,
    time_range: tuple[float, float] | None = None,
) -> RenderedImageBundle:
    """渲染预测输入图像。

    仅抽取模型推理需要的两个核心特征（即 PA 极化角度和 DTOA 差分时间），
    分别生成二维张量图像用于送往后续的识别器推理网络，
    减少渲染其余无关维度（如CF/DOA）的开销。

    Args:
        cluster_points (np.ndarray): 用于预测的类别簇对应的特征点阵矩阵。
        band (str | None, optional): 控制绘制规格及上下量程，默认回退为空。
        profile (PlotProfile | None, optional): 给定的具体图表配置文件实例。
        time_range (tuple[float, float] | None, optional): 如果被提供则以此定为横轴的时间标尺起止极值。

    Returns:
        RenderedImageBundle: 一个仅包含 "PA" 与 "DTOA" 的键值对图像封装集合。

    Raises:
        ValueError: 当参数不符合绘图二维矩阵数据格式或不满足最小列宽时报错。
    """

    # 校验输入并获取默认规格
    points = validate_points(cluster_points)
    profile_obj = profile or build_plot_profile(band)
    
    # 取出 X 轴基准列并确定目标时间范围
    toa = points[:, COL_TOA]
    target_time_range = resolve_time_range(
        toa=toa,
        time_range=time_range,
        slice_length=profile_obj.slice_length,
    )
    
    # 动态派生 DTOA 差分序列
    dtoa = build_dtoa_series(toa)
    
    # 仅保留预测所需的核心维度 PA 与 DTOA
    images = {
        "PA": rasterize_dimension(toa, points[:, COL_PA], profile_obj.get_spec("PA"), target_time_range),
        "DTOA": rasterize_dimension(
            toa,
            dtoa,
            resolve_dtoa_spec(profile_obj.get_spec("DTOA"), dtoa),
            target_time_range,
        ),
    }
    
    # 返回仅含部分图像的渲染包
    return RenderedImageBundle(images=images, metadata={"time_range": target_time_range, "band": band})


def render_merge_images(
    cluster_data_list: list[np.ndarray],
    *,
    band: str | None = None,
    profile: PlotProfile | None = None,
    time_range: tuple[float, float] | None = None,
    visible_cluster_indices: list[int] | None = None,
    palette: MergePalette | None = None,
    recompute_merged_dtoa: bool = False,
) -> RenderedImageBundle:
    """渲染合并可视化图像。

    生成用于人工干预/检查时进行类间比对的视觉展示图；它将接受多个类别矩阵数据
    列表，通过调色板分给每个子集特定的颜色代号，将它们一同画到一张具有统一时间极值
    的图层上。此外通过控制列表可以快速过滤掉一些不希望显示的类别组。

    Args:
        cluster_data_list (list[np.ndarray]): 一组各个单独聚类识别结果特征二维数组构成的数据池。
        band (str | None, optional): 频段类型标识字符串。
        profile (PlotProfile | None, optional): 描述规格范围的对象实例。
        time_range (tuple[float, float] | None, optional): 指定时间的绝对跨度（微秒级浮点）。
        visible_cluster_indices (list[int] | None, optional): 一个包含要渲染的
            数据集索引位整数列表；``None`` 表示全部来源。
        palette (MergePalette | None, optional): 用于多类分配不同色彩的三通道调色板映射对象。
        recompute_merged_dtoa (bool, optional): 是否基于当前可见来源的完整
            脉冲序列重新计算 DTOA；默认保持各来源分别计算后叠加。

    Returns:
        RenderedImageBundle: 输出五维的彩色（RGB）图像数组封装字典。

    Raises:
        ValueError: 由引擎调用的底层渲染极值倒置或格式错乱时引起异常向上传递。
    """

    # 获取通用绘图规格
    profile_obj = profile or build_plot_profile(band)
    
    # 抽取所有待合并类别的 TOA 并解析统一的时间轴基准
    all_toa = collect_toa(cluster_data_list)
    target_time_range = resolve_time_range(
        toa=all_toa,
        time_range=time_range,
        slice_length=profile_obj.slice_length,
    )
    
    # 逐维度绘制颜色索引图并转换为 RGB 图
    images: dict[str, np.ndarray] = {}
    for dim_name in _DIMENSION_ORDER:
        # 新模式只替换 PRI/DTOA 图，其它维度继续沿用来源点云叠加逻辑。
        if dim_name == "DTOA" and recompute_merged_dtoa:
            color_index_image = rasterize_recomputed_merge_dtoa(
                cluster_data_list=cluster_data_list,
                profile=profile_obj,
                time_range=target_time_range,
                visible_cluster_indices=visible_cluster_indices,
                palette=palette,
            )
        else:
            color_index_image = rasterize_merge_dimension(
                cluster_data_list=cluster_data_list,
                dim_name=dim_name,
                profile=profile_obj,
                time_range=target_time_range,
                visible_cluster_indices=visible_cluster_indices,
                palette=palette,
            )
        # 通过调色板将索引转换为可直接显示的 RGB 三通道矩阵
        images[dim_name] = convert_color_index_to_rgb(
            color_index_image,
            palette=palette,
        )
        
    # 封装渲染结果并附带时间与波段元数据
    return RenderedImageBundle(images=images, metadata={"time_range": target_time_range, "band": band})
