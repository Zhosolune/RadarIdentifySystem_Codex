from PyQt5.QtWidgets import QStackedWidget, QWidget, QGraphicsOpacityEffect
from PyQt5.QtCore import (
    QPropertyAnimation,
    QParallelAnimationGroup,
    QEasingCurve,
    QPoint,
)


class SlidingStackedWidget(QStackedWidget):
    """支持滑动动画的堆叠控件

    实现界面切换时的平移遮罩动画效果。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animation_duration = 300  # 动画持续时间（毫秒）
        self._animation_type = QEasingCurve.OutCubic  # 动画缓动类型
        self._current_index = 0
        self._next_index = 0
        self._is_animating = False
        self._wrap = False  # 是否循环切换

    def set_animation_duration(self, duration: int):
        """设置动画持续时间"""
        self._animation_duration = duration

    def set_animation_type(self, animation_type: QEasingCurve):
        """设置动画缓动类型"""
        self._animation_type = animation_type

    def slide_to_index(self, index: int):
        """滑动到指定索引的界面

        Args:
            index: 目标界面索引
        """
        if self._is_animating:
            return

        if index == self.currentIndex():
            return

        if index < 0 or index >= self.count():
            return

        self._is_animating = True
        self._current_index = self.currentIndex()
        self._next_index = index

        # 获取当前和目标控件
        current_widget = self.widget(self._current_index)
        next_widget = self.widget(self._next_index)

        # 确定滑动方向
        # A(0) -> B(1): B从右侧滑入遮住A
        # B(1) -> A(0): B向右滑出露出A
        width = self.frameRect().width()

        if self._next_index > self._current_index:
            # 向前切换（A -> B）：新界面从右侧滑入
            next_widget.setGeometry(width, 0, width, self.frameRect().height())
            current_start = QPoint(0, 0)
            current_end = QPoint(-width, 0)
            next_start = QPoint(width, 0)
            next_end = QPoint(0, 0)
        else:
            # 向后切换（B -> A）：当前界面向右滑出
            next_widget.setGeometry(-width, 0, width, self.frameRect().height())
            current_start = QPoint(0, 0)
            current_end = QPoint(width, 0)
            next_start = QPoint(-width, 0)
            next_end = QPoint(0, 0)

        # 显示目标控件
        next_widget.show()
        next_widget.raise_()

        # 创建动画组
        self._animation_group = QParallelAnimationGroup()
        self._animation_group.finished.connect(self._on_animation_finished)

        # 当前控件的动画
        current_anim = QPropertyAnimation(current_widget, b"pos")
        current_anim.setDuration(self._animation_duration)
        current_anim.setEasingCurve(self._animation_type)
        current_anim.setStartValue(current_start)
        current_anim.setEndValue(current_end)

        # 目标控件的动画
        next_anim = QPropertyAnimation(next_widget, b"pos")
        next_anim.setDuration(self._animation_duration)
        next_anim.setEasingCurve(self._animation_type)
        next_anim.setStartValue(next_start)
        next_anim.setEndValue(next_end)

        self._animation_group.addAnimation(current_anim)
        self._animation_group.addAnimation(next_anim)

        # 开始动画
        self._animation_group.start()

    def _on_animation_finished(self):
        """动画完成回调"""
        # 设置当前索引
        self.setCurrentIndex(self._next_index)

        # 重置控件位置
        current_widget = self.widget(self._current_index)
        current_widget.move(0, 0)

        self._is_animating = False

    def slide_to_next(self):
        """滑动到下一个界面"""
        next_index = self.currentIndex() + 1
        if next_index >= self.count():
            if self._wrap:
                next_index = 0
            else:
                return
        self.slide_to_index(next_index)

    def slide_to_prev(self):
        """滑动到上一个界面"""
        prev_index = self.currentIndex() - 1
        if prev_index < 0:
            if self._wrap:
                prev_index = self.count() - 1
            else:
                return
        self.slide_to_index(prev_index)
