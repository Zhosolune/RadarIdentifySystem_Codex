# -*- coding: utf-8 -*-
"""仪表盘组件

提供数据解析结果的仪表盘显示功能，使用卡片样式布局。
"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class DashboardCard(QFrame):
    """仪表盘卡片项"""

    def __init__(self, label: str, value: str = "--", parent=None):
        super().__init__(parent)
        self._label = label
        self._value = value
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(60)
        self.setStyleSheet("""
            DashboardCard {
                background-color: white;
                border: none;
                border-radius: 8px;

            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        # 值标签（大数字）
        self._value_label = QLabel(self._value)
        self._value_label.setStyleSheet("""
            QLabel {
                color: #4772c3;
                font-size: 16px;
                font-weight: bold;
                font-family: "Microsoft YaHei";
                background: transparent;
            }
        """)
        self._value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._value_label)

        # 名称标签（小文字）
        self._name_label = QLabel(self._label)
        self._name_label.setStyleSheet("""
            QLabel {
                color: #4772c3;
                font-size: 12px;
                font-family: "Microsoft YaHei";
                background: transparent;
            }
        """)
        self._name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._name_label)

    def set_value(self, value: str):
        """设置值"""
        self._value = value
        self._value_label.setText(value)


class DashboardWidget(QWidget):
    """仪表盘组件 - 纯内容布局，使用卡片样式"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = {}
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        self.setStyleSheet("background: transparent;")

        # 使用 QGridLayout 并通过 _reflow 管理卡片位置
        # 这允许我们在隐藏某些卡片时，自动顺延后续卡片，保持紧凑布局
        from PyQt5.QtWidgets import QGridLayout
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(10)

        self._grid_layout = QGridLayout()
        self._grid_layout.setSpacing(10)
        # 确保所有列宽一致 (5列)
        for i in range(5):
            self._grid_layout.setColumnStretch(i, 1)
        
        main_layout.addLayout(self._grid_layout)

        # 定义卡片顺序
        # 逻辑顺序：总脉冲 -> 剔除脉冲 -> [丢弃详情] -> 剩余脉冲 -> 持续时间 -> 波段 -> 预计切片数
        self._ordered_keys = [
            "total_pulses",
            "filtered_pulses",
            "drop_f26",
            "drop_pa",
            "drop_doa",
            "remaind_pulses",
            "time_range",
            "band",
            "slice_count"
        ]
        
        # 卡片标签定义
        labels = {
            "total_pulses": "总脉冲",
            "filtered_pulses": "剔除脉冲",
            "drop_f26": "F26丢弃",
            "drop_pa": "幅度丢弃",
            "drop_doa": "方位丢弃",
            "remaind_pulses": "剩余脉冲",
            "time_range": "持续时间",
            "band": "波段",
            "slice_count": "预计切片数"
        }

        # 创建所有卡片
        for key in self._ordered_keys:
            # 必须指定 parent=self，否则 setVisible(True) 时会作为独立窗口弹出
            card = DashboardCard(labels[key], parent=self)
            self._items[key] = card
            # 初始不添加到 layout，由 _reflow 处理

        # 初始回流 (默认为比幅策略)
        self._current_strategy = "amplitude"
        self._reflow()

    def _reflow(self):
        """根据当前策略重新排列卡片"""
        # 1. 移除所有卡片（不删除对象）
        # 注意：QGridLayout 没有 removeAllWidgets 方法，需要手动遍历
        # 更简单的方法是重新 addWidget，它会自动移动 widget
        # 但为了处理隐藏的 widget，我们需要显式 hide 它们
        
        row, col = 0, 0
        MAX_COLS = 5
        
        for key in self._ordered_keys:
            card = self._items[key]
            should_show = True
            
            # 根据策略判断可见性
            if key == "drop_f26" and self._current_strategy != "amplitude":
                should_show = False
            elif key == "drop_doa" and self._current_strategy == "amplitude":
                should_show = False
                
            if should_show:
                # 先添加到布局，再显示，防止可能的闪烁
                self._grid_layout.addWidget(card, row, col)
                card.setVisible(True)
                col += 1
                if col >= MAX_COLS:
                    col = 0
                    row += 1
            else:
                card.setVisible(False)
                # 隐藏的卡片不需要从 layout 移除，只要不显示且不占用 grid 位置即可
                # 但为了保险，我们可以将其移除，或者只是不调用 addWidget
                # QGridLayout 中，如果不调用 addWidget，它保留在原位？
                # 测试表明 addWidget 会移动。如果之前在 layout 中但现在不 add，它还在 layout 中吗？
                # 是的。所以我们需要先移除。
                self._grid_layout.removeWidget(card)
                
    def update_values(self, data: dict):
        """更新仪表盘数值
        
        Args:
            data: 包含各项统计数据的字典
        """
        # 更新策略并回流布局（如果策略改变）
        new_strategy = data.get("strategy", "amplitude")
        if new_strategy != self._current_strategy:
            self._current_strategy = new_strategy
            self._reflow()
            
        # ... (后续更新数值的代码保持不变)

    def _format_time(self, time_ms: float) -> str:
        """格式化时间，自适应单位

        单位策略：确保整数部分不超过4位
        us -> ms -> s -> min -> h

        Args:
            time_ms: 毫秒为单位的时间

        Returns:
            格式化后的时间字符串
        """
        # 定义单位转换（从ms开始）
        units = [
            ("ms", 1),
            ("s", 1000),
            ("min", 60 * 1000),
            ("h", 60 * 60 * 1000),
        ]

        # 从最小单位开始，找到合适的单位
        for unit, divisor in units:
            value = time_ms / divisor
            if round(value) < 10000:
                return f"{round(value)}{unit}"

        # 默认使用小时
        return f"{round(time_ms / (60 * 60 * 1000))}h"

    def update_values(self, data: dict):
        """更新仪表盘数值
        
        Args:
            data: 包含各项统计数据的字典
        """
        # 更新策略并回流布局（如果策略改变）
        new_strategy = data.get("strategy", "amplitude")
        if new_strategy != self._current_strategy:
            self._current_strategy = new_strategy
            self._reflow()
            
        if "total_pulses" in data:
            self._items["total_pulses"].set_value(str(data["total_pulses"]))
        if "time_range" in data:
            self._items["time_range"].set_value(self._format_time(data["time_range"]))
        if "filtered_pulses" in data:
            self._items["filtered_pulses"].set_value(str(data["filtered_pulses"]))
        if "band" in data and data["band"]:
            # 提取波段字母（去除"波段"后缀）
            band_str = data["band"]
            if band_str.endswith("波段"):
                band_str = band_str[:-2]
            self._items["band"].set_value(band_str)
        if "slice_count" in data:
            self._items["slice_count"].set_value(str(data["slice_count"]))

        # 自动计算保留脉冲数量（总脉冲数 - 剔除脉冲数）
        if "remaind_pulses" in data:
            self._items["remaind_pulses"].set_value(str(data["remaind_pulses"]))
        elif "total_pulses" in data and "filtered_pulses" in data:
            retained = data["total_pulses"] - data["filtered_pulses"]
            self._items["remaind_pulses"].set_value(str(retained))

        # 处理丢弃统计
        if "drop_stats" in data:
            stats = data["drop_stats"]

            # 始终更新幅度丢弃
            if "pa" in stats:
                self._items["drop_pa"].set_value(str(stats["pa"]))

            if self._current_strategy == "amplitude":
                if "f26" in stats:
                    self._items["drop_f26"].set_value(str(stats["f26"]))
            else:
                if "doa" in stats:
                    self._items["drop_doa"].set_value(str(stats["doa"]))

    def clear_values(self):
        """清空所有数值"""
        for item in self._items.values():
            item.set_value("--")
