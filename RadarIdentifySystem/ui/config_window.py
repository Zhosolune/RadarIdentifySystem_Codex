# -*- coding: utf-8 -*-
"""
默认参数配置窗口模块

提供用户界面来配置系统的默认参数，包括聚类参数、识别参数和合并参数。
使用PyQt5实现，采用两栏式布局，左侧侧边栏选择参数类型，右侧内容区显示具体参数。
"""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFrame,
    QScrollArea,
    QWidget,
    QListWidget,
    QListWidgetItem,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from typing import Dict, Optional

try:
    from .default_config import DefaultConfig
    from .style_manager import StyleManager
    from .components.custom_dialog import BaseFramelessDialog
except ImportError:
    # 支持独立运行时的导入
    import sys
    from pathlib import Path

    ui_path = Path(__file__).parent
    sys.path.insert(0, str(ui_path))
    sys.path.insert(0, str(ui_path.parent))
    from default_config import DefaultConfig
    from style_manager import StyleManager
    from components.custom_dialog import BaseFramelessDialog

from cores.log_manager import LogManager


class ConfigWindow(BaseFramelessDialog):
    # 添加配置保存成功的信号
    config_saved = pyqtSignal()
    """默认参数配置窗口
    
    提供用户界面来配置系统的默认参数，包括聚类参数、识别参数和合并参数。
    采用PyQt5实现，使用两栏式布局，左侧侧边栏选择参数类型，右侧内容区显示具体参数。
    """

    def __init__(self, parent=None):
        """初始化配置窗口

        Args:
            parent: 父窗口
        """
        super().__init__(parent, title="")
        self.parent = parent
        self.logger = LogManager()
        self.config = DefaultConfig()

        # 获取样式和尺寸
        self.styles = StyleManager.get_styles()
        self.dimensions = StyleManager.get_dimensions()

        # 存储输入控件的字典
        self.input_widgets: Dict[str, QLineEdit] = {}

        # 存储内容区域的字典
        self.content_areas: Dict[str, QWidget] = {}

        # 当前选中的参数类型
        self.current_section: Optional[str] = None

        # 滚动更新标志，防止循环触发
        self._updating_from_scroll: bool = False

        # 滚动防抖定时器
        self._scroll_timer: Optional[QTimer] = None

        # 百分比参数列表
        self.percentage_params = {"cf_extraction_threshold_ratio", "pw_extraction_threshold_ratio", "pri_extraction_threshold_ratio"}

        # 参数单位映射字典
        self.param_units = {
            # 聚类参数
            "epsilon_CF": "MHz",
            "epsilon_PW": "μs",
            "min_pts": "个",
            # 识别参数
            "pa_weight": "",
            "dtoa_weight": "",
            "threshold": "",
            # CF参数提取
            "cf_extraction_eps": "MHz",
            "cf_extraction_min_samples": "个",
            "cf_extraction_threshold_ratio": "%",
            # PW参数提取
            "pw_extraction_eps": "μs",
            "pw_extraction_min_samples": "个",
            "pw_extraction_threshold_ratio": "%",
            # PRI参数提取
            "pri_extraction_eps": "μs",
            "pri_extraction_min_samples": "个",
            "pri_extraction_threshold_ratio": "%",
            "pri_extraction_filter_threshold": "μs",
            "pri_extraction_harmonic_tolerance": "μs",
            # 合并参数
            "pri_different_cf_tolerance": "MHz",
            "pri_equal_doa_tolerance": "°",
            "pri_different_doa_tolerance": "°",
            "pri_none_doa_tolerance": "°",
        }

        # 设置窗口
        self._setup_window()

        # 创建UI
        self._create_ui()

        # 加载当前配置
        self._load_current_config()

        self.logger.info("配置窗口初始化完成")

    def _setup_window(self) -> None:
        """设置窗口基本属性"""
        self.setFixedSize(900, 700)
        self.setModal(True)

        # 居中显示
        if self.parent:
            parent_geometry = self.parent.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            self.move(x, y)

    def _create_ui(self) -> None:
        """创建用户界面"""
        # 设置内容区域样式
        self.content_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 5px;
                font-family: "Microsoft YaHei";
                font-size: 16px;
            }
        """)

        # 调整布局边距
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # 创建顶部栏
        self._create_header(self.content_layout)

        # 创建主内容区域（两栏布局）
        self._create_main_content(self.content_layout)

    def _create_header(self, parent_layout: QVBoxLayout) -> None:
        """创建顶部栏

        Args:
            parent_layout: 父布局
        """
        header = QWidget()
        header.setStyleSheet(
            """
            QWidget {
                background-color: #f8f9fa;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border-bottom: 1px solid #e9ecef;
            }
        """
        )
        header.setFixedHeight(60)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(15)

        # 左侧标题
        title_label = QLabel("参数设置")
        title_label.setStyleSheet(
            """
            QLabel {
                color: #4772c3;
                font-size: 20px;
                font-weight: bold;
                background-color: transparent;
                border: none;
            }
        """
        )
        header_layout.addWidget(title_label)

        # 弹性空间
        header_layout.addStretch()

        # 右侧按钮
        self._create_header_buttons(header_layout)

        parent_layout.addWidget(header)

    def _create_header_buttons(self, parent_layout: QHBoxLayout) -> None:
        """创建顶部栏按钮

        Args:
            parent_layout: 父布局
        """
        # 保存按钮（浅绿色）
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 14px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """
        )
        save_btn.clicked.connect(self._on_save)

        # 重置按钮（灰色）
        reset_btn = QPushButton("重置为默认")
        reset_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """
        )
        reset_btn.clicked.connect(self._on_reset)

        parent_layout.addWidget(save_btn)
        parent_layout.addWidget(reset_btn)

    def _create_main_content(self, parent_layout: QVBoxLayout) -> None:
        """创建主内容区域（两栏布局）

        Args:
            parent_layout: 父布局
        """
        main_content = QWidget()
        main_content_layout = QHBoxLayout(main_content)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(0)

        # 创建左侧侧边栏
        self._create_sidebar(main_content_layout)

        # 创建右侧内容区
        self._create_content_area(main_content_layout)

        parent_layout.addWidget(main_content)

    def _create_sidebar(self, parent_layout: QHBoxLayout) -> None:
        """创建左侧侧边栏

        Args:
            parent_layout: 父布局
        """
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(
            """
            QWidget {
                background-color: #f8f9fa;
                border-right: 1px solid #e9ecef;
                border-bottom-left-radius: 12px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """
        )

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(0)

        # 创建参数类型列表
        self.sidebar_list = QListWidget()
        self.sidebar_list.setStyleSheet(
            """
            QListWidget {
                border: none;
                background-color: transparent;
                outline: none;
                padding: 0px 10px;
            }
            QListWidget::item {
                padding: 12px 16px;
                margin: 4px 0px;
                border: none;
                border-radius: 8px;
                color: #495057;
                font-size: 20px;
                font-weight: bold;
                background-color: transparent;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
                color: #4772c3;
            }
            QListWidget::item:selected {
                background-color: #4772c3;
                color: white;
            }
        """
        )

        # 添加参数类型选项
        items = [
            ("聚类参数", "clustering"),
            ("识别参数", "identification"),
            ("参数提取", "extraction"),
            ("合并参数", "merging"),
        ]

        for text, key in items:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.sidebar_list.addItem(item)

        self.sidebar_list.currentItemChanged.connect(self._on_sidebar_selection_changed)

        sidebar_layout.addWidget(self.sidebar_list)
        sidebar_layout.addStretch()

        parent_layout.addWidget(sidebar)

    def _create_content_area(self, parent_layout: QHBoxLayout) -> None:
        """创建右侧内容区

        Args:
            parent_layout: 父布局
        """
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # 设置滚动条策略，确保只在需要时显示
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建自定义角落组件来实现圆角效果
        corner_widget = self._create_corner_widget()
        self.scroll_area.setCornerWidget(corner_widget)

        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background-color: white;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 12px;
            }
            QScrollArea > QWidget > QWidget {
                background-color: white;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #ced4da;
                border: none;
                border-radius: 5px;
                min-height: 20px;
                margin: 1px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #adb5bd;
                border: none;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #6c757d;
                border: none;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::add-page:vertical {
                background: transparent;
            }
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                height: 12px;
                background: transparent;
            }
        """
        )

        # 创建内容容器
        self.content_container = QWidget()
        self.content_container.setStyleSheet("background-color: white; border: none;")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(40)

        # 创建所有参数区域在同一个页面中
        self._create_unified_content()

        self.scroll_area.setWidget(self.content_container)

        # 连接滚动条值变化信号
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        parent_layout.addWidget(self.scroll_area)

    def _create_corner_widget(self) -> QWidget:
        """创建自定义角落组件实现圆角效果

        Returns:
            QWidget: 角落组件
        """
        corner = QWidget()
        corner.setFixedSize(12, 12)  # 略大于滚动条宽度，确保完全覆盖
        corner.setStyleSheet(
            """
            QWidget {
                background-color: white;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 5px;
            }
        """
        )
        # 设置角落组件的层级低于滚动条
        corner.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return corner

    def _create_unified_content(self) -> None:
        """创建统一的内容区域"""
        # 创建聚类参数区域
        clustering_widget = self._create_clustering_content()
        clustering_widget.setObjectName("clustering")
        self.content_areas["clustering"] = clustering_widget
        self.content_layout.addWidget(clustering_widget)

        # 添加分隔线
        self._add_section_separator()

        # 创建识别参数区域
        identification_widget = self._create_identification_content()
        identification_widget.setObjectName("identification")
        self.content_areas["identification"] = identification_widget
        self.content_layout.addWidget(identification_widget)

        # 添加分隔线
        self._add_section_separator()

        # 创建参数提取区域
        extraction_widget = self._create_extraction_content()
        extraction_widget.setObjectName("extraction")
        self.content_areas["extraction"] = extraction_widget
        self.content_layout.addWidget(extraction_widget)

        # 添加分隔线
        self._add_section_separator()

        # 创建合并参数区域
        merging_widget = self._create_merging_content()
        merging_widget.setObjectName("merging")
        self.content_areas["merging"] = merging_widget
        self.content_layout.addWidget(merging_widget)

        # 添加弹性空间
        self.content_layout.addStretch()

    def _on_sidebar_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """侧边栏选择改变事件

        Args:
            current: 当前选中项
            previous: 之前选中项
        """
        if current:
            section_key = current.data(Qt.UserRole)
            # 只有当不是由滚动触发的选择变化时才执行滚动
            if not hasattr(self, "_updating_from_scroll") or not self._updating_from_scroll:
                self._scroll_to_section(section_key)

    def _scroll_to_section(self, section_key: str) -> None:
        """滚动到指定参数区域

        Args:
            section_key: 参数区域键
        """
        if section_key in self.content_areas:
            target_widget = self.content_areas[section_key]
            # 获取目标控件在容器中的位置
            target_pos = target_widget.pos().y() - 40
            # 滚动到目标位置
            self.scroll_area.verticalScrollBar().setValue(target_pos)
            self.current_section = section_key

    def _select_section(self, section_key: str) -> None:
        """选择参数区域（用于初始化）

        Args:
            section_key: 参数区域键
        """
        # 更新侧边栏选中状态
        for i in range(self.sidebar_list.count()):
            item = self.sidebar_list.item(i)
            if item.data(Qt.UserRole) == section_key:
                self.sidebar_list.setCurrentItem(item)
                break

        # 滚动到对应区域
        self._scroll_to_section(section_key)

    def _on_scroll_changed(self, value: int) -> None:
        """滚动条值变化事件

        Args:
            value: 滚动条当前值
        """
        # 使用定时器防抖，避免滚动过程中频繁触发
        if self._scroll_timer is not None:
            self._scroll_timer.stop()

        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._update_sidebar_selection)
        self._scroll_timer.start(50)  # 50ms延迟

    def _update_sidebar_selection(self) -> None:
        """更新侧边栏选择状态"""
        # 获取当前可见的参数区域
        current_visible_section = self._get_visible_section()

        # 如果当前可见区域与选中区域不同，则更新侧边栏选择
        if current_visible_section and current_visible_section != self.current_section:
            self._updating_from_scroll = True
            try:
                # 更新侧边栏选中状态
                for i in range(self.sidebar_list.count()):
                    item = self.sidebar_list.item(i)
                    if item.data(Qt.UserRole) == current_visible_section:
                        self.sidebar_list.setCurrentItem(item)
                        self.current_section = current_visible_section
                        break
            finally:
                self._updating_from_scroll = False

    def _get_visible_section(self) -> str:
        """获取当前可见的参数区域

        Returns:
            str: 当前可见的参数区域键
        """
        scroll_value = self.scroll_area.verticalScrollBar().value()
        scroll_bar = self.scroll_area.verticalScrollBar()

        # 如果滚动值接近0，直接返回第一个区域
        if scroll_value <= 5:
            return "clustering"

        # 检查是否滚动到底部
        max_scroll = scroll_bar.maximum()
        if scroll_value >= max_scroll - 5:
            return "merging"

        # 简单的位置判断逻辑
        trigger_position = scroll_value + 40

        # 定义区域顺序
        section_keys = ["clustering", "identification", "extraction", "merging"]

        for i in range(len(section_keys) - 1, -1, -1):
            section_key = section_keys[i]
            if section_key in self.content_areas:
                widget = self.content_areas[section_key]
                widget_pos = widget.pos().y()

                # 如果控件位置有效且触发位置在控件下方
                if widget_pos >= 0 and trigger_position >= widget_pos:
                    return section_key

        return "clustering"

    def _create_clustering_content(self) -> QWidget:
        """创建聚类参数内容

        Returns:
            QWidget: 聚类参数内容控件
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 标题
        title = QLabel("聚类参数")
        title.setStyleSheet(
            """
            QLabel {
                color: #4772c3;
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 10px;
                background-color: transparent;
            }
        """
        )
        layout.addWidget(title)

        # 参数表单
        form_layout = QGridLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        # 聚类参数气泡卡片
        clustering_bubblecards = [
            {
                "text": "CF聚类半径\n\nCF维度上DBSCAN算法的ε参数",
                "arrow_direction": "left",
            },
            {
                "text": "PW聚类半径\n\nPW维度上DBSCAN算法的ε参数",
                "arrow_direction": "left",
            },
            {
                "text": "最小点数\n\nCF和PW维度上共用的DBSCAN算法的min_samples参数",
                "arrow_direction": "left",
            },
        ]

        # CF聚类半径
        self._create_param_row(form_layout, "CF聚类半径:", "epsilon_CF", 0, clustering_bubblecards[0])

        # PW聚类半径
        self._create_param_row(form_layout, "PW聚类半径:", "epsilon_PW", 1, clustering_bubblecards[1])

        # 最小点数
        self._create_param_row(form_layout, "最小点数:", "min_pts", 2, clustering_bubblecards[2])

        layout.addLayout(form_layout)

        return widget

    def _create_identification_content(self) -> QWidget:
        """创建识别参数内容

        Returns:
            QWidget: 识别参数内容控件
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 标题
        title = QLabel("识别参数")
        title.setStyleSheet(
            """
            QLabel {
                color: #4772c3;
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 10px;
                background-color: transparent;
            }
        """
        )
        layout.addWidget(title)

        # 参数表单
        form_layout = QGridLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        # 识别参数气泡卡片
        identification_bubblecards = [
            {
                "text": "PA判别门限\n\nPA维度识别结果的门限，高于此门限的概率被认为有效。",
                "arrow_direction": "left",
            },
            {
                "text": "DTOA判别门限\n\nDTOA维度识别结果的门限，高于此门限的概率被认为有效。",
                "arrow_direction": "left",
            },
            {
                "text": "PA判别权重\n\nPA维度识别结果的权重，用于联合判别。可以为任意值，生效的是其与DTOA判别权重的比例关系。",
                "arrow_direction": "left",
            },
            {
                "text": "DTOA判别权重\n\nDTOA维度识别结果的权重，用于联合判别。可以为任意值，生效的是其与PA判别权重的比例关系。",
                "arrow_direction": "left",
            },
            {
                "text": "联合判别门限\n\n联合判别门限，高于此门限的概率被认为有效。",
                "arrow_direction": "left",
            },
        ]

        # PA判别门限
        self._create_param_row(form_layout, "PA判别门限:", "pa_threshold", 0, identification_bubblecards[0])

        # DTOA判别门限
        self._create_param_row(form_layout, "DTOA判别门限:", "dtoa_threshold", 1, identification_bubblecards[1])

        # PA判别权重
        self._create_param_row(form_layout, "PA判别权重:", "pa_weight", 2, identification_bubblecards[2])

        # DTOA判别权重
        self._create_param_row(form_layout, "DTOA判别权重:", "dtoa_weight", 3, identification_bubblecards[3])

        # 联合判别门限
        self._create_param_row(form_layout, "联合判别门限:", "threshold", 4, identification_bubblecards[4])

        layout.addLayout(form_layout)

        return widget

    def _create_extraction_content(self) -> QWidget:
        """创建参数提取内容

        Returns:
            QWidget: 参数提取内容控件
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 标题
        title = QLabel("参数提取")
        title.setStyleSheet(
            """
            QLabel {
                color: #4772c3;
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 10px;
                margin-left: 0;
                padding-left: 0;
                background-color: transparent;
            }
        """
        )
        layout.addWidget(title)

        # 参数内容
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # CF参数提取组
        extraction_bubblecards_cf = [
            {
                "text": "邻域半径\n\nDBSCAN算法的ε参数",
                "arrow_direction": "left",
            },
            {
                "text": "最小邻居点数\n\nDBSCAN算法的min_samples参数",
                "arrow_direction": "left",
            },
            {
                "text": "门限率\n\n用于计算提取的参数是否有效的阈值比例。当提取的参数值所占的样本数与总样本数的比值高于门限率时，参数值被认为是有效的。\n范围：0-100，默认值：10。\n【注意】非必要避免修改该值！",
                "arrow_direction": "left",
            },
        ]
        cf_group = self._create_param_group(
            "CF参数提取",
            [
                ("邻域半径:", "cf_extraction_eps"),
                ("最小邻居点数:", "cf_extraction_min_samples"),
                ("门限率:", "cf_extraction_threshold_ratio"),
            ],
            extraction_bubblecards_cf,
        )
        content_layout.addWidget(cf_group)

        # 添加组间分割线
        self._add_group_separator(content_layout)

        # PW参数提取组
        extraction_bubblecards_pw = [
            {
                "text": "邻域半径\n\nDBSCAN算法的ε参数",
                "arrow_direction": "left",
            },
            {
                "text": "最小邻居点数\n\nDBSCAN算法的min_samples参数",
                "arrow_direction": "left",
            },
            {
                "text": "门限率\n\n用于计算提取的参数是否有效的阈值比例。当提取的参数值所占的样本数与总样本数的比值高于门限率时，参数值被认为是有效的。\n范围：0-100，默认值：10。\n【注意】非必要避免修改该值！",
                "arrow_direction": "left",
            },
        ]
        pw_group = self._create_param_group(
            "PW参数提取",
            [
                ("邻域半径:", "pw_extraction_eps"),
                ("最小邻居点数:", "pw_extraction_min_samples"),
                ("门限率:", "pw_extraction_threshold_ratio"),
            ],
            extraction_bubblecards_pw,
        )
        content_layout.addWidget(pw_group)

        # 添加组间分割线
        self._add_group_separator(content_layout)

        # PRI参数提取组
        extraction_bubblecards_pri = [
            {
                "text": "邻域半径\n\nDBSCAN算法的ε参数",
                "arrow_direction": "left",
            },
            {
                "text": "最小邻居点数\n\nDBSCAN算法的min_samples参数",
                "arrow_direction": "left",
            },
            {
                "text": "门限率\n\n用于计算提取的参数是否有效的阈值比例。当提取的参数值所占的样本数与总样本数的比值高于门限率时，参数值被认为是有效的。\n范围：0-100，默认值：10。\n【注意】非必要避免修改该值！",
                "arrow_direction": "left",
            },
            {
                "text": "过滤门限\n\n用于过滤提取的PRI参数值，只保留不小于该值的PRI值，小于该值的PRI值将被清空。\n默认值：2。",
                "arrow_direction": "left",
            },
            {
                "text": "谐波抑制容差\n\n设置谐波抑制时的容差范围，差值不大于该值的两个数值被认为相等。\n默认值：0.1。\n【注意】非必要避免修改该值！",
                "arrow_direction": "left",
            },
        ]
        pri_group = self._create_param_group(
            "PRI参数提取",
            [
                ("邻域半径:", "pri_extraction_eps"),
                ("最小邻居点数:", "pri_extraction_min_samples"),
                ("门限率:", "pri_extraction_threshold_ratio"),
                ("过滤门限:", "pri_extraction_filter_threshold"),
                ("谐波抑制容差:", "pri_extraction_harmonic_tolerance"),
            ],
            extraction_bubblecards_pri,
        )
        content_layout.addWidget(pri_group)

        layout.addLayout(content_layout)

        return widget

    def _create_merging_content(self) -> QWidget:
        """创建合并参数内容

        Returns:
            QWidget: 合并参数内容控件
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 标题
        title = QLabel("合并参数")
        title.setStyleSheet(
            """
            QLabel {
                color: #4772c3;
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 10px;
                background-color: transparent;
            }
        """
        )
        layout.addWidget(title)

        # 参数内容
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # 参数表单
        # 整体参数
        total_CF_tolerance = self._create_param_group("全局合并参数", [("CF容差:", "pri_different_cf_tolerance")])
        content_layout.addWidget(total_CF_tolerance)

        # PRI相等子组
        pri_equal_group = self._create_param_group("PRI可提取且存在相同值", [("DOA容差:", "pri_equal_doa_tolerance")])
        content_layout.addWidget(pri_equal_group)

        # PRI不同子组
        pri_different_group = self._create_param_group("PRI可提取但不存在相同值", [("DOA容差:", "pri_different_doa_tolerance")])
        content_layout.addWidget(pri_different_group)

        # PRI无法提取子组
        pri_none_group = self._create_param_group("PRI无法提取", [("DOA容差:", "pri_none_doa_tolerance")])
        content_layout.addWidget(pri_none_group)

        layout.addLayout(content_layout)

        return widget

    def _create_param_group(self, title: str, params: list, bubblecards: list = None) -> QWidget:
        """创建参数组

        Args:
            title: 组标题
            params: 参数列表，每个元素为(标签, 键)元组
            bubblecards: 气泡卡片配置列表，与params一一对应，每个元素为包含text、response_mode、arrow_direction等参数的字典

        Returns:
            QWidget: 参数组控件
        """
        group = QWidget()
        group.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 组标题
        group_title = QLabel(title)
        group_title.setStyleSheet(
            """
            QLabel {
                color: #4772c3;
                font-size: 18px;
                font-weight: bold;
                background-color: transparent;
            }
        """
        )
        layout.addWidget(group_title)

        # 参数表单
        form_layout = QGridLayout()
        form_layout.setSpacing(8)

        for i, (label_text, param_key) in enumerate(params):
            row = i * 2
            bubblecard = bubblecards[i] if bubblecards and i < len(bubblecards) else None
            self._create_param_row(form_layout, label_text, param_key, row, bubblecard)
            # if i < len(params) - 1:  # 不在最后一个参数后添加分隔线
            #     self._add_separator_to_grid(form_layout, row + 1)

        layout.addLayout(form_layout)

        return group

    def _add_section_separator(self) -> None:
        """添加参数区域间的分隔线"""
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet(
            """
            QFrame {
                color: #e9ecef;
                background-color: #e9ecef;
                border: none;
                height: 1px;
                margin: 10px 0px;
            }
        """
        )
        self.content_layout.addWidget(separator)

    def _add_group_separator(self, layout: QVBoxLayout) -> None:
        """添加参数组间的分隔线

        Args:
            layout: 要添加分隔线的布局
        """
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet(
            """
            QFrame {
                color: rgba(71, 114, 195, 0.3);
                background-color: rgba(71, 114, 195, 0.3);
                border: none;
                height: 1px;
            }
        """
        )
        separator.setFixedHeight(1)
        layout.addWidget(separator)

    def _create_param_row(
        self,
        layout: QGridLayout,
        label_text: str,
        param_key: str,
        row: int,
        bubblecard: dict = None,
    ) -> None:
        """创建参数行

        Args:
            layout: 网格布局
            label_text: 标签文本
            param_key: 参数键
            row: 行号
            bubblecard: 气泡卡片配置，包含text、response_mode、arrow_direction等参数
        """
        # 创建标签容器
        label_container = QWidget()
        label_container.setStyleSheet("background-color: transparent;")
        label_layout = QHBoxLayout(label_container)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(5)

        # 创建标签
        label = QLabel(label_text)
        label.setStyleSheet(
            """
            QLabel {
                color: #495057;
                font-size: 16px;
                padding: 10px 0;
                background-color: transparent;
            }
        """
        )
        label_layout.addWidget(label)

        # 如果提供了气泡卡片配置，添加信息图标按钮
        if bubblecard:
            from PyQt5.QtGui import QIcon

            info_button = QPushButton()
            info_button.setFixedSize(16, 16)

            # 加载两个状态的图标
            from common.paths import Paths
            normal_icon = QIcon(str(Paths.get_resource_path("resources/info_icons/info.png")))
            hover_icon = QIcon(str(Paths.get_resource_path("resources/info_icons/info_hover.png")))

            # 设置初始图标
            info_button.setIcon(normal_icon)
            info_button.setIconSize(info_button.size())

            # 去除所有边框和背景
            info_button.setStyleSheet(
                """
                QPushButton {
                    border: none;
                    background-color: transparent;
                    padding: 0px;
                }
            """
            )

            # 添加鼠标事件处理
            def on_enter_event(event):
                info_button.setIcon(hover_icon)
                return True

            def on_leave_event(event):
                info_button.setIcon(normal_icon)
                return True

            # 重写enterEvent和leaveEvent方法
            info_button.enterEvent = on_enter_event
            info_button.leaveEvent = on_leave_event

            # 创建气泡卡片
            try:
                from ui.bubble_card import BubbleCard

                _ = BubbleCard.create_toggle_bubble(
                    text=bubblecard.get("text", ""),
                    target_widget=info_button,
                    main_window=self,
                    text_color=bubblecard.get("text_color", "#4772c3"),
                    response_mode=bubblecard.get("response_mode", "hover"),
                    arrow_direction=bubblecard.get("arrow_direction", "auto"),
                    label_style=bubblecard.get("label_style", self.styles["label"]),
                )
            except ImportError:
                pass

            label_layout.addWidget(info_button)

        # 创建输入框
        entry = QLineEdit()
        entry.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px 12px;
                background-color: white;
                color: #495057;
                font-size: 14px;
            }
            QLineEdit:hover {
                border: 1px solid #4772c3;
            }
            QLineEdit:focus {
                border: 2px solid #4772c3;
                outline: none;
            }
        """
        )
        entry.setFixedHeight(36)
        entry.setMinimumWidth(200)

        # 创建输入框和单位标签的容器
        input_container = QWidget()
        input_container.setStyleSheet("background-color: transparent;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        # 添加输入框到容器
        input_layout.addWidget(entry)

        # 获取参数单位并创建单位标签
        unit = self.param_units.get(param_key, "")
        if unit:
            unit_label = QLabel(unit)
            unit_label.setStyleSheet(
                """
                QLabel {
                    color: #495057;
                    font-size: 16px;
                    padding: 8px 0;
                    background-color: transparent;
                    min-width: 30px;
                }
            """
            )
            input_layout.addWidget(unit_label)

        # 添加到布局
        layout.addWidget(label_container, row, 0, Qt.AlignLeft)
        layout.addWidget(input_container, row, 1, Qt.AlignLeft)

        # 存储输入框引用
        self.input_widgets[param_key] = entry

        # 为百分比参数添加输入验证
        if param_key in self.percentage_params:
            entry.setPlaceholderText("0-100")
            # 添加输入验证器（整数）
            from PyQt5.QtGui import QIntValidator

            validator = QIntValidator(0, 100)
            entry.setValidator(validator)

    def _decimal_to_percentage(self, value: float) -> float:
        """将小数转换为百分比

        Args:
            value: 小数值 (0-1)

        Returns:
            float: 百分比值 (0-100)
        """
        return value * 100

    def _percentage_to_decimal(self, value: float) -> float:
        """将百分比转换为小数

        Args:
            value: 百分比值 (0-100)

        Returns:
            float: 小数值 (0-1)，严格保存为两位小数格式
        """
        return round(value / 100, 2)

    def _load_current_config(self) -> None:
        """加载当前配置到界面"""
        try:
            # 从配置实体对象直接获取参数值
            params = self.config.params

            # 加载聚类参数
            self.input_widgets["epsilon_CF"].setText(str(params.clustering_params.epsilon_CF))
            self.input_widgets["epsilon_PW"].setText(str(params.clustering_params.epsilon_PW))
            self.input_widgets["min_pts"].setText(str(int(params.clustering_params.min_pts)))

            # 加载识别参数
            self.input_widgets["pa_threshold"].setText(str(params.identification_params.pa_threshold))
            self.input_widgets["dtoa_threshold"].setText(str(params.identification_params.dtoa_threshold))
            self.input_widgets["pa_weight"].setText(str(params.identification_params.pa_weight))
            self.input_widgets["dtoa_weight"].setText(str(params.identification_params.dtoa_weight))
            self.input_widgets["threshold"].setText(str(params.identification_params.threshold))

            # 加载参数提取参数
            self.input_widgets["cf_extraction_eps"].setText(str(params.extraction_params.cf_extraction.eps))
            self.input_widgets["cf_extraction_min_samples"].setText(str(int(params.extraction_params.cf_extraction.min_samples)))
            # 百分比参数：将小数转换为整数百分比显示
            cf_threshold_percentage = int(self._decimal_to_percentage(params.extraction_params.cf_extraction.threshold_ratio))
            self.input_widgets["cf_extraction_threshold_ratio"].setText(str(cf_threshold_percentage))

            self.input_widgets["pw_extraction_eps"].setText(str(params.extraction_params.pw_extraction.eps))
            self.input_widgets["pw_extraction_min_samples"].setText(str(int(params.extraction_params.pw_extraction.min_samples)))
            # 百分比参数：将小数转换为整数百分比显示
            pw_threshold_percentage = int(self._decimal_to_percentage(params.extraction_params.pw_extraction.threshold_ratio))
            self.input_widgets["pw_extraction_threshold_ratio"].setText(str(pw_threshold_percentage))

            self.input_widgets["pri_extraction_eps"].setText(str(params.extraction_params.pri_extraction.eps))
            self.input_widgets["pri_extraction_min_samples"].setText(str(int(params.extraction_params.pri_extraction.min_samples)))
            # 百分比参数：将小数转换为整数百分比显示
            pri_threshold_percentage = int(self._decimal_to_percentage(params.extraction_params.pri_extraction.threshold_ratio))
            self.input_widgets["pri_extraction_threshold_ratio"].setText(str(pri_threshold_percentage))
            self.input_widgets["pri_extraction_filter_threshold"].setText(str(int(params.extraction_params.pri_extraction.filter_threshold)))
            self.input_widgets["pri_extraction_harmonic_tolerance"].setText(str(params.extraction_params.pri_extraction.harmonic_tolerance))

            # 加载合并参数
            self.input_widgets["pri_equal_doa_tolerance"].setText(str(params.merge_params.pri_equal.doa_tolerance))
            self.input_widgets["pri_different_doa_tolerance"].setText(str(params.merge_params.pri_different.doa_tolerance))
            self.input_widgets["pri_different_cf_tolerance"].setText(str(params.merge_params.pri_different.cf_tolerance))
            self.input_widgets["pri_none_doa_tolerance"].setText(str(params.merge_params.pri_none.doa_tolerance))

        except Exception as e:
            self.logger.error(f"加载配置失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载配置失败: {str(e)}")

    def _validate_inputs(self) -> bool:
        """验证输入值

        Returns:
            bool: 验证是否通过
        """
        try:
            # 验证聚类参数
            epsilon_cf = float(self.input_widgets["epsilon_CF"].text())
            epsilon_pw = float(self.input_widgets["epsilon_PW"].text())
            min_pts = int(self.input_widgets["min_pts"].text())

            if epsilon_cf <= 0 or epsilon_pw <= 0 or min_pts <= 0:
                QMessageBox.warning(self, "输入错误", "聚类参数必须大于0")
                return False

            # 验证识别参数
            pa_threshold = float(self.input_widgets["pa_threshold"].text())
            dtoa_threshold = float(self.input_widgets["dtoa_threshold"].text())
            pa_weight = float(self.input_widgets["pa_weight"].text())
            dtoa_weight = float(self.input_widgets["dtoa_weight"].text())
            threshold = float(self.input_widgets["threshold"].text())

            if pa_threshold < 0 or pa_threshold > 1:
                QMessageBox.warning(self, "输入错误", "PA判别门限必须在0-1之间")
                return False

            if dtoa_threshold < 0 or dtoa_threshold > 1:
                QMessageBox.warning(self, "输入错误", "DTOA判别门限必须在0-1之间")
                return False

            if pa_weight < 0 or dtoa_weight < 0:
                QMessageBox.warning(self, "输入错误", "权重参数不能为负数")
                return False

            if threshold < 0 or threshold > 1:
                QMessageBox.warning(self, "输入错误", "联合判别门限必须在0-1之间")
                return False

            # 验证参数提取参数
            cf_eps = float(self.input_widgets["cf_extraction_eps"].text())
            cf_min_samples = int(self.input_widgets["cf_extraction_min_samples"].text())
            cf_threshold_ratio = int(self.input_widgets["cf_extraction_threshold_ratio"].text())

            pw_eps = float(self.input_widgets["pw_extraction_eps"].text())
            pw_min_samples = int(self.input_widgets["pw_extraction_min_samples"].text())
            pw_threshold_ratio = int(self.input_widgets["pw_extraction_threshold_ratio"].text())

            pri_eps = float(self.input_widgets["pri_extraction_eps"].text())
            pri_min_samples = int(self.input_widgets["pri_extraction_min_samples"].text())
            pri_threshold_ratio = int(self.input_widgets["pri_extraction_threshold_ratio"].text())
            pri_filter_threshold = int(self.input_widgets["pri_extraction_filter_threshold"].text())
            pri_harmonic_tolerance = float(self.input_widgets["pri_extraction_harmonic_tolerance"].text())

            if any(
                val <= 0
                for val in [
                    cf_eps,
                    cf_min_samples,
                    pw_eps,
                    pw_min_samples,
                    pri_eps,
                    pri_min_samples,
                    pri_filter_threshold,
                    pri_harmonic_tolerance,
                ]
            ):
                QMessageBox.warning(
                    self,
                    "输入错误",
                    "参数提取的邻域半径、最小邻居点数、过滤门限和谐波容差必须大于0",
                )
                return False

            # 验证百分比参数（0-100范围）
            if any(val < 0 or val > 100 for val in [cf_threshold_ratio, pw_threshold_ratio, pri_threshold_ratio]):
                QMessageBox.warning(self, "输入错误", "门限率必须在0-100之间")
                return False

            # 验证合并参数
            pri_equal_doa = float(self.input_widgets["pri_equal_doa_tolerance"].text())
            pri_different_doa = float(self.input_widgets["pri_different_doa_tolerance"].text())
            pri_different_cf = float(self.input_widgets["pri_different_cf_tolerance"].text())
            pri_none_doa = float(self.input_widgets["pri_none_doa_tolerance"].text())

            if any(
                val <= 0
                for val in [
                    pri_equal_doa,
                    pri_different_doa,
                    pri_different_cf,
                    pri_none_doa,
                ]
            ):
                QMessageBox.warning(self, "输入错误", "容差参数必须大于0")
                return False

            return True

        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数值")
            return False

    def _on_save(self) -> None:
        """保存配置"""
        if not self._validate_inputs():
            return

        try:
            # 构建新的配置数据
            new_config_data = {
                "clustering_params": {
                    "epsilon_CF": float(self.input_widgets["epsilon_CF"].text()),
                    "epsilon_PW": float(self.input_widgets["epsilon_PW"].text()),
                    "min_pts": int(self.input_widgets["min_pts"].text()),
                },
                "identification_params": {
                    "pa_threshold": float(self.input_widgets["pa_threshold"].text()),
                    "dtoa_threshold": float(self.input_widgets["dtoa_threshold"].text()),
                    "pa_weight": float(self.input_widgets["pa_weight"].text()),
                    "dtoa_weight": float(self.input_widgets["dtoa_weight"].text()),
                    "threshold": float(self.input_widgets["threshold"].text()),
                },
                "extraction_params": {
                    "cf_extraction": {
                        "eps": float(self.input_widgets["cf_extraction_eps"].text()),
                        "min_samples": int(self.input_widgets["cf_extraction_min_samples"].text()),
                        # 百分比参数：将整数百分比转换为小数保存
                        "threshold_ratio": self._percentage_to_decimal(float(int(self.input_widgets["cf_extraction_threshold_ratio"].text()))),
                    },
                    "pw_extraction": {
                        "eps": float(self.input_widgets["pw_extraction_eps"].text()),
                        "min_samples": int(self.input_widgets["pw_extraction_min_samples"].text()),
                        # 百分比参数：将整数百分比转换为小数保存
                        "threshold_ratio": self._percentage_to_decimal(float(int(self.input_widgets["pw_extraction_threshold_ratio"].text()))),
                    },
                    "pri_extraction": {
                        "eps": float(self.input_widgets["pri_extraction_eps"].text()),
                        "min_samples": int(self.input_widgets["pri_extraction_min_samples"].text()),
                        # 百分比参数：将整数百分比转换为小数保存
                        "threshold_ratio": self._percentage_to_decimal(float(int(self.input_widgets["pri_extraction_threshold_ratio"].text()))),
                        "filter_threshold": int(self.input_widgets["pri_extraction_filter_threshold"].text()),
                        "harmonic_tolerance": float(self.input_widgets["pri_extraction_harmonic_tolerance"].text()),
                    },
                },
                "merge_params": {
                    "pri_equal": {"doa_tolerance": float(self.input_widgets["pri_equal_doa_tolerance"].text())},
                    "pri_different": {
                        "doa_tolerance": float(self.input_widgets["pri_different_doa_tolerance"].text()),
                        "cf_tolerance": float(self.input_widgets["pri_different_cf_tolerance"].text()),
                    },
                    "pri_none": {"doa_tolerance": float(self.input_widgets["pri_none_doa_tolerance"].text())},
                },
            }

            # 使用新的API更新配置
            if self.config.update_config_from_window(new_config_data):
                QMessageBox.information(self, "成功", "配置已保存")
                self.logger.info("用户保存了默认参数配置")
                # 发射配置保存成功信号
                self.config_saved.emit()
            else:
                QMessageBox.critical(self, "错误", "保存配置失败")

        except Exception as e:
            self.logger.error(f"保存配置失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def _on_reset(self) -> None:
        """重置为默认值"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置所有参数为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                # 重置配置
                if self.config.reset_to_defaults():
                    # 清空所有输入框并重新加载
                    for widget in self.input_widgets.values():
                        widget.clear()

                    # 重新加载默认配置
                    self._load_current_config()

                    QMessageBox.information(self, "成功", "已重置为默认值")
                    self.logger.info("用户重置了默认参数配置")
                else:
                    QMessageBox.critical(self, "错误", "重置配置失败")

            except Exception as e:
                self.logger.error(f"重置配置失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"重置配置失败: {str(e)}")

    def _on_close(self) -> None:
        """关闭窗口事件处理"""
        try:
            self.logger.info("关闭配置窗口")
            self.close()
        except Exception as e:
            self.logger.error(f"关闭窗口时发生错误: {e}")
            QMessageBox.critical(self, "错误", f"关闭窗口时发生错误: {e}")

    def show(self) -> None:
        """显示窗口"""
        super().show()
        self.activateWindow()
        self.raise_()

    def showEvent(self, event) -> None:
        """窗口显示事件处理"""
        super().showEvent(event)

        # 使用QTimer延迟设置初始选择，确保UI完全显示和布局完成
        QTimer.singleShot(200, self._initialize_first_selection)

    def _initialize_first_selection(self) -> None:
        """初始化第一个侧边栏选项选择"""
        if self.sidebar_list.count() > 0:
            # 直接选中第一个选项
            first_item = self.sidebar_list.item(0)
            if first_item:
                # 设置当前项，不触发滚动信号
                self._updating_from_scroll = True
                try:
                    # 先断开信号，避免初始化时触发
                    try:
                        self.scroll_area.verticalScrollBar().valueChanged.disconnect(self._on_scroll_changed)
                    except TypeError:
                        pass  # 信号可能未连接

                    # 设置选中项
                    self.sidebar_list.setCurrentItem(first_item)
                    self.current_section = "clustering"

                    # 强制滚动到顶部
                    self.scroll_area.verticalScrollBar().setValue(0)

                    # 重新连接信号
                    self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

                finally:
                    self._updating_from_scroll = False
