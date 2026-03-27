from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QGroupBox,
    QTableWidget,
    QHeaderView,
    QSizePolicy,
    QSpacerItem,
    QTableWidgetItem,
    QCheckBox,
    QTabWidget,
    QComboBox,
    QStackedWidget,
    QFrame,
    QScrollArea,
)
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtCore import Qt, QTimer, QSize
from cores.log_manager import LogManager
from common.paths import Paths
from .switch_widget import Switch
from .default_config import get_params
from .scroll_layout_manager import ScrollLayoutManager
from .sliding_stacked_widget import SlidingStackedWidget
from .components import CollapsibleCard, TabBar, CommandBar, FileListWidget, DashboardWidget


def setup_ui(window, params=None) -> None:
    """设置主窗口UI

    Args:
        window: 主窗口实例
        params: 参数配置实例，如果为None则使用window.params
    """
    logger = LogManager()
    logger.debug("开始设置主窗口UI")

    # 如果没有传入参数实例，尝试从window获取
    if params is None:
        params = getattr(window, "params", None)

    # 创建中央窗口部件
    central_widget = QWidget()
    window.setCentralWidget(central_widget)

    # 设置主窗口样式
    window.setStyleSheet(window.styles["main_window"])

    # 设置主布局的边距：上35px，其他10px
    main_layout = QHBoxLayout(central_widget)
    main_layout.setContentsMargins(10, 0, 10, 10)

    # 创建白色背景容器
    container = QWidget()
    container.setStyleSheet(window.styles["container"])
    main_layout.addWidget(container)

    # 在白色容器内创建布局，统一设置10px的边距
    container_layout = QHBoxLayout(container)
    container_layout.setContentsMargins(10, 10, 10, 10)
    container_layout.setSpacing(10)  # 列之间的间距设为10px

    # 创建滚动布局管理器
    scroll_manager = ScrollLayoutManager(window)
    window.scroll_layout_manager = scroll_manager  # 保存引用以便在main_window中使用
    window.scroll_container = scroll_manager.create_scroll_container()

    # 创建右侧列容器（使用SlidingStackedWidget管理数据导入界面和数据处理界面，支持滑动动画）
    right_stacked_widget = SlidingStackedWidget()
    right_stacked_widget.setFixedWidth(500)
    right_stacked_widget.set_animation_duration(350)  # 设置动画时长
    window.right_stacked_widget = right_stacked_widget  # 保存引用便于切换

    # 创建数据导入界面
    import_interface = _create_import_interface(window)
    right_stacked_widget.addWidget(import_interface)  # 索引0

    # 创建数据处理界面
    process_interface = _create_process_interface(window, params)
    right_stacked_widget.addWidget(process_interface)  # 索引1

    # 默认显示数据导入界面
    right_stacked_widget.setCurrentIndex(0)

    # 设置滚动布局（包含左侧、中间和合并区域）
    left_widget, middle_widget, merge_widget = scroll_manager.setup_scroll_layout()

    # 添加滚动容器和右侧控件到主布局
    container_layout.addWidget(window.scroll_container, 1)
    container_layout.addWidget(right_stacked_widget)

    # 连接滚动相关事件
    scroll_manager.connect_scroll_events()


def _create_import_interface(window) -> QWidget:
    """创建数据导入界面

    Args:
        window: 主窗口实例

    Returns:
        QWidget: 数据导入界面控件
    """
    widget = QWidget()
    widget.setMaximumWidth(500)
    widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 35, 0, 0)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    # 创建滚动区域
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_area.setMaximumWidth(500)
    scroll_area.setStyleSheet("""
        QScrollArea {
            background-color: transparent;
            border: none;
        }
        QScrollBar:vertical {
            width: 0px;
        }
    """)

    # 创建滚动内容容器
    scroll_content = QWidget()
    scroll_content.setStyleSheet("background-color: transparent;")
    scroll_content.setMaximumWidth(500)
    scroll_content_layout = QVBoxLayout(scroll_content)
    scroll_content_layout.setContentsMargins(0, 0, 0, 0)
    scroll_content_layout.setSpacing(15)

    # 创建可折叠卡片（已选择的文件）
    window.import_files_card = CollapsibleCard(
        title="脉冲描述字搜索数据库",
        icon_path=str(Paths.get_resource_path("resources/folder/folder.png")),
        action_text="添加新目录"
    )
    window.import_files_card.setMaximumWidth(500)
    scroll_content_layout.addWidget(window.import_files_card)

    # 创建标签页组件容器
    tab_container = QFrame()
    tab_container.setFixedHeight(500)
    tab_container.setFrameShape(QFrame.StyledPanel)
    tab_container.setMaximumWidth(500)
    tab_container.setStyleSheet("""
        QFrame {
            background-color: #F3F3F3;
            border: 1px solid #4772c3;
            border-radius: 3px;
        }
    """)

    tab_container_layout = QVBoxLayout(tab_container)
    tab_container_layout.setContentsMargins(0, 0, 0, 0)
    tab_container_layout.setSpacing(0)

    # 命令栏（放在标签栏上方）
    window.import_command_bar = CommandBar()
    tab_container_layout.addWidget(window.import_command_bar)

    # 命令栏与标签栏之间的分割线
    separator_line = QWidget()
    separator_line.setFixedHeight(1)
    separator_line.setStyleSheet("background-color: #E5E5E5;")
    tab_container_layout.addWidget(separator_line)

    # 创建标签栏（允许滚动）
    window.import_tab_bar = TabBar()
    window.import_tab_bar.setUsesScrollButtons(True)  # 启用滚动按钮
    window.import_tab_bar.add_tab("Excel", str(Paths.get_resource_path("resources/icons/Excel.png")))
    window.import_tab_bar.add_tab("Bin", str(Paths.get_resource_path("resources/icons/Data.png")))
    window.import_tab_bar.add_tab("MAT", str(Paths.get_resource_path("resources/icons/Mat.png")))
    tab_container_layout.addWidget(window.import_tab_bar)

    # 标签内容区域
    window.import_tab_stack = QStackedWidget()
    window.import_tab_stack.setStyleSheet("background-color: white; border: none")

    # 保存文件列表组件引用
    window.import_file_lists = {}

    # 为每个标签页创建内容页面
    for tab_name in ["Excel", "Bin", "MAT"]:
        # 创建文件列表组件
        file_list = FileListWidget()
        window.import_file_lists[tab_name] = file_list
        window.import_tab_stack.addWidget(file_list)

    tab_container_layout.addWidget(window.import_tab_stack, 1)

    # 连接标签切换信号
    window.import_tab_bar.tab_changed.connect(window.import_tab_stack.setCurrentIndex)

    scroll_content_layout.addWidget(tab_container)

    # 创建仪表盘组件容器（自适应高度）
    dashboard_container = QFrame()
    dashboard_container.setFrameShape(QFrame.StyledPanel)
    dashboard_container.setMaximumWidth(500)
    dashboard_container.setStyleSheet("""
        QFrame {
            background-color: #F3F3F3;
            border: 1px solid #4772c3;
            border-radius: 3px;
        }
    """)

    dashboard_container_layout = QVBoxLayout(dashboard_container)
    dashboard_container_layout.setContentsMargins(0, 0, 0, 0)
    dashboard_container_layout.setSpacing(0)

    # 仪表盘标题区域（水平布局：标签 + 导出按钮）
    dashboard_header = QWidget()
    dashboard_header.setFixedHeight(40)
    dashboard_header.setStyleSheet("background: transparent; border: none;")
    dashboard_header_layout = QHBoxLayout(dashboard_header)
    dashboard_header_layout.setContentsMargins(15, 4, 10, 4)
    dashboard_header_layout.setSpacing(0)

    window.dashboard_info_label = QLabel("文件信息")
    window.dashboard_info_label.setStyleSheet("""
        QLabel {
            color: #4772c3;
            font-size: 14px;
            font-family: "Microsoft YaHei";
            background: transparent;
            border: none;
        }
    """)
    dashboard_header_layout.addWidget(window.dashboard_info_label)
    dashboard_header_layout.addStretch(1)

    # 导出按钮
    window.export_dashboard_btn = QPushButton()
    window.export_dashboard_btn.setIcon(QIcon(str(Paths.get_resource_path("resources/icons/export.svg"))))
    window.export_dashboard_btn.setIconSize(QSize(16, 16))
    window.export_dashboard_btn.setText(" 导出")
    window.export_dashboard_btn.setCursor(Qt.PointingHandCursor)
    window.export_dashboard_btn.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            border: none;
            padding: 6px 6px;
            color: #4772c3;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: rgba(0, 0, 0, 0.05);
            border-radius: 4px;
        }
        QPushButton:pressed {
            background-color: rgba(0, 0, 0, 0.1);
        }
        QPushButton:disabled {
            color: #999999;
        }
    """)
    dashboard_header_layout.addWidget(window.export_dashboard_btn)
    window.export_dashboard_btn.setEnabled(False)  # 初始禁用，BIN解析完成后启用

    dashboard_container_layout.addWidget(dashboard_header)

    # 仪表盘信息与标签栏之间的分割线
    separator_line = QWidget()
    separator_line.setFixedHeight(1)
    separator_line.setStyleSheet("background-color: #E5E5E5;")
    dashboard_container_layout.addWidget(separator_line)

    # 创建标签栏（允许滚动）
    window.dashboard_tab_bar = TabBar()
    window.dashboard_tab_bar.add_tab("", "")
    dashboard_container_layout.addWidget(window.dashboard_tab_bar)

    # 标签内容区域
    window.dashboard_tab_stack = QStackedWidget()
    window.dashboard_tab_stack.setStyleSheet("background-color: white; border: none")

    # 为每个标签页创建内容页面
    for tab_name in ["L波段"]:
        # 创建仪表盘组件
        dashboard = DashboardWidget()
        window.dashboard_tab_stack.addWidget(dashboard)

    dashboard_container_layout.addWidget(window.dashboard_tab_stack)

    # 连接标签切换信号
    window.dashboard_tab_bar.tab_changed.connect(window.dashboard_tab_stack.setCurrentIndex)

    scroll_content_layout.addWidget(dashboard_container)
    scroll_content_layout.addStretch(1)  # 添加弹性空间，防止组件被拉伸

    # 设置滚动区域内容
    scroll_area.setWidget(scroll_content)
    layout.addWidget(scroll_area, 1)  # 给滚动区域分配伸展因子

    # 滚动区域与底部按钮之间的间距
    layout.addSpacing(15)

    # 底部按钮区域
    bottom_layout = QHBoxLayout()
    bottom_layout.setContentsMargins(0, 0, 0, 0)
    bottom_layout.setSpacing(10)
    bottom_layout.addStretch(1)  # 左侧弹性空间

    # 创建已选中标签（初始隐藏）
    window.selected_info_label = QLabel("")
    window.selected_info_label.setStyleSheet("""
        QLabel {
            color: #4772c3;
            font-size: 12px;
            font-family: "Microsoft YaHei";
        }
    """)
    window.selected_info_label.hide()
    bottom_layout.addWidget(window.selected_info_label)

    # 创建导入数据按钮
    window.import_data_btn = QPushButton("导入数据")
    window.import_data_btn.setStyleSheet(window.styles["large_button"])
    window.import_data_btn.setCursor(Qt.PointingHandCursor)
    window.import_data_btn.setEnabled(False)  # 默认禁用，解析完成后启用
    bottom_layout.addWidget(window.import_data_btn)

    # 创建返回数据处理界面按钮（初始隐藏）
    window.return_to_process_btn = QPushButton("返回")
    window.return_to_process_btn.setStyleSheet(window.styles["button"])
    window.return_to_process_btn.setCursor(Qt.PointingHandCursor)
    window.return_to_process_btn.hide()  # 初始隐藏
    bottom_layout.addWidget(window.return_to_process_btn)

    layout.addLayout(bottom_layout)

    return widget


def _create_process_interface(window, params=None) -> QWidget:
    """创建数据处理界面

    Args:
        window: 主窗口实例
        params: 参数配置实例

    Returns:
        QWidget: 数据处理界面控件
    """
    widget = QWidget()
    main_layout = QVBoxLayout(widget)
    main_layout.setContentsMargins(0, 5, 0, 0)
    main_layout.setSpacing(0)

    # 后退按钮模块（独立区域）
    back_layout = QHBoxLayout()
    back_layout.setContentsMargins(0, 0, 0, 0)
    back_layout.setSpacing(0)

    # 创建后退按钮
    window.back_btn = QPushButton()
    window.back_btn.setIcon(QIcon(str(Paths.get_resource_path("resources/Arrow/back_arrow.png"))))
    window.back_btn.setIconSize(QSize(24, 24))
    window.back_btn.setFixedSize(30, 30)
    window.back_btn.setCursor(Qt.PointingHandCursor)
    window.back_btn.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            border: none;
        }
        QPushButton:hover {
            background-color: #e6f3ff;
            border-radius: 5px;
        }
        QPushButton:pressed {
            background-color: #d0e8ff;
            border-radius: 5px;
        }
    """)
    window.back_btn.setToolTip("返回初始界面")
    back_layout.addWidget(window.back_btn)
    back_layout.addStretch(1)

    main_layout.addLayout(back_layout)

    # 固定间距 10px
    main_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 切片信息模块
    slice_info_layout = _create_slice_info_module(window)
    main_layout.addLayout(slice_info_layout)

    # 固定间距 10px
    main_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 切换模型模块
    model_switch_layout = _create_model_switch_module(window)
    main_layout.addLayout(model_switch_layout)

    # 固定间距 10px
    main_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
    
    # 参数配置模块（带折叠功能）
    params_container = _create_collapsible_params_module(window, params)
    
    main_layout.addWidget(params_container)

    # 固定间距 10px
    main_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 标签页区域
    tab_widget = _create_tab_widget(window)
    tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    main_layout.addWidget(tab_widget)

    return widget

def _create_slice_info_module(window) -> QHBoxLayout:
    """创建切片信息模块"""
    layout = QHBoxLayout()
    layout.setSpacing(0)
    layout.setContentsMargins(0, 0, 0, 0)

    # 创建标签
    window.slice_info_label1 = QLabel("数据包位于？波段，")
    window.slice_info_label1.setStyleSheet(window.styles["title_label"])
    window.slice_info_label1.setAlignment(Qt.AlignLeft)
    window.slice_info_label1.setFixedHeight(window.dimensions["line_max_height"])

    window.slice_info_label2 = QLabel("预计将获得  0  个250ms切片")
    window.slice_info_label2.setStyleSheet(window.styles["title_label"])
    window.slice_info_label2.setAlignment(Qt.AlignLeft)
    window.slice_info_label2.setFixedHeight(window.dimensions["line_max_height"])
    window.slice_info_label2.setTextFormat(Qt.RichText)  # 允许 HTML 格式

    layout.addWidget(window.slice_info_label1)
    layout.addWidget(window.slice_info_label2)
    layout.addStretch()

    return layout


def _create_collapsible_params_module(window, params) -> QWidget:
    """创建可折叠的参数配置模块"""
    params_container = QWidget()
    params_container_layout = QVBoxLayout(params_container)
    params_container_layout.setContentsMargins(0, 0, 0, 0)
    params_container_layout.setSpacing(0)

    # 标题栏
    header_widget = QWidget()
    header_layout = QHBoxLayout(header_widget)
    header_layout.setContentsMargins(0, 0, 0, 0)
    
    title_label = QLabel("参数配置")
    title_label.setStyleSheet(window.styles["title_label"]) 
    
    toggle_btn = QPushButton()
    toggle_btn.setFixedSize(24, 24)
    toggle_btn.setCursor(Qt.PointingHandCursor)
    toggle_btn.setStyleSheet("border: none; background: transparent;")
    
    # 图标路径
    up_icon_path = str(Paths.get_resource_path("resources/icons/up.png")).replace("\\", "/")
    down_icon_path = str(Paths.get_resource_path("resources/icons/down.png")).replace("\\", "/")
    
    up_icon = QIcon(up_icon_path)
    down_icon = QIcon(down_icon_path)
    
    toggle_btn.setIcon(down_icon) # 默认收起，显示向下箭头（点击展开）
    
    header_layout.addWidget(title_label)
    header_layout.addStretch()
    header_layout.addWidget(toggle_btn)
    
    params_container_layout.addWidget(header_widget)
    
    # 内容区域
    content_widget = QWidget()
    params_layout = QHBoxLayout(content_widget)
    params_layout.setContentsMargins(0, 5, 0, 0)
    params_layout.setSpacing(10)
    
    cluster_module = _create_cluster_params_module(window, params)
    recognition_module = _create_recognition_params_module(window, params)
    
    cluster_module.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    recognition_module.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    params_layout.addWidget(cluster_module)
    params_layout.addWidget(recognition_module)
    
    params_container_layout.addWidget(content_widget)
    
    # 默认隐藏内容区域
    content_widget.hide()

    # 折叠逻辑
    def toggle_params(event=None):
        if content_widget.isVisible():
            content_widget.hide()
            toggle_btn.setIcon(down_icon)
        else:
            content_widget.show()
            toggle_btn.setIcon(up_icon)
            
    toggle_btn.clicked.connect(lambda: toggle_params())
    
    # 使整个标题栏可点击
    header_widget.setCursor(Qt.PointingHandCursor)
    header_widget.mousePressEvent = toggle_params
    
    return params_container


def _create_model_switch_module(window) -> QVBoxLayout:
    """创建模型切换模块"""
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)


    # 样式设置 (参考 image_render_combo)
    combo_style = window.styles["combo_box"]
    # 使用 Paths 管理图标路径
    expand_path = str(Paths.get_resource_path("resources/Arrow/expand.png")).replace("\\", "/")
    collapse_path = str(Paths.get_resource_path("resources/Arrow/collapse.png")).replace("\\", "/")
    combo_style = combo_style.replace("resources/Arrow/expand.png", expand_path)
    combo_style = combo_style.replace("resources/Arrow/collapse.png", collapse_path)

    # --- PA模型切换部分 ---
    pa_layout = QHBoxLayout()
    pa_label = QLabel("PA模型")
    pa_label.setStyleSheet(window.styles["label"])
    pa_label.setFixedWidth(window.dimensions["label_width_small"])
    pa_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    window.pa_model_combo = QComboBox()
    window.pa_model_combo.setStyleSheet(combo_style)
    window.pa_model_combo.setFixedHeight(window.dimensions["input_height"])
    window.pa_model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def update_pa_model_combo():
        current_model = window.pa_model_combo.currentText()
        models = window.data_controller.get_pa_model_list()
        window.pa_model_combo.blockSignals(True)
        window.pa_model_combo.clear()
        window.pa_model_combo.addItems(models)
        
        index = window.pa_model_combo.findText(current_model)
        if index >= 0:
            window.pa_model_combo.setCurrentIndex(index)
        elif window.pa_model_combo.count() > 0:
            window.pa_model_combo.setCurrentIndex(0)
        
        window.pa_model_combo.blockSignals(False)

    window.data_controller.models_changed.connect(update_pa_model_combo)
    window.pa_model_combo.currentTextChanged.connect(window.data_controller.switch_pa_model)
    update_pa_model_combo()

    pa_layout.addWidget(pa_label)
    pa_layout.addWidget(window.pa_model_combo)
    layout.addLayout(pa_layout)

    # --- DTOA模型切换部分 ---
    dtoa_layout = QHBoxLayout()
    dtoa_label = QLabel("DTOA模型")
    dtoa_label.setStyleSheet(window.styles["label"])
    dtoa_label.setFixedWidth(window.dimensions["label_width_small"])
    dtoa_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    window.dtoa_model_combo = QComboBox()
    window.dtoa_model_combo.setStyleSheet(combo_style)
    window.dtoa_model_combo.setFixedHeight(window.dimensions["input_height"])
    window.dtoa_model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def update_dtoa_model_combo():
        current_model = window.dtoa_model_combo.currentText()
        models = window.data_controller.get_dtoa_model_list()
        window.dtoa_model_combo.blockSignals(True)
        window.dtoa_model_combo.clear()
        window.dtoa_model_combo.addItems(models)
        
        index = window.dtoa_model_combo.findText(current_model)
        if index >= 0:
            window.dtoa_model_combo.setCurrentIndex(index)
        elif window.dtoa_model_combo.count() > 0:
            window.dtoa_model_combo.setCurrentIndex(0)
        
        window.dtoa_model_combo.blockSignals(False)

    window.data_controller.models_changed.connect(update_dtoa_model_combo)
    window.dtoa_model_combo.currentTextChanged.connect(window.data_controller.switch_dtoa_model)
    update_dtoa_model_combo()

    dtoa_layout.addWidget(dtoa_label)
    dtoa_layout.addWidget(window.dtoa_model_combo)
    layout.addLayout(dtoa_layout)
    
    return layout


def _create_cluster_params_module(window, params_config=None) -> QGroupBox:
    """创建聚类参数模块

    Args:
        window: 主窗口实例
        params_config: 参数配置实例，如果为None则调用get_params()

    Returns:
        QGroupBox: 聚类参数设置组件
    """
    if params_config is None:
        params_config = get_params()

    group = QGroupBox("聚类参数设置")
    group.setStyleSheet(window.styles["group_box"])
    group.setFixedHeight(window.dimensions["group_box_height"])

    layout = QVBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(0)

    # 参数配置 - 使用配置管理类获取默认值
    params = [
        ("epsilon_CF:", str(params_config.clustering_params.epsilon_CF), "  MHz"),
        ("epsilon_PW:", str(params_config.clustering_params.epsilon_PW), "  us"),
        ("min_pts:", str(params_config.clustering_params.min_pts), ""),
    ]

    window.param_inputs = []

    for label_text, default_value, label_unit in params:
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(label_text)
        label.setFixedHeight(window.dimensions["label_height"])
        label.setFixedWidth(window.dimensions["label_width_middle"])
        label.setStyleSheet(window.styles["label"])

        input_field = QLineEdit(default_value)
        input_field.setFixedHeight(window.dimensions["input_height"])
        input_field.setFixedWidth(window.dimensions["input_width"])
        input_field.setStyleSheet(window.styles["line_edit"])
        input_field.setFocusPolicy(Qt.ClickFocus)

        unit = QLabel(label_unit)
        unit.setFixedHeight(window.dimensions["label_height"])
        unit.setFixedWidth(window.dimensions["label_unit_width"])
        unit.setStyleSheet(window.styles["label"])

        window.param_inputs.append(input_field)

        row_layout.addWidget(label)
        row_layout.addWidget(input_field)
        row_layout.addWidget(unit)
        row_layout.addStretch()

        layout.addLayout(row_layout)
        # 添加固定间距（除了最后一个参数）
        if label_text != params[-1][0]:
            layout.addSpacing(5)

    group.setLayout(layout)
    return group


def _create_recognition_params_module(window, params_config=None) -> QGroupBox:
    """创建识别参数模块

    Args:
        window: 主窗口实例
        params_config: 参数配置实例，如果为None则调用get_params()

    Returns:
        QGroupBox: 识别参数设置组件
    """
    if params_config is None:
        params_config = get_params()

    group = QGroupBox("识别参数设置")
    group.setStyleSheet(window.styles["group_box"])
    group.setFixedHeight(window.dimensions["group_box_height"])

    layout = QVBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(0)

    # 获取配置参数
    params_config = get_params()

    # 参数配置 - 使用配置管理类获取默认值
    params = [
        ("PA判别门限", str(params_config.identification_params.pa_threshold)),
        ("DTOA判别门限", str(params_config.identification_params.dtoa_threshold)),
        ("PA判别权重:", str(params_config.identification_params.pa_weight)),
        ("DTOA判别权重:", str(params_config.identification_params.dtoa_weight)),
        ("联合判别门限:", str(params_config.identification_params.threshold)),
    ]

    # 定义需要隐藏的参数标签
    hidden_params = ["PA判别权重:", "DTOA判别权重:"]

    for label_text, default_value in params:
        # 跳过隐藏的参数，但仍然创建输入框以保持索引一致性
        if label_text in hidden_params:
            # 创建隐藏的输入框，添加到param_inputs但不显示在UI上
            hidden_input = QLineEdit(default_value)
            hidden_input.setVisible(False)  # 设置为不可见
            window.param_inputs.append(hidden_input)
            continue

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(label_text)
        label.setFixedHeight(window.dimensions["label_height"])
        label.setFixedWidth(window.dimensions["label_width_large"])
        label.setStyleSheet(window.styles["label"])

        input_field = QLineEdit(default_value)
        input_field.setFixedHeight(window.dimensions["input_height"])
        input_field.setFixedWidth(window.dimensions["input_width"])
        input_field.setStyleSheet(window.styles["line_edit"])
        input_field.setFocusPolicy(Qt.ClickFocus)

        window.param_inputs.append(input_field)

        row_layout.addWidget(label)
        row_layout.addWidget(input_field)
        row_layout.addStretch()

        layout.addLayout(row_layout)
        # 添加固定间距（除了最后一个参数）
        if label_text != params[-1][0]:
            layout.addSpacing(5)

    group.setLayout(layout)
    return group


def _create_merge_params_module(window, params_config=None) -> QGroupBox:
    """创建合并参数模块

    Args:
        window: 主窗口实例
        params_config: 参数配置实例，如果为None则调用get_params()

    Returns:
        QGroupBox: 合并参数设置组件
    """
    if params_config is None:
        params_config = get_params()

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    merge_title = QLabel("合并参数设置：")
    merge_title.setAlignment(Qt.AlignLeft)
    merge_title.setStyleSheet(window.styles["title_label"])
    merge_title.setFixedHeight(window.dimensions["title_height"])

    total_CF_layout, cf_input2 = _create_merge_cf_params_module(window, params_config.merge_params.pri_different.cf_tolerance)

    group1 = QGroupBox("PRI可提取且存在相同值")
    group1.setStyleSheet(window.styles["group_box"])
    group1.setFixedHeight(70)
    group1_layout = QVBoxLayout()
    group1_layout.setContentsMargins(5, 5, 5, 5)
    group1_layout.setSpacing(0)
    doa_layout1, doa_input1 = _create_merge_doa_params_module(window, params_config.merge_params.pri_equal.doa_tolerance)
    group1_layout.addLayout(doa_layout1)
    group1.setLayout(group1_layout)

    group2 = QGroupBox("PRI可提取但不存在相同值")
    group2.setStyleSheet(window.styles["group_box"])
    group2.setFixedHeight(70)
    group2_layout = QVBoxLayout()
    group2_layout.setContentsMargins(5, 5, 5, 5)
    group2_layout.setSpacing(0)
    doa_layout2, doa_input2 = _create_merge_doa_params_module(window, params_config.merge_params.pri_different.doa_tolerance)
    # cf_layout2, cf_input2 = _create_merge_cf_params_module(window, params_config.merge_params.pri_different.cf_tolerance)
    group2_layout.addLayout(doa_layout2)
    # group2_layout.addSpacing(5)
    # group2_layout.addLayout(cf_layout2)
    group2.setLayout(group2_layout)

    group3 = QGroupBox("PRI暂无法提取")
    group3.setStyleSheet(window.styles["group_box"])
    group3.setFixedHeight(70)
    group3_layout = QVBoxLayout()
    group3_layout.setContentsMargins(5, 5, 5, 5)
    group3_layout.setSpacing(0)
    doa_layout3, doa_input3 = _create_merge_doa_params_module(window, params_config.merge_params.pri_none.doa_tolerance)
    group3_layout.addLayout(doa_layout3)
    group3.setLayout(group3_layout)

    # 初始化合并参数输入框列表
    window.merge_param_inputs = []
    window.merge_param_inputs.append(doa_input1)
    window.merge_param_inputs.append(doa_input2)
    window.merge_param_inputs.append(cf_input2)
    window.merge_param_inputs.append(doa_input3)

    group1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    group2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    group3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    layout.addWidget(merge_title)
    layout.addLayout(total_CF_layout)
    layout.addSpacing(10)
    layout.addWidget(group1)
    layout.addSpacing(10)
    layout.addWidget(group2)
    layout.addSpacing(10)
    layout.addWidget(group3)

    return layout


def _create_merge_doa_params_module(window, doa_tolerance):
    """创建DOA参数设置模块

    Args:
        doa_tolerance: DOA容差值

    Returns:
        Tuple[QHBoxLayout, QLineEdit]: 布局和输入框
    """
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)

    doa_label = QLabel("DOA容差范围：")
    doa_label.setFixedHeight(window.dimensions["label_height"])
    doa_label.setFixedWidth(window.dimensions["label_width_large"])
    doa_label.setStyleSheet(window.styles["label"])

    doa_input = QLineEdit(str(doa_tolerance))
    doa_input.setFixedHeight(window.dimensions["input_height"])
    doa_input.setFixedWidth(window.dimensions["input_width"])
    doa_input.setStyleSheet(window.styles["line_edit"])
    doa_input.setFocusPolicy(Qt.ClickFocus)

    doa_unit = QLabel("  °")
    doa_unit.setFixedHeight(window.dimensions["label_height"])
    doa_unit.setFixedWidth(window.dimensions["label_unit_width"])
    doa_unit.setStyleSheet(window.styles["label"])

    layout.addWidget(doa_label)
    layout.addWidget(doa_input)
    layout.addWidget(doa_unit)
    layout.addStretch()

    return layout, doa_input


def _create_merge_cf_params_module(window, cf_tolerance):
    """创建CF参数设置模块

    Args:
        cf_tolerance: CF容差值

    Returns:
        Tuple[QHBoxLayout, QLineEdit]: 布局和输入框
    """
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)

    cf_label = QLabel("全局CF容差范围：")
    cf_label.setFixedHeight(window.dimensions["label_height"])
    cf_label.setFixedWidth(130)
    cf_label.setStyleSheet(window.styles["bold_label"])

    cf_input = QLineEdit(str(cf_tolerance))
    cf_input.setFixedHeight(window.dimensions["input_height"])
    cf_input.setFixedWidth(window.dimensions["input_width"])
    cf_input.setStyleSheet(window.styles["line_edit"])
    cf_input.setFocusPolicy(Qt.ClickFocus)

    cf_unit = QLabel("  MHz")
    cf_unit.setFixedHeight(window.dimensions["label_height"])
    cf_unit.setFixedWidth(window.dimensions["label_unit_width"])
    cf_unit.setStyleSheet(window.styles["label"])

    layout.addWidget(cf_label)
    layout.addWidget(cf_input)
    layout.addWidget(cf_unit)
    layout.addStretch()

    return layout, cf_input


def _create_tab_widget(window) -> QTabWidget:
    """创建标签页布局"""
    # 创建标签页容器
    tab_widget = QTabWidget()
    tab_widget.setStyleSheet(window.styles["tab_widgets"])

    # 创建切片处理标签页
    slice_proc_tab = QWidget()
    slice_proc_tab_layout = QVBoxLayout(slice_proc_tab)
    slice_proc_tab_layout.setContentsMargins(0, 10, 0, 0)
    slice_proc_tab_layout.setSpacing(0)

    # 添加切片处理模块到切片处理标签页
    slice_process_layout = _create_slice_process_module(window)
    slice_proc_tab_layout.addLayout(slice_process_layout)

    # 固定间距 10px
    slice_proc_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 添加图像显示模式模块到切片处理标签页
    figure_show_mode = _create_switch_module(window)
    slice_proc_tab_layout.addLayout(figure_show_mode)

    # 固定间距 10px
    slice_proc_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 添加重绘模块到切片处理标签页
    redraw_layout = _create_redraw_module(window)
    slice_proc_tab_layout.addLayout(redraw_layout)

    # 固定间距 10px
    slice_proc_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 添加保存模块到切片处理标签页
    save_layout = _create_save_slice_proc_module(window)
    slice_proc_tab_layout.addLayout(save_layout)

    # 固定间距 10px
    slice_proc_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 添加表格到切片处理标签页
    table_layout = _create_table_widget(window)
    slice_proc_tab_layout.addLayout(table_layout)  # 给表格分配权重1，让它占用更多空间

    # 切片处理标签页添加最小弹性空间
    # slice_proc_tab_layout.addStretch(0)

    # 创建全速处理标签页
    full_speed_tab = QWidget()
    full_speed_layout = QVBoxLayout(full_speed_tab)
    full_speed_layout.setContentsMargins(0, 10, 0, 0)
    full_speed_layout.setSpacing(0)

    # 添加合并参数模块
    merge_params_layout = _create_merge_params_module(window)
    full_speed_layout.addLayout(merge_params_layout)

    # 添加保存全速处理结果模块
    save_full_speed_layout = _create_save_full_speed_module(window)
    full_speed_layout.addLayout(save_full_speed_layout)

    # 固定间距 10px
    full_speed_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 添加开始处理按钮模块
    start_process_layout = _create_full_speed_start_process_module(window)
    full_speed_layout.addLayout(start_process_layout)

    # 固定间距 10px
    full_speed_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

    # 添加进度条模块
    progress_layout = _create_progress_module(window)
    full_speed_layout.addLayout(progress_layout)

    # 添加处理详情标签
    process_detail_layout = _create_process_detail_module(window)
    full_speed_layout.addLayout(process_detail_layout)

    # 全速处理标签页添加最小弹性空间
    full_speed_layout.addStretch(0)

    # 添加标签页到标签页容器
    tab_widget.addTab(slice_proc_tab, "切片处理")
    tab_widget.addTab(full_speed_tab, "全速处理")

    # 保存标签页对象方便后续访问
    window.slice_proc_tab = slice_proc_tab
    window.full_speed_tab = full_speed_tab
    window.tab_widget = tab_widget

    # 标签页切换的事件处理
    def on_tab_changed(index):
        # 切换到切片处理标签页
        if index == 0:
            window.logger.debug("切换到切片处理标签页")
            # 在这里可以添加切换到切片处理标签页时的逻辑
        # 切换到全速处理标签页
        elif index == 1:
            window.logger.debug("切换到全速处理标签页")
            # 在这里可以添加切换到全速处理标签页时的逻辑

    # 连接标签页切换信号
    tab_widget.currentChanged.connect(on_tab_changed)

    # 获取标签页栏并设置光标
    tab_bar = tab_widget.tabBar()
    tab_bar.setCursor(Qt.PointingHandCursor)

    return tab_widget


def _create_slice_process_module(window) -> QVBoxLayout:
    """创建切片处理模块"""
    main_layout = QVBoxLayout()  # 使用垂直布局

    # 创建水平布局1
    row_layout1 = QHBoxLayout()

    # 创建开始切片按钮
    window.start_slice_btn = QPushButton("开始切片")
    window.start_slice_btn.setStyleSheet(window.styles["button"])
    window.start_slice_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.start_slice_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建识别按钮
    window.identify_btn = QPushButton("识别")
    window.identify_btn.setStyleSheet(window.styles["button"])
    window.identify_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.identify_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建合并菜单按钮
    window.merge_menu_btn = QPushButton("合并菜单")
    window.merge_menu_btn.setStyleSheet(window.styles["button"])
    window.merge_menu_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.merge_menu_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 添加组件到第一行布局
    row_layout1.addWidget(window.start_slice_btn)  # 开始切片按钮
    row_layout1.addSpacing(8)
    row_layout1.addWidget(window.identify_btn)  # 识别按钮
    row_layout1.addSpacing(8)
    row_layout1.addWidget(window.merge_menu_btn)  # 合并菜单按钮
    row_layout1.addStretch()

    # 创建下一片按钮
    window.next_slice_btn = QPushButton("下一片")
    window.next_slice_btn.setStyleSheet(window.styles["button"])
    window.next_slice_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.next_slice_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建下一类按钮
    window.next_cluster_btn = QPushButton("下一类")
    window.next_cluster_btn.setStyleSheet(window.styles["button"])
    window.next_cluster_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.next_cluster_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建重置当前切片按钮
    window.reset_slice_btn = QPushButton("重置当前切片")
    window.reset_slice_btn.setStyleSheet(window.styles["large_button"])
    window.reset_slice_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.reset_slice_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建复选框
    window.auto_identify_checkbox = QCheckBox("点击下一片后自动识别")
    window.auto_identify_checkbox.setStyleSheet(window.styles["checkbox"])
    window.auto_identify_checkbox.setChecked(True)
    window.auto_identify_checkbox.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建水平布局2
    row_layout2 = QHBoxLayout()
    row_layout2.addWidget(window.next_cluster_btn)
    row_layout2.addSpacing(8)
    row_layout2.addWidget(window.next_slice_btn)
    row_layout2.addSpacing(8)
    row_layout2.addWidget(window.reset_slice_btn)
    row_layout2.addSpacing(25)
    row_layout2.addWidget(window.auto_identify_checkbox)

    # 添加到主布局
    main_layout.addLayout(row_layout1)
    main_layout.addSpacing(5)
    main_layout.addLayout(row_layout2)

    return main_layout


def _create_progress_module(window) -> QHBoxLayout:
    """创建进度条模块"""
    layout = QHBoxLayout()

    # 创建进度条
    window.progress_bar = QProgressBar()
    window.progress_bar.setFixedHeight(window.dimensions["progress_height"])
    window.progress_bar.setStyleSheet(window.styles["progress_bar"])
    window.progress_bar.setAlignment(Qt.AlignCenter)
    window.progress_bar.setTextVisible(False)

    # 创建进度标签
    window.progress_label = QLabel("0%")
    window.progress_label.setStyleSheet(window.styles["title_label"])
    window.progress_label.setFixedWidth(60)
    window.progress_label.setFixedHeight(20)
    window.progress_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

    # 添加到布局
    layout.addWidget(window.progress_bar)
    layout.addWidget(window.progress_label)

    return layout


def _create_process_detail_module(window) -> QHBoxLayout:
    """创建处理详情模块"""
    layout = QHBoxLayout()

    # 创建标签
    window.process_detail_label = QLabel("")
    window.process_detail_label.setStyleSheet(window.styles["label"])
    window.process_detail_label.setFixedHeight(window.dimensions["input_height"])
    window.process_detail_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    # 添加到布局
    layout.addWidget(window.process_detail_label)

    return layout


def _create_redraw_module(window) -> QHBoxLayout:
    """创建重绘模块"""
    layout = QHBoxLayout()
    layout.setSpacing(0)

    # 创建选择切片标签
    window.slice_select_label = QLabel("输入切片编号:")
    window.slice_select_label.setFixedHeight(window.dimensions["label_height"])
    window.slice_select_label.setFixedWidth(window.dimensions["label_width_middle"])
    window.slice_select_label.setStyleSheet(window.styles["label"])

    # 创建输入框
    window.additional_input = QLineEdit()
    window.additional_input.setFixedHeight(window.dimensions["input_height"])
    window.additional_input.setStyleSheet(window.styles["line_edit"])
    window.additional_input.setFocusPolicy(Qt.ClickFocus)
    window.additional_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # 创建重绘按钮
    window.redraw_btn = QPushButton("绘制")
    window.redraw_btn.setStyleSheet(window.styles["button"])
    window.redraw_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    window.redraw_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 添加到布局
    layout.addWidget(window.slice_select_label)
    layout.addSpacing(10)
    layout.addWidget(window.additional_input)
    layout.addSpacing(5)
    layout.addWidget(window.redraw_btn)

    return layout


def _create_save_slice_proc_module(window) -> QHBoxLayout:
    """创建保存模块"""
    layout = QHBoxLayout()
    layout.setSpacing(window.dimensions["spacing_small"])
    layout.setContentsMargins(0, 0, 0, 0)

    # 创建选择保存路径按钮
    window.browse_save_btn1 = QPushButton("选择路径")
    window.browse_save_btn1.setStyleSheet(window.styles["middle_button"])
    window.browse_save_btn1.setFixedHeight(window.dimensions["input_height"])
    window.browse_save_btn1.setFixedWidth(80)  # 缩短按钮宽度
    window.browse_save_btn1.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建路径显示标签
    window.save_path_label1 = QLabel()
    window.save_path_label1.setFixedHeight(window.dimensions["input_height"])
    # 默认为浅红色阴影样式（未选择路径）
    window.save_path_label1.setStyleSheet(window.styles["path_empty_label"])
    window.save_path_label1.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    window.save_path_label1.setText("")  # 初始为空

    # 保存样式引用便于后续使用
    window.path_empty_style = window.styles["path_empty_label"]
    window.path_selected_style = window.styles["path_selected_label"]
    window.path_error_style = window.styles["path_error_label"]

    # 创建保存按钮
    window.save_btn = QPushButton("保存")
    window.save_btn.setStyleSheet(window.styles["button"])
    window.save_btn.setFixedHeight(window.dimensions["input_height"])
    window.save_btn.setFixedWidth(60)
    window.save_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建自动保存开关
    window.auto_save_switch = Switch()
    window.auto_save_switch.setChecked(False)  # 默认关闭自动保存（修改时也要修改main_window.py中的初始化部分：self.auto_save = False，以及下一行标签初始位置）
    window.auto_save_switch._pos = 0.0

    # 自动保存标签
    auto_save_label = QLabel("自动保存")
    auto_save_label.setStyleSheet(window.styles["switch_label"])
    auto_save_label.setFixedHeight(window.dimensions["input_height"])
    auto_save_label.setAlignment(Qt.AlignCenter)

    # 添加到布局
    layout.addWidget(window.browse_save_btn1)
    layout.addWidget(window.save_path_label1, 1)  # 设置伸展系数为1，使其占据所有可用空间
    layout.addWidget(window.save_btn)
    layout.addWidget(window.auto_save_switch)
    layout.addWidget(auto_save_label)

    # 设置文本滚动效果
    window.path_scroll_timer = QTimer(window)
    window.path_scroll_timer.setInterval(100)  # 滚动速度
    window.path_scroll_position = 0

    # 添加闪烁效果的定时器
    window.blink_timer = QTimer(window)
    window.blink_timer.setInterval(300)  # 闪烁速度
    window.blink_count = 0
    window.max_blink_count = 4  # 闪烁2次 = 4次状态变化

    # 创建工具类实例
    save_tools = SaveModuleTools(window)

    # 连接闪烁定时器
    window.blink_timer.timeout.connect(save_tools.blink_path_label)

    # 将工具函数添加到window对象
    window.trigger_path_label_blink = save_tools.trigger_blink
    window.update_path_label_style = save_tools.update_path_label_style

    # 连接滚动定时器
    window.path_scroll_timer.timeout.connect(save_tools.scroll_path_text)

    # 在标签大小变化时检查是否需要滚动
    window.save_path_label1.resizeEvent = save_tools.new_resize_event

    # 设置自动保存状态改变的事件处理
    window.auto_save_switch.stateChanged.connect(lambda checked: save_tools.on_auto_save_toggled(checked, auto_save_label))

    return layout


def _create_save_full_speed_module(window) -> QVBoxLayout:
    """创建保存全速处理结果模块"""
    # 创建垂直布局
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(0, 0, 0, 0)

    save_label_layout = QVBoxLayout()

    window.start_process_label = QLabel("全速处理之前必须指定结果保存路径！")
    window.start_process_label.setStyleSheet(window.styles["title_label"])
    window.start_process_label.setFixedHeight(window.dimensions["input_height"])
    window.start_process_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    save_label_layout.addWidget(window.start_process_label)

    save_layout = QHBoxLayout()
    save_layout.setSpacing(window.dimensions["spacing_small"])

    # 创建选择保存路径按钮
    window.browse_save_btn2 = QPushButton("选择保存路径")
    window.browse_save_btn2.setStyleSheet(window.styles["large_button"])
    window.browse_save_btn2.setFixedHeight(window.dimensions["input_height"])
    window.browse_save_btn2.setFixedWidth(80)  # 缩短按钮宽度
    window.browse_save_btn2.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # 创建路径显示标签
    window.save_path_label2 = QLabel()
    window.save_path_label2.setFixedHeight(window.dimensions["input_height"])
    # 默认为浅红色阴影样式（未选择路径）
    window.save_path_label2.setStyleSheet(window.styles["path_empty_label"])
    window.save_path_label2.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    window.save_path_label2.setText("")  # 初始为空

    # 保存样式引用便于后续使用
    window.path_empty_style = window.styles["path_empty_label"]
    window.path_selected_style = window.styles["path_selected_label"]
    window.path_error_style = window.styles["path_error_label"]

    # 添加到布局
    save_layout.addWidget(window.browse_save_btn2)
    save_layout.addWidget(window.save_path_label2, 1)  # 设置伸展系数为1，使其占据所有可用空间

    main_layout.addLayout(save_label_layout)
    main_layout.addSpacing(10)
    main_layout.addLayout(save_layout)

    return main_layout


def _create_full_speed_start_process_module(window) -> QVBoxLayout:
    """创建全速处理开始按钮模块"""

    # 添加开始处理按钮
    button_layout = QVBoxLayout()

    # 创建开始处理按钮
    window.start_process_btn = QPushButton("开始处理")
    window.start_process_btn.setStyleSheet(window.styles["middle_button"])
    window.start_process_btn.setFixedHeight(window.dimensions["button_height"])
    window.start_process_btn.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时为手指形状

    # TODO: 创建暂停按钮
    pass

    # TODO: 创建继续按钮
    pass

    # TODO: 创建终止按钮
    pass

    button_layout.addWidget(window.start_process_btn)

    return button_layout


def _create_switch_module(window) -> QVBoxLayout:
    """创建拨动开关模块"""
    main_layout = QVBoxLayout()

    # 第一行：图像展示模式标签和拨动开关
    switch_layout = QHBoxLayout()

    # 图像展示模式标签
    pic_show_mode_label = QLabel("图像展示模式:")
    pic_show_mode_label.setStyleSheet(window.styles["label"])
    pic_show_mode_label.setFixedWidth(window.dimensions["label_width_middle"])
    pic_show_mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    # 左侧标签
    left_label = QLabel("展示全部聚类结果")
    # left_label.setStyleSheet(window.styles['label'])  # 默认选中左侧
    left_label.setStyleSheet(window.styles["switch_label"])  # 默认选中右侧
    left_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 左对齐

    # 拨动开关
    window.display_switch = Switch()
    # window.display_switch.setChecked(False)  # 设置初始状态为左侧
    # window.display_switch._pos = 0.0  # 初始化滑块位置
    window.display_switch.setChecked(True)  # 设置初始状态为右侧
    window.display_switch._pos = 1.0  # 初始化滑块位置

    # 右侧标签
    right_label = QLabel("仅展示识别后结果")
    # right_label.setStyleSheet(window.styles['switch_label'])
    right_label.setStyleSheet(window.styles["label"])
    right_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    # 设置固定高度
    layout_height = window.dimensions["input_height"]
    left_label.setFixedHeight(layout_height)
    right_label.setFixedHeight(layout_height)

    # 添加切换事件处理
    def on_switch_toggled(checked):
        # 更新标签样式
        if checked:
            left_label.setStyleSheet(window.styles["switch_label"])
            right_label.setStyleSheet(window.styles["label"])
        else:
            left_label.setStyleSheet(window.styles["label"])
            right_label.setStyleSheet(window.styles["switch_label"])
        # 更新 DataController 的显示模式
        window.data_controller.set_display_mode(checked)

    # 连接开关的状态改变信号
    window.display_switch.stateChanged.connect(on_switch_toggled)

    # 添加到第一行布局
    switch_layout.addWidget(pic_show_mode_label)
    switch_layout.addSpacing(5)
    switch_layout.addWidget(left_label)
    switch_layout.addSpacing(10)
    switch_layout.addWidget(window.display_switch)
    switch_layout.addSpacing(10)
    switch_layout.addWidget(right_label)
    switch_layout.addStretch()

    # 第二行：图像绘制模式下拉框
    combo_layout = QHBoxLayout()

    # 图像绘制模式标签
    render_mode_label = QLabel("图像绘制模式:")
    render_mode_label.setStyleSheet(window.styles["label"])
    render_mode_label.setFixedWidth(window.dimensions["label_width_middle"])
    render_mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    # 图像绘制模式下拉框
    window.image_render_combo = QComboBox()
    window.image_render_combo.addItems(["模式一：原始拉伸", "模式二：双线性插值", "模式三：最近邻保留"])
    window.image_render_combo.setCurrentIndex(0)  # 默认选择第一个
    # 使用 Paths 管理图标路径，解决打包后图标丢失问题
    combo_style = window.styles["combo_box"]
    expand_path = str(Paths.get_resource_path("resources/Arrow/expand.png")).replace("\\", "/")
    collapse_path = str(Paths.get_resource_path("resources/Arrow/collapse.png")).replace("\\", "/")
    
    # 替换样式表中的相对路径为绝对路径
    combo_style = combo_style.replace("resources/Arrow/expand.png", expand_path)
    combo_style = combo_style.replace("resources/Arrow/collapse.png", collapse_path)
    
    window.image_render_combo.setStyleSheet(combo_style)  # 应用样式
    window.image_render_combo.setFixedHeight(window.dimensions["input_height"])
    window.image_render_combo.setFixedWidth(200)  # 设置固定宽度

    # 连接下拉框选择事件
    def on_render_mode_changed(index):
        mode_names = ["STRETCH", "STRETCH_BILINEAR", "STRETCH_NEAREST_PRESERVE"]
        if hasattr(window, "_set_image_stretch_mode"):
            window._set_image_stretch_mode(mode_names[index])

    window.image_render_combo.currentIndexChanged.connect(on_render_mode_changed)

    # 添加到第二行布局
    combo_layout.addWidget(render_mode_label)
    combo_layout.addSpacing(5)
    combo_layout.addWidget(window.image_render_combo)
    combo_layout.addStretch()

    # 添加两行到主布局
    main_layout.addLayout(switch_layout)
    main_layout.addSpacing(10)
    main_layout.addLayout(combo_layout)

    return main_layout


def _create_table_widget(window) -> QVBoxLayout:
    """创建表格模块"""
    layout = QVBoxLayout()

    # 创建表格标签
    table_label = QLabel("雷达信号识别结果：")
    table_label.setStyleSheet(window.styles["title_label"])
    table_label.setFixedHeight(window.dimensions["input_height"])
    table_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    # 创建表格部件
    window.table = QTableWidget(9, 3)

    # 设置表头
    window.table.setHorizontalHeaderLabels(["雷达信号", "1", "2"])
    window.table.horizontalHeader().setFixedHeight(40)

    # 启用自动换行
    window.table.setWordWrap(True)

    # 设置行标签
    # row_labels = [
    #     "载频/MHz",
    #     "脉宽/us",
    #     "PRI/us",
    #     "DOA/°",
    #     "PA预测分类",
    #     "PA预测概率",
    #     "DTOA预测分类",
    #     "DTOA预测概率",
    #     "联合预测概率"
    # ]
    row_labels = ["载频/MHz", "脉宽/us", "PRI/us", "DOA/°", "PA预测结果", "PA预测分类", "DTOA预测结果", "DTOA预测分类", "联合预测概率"]

    # 在第一列填充标签
    for i, label in enumerate(row_labels):
        item = QTableWidgetItem(label)
        # 设置单元格不可编辑
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        # 设置文本居中对齐
        item.setTextAlignment(Qt.AlignCenter)
        # 可以设置背景色使其更像标签
        item.setBackground(QColor(240, 240, 240))
        window.table.setItem(i, 0, item)

    # 设置固定行高
    for i in range(9):
        if i != 2 and i != 4 and i != 6:  # 除了第3行（索引为2）外的所有行
            window.table.setRowHeight(i, 40)
            window.table.verticalHeader().setSectionResizeMode(i, QHeaderView.Fixed)

    # 设置第3行高度自适应
    window.table.verticalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
    window.table.verticalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
    window.table.verticalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)

    # 表格基本设置
    window.table.setShowGrid(True)  # 显示网格线
    window.table.verticalHeader().setVisible(False)  # 隐藏行号

    # 设置列宽策略
    window.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)  # 第一列固定宽度
    window.table.setColumnWidth(0, 130)  # 设置第一列宽度为130
    window.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # 第二列自适应
    window.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # 第三列自适应

    window.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用水平滚动条
    window.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用垂直滚动条

    # 设置表格样式
    window.table.setStyleSheet(window.styles["table"])

    # 修改大小策略
    # size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    # size_policy.setVerticalStretch(1)  # 保持垂直方向的弹性
    # table.setSizePolicy(size_policy)

    # 修改大小策略
    size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    size_policy.setVerticalStretch(1)  # 保持垂直方向的弹性
    size_policy.setHeightForWidth(window.table.sizePolicy().hasHeightForWidth())
    window.table.setSizePolicy(size_policy)

    # 设置表格的最小高度为实际内容高度
    def update_table_height():
        header_height = window.table.horizontalHeader().height()
        content_height = sum(window.table.rowHeight(i) for i in range(window.table.rowCount()))
        total_height = header_height + content_height + 2

        # 计算最小高度（显示至少3行）
        min_row_height = 40  # 普通行的固定高度
        min_visible_rows = 3  # 最少显示3行
        min_height = header_height + (min_row_height * min_visible_rows)

        # 设置最小高度
        window.table.setMinimumHeight(min_height)

        # 如果有足够空间，则设置为完整高度
        if total_height > min_height:
            window.table.setMaximumHeight(total_height)
        else:
            window.table.setMaximumHeight(min_height)

    # 在行高变化后更新表格高度
    window.table.verticalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
    window.table.verticalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
    window.table.verticalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
    # 监听内容变化
    window.table.itemChanged.connect(lambda: QTimer.singleShot(0, update_table_height))

    # 监听列宽变化（窗口大小变化会导致列宽变化）
    window.table.horizontalHeader().sectionResized.connect(lambda: QTimer.singleShot(0, update_table_height))

    # 初始更新一次高度
    QTimer.singleShot(0, update_table_height)

    # 添加标签到布局
    layout.addWidget(table_label)

    # 添加表格部件到布局
    layout.addWidget(window.table)
    layout.addStretch()

    return layout


class SaveModuleTools:
    """保存模块工具类"""

    def __init__(self, window):
        self.window = window
        # 保存原始的resize事件处理函数
        self.original_resize_event = self.window.save_path_label1.resizeEvent

    def blink_path_label(self):
        """路径标签闪烁效果"""
        if self.window.blink_count >= self.window.max_blink_count:
            self.window.blink_timer.stop()
            self.window.blink_count = 0
            # 恢复到未选择路径的样式
            self.window.save_path_label1.setStyleSheet(self.window.path_empty_style)
            return

        # 切换样式
        if self.window.blink_count % 2 == 0:
            self.window.save_path_label1.setStyleSheet(self.window.path_error_style)
        else:
            self.window.save_path_label1.setStyleSheet(self.window.path_empty_style)

        self.window.blink_count += 1

    def trigger_blink(self):
        """触发路径标签闪烁效果"""
        self.window.blink_count = 0
        self.window.blink_timer.start()

    def update_path_label_style(self, has_path=False):
        """更新路径标签样式"""
        if self.window.blink_timer.isActive():
            # 如果正在闪烁，不更新样式
            return

        if has_path:
            self.window.save_path_label1.setStyleSheet(self.window.path_selected_style)
            self.window.save_path_label2.setStyleSheet(self.window.path_selected_style)
        else:
            self.window.save_path_label1.setStyleSheet(self.window.path_empty_style)
            self.window.save_path_label2.setStyleSheet(self.window.path_empty_style)

    def scroll_path_text(self):
        """滚动显示路径文本"""
        label = self.window.save_path_label1
        text = label.text()
        if not text:
            return

        # 获取文本宽度和标签宽度
        metrics = label.fontMetrics()
        text_width = metrics.width(text)
        label_width = label.width() - 10  # 考虑内边距

        # 如果文本宽度小于标签宽度，不需要滚动
        if text_width <= label_width:
            return

        # 文本太长，需要滚动
        self.window.path_scroll_position = (self.window.path_scroll_position + 1) % (text_width + label_width)

        # 计算可见文本
        if self.window.path_scroll_position < text_width:
            # 找到从当前位置开始的字符
            visible_start = 0
            current_width = 0
            for i, char in enumerate(text):
                char_width = metrics.width(char)
                if current_width >= self.window.path_scroll_position:
                    visible_start = i
                    break
                current_width += char_width

            visible_text = text[visible_start:]
            if metrics.width(visible_text) > label_width:
                # 截断超出显示区域的文本
                visible_text = visible_text[:30] + "..."  # 简单处理
        else:
            # 显示文本开头
            visible_text = text

        # 更新显示
        label.setText(visible_text)

    def check_scroll_needed(self):
        """检查是否需要滚动显示"""
        label = self.window.save_path_label1
        text = label.text()
        if not text:
            if self.window.path_scroll_timer.isActive():
                self.window.path_scroll_timer.stop()
            return

        metrics = label.fontMetrics()
        if metrics.width(text) > label.width() - 10:
            if not self.window.path_scroll_timer.isActive():
                self.window.path_scroll_position = 0
                self.window.path_scroll_timer.start()
        else:
            if self.window.path_scroll_timer.isActive():
                self.window.path_scroll_timer.stop()

    def new_resize_event(self, event):
        """标签大小变化事件处理"""
        # 调用原始的resize事件处理函数
        if self.original_resize_event is not None:
            self.original_resize_event(event)
        # 检查是否需要滚动
        self.check_scroll_needed()

    def on_auto_save_toggled(self, checked, auto_save_label):
        """处理自动保存状态改变"""
        self.window.auto_save = checked
        # 更新标签样式
        if checked:
            auto_save_label.setStyleSheet(self.window.styles["label"])
        else:
            auto_save_label.setStyleSheet(self.window.styles["switch_label"])
        self.window.logger.info(f"自动保存设置已{'启用' if checked else '禁用'}")
