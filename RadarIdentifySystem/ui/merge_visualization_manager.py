"""
合并可视化管理器

负责处理合并结果的可视化显示，包括：
1. 多颜色图像生成
2. 类别控制界面
3. 图像显示更新
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal, QObject
import numpy as np
from typing import List
from cores.log_manager import LogManager
from ui.style_manager import StyleManager


class CategoryControlWidget(QWidget):
    """类别控制组件"""

    # 信号：当类别可见性改变时发出
    category_visibility_changed = pyqtSignal(list)  # 发出可见类别索引列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = LogManager()
        self.category_items = []  # 存储类别项
        self.placeholder_items = []  # 存储占位符项
        self.select_all_checkbox = None  # 全选/全不选勾选框
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        styles = StyleManager.get_styles()

        # 创建标题行布局
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 10, 0)

        # 标题标签
        self.merge_result_label = QLabel("类别显示控制：")
        self.merge_result_label.setAlignment(Qt.AlignLeft)
        self.merge_result_label.setStyleSheet(styles["label"])
        self.merge_result_label.setFixedHeight(25)
        title_layout.addWidget(self.merge_result_label)

        # 添加弹性空间
        title_layout.addStretch()

        # 全选/全不选勾选框
        self.select_all_checkbox = QCheckBox()
        self.select_all_checkbox.setFixedHeight(25)
        self.select_all_checkbox.setTristate(False)  # 禁用三态模式，直接切换
        self.select_all_checkbox.setChecked(True)
        self.select_all_checkbox.setVisible(False)  # 初始隐藏
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)
        title_layout.addWidget(self.select_all_checkbox)

        # 将标题行布局添加到主布局
        title_widget = QWidget()
        title_widget.setLayout(title_layout)
        title_widget.setFixedHeight(25)
        layout.addWidget(title_widget)
        layout.addSpacing(5)

        # 创建固定高度的视窗容器
        self.viewport_container = QWidget()
        self.viewport_container.setFixedHeight(95)  # 默认高度95px
        self.viewport_container.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #A8D4FF;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.viewport_container)

        # 视窗内容布局
        self.viewport_layout = QVBoxLayout(self.viewport_container)
        self.viewport_layout.setContentsMargins(5, 5, 5, 5)  # 内边距5px
        self.viewport_layout.setSpacing(0)  # 类别间垂直间距0px

        # 创建初始占位符
        self.create_placeholders()

    def create_placeholders(self):
        """创建占位符元素"""
        self.clear_viewport()

        # 创建3个占位符矩形
        for i in range(3):
            placeholder = QLabel()
            placeholder.setFixedSize(200, 25)  # 宽度100px，高度25px（与类别项一致）
            placeholder.setStyleSheet("""
                QLabel {
                    background-color: #cccccc;
                    border-radius: 5px;
                    border: none;
                }
            """)
            self.placeholder_items.append(placeholder)
            self.viewport_layout.addWidget(placeholder)

            # 除了最后一个占位符，其他都添加间距
            if i < 2:  # 只在前两个占位符后添加间距
                self.viewport_layout.addSpacing(5)

    def clear_viewport(self):
        """清空视窗内容"""
        # 清除占位符
        for item in self.placeholder_items:
            item.setParent(None)
        self.placeholder_items.clear()

        # 清除类别项
        for item in self.category_items:
            item.setParent(None)
        self.category_items.clear()

        # 清除弹性空间
        while self.viewport_layout.count() > 0:
            child = self.viewport_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
            elif child.spacerItem():
                del child

        # 重置容器高度为默认值95px
        self.viewport_container.setFixedHeight(95)

    def update_categories(self, merged_data: dict, plot_manager):
        """更新类别列表

        Args:
            merged_data (dict): 合并数据
            plot_manager: 绘图管理器实例
        """
        try:
            # 清空视窗
            self.clear_viewport()

            # 获取类别信息
            dim_names = merged_data.get("dim_name", [])
            dim_indices = merged_data.get("dim_cluster_idx", [])
            cluster_data_list = merged_data.get("cluster_data", [])

            if not cluster_data_list:
                # 如果没有合并结果，隐藏全选勾选框并显示占位符
                if self.select_all_checkbox:
                    self.select_all_checkbox.setVisible(False)
                self.create_placeholders()
                return

            # 过滤有效的聚类数据
            valid_clusters = []
            for i, cluster_data in enumerate(cluster_data_list):
                if cluster_data is not None:
                    valid_clusters.append((i, cluster_data))

            category_count = len(valid_clusters)

            # 动态调整视窗高度
            if category_count <= 3:
                # 类别数量 ≤ 3，保持默认高度120px
                self.viewport_container.setFixedHeight(95)
            else:
                # 类别数量 > 3，动态计算高度
                # 高度 = 类别数量 × 25px + (类别数量-1) × 5px + 容器内边距(10px)
                new_height = category_count * 25 + (category_count - 1) * 5 + 10
                self.viewport_container.setFixedHeight(new_height)

            # 创建类别项
            for i, (original_index, cluster_data) in enumerate(valid_clusters):
                # 获取类别信息
                dim_name = (
                    dim_names[original_index]
                    if original_index < len(dim_names)
                    else f"未知{original_index}"
                )
                dim_idx = (
                    dim_indices[original_index]
                    if original_index < len(dim_indices)
                    else original_index
                )

                # 获取颜色信息
                color_index = (i % 10) + 1  # 颜色索引从1开始
                color_name, color_rgb = plot_manager.get_color_info(color_index)

                # 创建类别项
                category_item = self.create_category_item(
                    original_index,
                    f"{dim_name}维度第{dim_idx}类",
                    color_name,
                    color_rgb,
                )
                self.category_items.append(category_item)
                self.viewport_layout.addWidget(category_item)

                # 除了最后一个类别项，其他都添加间距（与占位符保持一致）
                if i < category_count - 1:
                    self.viewport_layout.addSpacing(5)

            # 显示全选勾选框（合并完成后）
            if self.select_all_checkbox:
                self.select_all_checkbox.setVisible(True)

            # 默认全选，更新全选勾选框状态
            self.update_select_all_state()

        except Exception as e:
            self.logger.error(f"更新类别列表出错: {str(e)}")

    def create_category_item(
        self, index: int, name: str, color_name: str, color_rgb: tuple
    ) -> QWidget:
        """创建类别项

        Args:
            index (int): 类别索引
            name (str): 类别名称
            color_name (str): 颜色名称
            color_rgb (tuple): RGB颜色值

        Returns:
            QWidget: 类别项组件
        """
        try:
            # 创建容器
            container = QWidget()
            container.setFixedHeight(25)  # 设置固定高度30px
            container.setStyleSheet(
                "QWidget { border: none; background-color: transparent; }"
            )
            layout = QHBoxLayout(container)
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(5)

            # 颜色指示器
            color_label = QLabel()
            color_label.setFixedSize(16, 16)
            color_label.setStyleSheet(f"""
                QLabel {{
                    background-color: rgb({color_rgb[0]}, {color_rgb[1]}, {color_rgb[2]});
                    border-radius: 2px;
                }}
            """)

            # 名称标签 - 使用StyleManager中的标签样式
            name_label = QLabel(name)
            styles = StyleManager.get_styles()
            label_style = styles.get("label", "")
            name_label.setStyleSheet(label_style)

            # 复选框
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(
                lambda state, idx=index: self.on_category_visibility_changed(
                    idx, state == Qt.CheckState.Checked
                )
            )

            # 存储索引信息
            container.category_index = index
            container.checkbox = checkbox

            # 添加到布局
            layout.addWidget(color_label)
            layout.addWidget(name_label)
            layout.addStretch()
            layout.addWidget(checkbox)

            return container

        except Exception as e:
            self.logger.error(f"创建类别项出错: {str(e)}")
            return QWidget()

    def on_category_visibility_changed(self, index: int, visible: bool):
        """类别可见性改变时的处理"""
        visible_indices = self.get_visible_categories()
        self.category_visibility_changed.emit(visible_indices)

        # 更新全选勾选框的状态
        self.update_select_all_state()

    def get_visible_categories(self) -> List[int]:
        """获取可见的类别索引列表"""
        visible_indices = []
        for item in self.category_items:
            if hasattr(item, "checkbox") and hasattr(item, "category_index"):
                if item.checkbox.isChecked():
                    visible_indices.append(item.category_index)
        return visible_indices

    def on_select_all_changed(self, state):
        """全选/全不选勾选框状态改变时的处理"""
        if self.select_all_checkbox is None:
            return

        # 避免递归调用
        if hasattr(self, "_updating_select_all") and self._updating_select_all:
            return

        # 处理状态切换逻辑
        if state == Qt.CheckState.Checked:
            # 全选
            checked = True
        elif state == Qt.CheckState.Unchecked:
            # 全不选
            checked = False
        else:
            # 中间态时，切换到全选
            checked = True

        # 应用到所有类别项
        for item in self.category_items:
            if hasattr(item, "checkbox"):
                item.checkbox.setChecked(checked)

    def update_select_all_state(self):
        """更新全选勾选框的状态"""
        if self.select_all_checkbox is None or not self.category_items:
            return

        # 统计选中和未选中的数量
        checked_count = 0
        total_count = len(self.category_items)

        for item in self.category_items:
            if hasattr(item, "checkbox") and item.checkbox.isChecked():
                checked_count += 1

        # 设置标志避免递归调用
        self._updating_select_all = True

        try:
            if checked_count == 0:
                # 全部未选中 - 禁用三态模式
                self.select_all_checkbox.setTristate(False)
                self.select_all_checkbox.setCheckState(Qt.CheckState.Unchecked)
            elif checked_count == total_count:
                # 全部选中 - 禁用三态模式
                self.select_all_checkbox.setTristate(False)
                self.select_all_checkbox.setCheckState(Qt.CheckState.Checked)
            else:
                # 部分选中 - 启用三态模式显示中间态
                self.select_all_checkbox.setTristate(True)
                self.select_all_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        finally:
            self._updating_select_all = False

    def all_select(self):
        for item in self.category_items:
            if hasattr(item, "checkbox"):
                item.checkbox.setChecked(True)

    def all_unselect(self):
        for item in self.category_items:
            if hasattr(item, "checkbox"):
                item.checkbox.setChecked(False)


class MergeVisualizationManager(QObject):
    """合并可视化管理器"""

    table_refresh = pyqtSignal(dict)

    def __init__(self, window, plot_manager):
        super().__init__()
        self.window = window
        self.plot_manager = plot_manager
        self.logger = LogManager()
        self.current_merged_data = None
        self.category_control = None

    def create_category_control_widget(self) -> CategoryControlWidget:
        """创建类别控制组件"""
        if self.category_control is None:
            self.category_control = CategoryControlWidget()
            self.category_control.category_visibility_changed.connect(
                self.on_category_visibility_changed
            )
        return self.category_control

    def update_merge_display(self, merged_data: dict, merge_index: int):
        """更新合并结果显示

        Args:
            merged_data (dict): 合并数据
            merge_index (int): 合并索引
        """
        try:
            self.current_merged_data = merged_data

            # 更新类别控制组件
            if self.category_control:
                self.category_control.update_categories(merged_data, self.plot_manager)

            # 生成并显示图像
            self.generate_and_display_images()

        except Exception as e:
            self.logger.error(f"更新合并显示出错: {str(e)}")

    def generate_and_display_images(self, visible_clusters: List[int] = None):
        """生成并显示合并图像

        Args:
            visible_clusters (List[int], optional): 可见的聚类索引列表
        """
        try:
            if not self.current_merged_data:
                return

            # 如果没有指定可见聚类，获取当前可见的聚类
            if visible_clusters is None and self.category_control:
                visible_clusters = self.category_control.get_visible_categories()

            # 生成合并图像
            merge_index = self.current_merged_data.get("index_merge", 1)
            base_name = f"merge_result_{merge_index}"

            image_paths = self.plot_manager.plot_merged_cluster(
                self.current_merged_data, base_name, visible_clusters
            )

            # 显示图像
            if image_paths and hasattr(self.window, "merge_plots"):
                plot_types = ["CF", "PW", "PA", "DTOA", "DOA"]
                for i, plot_type in enumerate(plot_types):
                    if i < len(self.window.merge_plots):
                        path = image_paths.get(plot_type)
                        if path:
                            self.window.merge_plots[i].display_image(path)
                        else:
                            self.window.merge_plots[i].clear()

        except Exception as e:
            self.logger.error(f"生成并显示合并图像出错: {str(e)}")

    def extract_and_update_parameters(self, visible_clusters: List[int]):
        """根据可见聚类提取参数并更新表格

        Args:
            visible_clusters (List[int]): 可见的聚类索引列表
        """
        try:
            if not self.current_merged_data or not visible_clusters:
                return

            cluster_data_list = self.current_merged_data.get("cluster_data", [])
            if not cluster_data_list:
                self.logger.warning("没有找到聚类数据")
                return

            # 构建新的脉冲数据
            merged_pulse_data = []
            for idx in visible_clusters:
                if idx < len(cluster_data_list) and cluster_data_list[idx] is not None:
                    merged_pulse_data.append(cluster_data_list[idx])

            if not merged_pulse_data:
                self.logger.warning("没有找到有效的聚类脉冲数据")
                return

            pulse_data = np.vstack([data for data in merged_pulse_data])
            pulse_data = pulse_data[np.argsort(pulse_data[:, 4])]

            # 调用data_controller的_extract_parameters_after_merge方法
            merged_cf, merged_pw, merged_pri, merged_doa = (
                self.window.data_controller._extract_parameters_after_merge(pulse_data)
            )

            # 创建合并后数据结构
            self.merged_data = {
                "merged_pulse_data": pulse_data,
                "CF": f"{', '.join([f'{v:.0f}' for v in merged_cf])}",
                "PW": f"{', '.join([f'{v:.1f}' for v in merged_pw])}",
                "DOA": f"{np.mean(merged_doa):.0f}",  # DOA取均值
                "DTOA": f"{', '.join([f'{v:.1f}' for v in merged_pri])}",
            }

            if self.merged_data:
                # 更新参数表格
                self.table_refresh.emit(self.merged_data)
            else:
                self.logger.warning("参数提取失败")

        except Exception as e:
            self.logger.error(f"提取和更新参数时出错: {str(e)}")
            import traceback

            self.logger.error(f"错误堆栈:\n{traceback.format_exc()}")

    def on_category_visibility_changed(self, visible_clusters: List[int]):
        """类别可见性改变时的处理"""
        self.generate_and_display_images(visible_clusters)

        # 重新提取参数并更新表格
        self.extract_and_update_parameters(visible_clusters)

    def clear_display(self):
        """清空合并可视化显示"""
        try:
            # 清空当前合并数据
            self.current_merged_data = None

            # 将类别控制组件恢复到初始的仿懒加载界面
            if self.category_control:
                self.category_control.clear_viewport()
                self.category_control.create_placeholders()

            self.logger.info("合并可视化显示已清空")

        except Exception as e:
            self.logger.error(f"清空合并可视化显示出错: {str(e)}")
