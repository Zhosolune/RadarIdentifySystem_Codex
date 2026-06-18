"""切片处理子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QColor
from qfluentwidgets import TransparentToolButton, ToolTipFilter, ToolTipPosition, themeColor, SimpleCardWidget, ScrollArea, qconfig

from app.custom_icon import CustomIcon
from app.style_sheet import StyleSheet
from ui.components import (
    DrawerPosition,
    JitterFreeCardGroup,
    NavigationControlCard,
    PlotOptionCard,
    RedrawOptionCard,
    SliceParamPanel,
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

    RIGHT_COLUMN_MAX_WIDTH = 580

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

        # 初始化控制器，将业务逻辑抽离
        self._slice_controller = SliceController(self)
        self._identify_controller = IdentifyController(self)

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

        # 设置右侧面板最大宽度
        self.right_column.setMaximumWidth(self.RIGHT_COLUMN_MAX_WIDTH)

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

        self.cluster_title_label = QLabel("暂无聚类结果", column)
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
        
        # 1. 切片信息标题区
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self.slice_info_label = QLabel("预计将获得 0 个250ms切片", column)
        self.slice_info_label.setObjectName("sliceInfoLabel")
        # self.slice_info_label.setStyleSheet("margin-left: 12px")
        self.slice_info_label.setFixedHeight(25)

        # 2. 操作面板滚动区域
        self.right_panel_scroll_area = ScrollArea(column)
        self.right_panel_scroll_area.setObjectName("rightPanelScrollArea")
        self.right_panel_scroll_area.setWidgetResizable(True)

        # 业务面板容器 (作为 ScrollArea 的内容部件)
        self.scroll_content_widget = QWidget()
        self.scroll_content_widget.setObjectName("scrollContentWidget")

        self.scroll_content_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_content_layout.setSpacing(10)

        # 业务面板卡片容器
        self.operate_panel_card = SimpleCardWidget(self.scroll_content_widget)
        
        # 业务面板布局
        operate_panel_layout = QVBoxLayout(self.operate_panel_card)
        operate_panel_layout.setContentsMargins(12, 12, 12, 12)
        operate_panel_layout.setSpacing(8)
        
        # 导航与操作控制卡片
        self.navigation_control_card = NavigationControlCard(self.operate_panel_card)
        
        # 选项卡用 JitterFreeCardGroup 包裹，放入右侧面板
        option_cards_group = JitterFreeCardGroup(self.operate_panel_card)

        # 绘图选项卡
        self.plot_option_card = PlotOptionCard(option_cards_group)
        
        # 重绘选项卡
        self.redraw_option_card = RedrawOptionCard(option_cards_group)
        
        # option_cards_group.addSettingCard(self.navigation_control_card)
        option_cards_group.addSettingCard(self.plot_option_card)
        option_cards_group.addSettingCard(self.redraw_option_card)
        
        operate_panel_layout.addWidget(self.navigation_control_card)
        operate_panel_layout.addWidget(option_cards_group)

        self.scroll_content_layout.addWidget(self.operate_panel_card)
        self.scroll_content_layout.addStretch(1)

        self.right_panel_scroll_area.setWidget(self.scroll_content_widget)
        
        # 抽屉外壳由页面管理，内部卡片布局由独立参数面板负责。
        self.slice_param_drawer: SlidingDrawer = SlidingDrawer(
            DrawerPosition.RIGHT,
            self.RIGHT_COLUMN_MAX_WIDTH,
            self,
            title="当前Session配置",
        )
        self.slice_param_panel: SliceParamPanel = SliceParamPanel(
            self.slice_param_drawer
        )
        self.slice_param_drawer.setContentWidget(self.slice_param_panel)
        self.slice_param_drawer.setToggleButtonVisible(False)
        self.slice_param_drawer.setTriggerWidget(
            self.navigation_control_card.drawer_options_button
        )
        self.navigation_control_card.drawer_options_button.clicked.connect(
            self.slice_param_drawer.toggle
        )

        header_layout.addWidget(self.slice_info_label, 1)
        right_layout.addLayout(header_layout)
        right_layout.addWidget(self.right_panel_scroll_area)
        
        return column
