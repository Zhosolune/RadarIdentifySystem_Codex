"""绘图选项卡片组件。"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from qfluentwidgets import ExpandGroupSettingCard, FluentIcon
from app.app_config import appConfig


class PlotOptionWidget(ExpandGroupSettingCard):
    """绘图选项卡片组件。

    功能描述：
        使用 ExpandGroupSettingCard 包裹与绘图相关的子配置卡片。
        包含“图像展示模式”和“图像绘制模式”两项下拉选择配置。
        绑定全局 appConfig 的相应属性以实现持久化与双向同步。

    参数说明：
        parent (QWidget | None): 父级控件。

    属性说明：
        show_mode_card: 图像展示模式的下拉配置卡。
        scale_mode_card: 图像绘制模式的下拉配置卡。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化绘图控制卡片。

        功能描述：
            设置主卡片的图标和文字，创建并添加两个子 ComboBoxSettingCard。

        参数说明：
            parent (QWidget | None): 父级控件。

        返回值说明：
            None: 无返回值。

        异常说明：
            无。
        """
        super().__init__(
            icon=FluentIcon.PHOTO,
            title="绘图选项",
            content="调整图像的展示规则与绘制算法",
            parent=parent
        )
        self.setObjectName("PlotControlSettingCard")

        # 使用 addGroup 将下拉框包装为折叠项
        self.show_mode_combo = self._create_combobox(appConfig.plotOnlyShowIdentified, ["展示全部聚类结果", "仅展示识别后结果"])
        self.addGroup(FluentIcon.FILTER, "图像展示模式", None, self.show_mode_combo)

        self.scale_mode_combo = self._create_combobox(appConfig.plotScaleMode, ["模式一：原始拉伸", "模式二：双线性插值", "模式三：最近邻保留"])
        self.addGroup(FluentIcon.BRUSH, "图像绘制模式", None, self.scale_mode_combo)

    def _create_combobox(self, config_item, texts):
        from qfluentwidgets import ComboBox
        cb = ComboBox()
        cb.addItems(texts)
        
        # 初始化选中项
        index = 0
        try:
            # ConfigItem 的 validator 会确保其值合法
            # OptionsValidator 的 options 列表存储了可用选项
            if config_item.value in config_item.validator.options:
               index = config_item.validator.options.index(config_item.value)
        except Exception:
            pass
        cb.setCurrentIndex(index)
        
        # 绑定下拉框改变事件到全局配置
        cb.currentIndexChanged.connect(lambda i: self._on_combo_changed(config_item, i))
        
        # 绑定全局配置的改变事件到下拉框（双向同步）
        config_item.valueChanged.connect(lambda val: self._on_config_changed(cb, config_item, val))
        
        return cb

    def _on_combo_changed(self, config_item, index):
        """当下拉框选择改变时，同步更新 appConfig"""
        try:
            value = config_item.validator.options[index]
            # 只有值不同才更新，避免死循环
            if config_item.value != value:
                config_item.value = value
        except Exception:
            pass

    def _on_config_changed(self, combobox, config_item, new_value):
        """当 appConfig 改变时，同步更新下拉框的显示"""
        try:
            if new_value in config_item.validator.options:
                index = config_item.validator.options.index(new_value)
                if combobox.currentIndex() != index:
                    combobox.setCurrentIndex(index)
        except Exception:
            pass