"""图像导出工具。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from .types import RenderedImageBundle


def save_rendered_images(
    bundle: RenderedImageBundle,
    output_dir: str | Path,
    base_name: str,
) -> dict[str, Path]:
    """将渲染结果落盘为 PNG 文件。

    接受一组已经通过 `infra.plotting` 函数完成生成的内存图像矩阵包，
    通过配置输出目录与基本文件名前缀，将其转换为对应维度的物理 PNG 图片，
    为外部持久化和预览调试提供可选支持。

    Args:
        bundle (RenderedImageBundle): 待写入硬盘的内存图片数据结果对象。
        output_dir (str | Path): 需要输出图片保存到的绝对或相对目标文件目录路径。
        base_name (str): 决定这批输出图片集文件名的共享基础前缀标识字符串。

    Returns:
        dict[str, Path]: 映射每一个独立维度代号与所生成的具体完整保存路径 Path 实例字典。

    Raises:
        ValueError: 当遇到既非二维灰度图也非三通道彩色图的其他结构图矩阵抛出。
    """

    # 转换并创建目标目录，兼容相对路径及用户家目录
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 遍历图像集合分别生成对应文件
    saved: dict[str, Path] = {}
    for dim_name, image in bundle.images.items():
        # 拼接小写的维度后缀并落盘
        file_path = output_path / f"{base_name}_{dim_name.lower()}.png"
        
        # 二维灰度图配置指定 cmap
        if image.ndim == 2:
            plt.imsave(file_path, image, cmap="gray", vmin=0, vmax=255)
        # 三维 RGB/RGBA 图像直接保存
        elif image.ndim == 3:
            plt.imsave(file_path, image)
        else:
            raise ValueError(f"不支持的图像维度：{image.ndim}")
            
        # 记录已保存的文件路径
        saved[dim_name] = file_path
        
    return saved
