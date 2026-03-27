# -*- coding: utf-8 -*-
"""简化的圆形进度条组件"""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QFont


class CircleProgressBar(QWidget):
    """圆形进度条组件
    
    简化版本，只提供基本的进度显示功能。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0  # 0-100
        self._stroke_width = 6
        self._bar_color = QColor("#4772c3")  # 进度条颜色
        self._bg_color = QColor(200, 200, 200, 100)  # 背景颜色
        
        self.setFixedSize(80, 80)

    def value(self) -> int:
        """获取当前进度值"""
        return self._progress

    def setProgress(self, value: int):
        """设置进度值 (0-100)"""
        self._progress = max(0, min(100, value))
        self.update()

    def setBarColor(self, color):
        """设置进度条颜色"""
        self._bar_color = QColor(color)
        self.update()

    def setStrokeWidth(self, width: int):
        """设置圆环宽度"""
        self._stroke_width = width
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 计算绘制区域
        cw = self._stroke_width
        w = min(self.height(), self.width()) - cw
        rect = QRectF(cw / 2, self.height() / 2 - w / 2, w, w)

        # 绘制背景圆环
        bg_pen = QPen(self._bg_color, cw, cap=Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # 绘制进度圆弧
        if self._progress > 0:
            progress_pen = QPen(self._bar_color, cw, cap=Qt.RoundCap)
            painter.setPen(progress_pen)
            
            degree = max(1, int(self._progress / 100 * 360))
            # 从12点钟位置开始，顺时针绘制
            painter.drawArc(rect, 90 * 16, -degree * 16)

        # 绘制中心文字
        painter.setPen(QColor("#333333"))
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.drawText(self.rect(), Qt.AlignCenter, f"{self._progress}%")
