"""切片处理子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import PrimaryPushButton, PushButton

from app.signal_bus import signal_bus
from app.style_sheet import StyleSheet
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.pulse_batch import PulseBatch
from ui.components import SliceDimensionCard, SliceActionCard
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

        root_layout.addWidget(left_column, 1)
        root_layout.addWidget(middle_column, 1)
        root_layout.addWidget(right_column, 1)

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

        title = QLabel("第0个切片数据  原始图像", column)
        title.setObjectName("sliceLeftTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_title_label = title
        layout.addWidget(title)

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

        title = QLabel("CF/PW维度聚类 第0类", column)
        title.setObjectName("sliceMiddleTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

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
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(16)
        
        title = QLabel("操作面板 (测试版)", right_column)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.import_data_button = PushButton("1. 从 Excel 导入数据", right_column)
        self.action_card = SliceActionCard(right_column)
        
        right_layout.addWidget(title)
        right_layout.addWidget(self.import_data_button)
        right_layout.addWidget(self.action_card)
        right_layout.addStretch(1)
        
        return right_column
