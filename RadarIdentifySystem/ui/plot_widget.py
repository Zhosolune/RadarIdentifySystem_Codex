from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFrame, QSizePolicy
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np
from enum import Enum
from cores.log_manager import LogManager

class ScaleMode(Enum):
    """缩放模式枚举"""
    FIT = 1                    # 适应窗口（保持比例）
    STRETCH = 2                # 拉伸填充（像素精准映射）
    STRETCH_BILINEAR = 5       # 拉伸填充（双线性插值）
    STRETCH_NEAREST_PRESERVE = 6  # 拉伸填充（最近邻插值+非底色像素保留）
    FILL = 3                   # 填充（可能裁剪）
    CENTER = 4                 # 居中显示（原始大小）

class PlotWidget(QWidget):
    def __init__(self, scale_mode=ScaleMode.STRETCH):
        super().__init__()
        self.scale_mode = scale_mode
        self.logger = LogManager()
        
        # 创建布局
        self.plot_layout = QVBoxLayout(self)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_layout.setSpacing(0)
        
        # 创建带边框的框架
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Box)
        self.frame.setLineWidth(1)
        self.frame.setStyleSheet("""
            QFrame {
                border: 1px solid #4772c3;
                background-color: white;
            }
        """)
        
        # 创建框架的布局
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)
        
        # 创建 Figure 和 Canvas，设置紧凑布局
        self.figure = Figure(facecolor='white', constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame_layout.addWidget(self.canvas)
        
        # 添加框架到主布局
        self.plot_layout.addWidget(self.frame)
        
        # 添加子图并设置边距
        self.ax = self.figure.add_subplot(111)
        self.ax.set_position([0, 0, 1, 1])  # 设置子图位置填充整个画布
        
        # 移除坐标轴
        self.ax.axis('off')
        
        # 存储当前图像
        self.current_image = None
        
        # 连接重绘事件
        self.canvas.mpl_connect('resize_event', self.on_resize)
    
    def set_scale_mode(self, mode: ScaleMode):
        """设置缩放模式
        
        Args:
            mode: 缩放模式枚举值
        """
        self.scale_mode = mode
        self._update_image()
        self.canvas.draw()
    
    def get_available_stretch_modes(self) -> list:
        """获取可用的拉伸模式列表
        
        Returns:
            包含拉伸模式的列表，每个元素为(模式枚举, 模式描述)的元组
        """
        return [
            (ScaleMode.STRETCH, "像素精准映射（保证不丢失像素）"),
            (ScaleMode.STRETCH_BILINEAR, "双线性插值（平滑处理）"),
            (ScaleMode.STRETCH_NEAREST_PRESERVE, "最近邻插值（非底色像素保留）")
        ]
    
    def set_stretch_mode(self, stretch_mode: ScaleMode):
        """设置拉伸模式的便捷方法
        
        Args:
            stretch_mode: 拉伸模式枚举值（STRETCH, STRETCH_BILINEAR, STRETCH_NEAREST_PRESERVE）
        """
        if stretch_mode in [ScaleMode.STRETCH, ScaleMode.STRETCH_BILINEAR, ScaleMode.STRETCH_NEAREST_PRESERVE]:
            self.set_scale_mode(stretch_mode)
        else:
            self.logger.warning(f"不支持的拉伸模式: {stretch_mode}")
    
    def get_current_stretch_mode(self) -> ScaleMode:
        """获取当前的拉伸模式
        
        Returns:
            当前的拉伸模式枚举值，如果不是拉伸模式则返回None
        """
        if self.scale_mode in [ScaleMode.STRETCH, ScaleMode.STRETCH_BILINEAR, ScaleMode.STRETCH_NEAREST_PRESERVE]:
            return self.scale_mode
        return None
    
    def display_image(self, image_path):
        """显示PNG图像"""
        try:
            self.logger.debug(f"尝试显示图像: {image_path}")
            self.ax.clear()
            
            # 读取图像并检查
            self.current_image = plt.imread(image_path)
            if self.current_image is None:
                self.logger.warning(f"警告：无法读取图像: {image_path}")
                return

            # 检查图像格式，支持RGB和灰度图像
            if len(self.current_image.shape) == 3:
                # RGB图像，保持原始格式
                self.logger.debug(f"加载RGB图像，形状: {self.current_image.shape}")
            elif len(self.current_image.shape) == 2:
                # 灰度图像
                self.logger.debug(f"加载灰度图像，形状: {self.current_image.shape}")
            else:
                self.logger.warning(f"不支持的图像格式，形状: {self.current_image.shape}")
                return
            
            # 更新图像显示
            self._update_image()
            self.canvas.draw_idle()  # 使用draw_idle代替draw
            
        except Exception as e:
            self.logger.error(f"显示图像出错: {str(e)}")
    
    def _stretch_image_bilinear(self, image: np.ndarray, target_width: int, target_height: int) -> np.ndarray:
        """使用双线性插值拉伸图像
        
        Args:
            image: 输入图像
            target_width: 目标宽度
            target_height: 目标高度
            
        Returns:
            拉伸后的图像
        """
        try:
            img_height, img_width = image.shape[:2]
            
            # 计算缩放比例
            scale_x = img_width / target_width
            scale_y = img_height / target_height
            
            # 创建目标坐标网格
            y_indices, x_indices = np.mgrid[0:target_height, 0:target_width]
            
            # 计算源图像中的浮点坐标
            src_x = x_indices * scale_x
            src_y = y_indices * scale_y
            
            # 获取四个最近邻点的整数坐标
            x0 = np.floor(src_x).astype(np.int32)
            x1 = np.minimum(x0 + 1, img_width - 1)
            y0 = np.floor(src_y).astype(np.int32)
            y1 = np.minimum(y0 + 1, img_height - 1)
            
            # 计算权重
            wx = src_x - x0
            wy = src_y - y0
            
            # 双线性插值
            if len(image.shape) == 3:  # RGB图像
                stretched_image = np.zeros((target_height, target_width, image.shape[2]), dtype=image.dtype)
                for c in range(image.shape[2]):
                    stretched_image[:, :, c] = (
                        image[y0, x0, c] * (1 - wx) * (1 - wy) +
                        image[y0, x1, c] * wx * (1 - wy) +
                        image[y1, x0, c] * (1 - wx) * wy +
                        image[y1, x1, c] * wx * wy
                    )
            else:  # 灰度图像
                stretched_image = (
                    image[y0, x0] * (1 - wx) * (1 - wy) +
                    image[y0, x1] * wx * (1 - wy) +
                    image[y1, x0] * (1 - wx) * wy +
                    image[y1, x1] * wx * wy
                )
            
            return stretched_image.astype(image.dtype)
            
        except Exception as e:
            self.logger.error(f"双线性插值拉伸时出错: {e}")
            return image  # 返回原图像
    
    def _stretch_image_nearest_preserve(self, image: np.ndarray, target_width: int, target_height: int) -> np.ndarray:
        """使用最近邻插值拉伸图像，并对非底色像素进行特殊保留处理
        
        Args:
            image: 输入图像
            target_width: 目标宽度
            target_height: 目标高度
            
        Returns:
            拉伸后的图像
        """
        try:
            img_height, img_width = image.shape[:2]
            
            # 检测底色（假设底色是最常见的颜色）
            if len(image.shape) == 3:  # RGB图像
                # 将RGB图像转换为单一值进行统计
                flat_image = image.reshape(-1, image.shape[2])
                unique_colors, counts = np.unique(flat_image, axis=0, return_counts=True)
                background_color = unique_colors[np.argmax(counts)]
                
                # 创建非底色像素掩码
                non_bg_mask = ~np.all(image == background_color, axis=2)
            else:  # 灰度图像
                unique_values, counts = np.unique(image, return_counts=True)
                background_value = unique_values[np.argmax(counts)]
                
                # 创建非底色像素掩码
                non_bg_mask = image != background_value
            
            # 计算缩放比例
            scale_x = img_width / target_width
            scale_y = img_height / target_height
            
            # 创建目标图像
            if len(image.shape) == 3:
                stretched_image = np.full((target_height, target_width, image.shape[2]), 
                                        background_color, dtype=image.dtype)
            else:
                stretched_image = np.full((target_height, target_width), 
                                        background_value, dtype=image.dtype)
            
            # 对于每个非底色像素，在目标图像中进行扩展映射
            non_bg_coords = np.where(non_bg_mask)
            
            for i in range(len(non_bg_coords[0])):
                src_y, src_x = non_bg_coords[0][i], non_bg_coords[1][i]
                
                # 计算在目标图像中的位置范围
                target_x_start = int(src_x / scale_x)
                target_x_end = int((src_x + 1) / scale_x) + 1
                target_y_start = int(src_y / scale_y)
                target_y_end = int((src_y + 1) / scale_y) + 1
                
                # 确保不超出边界
                target_x_start = max(0, target_x_start)
                target_x_end = min(target_width, target_x_end)
                target_y_start = max(0, target_y_start)
                target_y_end = min(target_height, target_y_end)
                
                # 将非底色像素值复制到目标区域
                if len(image.shape) == 3:
                    stretched_image[target_y_start:target_y_end, target_x_start:target_x_end] = image[src_y, src_x]
                else:
                    stretched_image[target_y_start:target_y_end, target_x_start:target_x_end] = image[src_y, src_x]
            
            return stretched_image
            
        except Exception as e:
            self.logger.error(f"最近邻插值保留拉伸时出错: {e}")
            return image  # 返回原图像
    
    def _calculate_image_position(self, ratio):
        """计算图像位置和尺寸"""
        if not isinstance(self.current_image, np.ndarray):
            return 0, 0
            
        canvas_width, canvas_height = self.canvas.get_width_height()
        
        try:
            img_height, img_width = self.current_image.shape[:2]
            
            # 计算新尺寸
            new_width = img_width * ratio
            new_height = img_height * ratio
            
            # 计算偏移量
            x_offset = (canvas_width - new_width) / 2 / canvas_width
            y_offset = (canvas_height - new_height) / 2 / canvas_height
            
            return x_offset, y_offset
            
        except (AttributeError, IndexError) as e:
            self.logger.error(f"Error calculating image position: {e}")
            return 0, 0
    
    def _update_image(self):
        """根据不同缩放模式更新图像显示"""
        if self.current_image is None or not isinstance(self.current_image, np.ndarray):
            return
        
        try:
            # 清除当前图像
            self.ax.clear()
            
            if self.scale_mode in [ScaleMode.STRETCH, ScaleMode.STRETCH_BILINEAR, ScaleMode.STRETCH_NEAREST_PRESERVE]:
                # 获取画布和图像尺寸
                canvas_width, canvas_height = self.canvas.get_width_height()
                
                img_height, img_width = self.current_image.shape[:2]
                
                if self.scale_mode == ScaleMode.STRETCH:
                    # 模式一：拉伸填充（像素精准映射，保证不丢失每一个像素点）
                    # 计算缩放比例
                    scale_x = canvas_width / img_width
                    scale_y = canvas_height / img_height
                    
                    # 创建目标网格
                    y, x = np.mgrid[0:canvas_height, 0:canvas_width]
                    
                    # 计算源图像坐标（向量化操作）
                    source_x = np.clip(np.round(x / scale_x).astype(np.int32), 0, img_width - 1)
                    source_y = np.clip(np.round(y / scale_y).astype(np.int32), 0, img_height - 1)
                    
                    # 一次性完成映射（向量化操作）
                    stretched_image = self.current_image[source_y, source_x]
                    
                elif self.scale_mode == ScaleMode.STRETCH_BILINEAR:
                    # 模式二：拉伸填充（双线性插值，平滑处理）
                    stretched_image = self._stretch_image_bilinear(
                        self.current_image, canvas_width, canvas_height
                    )
                    
                elif self.scale_mode == ScaleMode.STRETCH_NEAREST_PRESERVE:
                    # 模式三：拉伸填充（最近邻插值+非底色像素特殊保留）
                    stretched_image = self._stretch_image_nearest_preserve(
                        self.current_image, canvas_width, canvas_height
                    )
                
                # 显示拉伸后的图像
                if len(stretched_image.shape) == 3:
                    # RGB图像，不使用colormap
                    self.ax.imshow(stretched_image,
                                  aspect='auto',
                                  interpolation='nearest',
                                  extent=[0, 1, 0, 1])
                else:
                    # 灰度图像，使用灰度colormap
                    self.ax.imshow(stretched_image,
                                  aspect='auto',
                                  interpolation='nearest',
                                  extent=[0, 1, 0, 1],
                                  cmap='gray')
                self.ax.set_position([0, 0, 1, 1])
            else:
                # 获取画布和图像尺寸
                canvas_width, canvas_height = self.canvas.get_width_height()
                img_height, img_width = self.current_image.shape[:2]
                
                # 清除当前图像
                self.ax.clear()
                
                if self.scale_mode == ScaleMode.FIT:
                    # 适应窗口（保持比例）
                    width_ratio = canvas_width / img_width
                    height_ratio = canvas_height / img_height
                    ratio = min(width_ratio, height_ratio)
                    x_offset, y_offset = self._calculate_image_position(ratio)
                    
                elif self.scale_mode == ScaleMode.FILL:
                    # 填充（可能裁剪）
                    width_ratio = canvas_width / img_width
                    height_ratio = canvas_height / img_height
                    ratio = max(width_ratio, height_ratio)
                    x_offset, y_offset = self._calculate_image_position(ratio)
                    
                elif self.scale_mode == ScaleMode.CENTER:
                    # 居中显示（原始大小）
                    scale = min(canvas_width / img_width, canvas_height / img_height, 1.0)
                    x_offset, y_offset = self._calculate_image_position(scale)
                
                # 显示图像
                if len(self.current_image.shape) == 3:
                    # RGB图像，不使用colormap
                    self.ax.imshow(self.current_image,
                                  extent=(x_offset, 1-x_offset, y_offset, 1-y_offset))
                else:
                    # 灰度图像，使用灰度colormap
                    self.ax.imshow(self.current_image,
                                  extent=(x_offset, 1-x_offset, y_offset, 1-y_offset),
                                  cmap='gray')
                self.ax.axis('off')
            
            self.ax.axis('off')
            self.canvas.draw()
            
        except Exception as e:
            self.logger.error(f"更新图像显示出错: {str(e)}")
    
    def on_resize(self, event):
        """窗口大小改变时重新调整图像"""
        self._update_image()
        self.canvas.draw()
    
    def clear(self):
        """清除当前图像"""
        if hasattr(self, 'ax'):
            self.ax.clear()
            self.ax.axis('off')
            self.current_image = None
            self.canvas.draw_idle()