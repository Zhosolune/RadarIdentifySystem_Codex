from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QScrollArea, QVBoxLayout, QPushButton
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer
from PyQt5.QtGui import QResizeEvent, QWheelEvent, QIcon
from typing import Optional, List
from cores.log_manager import LogManager
import os


from common.paths import Paths

class HorizontalScrollContainer(QWidget):
    """横向滚动容器
    
    用于容纳左侧、中间和合并界面的横向滚动容器。
    支持动画滚动到指定位置。
    """
    
    # 滚动完成信号
    scrollFinished = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """初始化横向滚动容器

        Args:
            parent: 父控件
        """
        super().__init__(parent)
        self.logger = LogManager()

        # 初始化属性
        self.scroll_enabled = False  # 滚动功能默认禁用
        self.animation: Optional[QPropertyAnimation] = None

        # 锚点相关属性
        self.anchor_points: List[int] = []  # 锚点位置列表
        self.anchor_threshold = 50  # 锚点吸附阈值（像素）
        self.snap_timer: Optional[QTimer] = None  # 延迟吸附定时器

        # 滚动锁定相关属性
        self.scroll_locked = False  # 滚动锁定状态
        self.pin_button: Optional[QPushButton] = None  # 图钉按钮

        # 设置UI
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """设置用户界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)
        
        # 设置滚动区域样式
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # 创建内容容器
        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        
        # 设置滚动区域的内容
        self.scroll_area.setWidget(self.content_widget)
        
        # 添加到主布局
        main_layout.addWidget(self.scroll_area)

        # 创建图钉按钮
        self._create_pin_button()

        # 存储子控件引用
        self.left_widget: Optional[QWidget] = None
        self.middle_widget: Optional[QWidget] = None
        self.merge_widget: Optional[QWidget] = None
        
    def add_widgets(self, left_widget: QWidget, middle_widget: QWidget, merge_widget: QWidget) -> None:
        """添加三个子控件到容器中
        
        Args:
            left_widget: 左侧控件
            middle_widget: 中间控件
            merge_widget: 合并界面控件
        """
        # 清除现有控件
        self._clear_layout()
        
        # 存储控件引用
        self.left_widget = left_widget
        self.middle_widget = middle_widget
        self.merge_widget = merge_widget
        
        # 添加控件到布局
        self.content_layout.addWidget(left_widget)
        self.content_layout.addWidget(middle_widget)
        self.content_layout.addWidget(merge_widget)
        
        # 更新控件尺寸
        self._update_widget_sizes()
        
    def _clear_layout(self) -> None:
        """清除布局中的所有控件"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
                
    def _update_widget_sizes(self) -> None:
        """更新控件尺寸，保持1:1:2的比例"""
        if not all([self.left_widget, self.middle_widget, self.merge_widget]):
            return
            
        # 计算可用宽度
        available_width = self.width() - 10  # 10px间距
        
        # 按1:1:2比例分配宽度
        unit_width = available_width // 2
        left_width = unit_width
        middle_width = unit_width
        merge_width = unit_width * 2 + 10
        
        # 设置控件宽度
        self.left_widget.setFixedWidth(left_width)
        self.middle_widget.setFixedWidth(middle_width)
        self.merge_widget.setFixedWidth(merge_width)
        
        # 更新内容容器的总宽度
        total_width = left_width + middle_width + merge_width + 20  # 加上间距
        self.content_widget.setFixedWidth(total_width)
        
        # 更新锚点位置
        self._update_anchor_points()
        
    def _update_anchor_points(self) -> None:
        """更新锚点位置列表"""
        self.anchor_points.clear()
        
        if not all([self.left_widget, self.middle_widget, self.merge_widget]):
            return
            
        # 第一个锚点：初始位置（显示左侧和中间控件）
        self.anchor_points.append(0)
        
        # 第二个锚点：左侧页面+10px（用户要求的位置）
        anchor_position = self.left_widget.width() + 10
        self.anchor_points.append(anchor_position)
        
    def _find_nearest_anchor(self, position: int) -> Optional[int]:
        """查找最近的锚点
        
        Args:
            position: 当前滚动位置
            
        Returns:
            最近的锚点位置，如果没有在阈值范围内的锚点则返回None
        """
        if not self.anchor_points:
            return None
            
        nearest_anchor = None
        min_distance = float('inf')
        
        for anchor in self.anchor_points:
            distance = abs(position - anchor)
            if distance < self.anchor_threshold and distance < min_distance:
                min_distance = distance
                nearest_anchor = anchor
                
        return nearest_anchor
        
    def _snap_to_anchor(self, anchor_position: int, duration: int = 300) -> None:
        """吸附到指定锚点
        
        Args:
            anchor_position: 锚点位置
            duration: 动画持续时间（毫秒）
        """
        if self.animation:
            self.animation.stop()
            
        self.animation = QPropertyAnimation(self.scroll_area.horizontalScrollBar(), b"value")
        self.animation.setDuration(duration)
        self.animation.setStartValue(self.scroll_area.horizontalScrollBar().value())
        self.animation.setEndValue(anchor_position)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()
        
    def enable_scroll(self, enabled: bool = True) -> None:
        """启用或禁用滚动功能
        
        Args:
            enabled: 是否启用滚动
        """
        self.scroll_enabled = enabled
        
        # 始终隐藏滚动条，通过鼠标滚轮进行滚动
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        if not enabled:
            # 禁用滚动时，回到初始位置
            self.scroll_area.horizontalScrollBar().setValue(0)
            
    def scroll_to_merge_view(self, duration: int = 800) -> None:
        """滚动到合并界面视图

        Args:
            duration: 动画持续时间（毫秒）
        """
        if not self.scroll_enabled or not self.merge_widget or self.scroll_locked:
            return
            
        # 计算目标滚动位置（显示中间控件和合并控件）
        if self.left_widget:
            target_position = self.left_widget.width() + self.middle_widget.width() + 20  # 左侧控件宽度 + 间距
        else:
            target_position = 0
            
        # 创建滚动动画
        if self.animation:
            self.animation.stop()
            
        self.animation = QPropertyAnimation(self.scroll_area.horizontalScrollBar(), b"value")
        self.animation.setDuration(duration)
        self.animation.setStartValue(self.scroll_area.horizontalScrollBar().value())
        self.animation.setEndValue(target_position)
        
        # 设置缓动曲线（先快后慢）
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 连接动画完成信号
        self.animation.finished.connect(self.scrollFinished.emit)
        
        # 开始动画
        self.animation.start()
        
    def handle_return_to_normal_view(self) -> None:
        """处理返回按钮事件，从合并界面返回到正常视图"""
        self.scroll_to_normal_view()
        
    def scroll_to_normal_view(self, duration: int = 800) -> None:
        """滚动回正常视图（显示左侧和中间控件）

        Args:
            duration: 动画持续时间（毫秒）
        """
        if not self.scroll_enabled or self.scroll_locked:
            return
            
        # 创建滚动动画回到初始位置
        if self.animation:
            self.animation.stop()
            
        self.animation = QPropertyAnimation(self.scroll_area.horizontalScrollBar(), b"value")
        self.animation.setDuration(duration)
        self.animation.setStartValue(self.scroll_area.horizontalScrollBar().value())
        self.animation.setEndValue(0)
        
        # 设置缓动曲线
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 连接动画完成信号
        self.animation.finished.connect(self.scrollFinished.emit)
        
        # 开始动画
        self.animation.start()
        
    def get_current_view_mode(self) -> str:
        """获取当前视图模式
        
        Returns:
            'normal': 正常视图（显示左侧和中间）
            'merge': 合并视图（显示中间和合并界面）
        """
        if not self.scroll_enabled:
            return 'normal'
            
        current_pos = self.scroll_area.horizontalScrollBar().value()
        
        # 判断当前位置
        if current_pos < 50:  # 接近初始位置
            return 'normal'
        else:
            return 'merge'
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """处理鼠标滚轮事件

        Args:
            event: 滚轮事件
        """
        if not self.scroll_enabled or self.scroll_locked:
            return
            
        # 停止当前的吸附动画
        if self.animation and self.animation.state() == QPropertyAnimation.Running:
            self.animation.stop()
            
        # 获取滚轮滚动的角度
        angle_delta = event.angleDelta().y()
        
        # 计算滚动步长（每次滚动90像素）
        scroll_step = 90
        
        # 获取当前滚动位置
        current_value = self.scroll_area.horizontalScrollBar().value()
        
        # 计算新的滚动位置
        if angle_delta > 0:  # 向上滚动，向左移动
            new_value = max(0, current_value - scroll_step)
        else:  # 向下滚动，向右移动
            max_value = self.scroll_area.horizontalScrollBar().maximum()
            new_value = min(max_value, current_value + scroll_step)
        
        # 设置新的滚动位置
        self.scroll_area.horizontalScrollBar().setValue(new_value)
        
        # 重置吸附定时器
        self._reset_snap_timer()
        
        # 接受事件，防止传递给父控件
        event.accept()
        
    def _reset_snap_timer(self) -> None:
        """重置锚点吸附定时器"""
        if self.snap_timer:
            self.snap_timer.stop()
            
        self.snap_timer = QTimer()
        self.snap_timer.setSingleShot(True)
        self.snap_timer.timeout.connect(self._check_and_snap_to_anchor)
        self.snap_timer.start(500)  # 500毫秒后检查是否需要吸附
        
    def _check_and_snap_to_anchor(self) -> None:
        """检查当前位置并吸附到最近的锚点"""
        current_position = self.scroll_area.horizontalScrollBar().value()
        nearest_anchor = self._find_nearest_anchor(current_position)

        if nearest_anchor is not None:
            self._snap_to_anchor(nearest_anchor)

    def _create_pin_button(self) -> None:
        """创建图钉按钮"""
        self.pin_button = QPushButton(self)
        self.pin_button.setFixedSize(26, 26)

        # 设置按钮样式
        self.pin_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: rgba(204, 204, 204, 0.5);
                border-radius: 13px;
            }
            QPushButton:pressed {
                background-color: transparent;
                border-radius: 13px;
            }
        """)

        # 设置初始图标（未锁定状态）
        self._update_pin_icon()

        # 连接点击事件
        self.pin_button.clicked.connect(self._toggle_scroll_lock)

        # 设置按钮位置（右上角）
        self._update_pin_button_position()

        # 显示按钮
        self.pin_button.show()

    def _update_pin_icon(self) -> None:
        """更新图钉按钮图标"""
        try:
            if self.scroll_locked:
                icon_path = str(Paths.get_resource_path("resources/pin/pin_on.png"))
                self.pin_button.setToolTip("点击解锁滚动")
            else:
                icon_path = str(Paths.get_resource_path("resources/pin/pin_off.png"))
                self.pin_button.setToolTip("点击锁定滚动")

            # 检查文件是否存在
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                self.pin_button.setIcon(icon)
                self.pin_button.setIconSize(self.pin_button.size() * 0.7)  # 图标稍小一些
            else:
                # 如果图标文件不存在，使用文字
                self.pin_button.setText("📌" if self.scroll_locked else "📍")
                self.pin_button.setIcon(QIcon())  # 清除图标

        except Exception as e:
            self.logger.error(f"更新图钉图标时出错: {e}")
            # 使用文字作为备选方案
            self.pin_button.setText("📌" if self.scroll_locked else "📍")
            self.pin_button.setIcon(QIcon())

    def _update_pin_button_position(self) -> None:
        """更新图钉按钮位置（右上角）"""
        if self.pin_button:
            # 计算按钮位置：右上角，距离边缘10像素
            x = self.width() - self.pin_button.width()
            y = 0
            self.pin_button.move(x, y)

    def _toggle_scroll_lock(self) -> None:
        """切换滚动锁定状态"""
        self.scroll_locked = not self.scroll_locked
        self._update_pin_icon()

        # 打印状态变化（用于调试）
        status = "锁定" if self.scroll_locked else "解锁"
        self.logger.info(f"滚动状态已{status}")

    def resizeEvent(self, event: QResizeEvent) -> None:
        """窗口大小改变事件

        Args:
            event: 大小改变事件
        """
        super().resizeEvent(event)
        self._update_widget_sizes()
        # 更新图钉按钮位置
        self._update_pin_button_position()