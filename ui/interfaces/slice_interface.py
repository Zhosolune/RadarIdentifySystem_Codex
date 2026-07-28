"""切片处理子页面。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget
from qfluentwidgets import qconfig

from app.style_sheet import StyleSheet
from core.models.processing_session import ProcessingSession
from ui.components import (
    ClusterImageColumn,
    DrawerPosition,
    HorizontalImageWorkspace,
    MergeImageColumn,
    MergeOperationPanel,
    OriginalImageColumn,
    SliceParamPanel,
    SliceRightPanel,
    SlidingDrawer,
)
from ui.controllers.slice_controller import SliceController
from ui.controllers.identify_controller import IdentifyController
from ui.controllers.merge_controller import MergeController


class SliceInterface(QFrame):
    """组合切片图像工作区、右侧业务面板和页面级参数抽屉。

    Attributes:
        original_column [OriginalImageColumn]: 原始切片图像列 A。
        cluster_column [ClusterImageColumn]: 聚类图像列 B。
        merge_image_column [MergeImageColumn]: 合并图像列 C。
        merge_operation_panel [MergeOperationPanel]: 合并操作面板 D。
        right_panel [SliceRightPanel]: 右侧业务面板 E。
        image_workspace [HorizontalImageWorkspace]: A/B/C/D 横向滑动工作区。
        slice_param_drawer [SlidingDrawer]: 覆盖页面的参数抽屉。
        slice_param_panel [SliceParamPanel]: 参数抽屉内容组件。
        _merge_controller [MergeController]: 自动策略合并的流程控制器。
    """

    RIGHT_COLUMN_MAX_WIDTH = 580

    def __init__(
        self,
        parent: QWidget | None = None,
        session: ProcessingSession | None = None,
        on_config_changed: Callable[[], None] | None = None,
    ) -> None:
        """初始化切片处理子页面。

        创建三栏布局并应用页面样式资源。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 None。
            session [ProcessingSession | None]: 当前页面绑定的处理会话，默认新建空会话。
            on_config_changed [Callable[[], None] | None]: 子配置变更后的保存回调，默认不回调。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """

        super().__init__(parent)
        self.setObjectName("sliceInterface")
        self._session = session or ProcessingSession()
        self._on_config_changed = on_config_changed

        self._init_layout()
        StyleSheet.SLICE_INTERFACE.apply(self)
        qconfig.themeChanged.connect(self._update_icon_colors)

        # 初始化控制器，将业务逻辑抽离
        self._slice_controller = SliceController(self)
        self._identify_controller = IdentifyController(self)
        self._merge_controller = MergeController(self)

    def _init_layout(self) -> None:
        """初始化内容工作区与右侧业务面板布局。

        功能描述：
            使用等宽横向滚动工作区承载 A/B/C/D，视口固定显示两列；该工作区
            与原有右侧业务面板按 4:3 比例加入外层布局，因此默认 A+B+E 的
            视觉比例与原三栏布局保持一致。

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

        self.original_column = OriginalImageColumn(
            self,
            scale_mode_getter=self._current_plot_scale_mode,
        )
        self.cluster_column = ClusterImageColumn(
            self,
            scale_mode_getter=self._current_plot_scale_mode,
        )
        self.merge_image_column = MergeImageColumn(
            self,
            scale_mode_getter=self._current_plot_scale_mode,
        )
        self.merge_operation_panel = MergeOperationPanel(self)
        self.image_workspace = HorizontalImageWorkspace(
            (
                self.original_column,
                self.cluster_column,
                self.merge_image_column,
                self.merge_operation_panel,
            ),
            self,
        )
        self.right_panel = SliceRightPanel(
            session=self._session,
            on_config_changed=self._on_config_changed,
            on_scale_mode_changed=self._on_plot_scale_mode_changed,
            parent=self,
        )
        self._init_param_drawer()

        # 右侧固定按钮只切换滚动锁定和目标位置，不接入任何合并业务逻辑。
        self.right_panel.navigation_control_card.merge_menu_button.toggled.connect(
            self.image_workspace.set_merge_active
        )

        # 内容工作区保持原 A+B 合计伸缩权重，右侧业务面板结构和权重不变。
        root_layout.addWidget(self.image_workspace, 4)
        root_layout.addWidget(self.right_panel, 3)

        # 设置右侧面板最大宽度
        self.right_panel.setMaximumWidth(self.RIGHT_COLUMN_MAX_WIDTH)

    def _init_param_drawer(self) -> None:
        """创建覆盖切片页面的参数抽屉并绑定右侧触发按钮。"""
        self.slice_param_drawer = SlidingDrawer(
            DrawerPosition.RIGHT,
            self.RIGHT_COLUMN_MAX_WIDTH,
            self,
            title="当前Session配置",
        )
        self.slice_param_panel = SliceParamPanel(
            session=self._session,
            on_config_changed=self._on_config_changed,
            parent=self.slice_param_drawer,
        )
        self.slice_param_drawer.setContentWidget(self.slice_param_panel)
        self.slice_param_drawer.setToggleButtonVisible(False)
        drawer_button = self.right_panel.navigation_control_card.drawer_options_button
        self.slice_param_drawer.setTriggerWidget(drawer_button)
        drawer_button.clicked.connect(self.slice_param_drawer.toggle)

    def _update_icon_colors(self) -> None:
        """当主题切换时刷新图像列导航图标颜色。"""
        self.original_column.update_icon_colors()
        self.cluster_column.update_icon_colors()

    def _current_plot_scale_mode(self) -> str:
        """返回当前 session 的图像绘制模式。"""
        return str(self._session.config_snapshot.plot.scale_mode)

    def _on_plot_scale_mode_changed(self, _mode: str) -> None:
        """当绘图拉伸模式变更时，触发所有显示图片的重绘。"""
        cards = [
            *self.original_column.dimension_cards,
            *self.cluster_column.dimension_cards,
            *self.merge_image_column.dimension_cards,
        ]
        for card in cards:
            card.update_image_mode()
