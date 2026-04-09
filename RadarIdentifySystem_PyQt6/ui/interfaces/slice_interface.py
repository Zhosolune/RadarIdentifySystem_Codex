"""切片处理子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QFileDialog
from qfluentwidgets import PrimaryPushButton, PushButton, PushSettingCard, FluentIcon

from app.signal_bus import signal_bus
from app.style_sheet import StyleSheet
from app.app_config import appConfig
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.pulse_batch import PulseBatch
from ui.components import SliceDimensionCard, MainActionCard, NavigationControlCard, PlotControlCard
from ui.controllers.import_controller import ImportController
from ui.controllers.slice_controller import SliceController


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
        
        # 为了测试新架构，界面持有一个测试用的 Session 引用
        self._test_session = ProcessingSession()
        
        # 初始化控制器，将业务逻辑抽离
        self._import_controller = ImportController(self)
        self._slice_controller = SliceController(self)

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
        right_column = self._create_right_column()

        # 添加三列控件
        root_layout.addWidget(left_column, 2)
        root_layout.addWidget(middle_column, 2)
        root_layout.addWidget(right_column, 3)

        # 限制右侧面板最大宽度
        right_column.setFixedWidth(580)

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

        self.slice_title_label = QLabel("第0个切片数据  原始图像", column)
        self.slice_title_label.setObjectName("sliceLeftTitle")
        self.slice_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slice_title_label.setFixedHeight(25)

        layout.addWidget(self.slice_title_label)
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
        
        self.cluster_title_label = QLabel("CF/PW维度聚类 第0类", column)
        self.cluster_title_label.setObjectName("sliceMiddleTitle")
        self.cluster_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cluster_title_label.setFixedHeight(25)

        layout.addWidget(self.cluster_title_label)
        layout.addWidget(self.cluster_cf_card, 1)
        layout.addWidget(self.cluster_pw_card, 1)
        layout.addWidget(self.cluster_pa_card, 1)
        layout.addWidget(self.cluster_dtoa_card, 1)
        layout.addWidget(self.cluster_doa_card, 1)
        return column

    def _create_right_column(self) -> QWidget:
        """创建右侧空白业务列。

        构建右侧占位区域，添加测试用按钮来驱动 workflow。

        Returns:
            QWidget: 右侧列容器。
        """

        right_column = QWidget(self)
        right_column.setObjectName("sliceRightColumn")
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 35, 0, 0)
        right_layout.setSpacing(10)
        
        self.import_data_button = PushButton("1. 从 Excel 导入数据", right_column)

        # 切片信息标签
        self.slice_info_label = QLabel("预计将获得 0 个250ms切片", right_column)
        self.slice_info_label.setObjectName("sliceInfoLabel")
        self.slice_info_label.setFixedHeight(25)

        # 主操作卡片（切片、识别）
        self.main_action_card = MainActionCard(right_column)
        
        # 导航控制卡片
        self.navigation_control_card = NavigationControlCard(right_column)
        
        # 绘图控制卡片
        self.plot_control_card = PlotControlCard(right_column)
        
        # 导出路径设置卡
        self.export_path_card = PushSettingCard(
            text="选择文件夹",
            icon=FluentIcon.FOLDER,
            title="保存/导出路径",
            content=appConfig.exportDirPath.value,
            parent=right_column
        )
        self.export_path_card.clicked.connect(self._on_export_path_clicked)
        # 绑定配置改变事件以更新 UI
        appConfig.exportDirPath.valueChanged.connect(self._on_export_path_config_changed)
        
        right_layout.addWidget(self.import_data_button)
        right_layout.addWidget(self.slice_info_label)
        right_layout.addWidget(self.main_action_card)
        right_layout.addWidget(self.navigation_control_card)
        right_layout.addWidget(self.plot_control_card)
        right_layout.addWidget(self.export_path_card)
        right_layout.addStretch(1)
        
        return right_column

    def _on_export_path_clicked(self) -> None:
        """处理更改导出路径按钮点击事件。"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择保存/导出目录",
            appConfig.exportDirPath.value
        )
        if folder:
            appConfig.exportDirPath.value = folder

    def _on_export_path_config_changed(self, new_path: str) -> None:
        """同步全局配置到导出路径设置卡。"""
        self.export_path_card.setContent(new_path)
