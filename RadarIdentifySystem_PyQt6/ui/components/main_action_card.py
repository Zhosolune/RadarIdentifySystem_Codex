"""主操作卡片组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import PrimarySplitPushButton, PrimaryPushButton, SimpleCardWidget, RoundMenu, Action


class MainActionCard(SimpleCardWidget):
    """主操作卡片。

    功能描述：
        提供带有下拉菜单选项的切片操作拆分按钮与开始识别的主题色按钮，水平布局组合。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        start_slicing_button (PrimarySplitPushButton): 触发切片工作流的拆分按钮。
        start_recognition_button (PrimaryPushButton): 触发识别的按钮（主题色）。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化主操作卡片。

        功能描述：
            创建水平布局，依次添加切片拆分按钮和识别按钮。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(parent)
        self.setObjectName("mainActionCard")

        # 初始化内部组件
        self.start_slicing_button = PrimarySplitPushButton("开始切片", self)
        
        # 配置下拉菜单
        self._setup_button_menu()
        
        # 识别按钮
        self.start_recognition_button = PrimaryPushButton("开始识别", self)

        # 构建水平布局
        self._init_layout()

    def _setup_button_menu(self) -> None:
        """配置按钮的下拉菜单。

        功能描述：
            为拆分按钮添加“开始切片”和“自适应切片”两个选项，并处理文本显示。
        """
        self.slicing_menu = RoundMenu(parent=self.start_slicing_button)
        
        # 添加选项
        self.action_normal = Action('开始切片')
        self.action_adaptive = Action('自适应切片')
        
        self.slicing_menu.addAction(self.action_normal)
        self.slicing_menu.addAction(self.action_adaptive)
        
        # 绑定菜单
        self.start_slicing_button.setFlyout(self.slicing_menu)
        
        # 连接点击事件更新按钮文字
        self.action_normal.triggered.connect(lambda: self.start_slicing_button.setText("开始切片"))
        self.action_adaptive.triggered.connect(lambda: self.start_slicing_button.setText("自适应切片"))

    def _init_layout(self) -> None:
        """初始化内部布局。

        功能描述：
            创建水平布局，设置边距并将切片按钮与识别按钮放入其中。

        参数说明：
            无。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addWidget(self.start_slicing_button)
        layout.addWidget(self.start_recognition_button)
        layout.addStretch(1)
