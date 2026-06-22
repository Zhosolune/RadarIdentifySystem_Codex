import numpy as np
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt

def stretch_nearest_preserve(q_image: QImage, target_width: int, target_height: int) -> QImage:
    """使用最近邻插值拉伸图像，并对非底色像素进行特殊保留处理（向量化加速版）
    
    参数说明:
        q_image (QImage): 原始图像
        target_width (int): 目标宽度
        target_height (int): 目标高度
        
    返回说明:
        QImage: 缩放后的图像
    """
    if q_image.isNull() or target_width <= 0 or target_height <= 0:
        return q_image

    width = q_image.width()
    height = q_image.height()
    format = q_image.format()
    
    # 获取图像内存指针并转换为 numpy 数组
    ptr = q_image.bits()
    ptr.setsize(q_image.sizeInBytes())
    
    if format == QImage.Format.Format_Grayscale8:
        # 单通道 8 位灰度图
        image = np.array(ptr, copy=False).reshape(height, width)
        unique, counts = np.unique(image, return_counts=True)
        bg_color = unique[np.argmax(counts)]
        non_bg_mask = image != bg_color
        stretched = np.full((target_height, target_width), bg_color, dtype=np.uint8)
    elif format == QImage.Format.Format_RGB888:
        # 3 通道 8 位 RGB 图
        image = np.array(ptr, copy=False).reshape(height, width, 3)
        flat = image.reshape(-1, 3)
        unique, counts = np.unique(flat, axis=0, return_counts=True)
        bg_color = unique[np.argmax(counts)]
        non_bg_mask = ~np.all(image == bg_color, axis=2)
        stretched = np.full((target_height, target_width, 3), bg_color, dtype=np.uint8)
    else:
        # 其他格式直接使用内置的最近邻插值
        return q_image.scaled(target_width, target_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)

    scale_x = width / target_width
    scale_y = height / target_height

    # 提取非底色像素的原始坐标
    y_idx, x_idx = np.nonzero(non_bg_mask)
    if len(y_idx) > 0:
        colors = image[y_idx, x_idx]
        
        # 计算在目标图像中的投影坐标范围 (左闭右开)
        x_start = np.floor(x_idx / scale_x).astype(int)
        x_end = np.floor((x_idx + 1) / scale_x).astype(int) + 1
        y_start = np.floor(y_idx / scale_y).astype(int)
        y_end = np.floor((y_idx + 1) / scale_y).astype(int) + 1
        
        # 裁剪坐标防止越界
        x_start = np.clip(x_start, 0, target_width)
        x_end = np.clip(x_end, 0, target_width)
        y_start = np.clip(y_start, 0, target_height)
        y_end = np.clip(y_end, 0, target_height)
        
        # 向量化或轻量循环赋值
        # 对于较小的稀疏散点，循环填充切片通常只需几十到几百次，性能极快
        for i in range(len(y_idx)):
            stretched[y_start[i]:y_end[i], x_start[i]:x_end[i]] = colors[i]
            
    # 从 numpy 数组构造新的 QImage，必须复制以保证生命周期安全
    if format == QImage.Format.Format_Grayscale8:
        result = QImage(stretched.data, target_width, target_height, target_width, format).copy()
    else:
        result = QImage(stretched.data, target_width, target_height, target_width * 3, format).copy()
        
    return result

def apply_scale_mode(q_image: QImage, target_width: int, target_height: int, mode: str) -> QImage:
    """根据指定的模式对 QImage 进行缩放"""
    if mode == "STRETCH":
        # 像素精准映射（最近邻插值）
        return q_image.scaled(target_width, target_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
    elif mode == "STRETCH_BILINEAR":
        # 双线性插值（平滑处理）
        return q_image.scaled(target_width, target_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    elif mode == "STRETCH_NEAREST_PRESERVE":
        # 最近邻插值（非底色像素保留）
        return stretch_nearest_preserve(q_image, target_width, target_height)
    else:
        return q_image.scaled(target_width, target_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
