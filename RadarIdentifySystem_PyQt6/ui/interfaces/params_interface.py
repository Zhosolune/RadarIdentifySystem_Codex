# -*- coding: utf-8 -*-
"""参数配置界面。"""

import logging

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from qfluentwidgets import (
    ScrollArea,
    ExpandLayout,
    SettingCardGroup,
    FluentIcon,
    SwitchSettingCard,
)

from app.app_config import appConfig
from app.style_sheet import StyleSheet
from ui.components.spin_box_setting_card import SpinBoxSettingCard
from ui.components.double_spin_box_setting_card import DoubleSpinBoxSettingCard

LOGGER = logging.getLogger(__name__)


class ParamsInterface(ScrollArea):
    """参数配置界面类。

    功能描述：
        提供用于修改算法参数和业务控制选项的 UI 界面，包括聚类算法参数、合并算法容差等配置项，
        修改后直接通过 qfluentwidgets 的 qconfig 同步持久化。

    Attributes:
        MAX_CONTENT_WIDTH (int): 内容区最大宽度（px），超出后左右边距自动增大实现居中。
        settingScrollWidget (QWidget): 滚动区域内的容器部件。
        cardGroupsLayout (ExpandLayout): 容纳各个配置卡片组的布局管理器。
    """

    # 内容区最大宽度（px），超出后左右边距自动增大实现居中
    MAX_CONTENT_WIDTH = 860

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化参数配置界面。

        功能描述：
            构建滚动视图，初始化聚类、识别、提取、合并等参数组并应用全局样式。

        Args:
            parent (QWidget | None, optional): 挂载的父节点组件。默认为 None。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        super().__init__(parent)
        self.settingScrollWidget = QWidget()
        self.cardGroupsLayout = ExpandLayout(self.settingScrollWidget)

        # ── 聚类参数组 ────────────────────────────────────────────────────────
        self._clusterGroup = SettingCardGroup("聚类参数配置", self.settingScrollWidget)
        self._clusterGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                appConfig.algorithmEpsilonCF,
                FluentIcon.SETTING,
                "载频聚类半径",
                "DBSCAN 算法中 CF 维度的核心邻域半径容差值",
                self._clusterGroup,
                decimals=2,
                singleStep=0.01,
            )
        )
        self._clusterGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                appConfig.algorithmEpsilonPW,
                FluentIcon.SETTING,
                "脉宽聚类半径",
                "DBSCAN 算法中 PW 维度的核心邻域半径容差值",
                self._clusterGroup,
                decimals=2,
                singleStep=0.01,
            )
        )
        self._clusterGroup.addSettingCard(
            SpinBoxSettingCard(
                appConfig.algorithmMinPts,
                FluentIcon.PEOPLE,
                "核心点最小样本数",
                "DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
                self._clusterGroup,
            )
        )

        # ── 识别参数组 ────────────────────────────────────────────────────────
        self._recognizeGroup = SettingCardGroup(
            "识别参数配置", self.settingScrollWidget
        )
        self._recognizeGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                appConfig.recognizeTolerance,
                FluentIcon.SEARCH,
                "识别容差阈值",
                "配置识别模型中的基本容差判定阈值",
                self._recognizeGroup,
                decimals=2,
                singleStep=0.01,
            )
        )
        self._recognizeGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                appConfig.recognizeMinConfidence,
                FluentIcon.SEARCH,
                "置信度底线",
                "信号类型判定的最低置信度得分要求",
                self._recognizeGroup,
                decimals=2,
                singleStep=0.05,
            )
        )
        self._recognizeGroup.addSettingCard(
            SpinBoxSettingCard(
                appConfig.recognizeMaxCandidates,
                FluentIcon.SEARCH,
                "最大匹配候选数",
                "特征比对时保留的最大候选类型数量",
                self._recognizeGroup,
            )
        )

        # ── 提取参数组 ────────────────────────────────────────────────────────
        self._extractGroup = SettingCardGroup("提取参数配置", self.settingScrollWidget)
        self._extractGroup.addSettingCard(
            SpinBoxSettingCard(
                appConfig.extractStep,
                FluentIcon.FILTER,
                "特征点提取步长",
                "在时序域上抽取雷达信号特征的滑窗步长值",
                self._extractGroup,
            )
        )
        self._extractGroup.addSettingCard(
            SpinBoxSettingCard(
                appConfig.extractSmoothWindow,
                FluentIcon.FILTER,
                "平滑滤波窗口大小",
                "对提取的包络或特征序列进行平滑处理时的窗口点数",
                self._extractGroup,
            )
        )
        self._extractGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                appConfig.extractOutlierThreshold,
                FluentIcon.FILTER,
                "异常点剔除阈值",
                "特征提取阶段用于判断并剔除奇异值的相对误差限",
                self._extractGroup,
                decimals=1,
                singleStep=0.5,
            )
        )

        # ── 合并参数组 ────────────────────────────────────────────────────────
        self._mergeGroup = SettingCardGroup("合并参数配置", self.settingScrollWidget)
        self._mergeGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                appConfig.mergeTimeDecay,
                FluentIcon.LINK,
                "时间衰减权重",
                "跨切片航迹合并时时间间隔对关联概率的衰减系数",
                self._mergeGroup,
                decimals=2,
                singleStep=0.05,
            )
        )
        self._mergeGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                appConfig.mergeSimThreshold,
                FluentIcon.LINK,
                "特征相似度阈值",
                "判定相邻切片中两个信号目标属于同一实体的最低相似度",
                self._mergeGroup,
                decimals=2,
                singleStep=0.05,
            )
        )
        self._mergeGroup.addSettingCard(
            SpinBoxSettingCard(
                appConfig.mergeMaxExtrapolate,
                FluentIcon.LINK,
                "最大外推帧数",
                "航迹断点后允许外推保留的最大连续切片数量",
                self._mergeGroup,
            )
        )

        self._initWidget()

    def _initWidget(self) -> None:
        """初始化控件外观与布局结构。

        功能描述：
            设置滚动策略、边距以及透明背景，并组装各个配置卡片组。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 28, 0, 20)
        self.setWidget(self.settingScrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setObjectName("paramsInterface")

        # 初始化样式命名
        self.settingScrollWidget.setObjectName("settingScrollWidget")
        StyleSheet.SETTING_INTERFACE.apply(self)

        # 执行布局组装
        self._initLayout()

    def _initLayout(self) -> None:
        """初始化卡片组布局。

        功能描述：
            将实例化的各个参数组按垂直顺序挂载到主滚动布局中。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 配置布局间距与边距
        self.cardGroupsLayout.setSpacing(28)
        self.cardGroupsLayout.setContentsMargins(36, 10, 36, 0)

        # 依次添加四个参数组
        self.cardGroupsLayout.addWidget(self._clusterGroup)
        self.cardGroupsLayout.addWidget(self._recognizeGroup)
        self.cardGroupsLayout.addWidget(self._extractGroup)
        self.cardGroupsLayout.addWidget(self._mergeGroup)

    def resizeEvent(self, event) -> None:
        """处理窗口大小改变事件。

        功能描述：
            动态调整左右边距，让卡片内容区不超过 MAX_CONTENT_WIDTH 并始终保持水平居中。

        Args:
            event (QResizeEvent): 触发的窗口大小改变事件对象。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        super().resizeEvent(event)

        # 计算视口宽度并分配左右留白
        viewport_w = self.viewport().width()
        h_margin = max(36, (viewport_w - self.MAX_CONTENT_WIDTH) // 2)
        self.cardGroupsLayout.setContentsMargins(h_margin, 10, h_margin, 0)
