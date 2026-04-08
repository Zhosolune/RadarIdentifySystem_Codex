"""导航控制卡片组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import CardWidget, PushButton, PrimaryPushButton, TransparentPushButton, SimpleCardWidget, FluentIcon, ElevatedCardWidget, SwitchSettingCard, IconWidget
from app.app_config import appConfig


class NavButtonCard(CardWidget):
    """自定义的可点击悬浮卡片按钮。"""
    
    clicked = pyqtSignal()
    
    def __init__(self, icon: FluentIcon, text: str, parent=None):
        super().__init__(parent)
        # self.setFixedSize(60, 60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.icon_widget = IconWidget(icon, self)
        self.icon_widget.setFixedSize(20, 20)
        
        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 14px;")
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 10, 0, 10)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vBoxLayout.addWidget(self.icon_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignHCenter)
        
    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.clicked.emit()


class NavigationControlCard(SimpleCardWidget):
    """导航控制卡片。

    功能描述：
        提供“上一类”、“下一类”、“上一片”、“下一片”导航按钮（使用 ElevatedCardWidget，位于同一行）。
        下方包含一个“点击下一片直接识别”开关设置卡（SwitchSettingCard），与全局配置联动。
        整体采用垂直布局划分区域。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        prev_cluster_button (NavButtonCard): 切换上一类的按钮。
        next_cluster_button (NavButtonCard): 切换下一类的按钮。
        prev_slice_button (NavButtonCard): 切换上一片的按钮。
        next_slice_button (NavButtonCard): 切换下一片的按钮。
        auto_recognize_card (SwitchSettingCard): 切换下一片时是否自动识别的设置卡。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化导航控制卡片。

        功能描述：
            创建布局并实例化内部的所有导航按钮和复选框组件。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(parent)
        self.setObjectName("navigationControlCard")

        # 类别导航
        self.prev_cluster_button = NavButtonCard(FluentIcon.CHEVRON_RIGHT, "上一类", self)
        self.next_cluster_button = NavButtonCard(FluentIcon.CHEVRON_RIGHT, "下一类", self)

        # 重置按钮
        self.reset_cur_slice_button  = NavButtonCard(FluentIcon.CHEVRON_RIGHT, "重置当前切片", self)
        # self.reset_cur_slice_button = TransparentPushButton("重置当前切片", self)

        # 切片导航
        self.prev_slice_button = NavButtonCard(FluentIcon.CARE_LEFT_SOLID, "上一片", self)
        self.next_slice_button = NavButtonCard(FluentIcon.CARE_RIGHT_SOLID, "下一片", self)
        
        # 自动选项设置卡
        self.auto_recognize_card = SwitchSettingCard(
            icon=FluentIcon.PLAY,
            title="自动识别",
            content="切换下一片时自动执行识别工作流",
            configItem=appConfig.autoRecognizeNextSlice,
            parent=self
        )

        self._init_layout()

    def _init_layout(self) -> None:
        """初始化卡片内部布局。

        功能描述：
            将导航悬浮按钮放在同一行居中，设置卡放在下方，采用垂直嵌套布局排版。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(5)

        # 第一行：所有导航按钮
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        nav_layout.addWidget(self.prev_cluster_button)
        nav_layout.addWidget(self.next_cluster_button)
        nav_layout.addWidget(self.prev_slice_button)
        nav_layout.addWidget(self.next_slice_button)
        nav_layout.addWidget(self.reset_cur_slice_button)

        main_layout.addLayout(nav_layout)
        main_layout.addWidget(self.auto_recognize_card)
