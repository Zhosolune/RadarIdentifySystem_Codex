from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QTimer
from .plot_widget import PlotWidget, ScaleMode
from .horizontal_scroll_container import HorizontalScrollContainer
from .default_config import get_params
from .merge_visualization_manager import MergeVisualizationManager
from cores.log_manager import LogManager
from typing import Tuple


class ScrollLayoutManager:
    """横向滚动布局管理器

    负责管理横向滚动容器及其包含的三个主要区域：
    - 左侧图像显示区域（原始图像）
    - 中间图像显示区域（聚类结果）
    - 合并区域（合并界面）
    """

    def __init__(self, window):
        """初始化滚动布局管理器

        Args:
            window: 主窗口实例
        """
        self.window = window
        self.scroll_container = None
        self.logger = LogManager()

        # 合并结果导航相关变量
        self.current_merge_index = 0  # 当前显示的合并结果索引
        self.merged_results = []  # 存储合并结果列表

        # 存储data_controller引用
        self.data_controller = window.data_controller

        # 合并可视化管理器（延迟初始化）
        self.merge_visualization_manager = None

    def create_scroll_container(self) -> HorizontalScrollContainer:
        """创建横向滚动容器

        Returns:
            HorizontalScrollContainer: 横向滚动容器实例
        """
        self.scroll_container = HorizontalScrollContainer()
        return self.scroll_container

    def setup_scroll_layout(self) -> Tuple[QWidget, QWidget, QWidget]:
        """设置滚动布局，创建三个主要区域

        Returns:
            Tuple[QWidget, QWidget, QWidget]: 左侧控件、中间控件、合并控件的元组
        """
        # 创建三个区域的布局
        left_layout = self._create_left_column()
        middle_layout = self._create_middle_column()
        merge_widget = self._create_merge_widget()

        # 创建列容器并设置布局
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        middle_widget = QWidget()
        middle_widget.setLayout(middle_layout)
        middle_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 将控件添加到滚动容器
        if self.scroll_container:
            self.scroll_container.add_widgets(left_widget, middle_widget, merge_widget)

        return left_widget, middle_widget, merge_widget

    def _create_left_column(self) -> QVBoxLayout:
        """创建左侧列布局（图像显示区域1）

        Returns:
            QVBoxLayout: 左侧列布局
        """
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建标题
        self.window.left_title = QLabel("第0个切片数据  原始图像")
        self.window.left_title.setAlignment(Qt.AlignCenter)
        self.window.left_title.setStyleSheet(self.window.styles["title_label"])
        self.window.left_title.setFixedHeight(self.window.dimensions["title_height"])
        layout.addWidget(self.window.left_title)

        # 创建图像容器
        plots_container = QWidget()
        plots_layout = QVBoxLayout(plots_container)
        plots_layout.setSpacing(self.window.dimensions["spacing_small"])
        plots_layout.setContentsMargins(0, 0, 0, 0)

        # 图像标签文字，顺序决定标签和图像显示的顺序
        labels = ["载频", "脉宽", "幅度", "一级差", "方位角"]

        self.window.left_plots = []  # 初始化列表

        # 添加5个图像和对应的标签
        for i, label_text in enumerate(labels):
            # 创建水平布局来放置标签和图像
            row_layout = QHBoxLayout()
            row_layout.setSpacing(self.window.dimensions["spacing_small"])  # 标签和图像之间的间距

            # 创建竖排标签（通过在每个字符后添加换行符）
            vertical_text = "\n".join(label_text)
            label = QLabel(vertical_text)
            label.setStyleSheet(self.window.styles["figure_label"])
            label.setFixedWidth(25)  # 设置标签宽度

            # 创建图像
            plot_widget = PlotWidget()
            if i == 0:  # 第一个图像
                plot_widget.plot_layout.setContentsMargins(0, 0, 0, 5)
            elif i == 4:  # 最后一个图像
                plot_widget.plot_layout.setContentsMargins(0, 5, 0, 0)
            else:  # 中间的图像
                plot_widget.plot_layout.setContentsMargins(0, 5, 0, 5)

            # 存储图像显示区域
            self.window.left_plots.append(plot_widget)  # 添加到列表

            # 添加标签和图像到行布局
            row_layout.addWidget(label)
            row_layout.addWidget(plot_widget, 1)

            # 添加行布局到主布局
            plots_layout.addLayout(row_layout)

        layout.addWidget(plots_container)
        return layout

    def _create_middle_column(self) -> QVBoxLayout:
        """创建中间列布局（图像显示区域2）

        Returns:
            QVBoxLayout: 中间列布局
        """
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建标题
        self.window.middle_title = QLabel("CF/PW 维度聚类 第0类")
        self.window.middle_title.setAlignment(Qt.AlignCenter)
        self.window.middle_title.setStyleSheet(self.window.styles["title_label"])
        self.window.middle_title.setFixedHeight(self.window.dimensions["title_height"])
        layout.addWidget(self.window.middle_title)

        # 创建图像容器
        plots_container = QWidget()
        plots_layout = QVBoxLayout(plots_container)
        plots_layout.setSpacing(self.window.dimensions["spacing_small"])
        plots_layout.setContentsMargins(0, 0, 0, 0)

        # 图像标签文字和对应的图像类型，顺序决定标签和图像显示的顺序
        labels_and_types = [
            ("载频", "CF"),
            ("脉宽", "PW"),
            ("幅度", "PA"),
            ("一级差", "DTOA"),
            ("方位角", "DOA"),
        ]

        self.window.middle_plots = []  # 清空列表

        # 添加5个图像和对应的标签
        for i, (label_text, plot_type) in enumerate(labels_and_types):
            # 创建水平布局来放置标签和图像
            row_layout = QHBoxLayout()
            row_layout.setSpacing(self.window.dimensions["spacing_small"])  # 标签和图像之间的间距

            # 创建竖排标签
            vertical_text = "\n".join(label_text)
            label = QLabel(vertical_text)
            label.setStyleSheet(self.window.styles["figure_label"])
            label.setFixedWidth(25)

            # 创建图像显示区域，使用STRETCH模式
            plot_widget = PlotWidget(scale_mode=ScaleMode.STRETCH)
            if i == 0:
                plot_widget.plot_layout.setContentsMargins(0, 0, 0, 5)
            elif i == 4:
                plot_widget.plot_layout.setContentsMargins(0, 5, 0, 0)
            else:
                plot_widget.plot_layout.setContentsMargins(0, 5, 0, 5)

            # 存储图像显示区域
            self.window.middle_plots.append(plot_widget)

            # 添加标签和图像到行布局
            row_layout.addWidget(label)
            row_layout.addWidget(plot_widget, 1)

            # 添加行布局到主布局
            plots_layout.addLayout(row_layout)

        layout.addWidget(plots_container)
        return layout

    def _create_merge_widget(self) -> QWidget:
        """创建合并界面控件

        Returns:
            合并界面控件
        """
        # 创建合并界面容器
        merge_container = QWidget()
        merge_layout = QVBoxLayout(merge_container)
        merge_layout.setContentsMargins(0, 0, 0, 0)
        merge_layout.setSpacing(0)

        # 创建合并界面的左侧图像区域
        merge_left_layout = self._create_merge_image_area()
        merge_left_widget = QWidget()
        merge_left_widget.setLayout(merge_left_layout)

        # 创建合并界面的右侧控制区域
        merge_right_layout = self._create_merge_control_area()
        merge_right_widget = QWidget()
        merge_right_widget.setLayout(merge_right_layout)

        # 创建水平布局来放置左右两部分
        merge_content_layout = QHBoxLayout()
        merge_content_layout.setContentsMargins(0, 0, 0, 0)
        merge_content_layout.setSpacing(10)

        merge_content_layout.addWidget(merge_left_widget, 1)
        merge_content_layout.addWidget(merge_right_widget, 1)

        merge_layout.addLayout(merge_content_layout)

        return merge_container

    def _create_merge_image_area(self) -> QVBoxLayout:
        """创建合并界面的图像显示区域

        Returns:
            图像显示区域布局
        """
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建标题
        self.window.merge_title = QLabel("合并后图像")
        self.window.merge_title.setAlignment(Qt.AlignCenter)
        self.window.merge_title.setStyleSheet(self.window.styles["title_label"])
        self.window.merge_title.setFixedHeight(self.window.dimensions["title_height"])
        layout.addWidget(self.window.merge_title)

        # 创建图像容器
        plots_container = QWidget()
        plots_layout = QVBoxLayout(plots_container)
        plots_layout.setSpacing(self.window.dimensions["spacing_small"])
        plots_layout.setContentsMargins(0, 0, 0, 0)

        # 图像标签文字
        labels = ["载频", "脉宽", "幅度", "一级差", "方位角"]

        self.window.merge_plots = []  # 初始化列表

        # 添加5个图像和对应的标签
        for i, label_text in enumerate(labels):
            # 创建水平布局来放置标签和图像
            row_layout = QHBoxLayout()
            row_layout.setSpacing(self.window.dimensions["spacing_small"])

            # 创建竖排标签
            vertical_text = "\n".join(label_text)
            label = QLabel(vertical_text)
            label.setStyleSheet(self.window.styles["figure_label"])
            label.setFixedWidth(25)

            # 创建图像
            plot_widget = PlotWidget(scale_mode=ScaleMode.STRETCH)
            if i == 0:
                plot_widget.plot_layout.setContentsMargins(0, 0, 0, 5)
            elif i == 4:
                plot_widget.plot_layout.setContentsMargins(0, 5, 0, 0)
            else:
                plot_widget.plot_layout.setContentsMargins(0, 5, 0, 5)

            # 存储图像显示区域
            self.window.merge_plots.append(plot_widget)

            # 添加标签和图像到行布局
            row_layout.addWidget(label)
            row_layout.addWidget(plot_widget, 1)

            # 添加行布局到主布局
            plots_layout.addLayout(row_layout)

        layout.addWidget(plots_container)
        return layout

    def _create_merge_control_area(self) -> QVBoxLayout:
        """创建合并界面的控制区域

        Returns:
            控制区域布局
        """
        from .default_config import get_default_config

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 获取默认配置
        default_config = get_default_config()

        # 合并参数设置标题
        title_label = QLabel("合并参数设置")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(self.window.styles["title_label"])
        title_label.setFixedHeight(self.window.dimensions["title_height"])
        layout.addWidget(title_label)

        # 三组参数设置
        params_layout = QVBoxLayout()
        params_layout.setContentsMargins(0, 0, 0, 0)
        params_layout.setSpacing(10)

        self.window.merge_params = []

        # 创建三个参数组
        group1, doa_input1 = self._create_merge_mod1_group(default_config)
        group2, doa_input2 = self._create_merge_mod2_group(default_config)
        group3, doa_input3 = self._create_merge_mod3_group(default_config)

        params_config = get_params()
        cf_layout, cf_input2 = self._create_merge_cf_params_module(params_config.merge_params.pri_different.cf_tolerance)

        self.window.merge_params.append(doa_input1)
        self.window.merge_params.append(doa_input2)
        self.window.merge_params.append(cf_input2)
        self.window.merge_params.append(doa_input3)

        group1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        group2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        group3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        params_layout.addWidget(group1)
        params_layout.addWidget(group2)
        params_layout.addWidget(group3)

        # 按钮区域
        button_layout = self._create_merge_button_area()

        # 类别控制区域
        category_control_widget = self._create_category_control_area()

        # 表格
        table_layout = self._create_merge_table()

        # 添加到主布局
        layout.addLayout(cf_layout)
        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addLayout(params_layout)
        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addLayout(button_layout)
        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addWidget(category_control_widget)
        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        layout.addLayout(table_layout)
        # layout.addStretch()

        return layout

    def _create_category_control_area(self) -> QWidget:
        """创建类别控制区域

        Returns:
            QWidget: 类别控制组件
        """
        # 初始化合并可视化管理器
        if self.merge_visualization_manager is None:
            # 获取绘图管理器
            plot_manager = self.data_controller.plotter if self.data_controller else None
            if plot_manager:
                self.merge_visualization_manager = MergeVisualizationManager(self.window, plot_manager)

        # 创建并返回类别控制组件
        if self.merge_visualization_manager:
            # 连接信号和槽
            self.merge_visualization_manager.table_refresh.connect(self.update_table_data)
            return self.merge_visualization_manager.create_category_control_widget()
        else:
            # 如果无法创建管理器，返回空组件
            return QWidget()

    def _create_merge_mod1_group(self, default_config):
        """创建PRI存在且相等的参数设置组

        Args:
            default_config: 配置管理器实例

        Returns:
            Tuple[QGroupBox, QLineEdit]: 组件和输入框
        """
        group = QGroupBox("PRI可提取且存在相同值")
        group.setStyleSheet(self.window.styles["group_box"])
        group.setFixedHeight(70)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        params_config = get_params()
        doa_layout, doa_input = self._create_merge_doa_params_module(params_config.merge_params.pri_equal.doa_tolerance)

        layout.addLayout(doa_layout)
        group.setLayout(layout)

        return group, doa_input

    def _create_merge_mod2_group(self, default_config):
        """创建PRI存在且不相等的参数设置组

        Args:
            default_config: 配置管理器实例

        Returns:
            Tuple[QGroupBox, QLineEdit, QLineEdit]: 组件和输入框
        """
        group = QGroupBox("PRI可提取但不存在相同值")
        group.setStyleSheet(self.window.styles["group_box"])
        group.setFixedHeight(70)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        params_config = get_params()
        doa_layout, doa_input = self._create_merge_doa_params_module(params_config.merge_params.pri_different.doa_tolerance)
        # cf_layout, cf_input = self._create_merge_cf_params_module(params_config.merge_params.pri_different.cf_tolerance)

        layout.addLayout(doa_layout)
        # layout.addSpacing(5)
        # layout.addLayout(cf_layout)
        group.setLayout(layout)

        return group, doa_input

    def _create_merge_mod3_group(self, default_config):
        """创建PRI不存在的参数设置组

        Args:
            default_config: 配置管理器实例

        Returns:
            Tuple[QGroupBox, QLineEdit]: 组件和输入框
        """
        group = QGroupBox("PRI暂无法提取")
        group.setStyleSheet(self.window.styles["group_box"])
        group.setFixedHeight(70)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        params_config = get_params()
        doa_layout, doa_input = self._create_merge_doa_params_module(params_config.merge_params.pri_none.doa_tolerance)

        layout.addLayout(doa_layout)
        group.setLayout(layout)

        return group, doa_input

    def _create_merge_doa_params_module(self, doa_tolerance):
        """创建DOA参数设置模块

        Args:
            doa_tolerance: DOA容差值

        Returns:
            Tuple[QHBoxLayout, QLineEdit]: 布局和输入框
        """
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        doa_label = QLabel("DOA容差范围：")
        doa_label.setFixedHeight(self.window.dimensions["label_height"])
        doa_label.setFixedWidth(self.window.dimensions["label_width_large"])
        doa_label.setStyleSheet(self.window.styles["label"])

        doa_input = QLineEdit(str(doa_tolerance))
        doa_input.setFixedHeight(self.window.dimensions["input_height"])
        doa_input.setFixedWidth(self.window.dimensions["input_width"])
        doa_input.setStyleSheet(self.window.styles["line_edit"])
        doa_input.setFocusPolicy(Qt.ClickFocus)

        doa_unit = QLabel("  °")
        doa_unit.setFixedHeight(self.window.dimensions["label_height"])
        doa_unit.setFixedWidth(self.window.dimensions["label_unit_width"])
        doa_unit.setStyleSheet(self.window.styles["label"])

        layout.addWidget(doa_label)
        layout.addWidget(doa_input)
        layout.addWidget(doa_unit)
        layout.addStretch()

        return layout, doa_input

    def _create_merge_cf_params_module(self, cf_tolerance):
        """创建CF参数设置模块

        Args:
            cf_tolerance: CF容差值

        Returns:
            Tuple[QHBoxLayout, QLineEdit]: 布局和输入框
        """
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        cf_label = QLabel("全局CF容差范围：")
        cf_label.setFixedHeight(self.window.dimensions["label_height"])
        cf_label.setFixedWidth(130)
        cf_label.setStyleSheet(self.window.styles["bold_label"])

        cf_input = QLineEdit(str(cf_tolerance))
        cf_input.setFixedHeight(self.window.dimensions["input_height"])
        cf_input.setFixedWidth(self.window.dimensions["input_width"])
        cf_input.setStyleSheet(self.window.styles["line_edit"])
        cf_input.setFocusPolicy(Qt.ClickFocus)

        cf_unit = QLabel("  MHz")
        cf_unit.setFixedHeight(self.window.dimensions["label_height"])
        cf_unit.setFixedWidth(self.window.dimensions["label_unit_width"])
        cf_unit.setStyleSheet(self.window.styles["label"])

        layout.addWidget(cf_label)
        layout.addWidget(cf_input)
        layout.addWidget(cf_unit)
        layout.addStretch()

        return layout, cf_input

    def _create_merge_button_area(self):
        """创建合并界面按钮区域

        Returns:
            QVBoxLayout: 按钮区域布局
        """
        # 主布局使用垂直布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 第一行按钮布局
        first_row_layout = QHBoxLayout()
        first_row_layout.setContentsMargins(0, 0, 0, 0)

        # 开始合并按钮
        self.window.start_merge_btn = QPushButton("开始合并")
        self.window.start_merge_btn.setStyleSheet(self.window.styles["button"])
        self.window.start_merge_btn.clicked.connect(self._on_start_merge)

        # 重置合并按钮
        self.window.reset_merge_btn = QPushButton("重置")
        self.window.reset_merge_btn.setStyleSheet(self.window.styles["button"])
        self.window.reset_merge_btn.clicked.connect(self._on_reset_merge)

        # 上一个按钮
        self.window.last_btn = QPushButton("上一个")
        self.window.last_btn.setStyleSheet(self.window.styles["button"])
        self.window.last_btn.clicked.connect(self._on_previous)
        self.window.last_btn.setEnabled(False)  # 初始状态禁用

        # 下一个按钮
        self.window.next_btn = QPushButton("下一个")
        self.window.next_btn.setStyleSheet(self.window.styles["button"])
        self.window.next_btn.clicked.connect(self._on_next)
        self.window.next_btn.setEnabled(False)  # 初始状态禁用

        first_row_layout.addWidget(self.window.start_merge_btn)
        first_row_layout.addSpacing(5)
        first_row_layout.addWidget(self.window.reset_merge_btn)
        first_row_layout.addSpacing(5)
        first_row_layout.addWidget(self.window.last_btn)
        first_row_layout.addSpacing(5)
        first_row_layout.addWidget(self.window.next_btn)
        first_row_layout.addStretch()

        # 第二行：合并结果数量标签
        second_row_layout = QHBoxLayout()
        second_row_layout.setContentsMargins(0, 0, 0, 0)

        # 合并结果数量标签
        self.window.merge_count_label = QLabel("共获得？个合并结果")
        self.window.merge_count_label.setStyleSheet(self.window.styles["title_label"])
        self.window.merge_count_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        second_row_layout.addWidget(self.window.merge_count_label)
        second_row_layout.addStretch()

        # 将两行添加到主布局
        layout.addLayout(first_row_layout)
        layout.addSpacing(10)
        layout.addLayout(second_row_layout)

        return layout

    def _create_merge_table(self):
        """创建合并界面表格

        Returns:
            QVBoxLayout: 表格区域布局
        """
        layout = QVBoxLayout()

        # 创建表格标签
        table_label = QLabel("合并结果：")
        table_label.setStyleSheet(self.window.styles["title_label"])
        table_label.setFixedHeight(self.window.dimensions["input_height"])
        table_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # 创建表格部件
        self.window.merge_table = QTableWidget(4, 2)

        # 设置表头
        self.window.merge_table.setHorizontalHeaderLabels(["雷达信号", "合并结果"])
        self.window.merge_table.horizontalHeader().setFixedHeight(40)

        # 启用自动换行
        self.window.merge_table.setWordWrap(True)

        # 设置行标签
        row_labels = [
            "载频/MHz",
            "脉宽/us",
            "PRI/us",
            "DOA/°",
        ]

        # 在第一列填充标签
        for i, label in enumerate(row_labels):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(Qt.AlignCenter)
            item.setBackground(QColor(240, 240, 240))
            self.window.merge_table.setItem(i, 0, item)

        # 设置固定行高
        for i in range(4):
            if i != 2 and i != 0:
                self.window.merge_table.setRowHeight(i, 40)
                self.window.merge_table.verticalHeader().setSectionResizeMode(i, QHeaderView.Fixed)

        # 设置第1、3行高度自适应
        self.window.merge_table.verticalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.window.merge_table.verticalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        # 表格基本设置
        self.window.merge_table.setShowGrid(True)
        self.window.merge_table.verticalHeader().setVisible(False)

        # 设置列宽策略
        self.window.merge_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.window.merge_table.setColumnWidth(0, 130)
        self.window.merge_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.window.merge_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.window.merge_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 设置表格样式
        self.window.merge_table.setStyleSheet(self.window.styles["table"])

        # 修改大小策略
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        size_policy.setVerticalStretch(1)
        size_policy.setHeightForWidth(self.window.merge_table.sizePolicy().hasHeightForWidth())
        self.window.merge_table.setSizePolicy(size_policy)

        # 设置表格的最小高度
        def update_table_height():
            header_height = self.window.merge_table.horizontalHeader().height()
            content_height = sum(self.window.merge_table.rowHeight(i) for i in range(self.window.merge_table.rowCount()))
            total_height = header_height + content_height + 2

            min_row_height = 40
            min_visible_rows = 1
            min_height = header_height + (min_row_height * min_visible_rows)

            self.window.merge_table.setMinimumHeight(min_height)

            if total_height > min_height:
                self.window.merge_table.setMaximumHeight(total_height)
            else:
                self.window.merge_table.setMaximumHeight(min_height)

        # 在行高变化后更新表格高度
        self.window.merge_table.verticalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.window.merge_table.verticalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        # 监听内容变化
        self.window.merge_table.itemChanged.connect(lambda: QTimer.singleShot(0, update_table_height))

        # 监听列宽变化（窗口大小变化会导致列宽变化）
        self.window.merge_table.horizontalHeader().sectionResized.connect(lambda: QTimer.singleShot(0, update_table_height))

        # 初始更新一次高度
        QTimer.singleShot(0, update_table_height)

        # 添加到布局
        layout.addWidget(table_label)
        layout.addWidget(self.window.merge_table)
        layout.addStretch()

        return layout

    def _on_start_merge(self):
        """开始合并按钮点击事件"""
        try:
            if not self.data_controller:
                self.logger.error("错误：data_controller未初始化")
                return

            # 获取参数值
            params = self._get_merge_params()
            self.logger.info(f"合并参数: {params}")

            # 调用data_controller执行合并，传递参数
            success = self.data_controller.execute_merge_clusters(params)

            if success:
                # 获取合并结果
                self.merged_results = self.data_controller.merged_clusters
                self.logger.info(f"合并完成，生成了 {len(self.merged_results)} 个合并结果")

                if len(self.merged_results) > 0:
                    self.logger.info("进入合并结果显示")
                    # 重置到第一个合并结果
                    self.current_merge_index = 0
                    # 更新合并结果数量标签
                    self._update_merge_count_label(len(self.merged_results))
                    # 显示第一个合并结果的参数
                    self._display_merge_result(0)
                    # 更新按钮状态
                    self._update_navigation_buttons()
                else:
                    self.logger.info("没有生成合并结果")
                    # 显示没有合并结果的提示弹窗
                    from PyQt5.QtWidgets import QMessageBox

                    msg_box = QMessageBox()
                    msg_box.setWindowTitle("提示")
                    msg_box.setText("没有合并结果")
                    msg_box.setIcon(QMessageBox.Information)
                    msg_box.setStandardButtons(QMessageBox.Ok)
                    msg_box.exec_()
                    # 重置合并界面
                    self._on_reset_merge()
                    # 重置合并结果数量标签
                    self._update_merge_count_label(0)

            else:
                self.logger.info("合并失败或没有可合并的聚类")

        except Exception as e:
            self.logger.error(f"合并过程中出错: {str(e)}")

    def _on_reset_merge(self):
        """重置合并按钮点击事件"""
        try:
            # 清空本地合并结果
            self.merged_results = []
            self.current_merge_index = 0

            # 清空合并页面图像
            if hasattr(self.window, "merge_plots"):
                for plot in self.window.merge_plots:
                    plot.clear()
                self.logger.info("合并页面图像已清空")

            # 清空表格数据
            if hasattr(self.window, "merge_table"):
                for row in range(self.window.merge_table.rowCount()):
                    item = QTableWidgetItem(" ")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.window.merge_table.setItem(row, 1, item)
                self.logger.info("合并表格数据已清空")

            # 禁用导航按钮
            if hasattr(self.window, "last_btn"):
                self.window.last_btn.setEnabled(False)
            if hasattr(self.window, "next_btn"):
                self.window.next_btn.setEnabled(False)

            # 重置合并结果数量标签
            self._update_merge_count_label()

            # 重置合并图像标题
            self._update_merge_title()

            # 清空合并可视化管理器的状态
            if self.merge_visualization_manager:
                self.merge_visualization_manager.clear_display()

                self.logger.info("合并已重置")
            else:
                self.logger.info("错误：data_controller未初始化")
        except Exception as e:
            self.logger.error(f"重置合并时出错: {str(e)}")

    def _get_merge_params(self):
        """获取合并参数"""
        # 获取配置参数
        params_config = get_params()

        params = {
            "pri_equal": {
                "doa_tolerance": float(self.window.merge_params[0].text() or str(params_config.merge_params.pri_equal.doa_tolerance))  # doa_input1
            },
            "pri_different": {
                "doa_tolerance": float(self.window.merge_params[1].text() or str(params_config.merge_params.pri_different.doa_tolerance)),  # doa_input2
                "cf_tolerance": float(self.window.merge_params[2].text() or str(params_config.merge_params.pri_different.cf_tolerance)),  # cf_input2
            },
            "pri_none": {
                "doa_tolerance": float(self.window.merge_params[3].text() or str(params_config.merge_params.pri_none.doa_tolerance))  # doa_input3
            },
        }
        return params

    def update_table_data(self, merge_result):
        """更新表格数据

        Args:
            merge_result: 合并结果字典，包含参数信息
        """
        try:
            if not merge_result:
                return

            param_mapping = {
                0: ("CF", "载频/MHz"),
                1: ("PW", "脉宽/us"),
                2: ("DTOA", "PRI/us"),
                3: ("DOA", "DOA/°"),
            }

            # 更新表格第二列的数据
            for row, (key, _) in param_mapping.items():
                value = merge_result.get(key)
                if value is not None:
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.window.merge_table.setItem(row, 1, item)
                else:
                    # 如果参数值不存在，显示占位符
                    item = QTableWidgetItem(" ")
                    item.setTextAlignment(Qt.AlignCenter)
                    self.window.merge_table.setItem(row, 1, item)

            self.logger.info(f"表格已更新，显示 {self.window.merge_table.rowCount()} 行参数数据")

        except Exception as e:
            self.logger.error(f"更新表格数据时出错: {str(e)}")

    def _display_merge_result(self, index):
        """显示指定索引的合并结果

        Args:
            index: 合并结果索引
        """
        try:
            if 0 <= index < len(self.merged_results):
                merge_result = self.merged_results[index]
                # 更新表格显示
                self.logger.info(f"准备显示第 {index + 1} 个合并结果")
                self.update_table_data(merge_result)

                # 更新合并图像标题
                self._update_merge_title(index)

                # 更新图像显示
                if self.merge_visualization_manager:
                    self.merge_visualization_manager.update_merge_display(merge_result, index)

                self.logger.info(f"完成显示第 {index + 1} 个合并结果")
            else:
                self.logger.info(f"无效的合并结果索引: {index}")
        except Exception as e:
            self.logger.error(f"显示合并结果时出错: {str(e)}")

    def _update_navigation_buttons(self):
        """更新导航按钮的启用/禁用状态"""
        try:
            total_results = len(self.merged_results)

            if total_results <= 1:
                # 只有一个或没有结果时，禁用所有导航按钮
                self.window.last_btn.setEnabled(False)
                self.window.next_btn.setEnabled(False)
            else:
                # 多个结果时，根据当前索引更新按钮状态
                self.window.last_btn.setEnabled(self.current_merge_index > 0)
                self.window.next_btn.setEnabled(self.current_merge_index < total_results - 1)

            self.logger.info(f"导航按钮状态已更新 - 当前: {self.current_merge_index + 1}/{total_results}")
        except Exception as e:
            self.logger.error(f"更新导航按钮状态时出错: {str(e)}")

    def _on_previous(self):
        """上一个按钮点击事件"""
        try:
            if self.current_merge_index > 0:
                self.current_merge_index -= 1
                self._display_merge_result(self.current_merge_index)
                self._update_navigation_buttons()
                self.logger.info(f"切换到上一个合并结果: {self.current_merge_index + 1}/{len(self.merged_results)}")
        except Exception as e:
            self.logger.error(f"切换到上一个合并结果时出错: {str(e)}")

    def _on_next(self):
        """下一个按钮点击事件"""
        try:
            if self.current_merge_index < len(self.merged_results) - 1:
                self.current_merge_index += 1
                self._display_merge_result(self.current_merge_index)
                self._update_navigation_buttons()
                self.logger.info(f"切换到下一个合并结果: {self.current_merge_index + 1}/{len(self.merged_results)}")
        except Exception as e:
            self.logger.error(f"切换到下一个合并结果时出错: {str(e)}")

    def connect_scroll_events(self) -> None:
        """连接滚动相关的事件"""
        # 滚动相关事件连接
        pass

    def mousePressEvent(self, event):
        """处理鼠标点击事件，清除输入框焦点"""
        from PyQt5.QtWidgets import QApplication

        # 获取当前焦点控件
        focused_widget = QApplication.focusWidget()
        # 如果有控件被选中且是输入框
        if isinstance(focused_widget, QLineEdit):
            # 清除焦点
            focused_widget.clearFocus()
        # 调用父类的鼠标点击事件
        super().mousePressEvent(event)

    def update_merge_result(self, figure_data):
        """更新合并结果图像"""
        # TODO: 根据传入的数据更新图像显示
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # 这里可以根据实际需要绘制合并结果
        ax.text(
            0.5,
            0.5,
            "合并结果图像",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=16,
            color="blue",
        )

        self.figure.tight_layout()
        self.canvas.draw()

    def _update_merge_count_label(self, count: int = None):

        """更新合并结果数量标签"""
        try:
            if hasattr(self.window, "merge_count_label"):
                if count is not None:
                    self.window.merge_count_label.setText(f"共获得{count}个合并结果")
                else:
                    self.window.merge_count_label.setText("共获得？个合并结果")
                self.logger.info(f"合并结果数量标签已更新: {count}")
        except Exception as e:
            self.logger.error(f"更新合并结果数量标签时出错: {str(e)}")

    def _update_merge_title(self, index=None):
        """更新合并图像标题

        Args:
            index: 当前显示的合并结果索引，如果为None则显示默认标题
        """
        try:
            if hasattr(self.window, "merge_title"):
                if index is not None and len(self.merged_results) > 0:
                    total_results = len(self.merged_results)
                    self.window.merge_title.setText(f"合并后图像 ({index + 1}/{total_results})")
                else:
                    self.window.merge_title.setText("合并后图像")
                self.logger.info("合并图像标题已更新")
        except Exception as e:
            self.logger.error(f"更新合并图像标题时出错: {str(e)}")

    def _on_save(self):
        """保存按钮点击事件"""
        try:
            # 保存当前合并结果
            self.data_controller._save_current_merge_result(self.window.save_dir, self.merge_visualization_manager.merged_data)
            self.logger.info("合并结果已保存")
        except Exception as e:
            self.logger.error(f"保存合并结果时出错: {str(e)}")
