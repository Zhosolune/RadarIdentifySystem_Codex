"""切片处理子页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from PyQt6.QtGui import QImage, QPixmap
from qfluentwidgets import PrimaryPushButton, PushButton

from app.signal_bus import signal_bus
from app.style_sheet import StyleSheet
from core.models.processing_session import ProcessingSession, ProcessingStage
from core.models.pulse_batch import PulseBatch
from infra.plotting.types import RenderedImageBundle
from runtime.workflows.slice_workflow import slice_workflow
from ui.components import SliceDimensionCard


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
        
        # 绑定全局信号总线，监听渲染结果
        signal_bus.slice_image_ready.connect(self._on_slice_image_ready)

    def _on_slice_image_ready(self, session_id: str, slice_index: int, bundle: RenderedImageBundle) -> None:
        """接收渲染图片结果并展示到左侧卡片。"""
        if session_id != self._test_session.session_id:
            return
            
        import numpy as np
        
        # 更新标题
        if hasattr(self, 'left_title_label'):
            self.left_title_label.setText(f"第{slice_index}个切片数据  原始图像")
        
        # 更新 5 个维度的图片
        cards = {
            "CF": self.original_cf_card,
            "PW": self.original_pw_card,
            "PA": self.original_pa_card,
            "DTOA": self.original_dtoa_card,
            "DOA": self.original_doa_card,
        }
        
        for dim_name, image_data in bundle.images.items():
            if dim_name in cards:
                # np array(uint8) -> QImage
                height, width = image_data.shape
                bytes_per_line = width
                q_image = QImage(
                    image_data.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_Grayscale8,
                )
                cards[dim_name].set_image(QPixmap.fromImage(q_image))

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
        
        self.btn_import = PushButton("1. 模拟导入数据", right_column)
        self.btn_slice = PrimaryPushButton("2. 开始切片工作流", right_column)
        
        self.btn_import.clicked.connect(self._on_import_clicked)
        self.btn_slice.clicked.connect(self._on_slice_clicked)
        
        right_layout.addWidget(title)
        right_layout.addWidget(self.btn_import)
        right_layout.addWidget(self.btn_slice)
        right_layout.addStretch(1)
        
        return right_column

    def _on_import_clicked(self) -> None:
        """模拟外部完成导入写数据到 Session。"""
        import numpy as np
        
        # 伪造 100 个模拟脉冲 (列序: CF, PW, DOA, PA, TOA)
        fake_data = np.zeros((100, 5), dtype=np.float64)
        fake_data[:, 0] = np.random.uniform(5000, 5500, 100) # C波段
        fake_data[:, 1] = np.random.uniform(10, 50, 100)     # PW
        fake_data[:, 2] = np.random.uniform(0, 360, 100)     # DOA
        fake_data[:, 3] = np.random.uniform(50, 100, 100)    # PA
        # TOA 线性递增，模拟脉冲列
        fake_data[:, 4] = np.linspace(0, 1000, 100) + np.random.uniform(0, 5, 100)
        
        self._test_session.raw_batch = PulseBatch(fake_data)
        self._test_session.stage = ProcessingStage.IMPORTED
        self.btn_import.setText("1. 导入完成 (100条伪造数据)")
        
    def _on_slice_clicked(self) -> None:
        """触发切片工作流。"""
        if not self._test_session.is_imported:
            self.btn_slice.setText("请先导入数据！")
            return
            
        self.btn_slice.setText("切片计算中...")
        self.btn_slice.setEnabled(False)
        
        # 将测试 Session 发给全局单例切片工作流处理
        slice_workflow.start_slice(self._test_session)
        
        # 监听此 Session 阶段完成事件复位按钮
        def on_finished(sid: str, stage: str) -> None:
            if sid == self._test_session.session_id and stage == "slicing":
                self.btn_slice.setText("2. 开始切片工作流 (完成)")
                self.btn_slice.setEnabled(True)
                signal_bus.stage_finished.disconnect(on_finished)
                
        signal_bus.stage_finished.connect(on_finished)
