"""主页界面。"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QCursor, QResizeEvent
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    BodyLabel,
    ScrollArea,
    FolderListSettingCard,
)
from app.app_config import appConfig
from app.style_sheet import StyleSheet
from ui.components import (
    ImportDataPanel,
    DataPoolPanel,
    FullSpeedSessionPanel,
    JitterFreeCardGroup,
    SessionManagerPanel,
)


class _HomeScrollBarHoverController(QObject):
    """控制主页单个滚动区域仅在鼠标进入后按需显示滚动条。"""

    def __init__(self, scroll_area: QAbstractScrollArea) -> None:
        """记录原始方向策略并立即隐藏滚动条。"""
        super().__init__(scroll_area)
        self._scroll_area = scroll_area
        self._viewport = scroll_area.viewport()
        self._fluent_bars = []
        self._native_policies: (
            tuple[Qt.ScrollBarPolicy, Qt.ScrollBarPolicy] | None
        ) = None
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.timeout.connect(self._hide_if_pointer_outside)

        scroll_delegate = getattr(scroll_area, "scrollDelagate", None)
        if scroll_delegate is None:
            scroll_delegate = getattr(scroll_area, "delegate", None)

        vertical_bar = getattr(scroll_delegate, "vScrollBar", None)
        horizontal_bar = getattr(scroll_delegate, "hScrollBar", None)
        if vertical_bar is not None and horizontal_bar is not None:
            # Fluent 覆盖式滚动条的 Qt 原生策略始终为 AlwaysOff，
            # 因此必须从代理滚动条记录各方向是否原本允许按需显示。
            self._fluent_bars = [
                (vertical_bar, not vertical_bar._isForceHidden),
                (horizontal_bar, not horizontal_bar._isForceHidden),
            ]
        else:
            self._native_policies = (
                scroll_area.verticalScrollBarPolicy(),
                scroll_area.horizontalScrollBarPolicy(),
            )

        scroll_area.installEventFilter(self)
        self._viewport.installEventFilter(self)
        self._hide_scroll_bars()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """根据鼠标是否位于滚动区域内切换滚动条策略。"""
        if (
            watched is self._scroll_area
            or watched is self._viewport
        ):
            if event.type() == QEvent.Type.Enter:
                self._leave_timer.stop()
                self._show_scroll_bars_if_needed()
            elif (
                watched is self._scroll_area
                and event.type() == QEvent.Type.Leave
            ):
                self._leave_timer.stop()
                self._hide_scroll_bars()
            elif event.type() == QEvent.Type.Leave:
                # 指针从视口移到覆盖式滚动条时仍在滚动区域内部；
                # 延后一拍读取真实位置，避免滚动条刚出现便被隐藏。
                self._leave_timer.start(0)
        return super().eventFilter(watched, event)

    def _hide_if_pointer_outside(self) -> None:
        """指针确已离开整个滚动区域时再隐藏滚动条。"""
        local_position = self._scroll_area.mapFromGlobal(QCursor.pos())
        if not self._scroll_area.rect().contains(local_position):
            self._hide_scroll_bars()

    def _show_scroll_bars_if_needed(self) -> None:
        """恢复允许方向，具体显隐继续由实际滚动范围决定。"""
        if self._native_policies is not None:
            vertical_policy, horizontal_policy = self._native_policies
            self._scroll_area.setVerticalScrollBarPolicy(vertical_policy)
            self._scroll_area.setHorizontalScrollBarPolicy(horizontal_policy)
            return

        for bar, was_allowed in self._fluent_bars:
            bar.setForceHidden(not was_allowed)

    def _hide_scroll_bars(self) -> None:
        """隐藏滚动区域的全部原生或 Fluent 滚动条。"""
        if self._native_policies is not None:
            self._scroll_area.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self._scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            return

        for bar, _ in self._fluent_bars:
            bar.setForceHidden(True)


class HomeInterface(QFrame):
    """主页两栏界面。

    左侧滚动列依次展示数据目录、导入文件和数据池；右侧上下两个同级面板
    分别管理交互式切片 Session 与全速处理 Session。
    """

    _DATA_POOL_BASE_HEIGHT = 350
    _DATA_POOL_MEDIUM_HEIGHT = 400
    _DATA_POOL_LARGE_HEIGHT = 500
    _MEDIUM_HEIGHT_BREAKPOINT = 1000
    _LARGE_HEIGHT_BREAKPOINT = 1300

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """初始化主页界面。

        Args:
            parent: 父级控件，默认值为 None。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """

        super().__init__(parent)
        self.setObjectName("homeInterface")
        self._init_layout()
        self._install_scrollbar_hover_behavior()
        StyleSheet.HOME_INTERFACE.apply(self)

    def _init_layout(self) -> None:
        """初始化两栏布局。

        构建左侧数据导入/数据池列和右侧双 Session 列。
        """

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # 创建左侧数据导入与数据池布局。
        self.left_column = self._create_left_column()
        # 创建右侧上下双卡片布局。
        self.right_column = self._create_right_column()

        root_layout.addWidget(self.left_column, 4)
        root_layout.addWidget(self.right_column, 5)

    def _install_scrollbar_hover_behavior(self) -> None:
        """为主页当前全部滚动区域安装悬停按需显示控制器。"""
        self._scrollbar_hover_controllers = [
            _HomeScrollBarHoverController(scroll_area)
            for scroll_area in self.findChildren(QAbstractScrollArea)
        ]

    def _create_left_column(self) -> QWidget:
        """创建左侧数据导入与数据池面板。

        内容较高时由列内滚动区承载，避免压缩数据池操作按钮。
        """

        column = QWidget(self)
        column.setObjectName("homeLeftColumn")

        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(0)

        # ---------- ScrollArea ----------
        # 使用 qfluentwidgets 的 ScrollArea，自带主题感知滚动条样式
        scroll_area = ScrollArea(column)
        scroll_area.setObjectName("homeLeftScrollArea")
        scroll_area.setWidgetResizable(True)
        # 关闭水平滚动条，保持面板整洁
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # ---------- 滚动内容容器 ----------
        scroll_content = QWidget()
        scroll_content.setObjectName("homeLeftScrollContent")

        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # ---------- JitterFreeCardGroup ----------
        data_dir_group = JitterFreeCardGroup(scroll_content)
        data_dir_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        # FolderListSettingCard：自动从 appConfig.importDataDirs 读写
        # directory 参数指定"添加文件夹"对话框的初始目录
        import os
        default_dir = os.path.expanduser("~")
        self.import_dir_card = FolderListSettingCard(
            configItem=appConfig.importDataDirs,
            title="数据目录",
            content="管理雷达数据文件的导入目录列表",
            directory=default_dir,
            parent=data_dir_group,
        )
        data_dir_group.addSettingCard(self.import_dir_card)
        content_layout.addWidget(data_dir_group)

        # ---------- 导入数据面板（标签栏 + 文件列表） ----------
        # 放置在导入目录卡片下方，提供 Excel/Bin/MAT 三种格式的文件管理界面
        self.import_panel = ImportDataPanel(scroll_content)
        # 文件列表承担右侧栏剩余高度，空间不足时交给外层 ScrollArea 滚动。
        self.import_panel.setMinimumHeight(320)
        self.import_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        content_layout.addWidget(self.import_panel, 1)

        # ---------- 数据池面板 ----------
        # 解析完成的数据包在此统一注册，再从数据包创建不同处理模式的 Session。
        self.data_pool_panel = DataPoolPanel(scroll_content)
        self.data_pool_panel.setFixedHeight(self._DATA_POOL_BASE_HEIGHT)
        content_layout.addWidget(self.data_pool_panel, 0)

        # 将内容容器注入 ScrollArea
        scroll_area.setWidget(scroll_content)

        column_layout.addWidget(scroll_area)
        return column

    def _create_right_column(self) -> QWidget:
        """创建右侧两类同级 Session 面板。

        上方为交互式切片 Session，下方为全速处理 Session，两者按相同
        拉伸因子分配高度。
        """

        column = QWidget(self)
        column.setObjectName("homeSessionColumn")

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # session管理面板
        self.session_manager_panel = SessionManagerPanel(column)
        self.session_manager_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.session_manager_panel, 1)
        self.full_speed_session_panel = FullSpeedSessionPanel(column)
        layout.addWidget(self.full_speed_session_panel, 1)
        return column

    def resizeEvent(self, event: QResizeEvent) -> None:
        """在主页高度变化时调整数据池面板高度。

        Args:
            event [QResizeEvent]: 主页尺寸变化事件。

        Returns:
            None: 无返回值。
        """
        super().resizeEvent(event)
        if hasattr(self, "data_pool_panel"):
            self.data_pool_panel.setFixedHeight(
                self._responsive_data_pool_height(event.size().height())
            )

    def _responsive_data_pool_height(
        self,
        available_height: int | None = None,
    ) -> int:
        """根据主页可用高度返回 350、400 或 500px。"""
        if available_height is None:
            available_height = self.height()
        if available_height >= self._LARGE_HEIGHT_BREAKPOINT:
            return self._DATA_POOL_LARGE_HEIGHT
        if available_height >= self._MEDIUM_HEIGHT_BREAKPOINT:
            return self._DATA_POOL_MEDIUM_HEIGHT
        return self._DATA_POOL_BASE_HEIGHT
