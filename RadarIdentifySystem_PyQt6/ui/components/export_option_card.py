"""保存选项卡片组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QLabel, QFileDialog
from qfluentwidgets import ExpandGroupSettingCard, FluentIcon, PushButton, SwitchButton, IndicatorPosition, CaptionLabel, qconfig
from app.app_config import appConfig

class ExportOptionCard(ExpandGroupSettingCard):
    """保存选项卡片。

    功能描述：
        提供展示导出路径、修改导出路径以及控制是否自动保存的设置卡片。
        它是一个折叠设置卡，内部包含修改路径的按钮和自动保存开关。
        右侧动态显示自动保存的启用状态。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        change_export_path_button (PushButton): 更改路径按钮。
        auto_export_switch (SwitchButton): 自动保存开关。
        auto_export_status_label (QLabel): 自动保存状态文本标签。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化保存选项卡片。

        功能描述：
            初始化 ExpandGroupSettingCard，设置其基本内容，并添加内部控件。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(
            icon=FluentIcon.FOLDER,
            title="保存选项",
            content=appConfig.exportDirPath.value,
            parent=parent
        )
        self.setObjectName("exportOptionCard")

        self._init_layout()
        self._connect_signals()

    def _init_layout(self) -> None:
        """初始化卡片内部布局与控件。

        功能描述：
            动态添加状态标签到主卡片右侧，并添加内部展开项。
        """
        # 动态添加状态标签到主卡片
        self.auto_export_status_label = CaptionLabel("已启用自动保存" if appConfig.autoExport.value else "未启用自动保存", self)
        # self.auto_export_status_label.setStyleSheet("color: gray;")
        
        # 将标签插入到主卡片(HeaderSettingCard)的水平布局中（放在展开箭头之前）
        self.card.hBoxLayout.insertWidget(self.card.hBoxLayout.count() - 2, self.auto_export_status_label)
        self.card.hBoxLayout.insertSpacing(self.card.hBoxLayout.count() - 2, 16)

        # 展开项 1：更改路径按钮
        self.change_export_path_button = PushButton("选择文件夹", self)
        self.change_export_path_button.setFixedWidth(120)

        # 展开项 2：自动保存开关
        self.auto_export_switch = SwitchButton(parent=self, indicatorPos=IndicatorPosition.RIGHT)
        
        # 根据配置初始化状态
        self.auto_export_switch.setChecked(appConfig.autoExport.value)
        
        # 将开关绑定到全局配置并更新 UI
        appConfig.autoExport.valueChanged.connect(self.auto_export_switch.setChecked)
        self.auto_export_switch.checkedChanged.connect(self._on_switch_checked_changed)
        
        self.addGroup(FluentIcon.FOLDER, "导出路径", "更改切片或识别结果保存的默认目录", self.change_export_path_button)
        self.addGroup(FluentIcon.SAVE, "自动保存", "切片或识别完成后自动导出结果", self.auto_export_switch)

    def _connect_signals(self) -> None:
        """连接信号与槽函数。"""
        self.change_export_path_button.clicked.connect(self._on_export_path_clicked)
        appConfig.exportDirPath.valueChanged.connect(self._on_export_path_config_changed)
        appConfig.autoExport.valueChanged.connect(self._on_auto_export_config_changed)

    def _on_switch_checked_changed(self, is_checked: bool) -> None:
        """处理开关状态改变事件并同步到全局配置。"""
        if appConfig.autoExport.value != is_checked:
            qconfig.set(appConfig.autoExport, is_checked)

    def _on_export_path_clicked(self) -> None:
        """处理更改导出路径按钮点击事件。"""
        # 注意：这里的 parent 是 self，所以对话框会依附于此组件
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择保存/导出目录",
            appConfig.exportDirPath.value
        )
        if folder:
            qconfig.set(appConfig.exportDirPath, folder)

    def _on_export_path_config_changed(self, new_path: str) -> None:
        """同步全局配置到导出路径设置卡。"""
        self.card.setContent(new_path)

    def _on_auto_export_config_changed(self, enabled: bool) -> None:
        """同步自动保存配置状态到标签。"""
        text = "已启用自动保存" if enabled else "未启用自动保存"
        self.auto_export_status_label.setText(text)
