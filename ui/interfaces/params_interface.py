# -*- coding: utf-8 -*-
"""参数配置界面。"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from qfluentwidgets import (
    ScrollArea,
    ExpandLayout,
    SettingCardGroup,
    FluentIcon,
    SpinBox,
    DoubleSpinBox,
)

from app.app_config import appConfig
from app.style_sheet import StyleSheet
from ui.adapters import ResponsiveContentWidthAdapter
from ui.components.spin_box_setting_card import SpinBoxSettingCard
from ui.components.double_spin_box_setting_card import DoubleSpinBoxSettingCard
from ui.components.recognition_strategy_setting_card import (
    RecognitionStrategySettingCard,
)


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
    # 输入框统一宽度（px）
    INPUT_BOX_WIDTH = 140

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
                icon=FluentIcon.SETTING,
                configItem=appConfig.algorithmEpsilonCF,
                title="CF聚类半径",
                content="DBSCAN 算法中 CF 维度的核心邻域半径容差值",
                unit="MHz",
                decimals=2,
                singleStep=0.01,
                parent=self._clusterGroup,
            )
        )
        self._clusterGroup.addSettingCard(
            SpinBoxSettingCard(
                icon=FluentIcon.PEOPLE,
                configItem=appConfig.algorithmMinPtsCF,
                title="CF核心点最小点数",
                content="DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
                unit="个",
                parent=self._clusterGroup,
            )
        )
        self._clusterGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                icon=FluentIcon.SETTING,
                configItem=appConfig.algorithmEpsilonPW,
                title="PW聚类半径",
                content="DBSCAN 算法中 PW 维度的核心邻域半径容差值",
                unit="μs",
                decimals=2,
                singleStep=0.01,
            )
        )
        self._clusterGroup.addSettingCard(
            SpinBoxSettingCard(
                icon=FluentIcon.PEOPLE,
                configItem=appConfig.algorithmMinPtsPW,
                title="PW核心点最小点数",
                content="DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
                unit="个",
                parent=self._clusterGroup,
            )
        )
        self._clusterGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                icon=FluentIcon.PEOPLE,
                configItem=appConfig.algorithmEpsilonDOA,
                title="DOA聚类半径",
                content="DBSCAN 算法中 DOA 维度的核心邻域半径容差值",
                unit="°",
                parent=self._clusterGroup,
            )
        )
        self._clusterGroup.addSettingCard(
            SpinBoxSettingCard(
                icon=FluentIcon.PEOPLE,
                configItem=appConfig.algorithmMinPtsDOA,
                title="DOA核心点最小点数",
                content="DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
                unit="个",
                parent=self._clusterGroup,
            )
        )
        self._clusterGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                icon=FluentIcon.PEOPLE,
                configItem=appConfig.algorithmClipThresholdDOA,
                title="DOA限幅阈值",
                content="DBSCAN 算法中 DOA 维度的限幅阈值",
                unit="%",
                parent=self._clusterGroup,
            )
        )

        # ── 识别参数组 ────────────────────────────────────────────────────────
        self._recognizeGroup = SettingCardGroup(
            "识别参数配置", self.settingScrollWidget
        )
        self._recognitionStrategyCard = RecognitionStrategySettingCard(
            configItem=appConfig.recognizeGreedyStrategy,
            icon=FluentIcon.SEARCH,
            title="识别策略",
            content="开关拨向贪婪时忽略门限；拨向严格时启用下方门限与权重",
            parent=self._recognizeGroup,
        )
        self._recognitionPaThresholdCard = DoubleSpinBoxSettingCard(
            configItem=appConfig.recognizePaConfidenceThreshold,
            icon=FluentIcon.SEARCH,
            title="PA置信度门限",
            content="严格门限策略中 PA 预测结果必须达到的最低置信度",
            parent=self._recognizeGroup,
            decimals=2,
            singleStep=0.05,
        )
        self._recognitionPaWeightCard = DoubleSpinBoxSettingCard(
            configItem=appConfig.recognizePaConfidenceWeight,
            icon=FluentIcon.SEARCH,
            title="PA置信度权重",
            content="严格门限策略中 PA 置信度参与联合判别的相对权重",
            parent=self._recognizeGroup,
            decimals=2,
            singleStep=0.05,
        )
        self._recognitionDtoaThresholdCard = DoubleSpinBoxSettingCard(
            configItem=appConfig.recognizeDtoaConfidenceThreshold,
            icon=FluentIcon.SEARCH,
            title="DTOA置信度门限",
            content="严格门限策略中 DTOA 预测结果必须达到的最低置信度",
            parent=self._recognizeGroup,
            decimals=2,
            singleStep=0.05,
        )
        self._recognitionDtoaWeightCard = DoubleSpinBoxSettingCard(
            configItem=appConfig.recognizeDtoaConfidenceWeight,
            icon=FluentIcon.SEARCH,
            title="DTOA置信度权重",
            content="严格门限策略中 DTOA 置信度参与联合判别的相对权重",
            parent=self._recognizeGroup,
            decimals=2,
            singleStep=0.05,
        )
        self._recognitionJointThresholdCard = DoubleSpinBoxSettingCard(
            configItem=appConfig.recognizeJointConfidenceThreshold,
            icon=FluentIcon.SEARCH,
            title="联合判别门限",
            content="严格门限策略中按 PA、DTOA 权重比例归一化后的联合概率门限",
            parent=self._recognizeGroup,
            decimals=2,
            singleStep=0.05,
        )
        self._recognitionStrictCards = (
            self._recognitionPaThresholdCard,
            self._recognitionPaWeightCard,
            self._recognitionDtoaThresholdCard,
            self._recognitionDtoaWeightCard,
            self._recognitionJointThresholdCard,
        )
        self._recognizeGroup.addSettingCard(self._recognitionStrategyCard)
        for card in self._recognitionStrictCards:
            self._recognizeGroup.addSettingCard(card)
        self._recognitionStrategyCard.checkedChanged.connect(
            self._sync_recognition_strict_cards_enabled
        )
        self._sync_recognition_strict_cards_enabled(
            self._recognitionStrategyCard.isChecked()
        )

        # ── 提取参数组 ────────────────────────────────────────────────────────
        self._extractCFGroup = SettingCardGroup(
            "CF参数提取配置", self.settingScrollWidget
        )
        self._extractCFGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractEpsilonCF,
                icon=FluentIcon.FILTER,
                title="CF邻域半径",
                content="CF 参数提取时的一维聚类邻域半径",
                unit="MHz",
                parent=self._extractCFGroup,
                decimals=2,
                singleStep=0.01,
            )
        )
        self._extractCFGroup.addSettingCard(
            SpinBoxSettingCard(
                configItem=appConfig.extractMinPtsCF,
                icon=FluentIcon.FILTER,
                title="CF最小邻居点数",
                content="CF 参数提取时形成有效邻域所需的最少邻居点数",
                unit="个",
                parent=self._extractCFGroup,
            )
        )
        self._extractCFGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractThresholdRatioCF,
                icon=FluentIcon.FILTER,
                title="CF门限率",
                content="CF 参数提取时过滤有效簇的点数比例门限",
                unit="%",
                parent=self._extractCFGroup,
                decimals=1,
                singleStep=0.5,
            )
        )
        self._extractPWGroup = SettingCardGroup(
            "PW参数提取配置", self.settingScrollWidget
        )
        self._extractPWGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractEpsilonPW,
                icon=FluentIcon.FILTER,
                title="PW邻域半径",
                content="PW 参数提取时的一维聚类邻域半径",
                unit="μs",
                parent=self._extractPWGroup,
                decimals=2,
                singleStep=0.01,
            )
        )
        self._extractPWGroup.addSettingCard(
            SpinBoxSettingCard(
                configItem=appConfig.extractMinPtsPW,
                icon=FluentIcon.FILTER,
                title="PW最小邻居点数",
                content="PW 参数提取时形成有效邻域所需的最少邻居点数",
                unit="个",
                parent=self._extractPWGroup,
            )
        )
        self._extractPWGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractThresholdRatioPW,
                icon=FluentIcon.FILTER,
                title="PW门限率",
                content="PW 参数提取时过滤有效簇的点数比例门限",
                unit="%",
                parent=self._extractPWGroup,
                decimals=1,
                singleStep=0.5,
            )
        )
        self._extractPRIGroup = SettingCardGroup(
            "PRI参数提取配置", self.settingScrollWidget
        )
        self._extractPRIGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractEpsilonPRI,
                icon=FluentIcon.FILTER,
                title="PRI邻域半径",
                content="PRI 参数提取时的一维聚类邻域半径",
                unit="μs",
                parent=self._extractPRIGroup,
                decimals=2,
                singleStep=0.01,
            )
        )
        self._extractPRIGroup.addSettingCard(
            SpinBoxSettingCard(
                configItem=appConfig.extractMinPtsPRI,
                icon=FluentIcon.FILTER,
                title="PRI最小邻居点数",
                content="PRI 参数提取时形成有效邻域所需的最少邻居点数",
                unit="个",
                parent=self._extractPRIGroup,
            )
        )
        self._extractPRIGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractThresholdRatioPRI,
                icon=FluentIcon.FILTER,
                title="PRI门限率",
                content="PRI 参数提取时过滤有效簇的点数比例门限",
                unit="%",
                parent=self._extractPRIGroup,
                decimals=1,
                singleStep=0.5,
            )
        )
        self._extractPRIGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractFilterThresholdPRI,
                icon=FluentIcon.FILTER,
                title="PRI过滤门限",
                content="PRI 参数提取时过滤过小间隔的时间门限",
                unit="μs",
                parent=self._extractPRIGroup,
                decimals=2,
                singleStep=0.01,
            )
        )
        self._extractPRIGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.extractHarmonicTolerancePRI,
                icon=FluentIcon.FILTER,
                title="PRI谐波抑制容差",
                content="PRI 参数提取时判断谐波关系的容差范围",
                unit="μs",
                parent=self._extractPRIGroup,
                decimals=2,
                singleStep=0.01,
            )
        )

        # ── 合并参数组 ────────────────────────────────────────────────────────
        self._mergeGroup = SettingCardGroup("合并参数配置", self.settingScrollWidget)
        self._mergeGroup.addSettingCard(
            DoubleSpinBoxSettingCard(
                configItem=appConfig.mergePlaceholderValue,
                icon=FluentIcon.LINK,
                title="合并参数占位值",
                content="仅保留全局配置链路，当前合并判别不会读取该值",
                parent=self._mergeGroup,
                decimals=2,
                singleStep=0.01,
            )
        )

        self._initWidget()
        self._responsive_width_adapter = ResponsiveContentWidthAdapter(
            self.viewport(),
            self.cardGroupsLayout,
            max_content_width=self.MAX_CONTENT_WIDTH,
        )

    def _sync_recognition_strict_cards_enabled(self, greedy: bool) -> None:
        """贪婪策略下禁用仅供严格策略使用的门限与权重卡片。"""
        for card in self._recognitionStrictCards:
            card.setEnabled(not greedy)

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
        # 统一输入框宽度
        self._unifyInputBoxWidth()

    def _unifyInputBoxWidth(self) -> None:
        """统一参数输入框宽度。

        功能描述：
            遍历当前参数页中的整数与浮点输入框，并设置统一固定宽度，保持视觉一致性。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        # 统一整数输入框宽度
        for spin_box in self.settingScrollWidget.findChildren(SpinBox):
            spin_box.setFixedWidth(self.INPUT_BOX_WIDTH)

        # 统一浮点输入框宽度
        for double_spin_box in self.settingScrollWidget.findChildren(DoubleSpinBox):
            double_spin_box.setFixedWidth(self.INPUT_BOX_WIDTH)

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

        # 依次添加参数组
        self.cardGroupsLayout.addWidget(self._clusterGroup)
        self.cardGroupsLayout.addWidget(self._recognizeGroup)
        self.cardGroupsLayout.addWidget(self._extractCFGroup)
        self.cardGroupsLayout.addWidget(self._extractPWGroup)
        self.cardGroupsLayout.addWidget(self._extractPRIGroup)
        self.cardGroupsLayout.addWidget(self._mergeGroup)
