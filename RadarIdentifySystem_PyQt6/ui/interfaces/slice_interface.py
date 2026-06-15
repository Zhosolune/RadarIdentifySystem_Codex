"""切片处理子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QColor
from qfluentwidgets import FluentIcon, TransparentToolButton, ToolTipFilter, ToolTipPosition, themeColor, SimpleCardWidget, ScrollArea, qconfig

from app.custom_icon import CustomIcon
from app.signal_bus import signal_bus
from app.style_sheet import StyleSheet
from core.models.processing_session import ProcessingSession
from ui.components import (
    DrawerPosition,
    JitterFreeCardGroup,
    NavigationControlCard,
    PlotOptionCard,
    RedrawOptionCard,
    ExportOptionCard,
    SlidingDrawer,
    SliceDimensionCard,
)
from ui.controllers.slice_controller import SliceController
from ui.controllers.identify_controller import IdentifyController


class SliceInterface(QFrame):
    """切片处理子页面（非滚动、三栏布局）。

    功能描述：
        提供切片处理阶段的三栏骨架布局，左中列按垂直方向预留 5 组“文字标签 + 图片卡片”区域，
        右列预留空白业务区，不启用滚动。

    参数说明：
        parent (QWidget | None): 父级控件，默认值为 None。

    返回值说明：
        无。

    异常说明：
        无。
    """

    RIGHT_COLUMN_WIDTH = 580

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化切片处理子页面。

        功能描述：
            创建三栏布局并应用页面样式资源。

        参数说明：
            parent (QWidget | None): 父级控件，默认值为 None。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        super().__init__(parent)
        self.setObjectName("sliceInterface")
        self.original_cf_card = SliceDimensionCard("载频", "originalCfCard", self)
        self.original_pw_card = SliceDimensionCard("脉宽", "originalPwCard", self)
        self.original_pa_card = SliceDimensionCard("幅度", "originalPaCard", self)
        self.original_dtoa_card = SliceDimensionCard("一级差", "originalDtoaCard", self)
        self.original_doa_card = SliceDimensionCard("方位角", "originalDoaCard", self)

        self.cluster_cf_card = SliceDimensionCard("载频", "clusterCfCard", self)
        self.cluster_pw_card = SliceDimensionCard("脉宽", "clusterPwCard", self)
        self.cluster_pa_card = SliceDimensionCard("幅度", "clusterPaCard", self)
        self.cluster_dtoa_card = SliceDimensionCard("一级差", "clusterDtoaCard", self)
        self.cluster_doa_card = SliceDimensionCard("方位角", "clusterDoaCard", self)

        self._init_layout()
        StyleSheet.SLICE_INTERFACE.apply(self)
        qconfig.themeChanged.connect(self._update_icon_colors)
        
        # 监听绘图拉伸模式变化，以通知子卡片重新拉伸图片
        from app.app_config import appConfig
        appConfig.plotScaleMode.valueChanged.connect(self._on_plot_scale_mode_changed)
        
        # 当前处理会话由首页解析流程通过 signal_bus 注入。
        self._session = ProcessingSession()
        signal_bus.import_completed.connect(self._on_import_completed)

        # 初始化控制器，将业务逻辑抽离
        self._slice_controller = SliceController(self)
        self._identify_controller = IdentifyController(self)

    def _on_import_completed(self, session: ProcessingSession) -> None:
        """接收导入完成会话并作为切片页当前会话。

        Args:
            session: 首页解析流程完成后广播的处理会话。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> from core.models.processing_session import ProcessingSession
            >>> isinstance(ProcessingSession(), ProcessingSession)
            True
        """
        self._session = session

    def _init_layout(self) -> None:
        """初始化三栏主布局。

        功能描述：
            创建左栏、中栏、右栏容器并按 1:1:1 比例加入主布局。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        left_column = self._create_left_column()
        middle_column = self._create_middle_column()
        self.right_column = self._create_right_column()

        # 添加三列控件
        root_layout.addWidget(left_column, 2)
        root_layout.addWidget(middle_column, 2)
        root_layout.addWidget(self.right_column, 3)

        # 限制右侧面板最大宽度
        self.right_column.setFixedWidth(self.RIGHT_COLUMN_WIDTH)

    def _update_icon_colors(self) -> None:
        """当主题切换时，重新获取当前正确的 themeColor 并应用"""
        light_color = themeColor()
        dark_color = QColor("white")

        # 更新透明图标按钮图标的颜色
        self.prev_slice_button.setIcon(CustomIcon.CHEVRONS_LEFT.colored(light_color, dark_color))
        self.next_slice_button.setIcon(CustomIcon.CHEVRONS_RIGHT.colored(light_color, dark_color))
        self.prev_cluster_button.setIcon(CustomIcon.CHEVRON_LEFT.colored(light_color, dark_color))
        self.next_cluster_button.setIcon(CustomIcon.CHEVRON_RIGHT.colored(light_color, dark_color))

    def _on_plot_scale_mode_changed(self, mode: str) -> None:
        """当绘图拉伸模式变更时，触发所有显示图片的重绘。"""
        cards = [
            self.original_cf_card, self.original_pw_card, self.original_pa_card,
            self.original_dtoa_card, self.original_doa_card,
            self.cluster_cf_card, self.cluster_pw_card, self.cluster_pa_card,
            self.cluster_dtoa_card, self.cluster_doa_card,
        ]
        for card in cards:
            if hasattr(card, "update_image_mode"):
                card.update_image_mode()

    def _create_left_column(self) -> QWidget:
        """创建左侧列容器。

        功能描述：
            构建左侧“原始图像”列，包含顶部标题和 5 个维度卡片组件。

        参数说明：
            无。

        返回值说明：
            QWidget: 左侧列容器。

        异常说明：
            无。
        """

        column = QWidget(self)
        column.setObjectName("sliceLeftColumn")

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 标题区域水平布局
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)

        from qfluentwidgets import TransparentToolButton, ToolTipFilter, ToolTipPosition, themeColor
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QColor
        from app.custom_icon import CustomIcon
        
        self.prev_slice_button = TransparentToolButton(CustomIcon.CHEVRONS_LEFT.colored(themeColor(), QColor("white")), column)
        self.prev_slice_button.setFixedSize(25, 25)
        self.prev_slice_button.setIconSize(QSize(20, 20))
        self.prev_slice_button.setToolTip("上一片")
        self.prev_slice_button.installEventFilter(ToolTipFilter(self.prev_slice_button, 1000, ToolTipPosition.TOP))
        
        self.slice_title_label = QLabel("第0个切片数据  原始图像", column)
        self.slice_title_label.setObjectName("sliceLeftTitle")
        self.slice_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slice_title_label.setFixedHeight(25)
        
        self.next_slice_button = TransparentToolButton(CustomIcon.CHEVRONS_RIGHT.colored(themeColor(), QColor("white")), column)
        self.next_slice_button.setFixedSize(25, 25)
        self.next_slice_button.setIconSize(QSize(20, 20))
        self.next_slice_button.setToolTip("下一片")
        self.next_slice_button.installEventFilter(ToolTipFilter(self.next_slice_button, 1000, ToolTipPosition.TOP))

        title_layout.addSpacing(33)
        title_layout.addWidget(self.prev_slice_button)
        title_layout.addWidget(self.slice_title_label, 1)
        title_layout.addWidget(self.next_slice_button)

        layout.addLayout(title_layout)
        layout.addWidget(self.original_cf_card, 1)
        layout.addWidget(self.original_pw_card, 1)
        layout.addWidget(self.original_pa_card, 1)
        layout.addWidget(self.original_dtoa_card, 1)
        layout.addWidget(self.original_doa_card, 1)
        return column

    def _create_middle_column(self) -> QWidget:
        """创建中间列容器。

        功能描述：
            构建中间“聚类结果”列，包含顶部标题和 5 个维度卡片组件。

        参数说明：
            无。

        返回值说明：
            QWidget: 中间列容器。

        异常说明：
            无。
        """

        column = QWidget(self)
        column.setObjectName("sliceMiddleColumn")

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 标题区域水平布局
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        
        self.prev_cluster_button = TransparentToolButton(CustomIcon.CHEVRON_LEFT.colored(themeColor(), QColor("white")), column)
        self.prev_cluster_button.setFixedSize(25, 25)
        self.prev_cluster_button.setIconSize(QSize(20, 20))
        self.prev_cluster_button.setToolTip("上一类")
        self.prev_cluster_button.installEventFilter(ToolTipFilter(self.prev_cluster_button, 1000, ToolTipPosition.TOP))

        self.cluster_title_label = QLabel("CF/PW维度聚类 第0类", column)
        self.cluster_title_label.setObjectName("sliceMiddleTitle")
        self.cluster_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cluster_title_label.setFixedHeight(25)
        
        self.next_cluster_button = TransparentToolButton(CustomIcon.CHEVRON_RIGHT.colored(themeColor(), QColor("white")), column)
        self.next_cluster_button.setFixedSize(25, 25)
        self.next_cluster_button.setIconSize(QSize(20, 20))
        self.next_cluster_button.setToolTip("下一类")
        self.next_cluster_button.installEventFilter(ToolTipFilter(self.next_cluster_button, 1000, ToolTipPosition.TOP))

        title_layout.addSpacing(33)
        title_layout.addWidget(self.prev_cluster_button)
        title_layout.addWidget(self.cluster_title_label, 1)
        title_layout.addWidget(self.next_cluster_button)

        layout.addLayout(title_layout)
        layout.addWidget(self.cluster_cf_card, 1)
        layout.addWidget(self.cluster_pw_card, 1)
        layout.addWidget(self.cluster_pa_card, 1)
        layout.addWidget(self.cluster_dtoa_card, 1)
        layout.addWidget(self.cluster_doa_card, 1)
        return column

    def _create_right_column(self) -> QWidget:
        """创建右侧业务列。

        构建右侧占位区域，添加测试用按钮来驱动 workflow。

        Returns:
            QWidget: 右侧列容器。
        """

        column = QWidget(self)
        column.setObjectName("sliceRightColumn")
        right_layout = QVBoxLayout(column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # 1. 切片信息与抽屉演示入口
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.slice_info_label = QLabel("预计将获得 0 个250ms切片", column)
        self.slice_info_label.setObjectName("sliceInfoLabel")
        # self.slice_info_label.setStyleSheet("margin-left: 12px")
        self.slice_info_label.setFixedHeight(25)

        self.drawer_demo_button = TransparentToolButton(FluentIcon.RIGHT_ARROW, column)
        self.drawer_demo_button.setFixedSize(28, 28)
        self.drawer_demo_button.setToolTip("打开右侧抽屉")
        self.drawer_demo_button.installEventFilter(
            ToolTipFilter(self.drawer_demo_button, 1000, ToolTipPosition.TOP)
        )

        # 2. 操作面板滚动区域
        self.right_panel_scroll_area = ScrollArea(column)
        self.right_panel_scroll_area.setObjectName("rightPanelScrollArea")
        self.right_panel_scroll_area.setWidgetResizable(True)

        # 业务面板容器 (作为 ScrollArea 的内容部件)
        self.scroll_content_widget = QWidget()
        self.scroll_content_widget.setObjectName("scrollContentWidget")

        self.panel_area_layout = QVBoxLayout(self.scroll_content_widget)
        self.panel_area_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_area_layout.setSpacing(10)

        # 业务面板卡片容器
        self.right_panel_card = SimpleCardWidget(self.scroll_content_widget)
        
        # 选项卡面板布局
        control_panel_layout = QVBoxLayout(self.right_panel_card)
        control_panel_layout.setContentsMargins(12, 12, 12, 12)
        control_panel_layout.setSpacing(5)
        
        # 所有的卡片组件用 JitterFreeCardGroup 包裹，放入右侧面板
        cards_group = JitterFreeCardGroup(self.right_panel_card)
        
        # 导航与主操作控制卡片
        self.navigation_control_card = NavigationControlCard(cards_group)
        
        # 绘图选项卡
        self.plot_option_card = PlotOptionCard(cards_group)
        
        # 重绘选项卡
        self.redraw_option_card = RedrawOptionCard(cards_group)
        
        # 导出路径设置卡
        self.export_path_card = ExportOptionCard(cards_group)

        cards_group.addSettingCard(self.navigation_control_card)
        cards_group.addSettingCard(self.plot_option_card)
        cards_group.addSettingCard(self.redraw_option_card)
        cards_group.addSettingCard(self.export_path_card)
        
        control_panel_layout.addWidget(cards_group)

        self.panel_area_layout.addWidget(self.right_panel_card)
        self.panel_area_layout.addStretch(1)
        self.right_panel_scroll_area.setWidget(self.scroll_content_widget)
        
        self.slice_param_config = SlidingDrawer(DrawerPosition.RIGHT, self.RIGHT_COLUMN_WIDTH, self)
        self.slice_param_config.setObjectName("sliceParamConfig")
        self.slice_param_config.setTitle("标题")
        self.slice_param_config.setToggleButtonVisible(False)
        self.slice_param_config.setTriggerWidget(self.drawer_demo_button)
        self.slice_param_config.contentLayout().addStretch(1)
        drawer_empty_label = QLabel("没有更多通知", self.slice_param_config)
        drawer_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slice_param_config.contentLayout().addWidget(drawer_empty_label)
        self.slice_param_config.contentLayout().addStretch(1)
        self.drawer_demo_button.clicked.connect(self.slice_param_config.toggle)

        header_layout.addWidget(self.slice_info_label, 1)
        header_layout.addWidget(self.drawer_demo_button)
        right_layout.addLayout(header_layout)
        right_layout.addWidget(self.right_panel_scroll_area)
        
        return column
