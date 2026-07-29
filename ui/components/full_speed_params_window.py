# -*- coding: utf-8 -*-
"""全速任务 Session 参数编辑窗口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    DoubleSpinBox,
    FluentIcon,
    FluentWidget,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SettingCardGroup,
    SpinBox,
    SubtitleLabel,
    SwitchSettingCard,
)

from app.app_config import appConfig
from app.session_config_item import SessionConfigItem, SessionConfigWriter
from app.style_sheet import StyleSheet
from core.models.session_config import SessionConfigSnapshot
from ui.components.double_spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
)
from ui.components.spin_box_setting_card import SpinBoxSettingCard


@dataclass(frozen=True, slots=True)
class _NumericParameterSpec:
    """描述一个需要绑定到 Session 快照的数值参数卡。"""

    path: str
    config_attr: str
    title: str
    content: str
    icon: FluentIcon
    value_type: Literal["int", "float"]
    unit: str | None = None
    decimals: int = 2
    single_step: float = 1.0


_CLUSTER_SPECS = (
    _NumericParameterSpec(
        "clustering.eps_cf",
        "algorithmEpsilonCF",
        "CF聚类半径",
        "DBSCAN 算法中 CF 维度的核心邻域半径容差值",
        FluentIcon.SETTING,
        "float",
        "MHz",
        2,
        0.01,
    ),
    _NumericParameterSpec(
        "clustering.min_pts_cf",
        "algorithmMinPtsCF",
        "CF核心点最小点数",
        "DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
        FluentIcon.PEOPLE,
        "int",
        "个",
    ),
    _NumericParameterSpec(
        "clustering.eps_pw",
        "algorithmEpsilonPW",
        "PW聚类半径",
        "DBSCAN 算法中 PW 维度的核心邻域半径容差值",
        FluentIcon.SETTING,
        "float",
        "μs",
        2,
        0.01,
    ),
    _NumericParameterSpec(
        "clustering.min_pts_pw",
        "algorithmMinPtsPW",
        "PW核心点最小点数",
        "DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
        FluentIcon.PEOPLE,
        "int",
        "个",
    ),
    _NumericParameterSpec(
        "clustering.eps_doa",
        "algorithmEpsilonDOA",
        "DOA聚类半径",
        "DBSCAN 算法中 DOA 维度的核心邻域半径容差值",
        FluentIcon.PEOPLE,
        "float",
        "°",
    ),
    _NumericParameterSpec(
        "clustering.min_pts_doa",
        "algorithmMinPtsDOA",
        "DOA核心点最小点数",
        "DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
        FluentIcon.PEOPLE,
        "int",
        "个",
    ),
    _NumericParameterSpec(
        "clustering.clip_threshold_doa",
        "algorithmClipThresholdDOA",
        "DOA限幅阈值",
        "DBSCAN 算法中 DOA 维度的限幅阈值",
        FluentIcon.PEOPLE,
        "float",
        "%",
    ),
)

_RECOGNITION_SPECS = (
    _NumericParameterSpec(
        "recognition.pa_confidence_threshold",
        "recognizePaConfidenceThreshold",
        "PA置信度门限",
        "严格门限策略中 PA 预测结果必须达到的最低置信度",
        FluentIcon.SEARCH,
        "float",
        decimals=2,
        single_step=0.05,
    ),
    _NumericParameterSpec(
        "recognition.pa_confidence_weight",
        "recognizePaConfidenceWeight",
        "PA置信度权重",
        "严格门限策略中 PA 置信度参与联合判别的相对权重",
        FluentIcon.SEARCH,
        "float",
        decimals=2,
        single_step=0.05,
    ),
    _NumericParameterSpec(
        "recognition.dtoa_confidence_threshold",
        "recognizeDtoaConfidenceThreshold",
        "DTOA置信度门限",
        "严格门限策略中 DTOA 预测结果必须达到的最低置信度",
        FluentIcon.SEARCH,
        "float",
        decimals=2,
        single_step=0.05,
    ),
    _NumericParameterSpec(
        "recognition.dtoa_confidence_weight",
        "recognizeDtoaConfidenceWeight",
        "DTOA置信度权重",
        "严格门限策略中 DTOA 置信度参与联合判别的相对权重",
        FluentIcon.SEARCH,
        "float",
        decimals=2,
        single_step=0.05,
    ),
    _NumericParameterSpec(
        "recognition.joint_confidence_threshold",
        "recognizeJointConfidenceThreshold",
        "联合判别门限",
        "严格门限策略中按 PA、DTOA 权重比例归一化后的联合概率门限",
        FluentIcon.SEARCH,
        "float",
        decimals=2,
        single_step=0.05,
    ),
)

_EXTRACT_CF_SPECS = (
    _NumericParameterSpec(
        "extract.eps_cf",
        "extractEpsilonCF",
        "CF邻域半径",
        "CF 参数提取时的一维聚类邻域半径",
        FluentIcon.FILTER,
        "float",
        "MHz",
        2,
        0.01,
    ),
    _NumericParameterSpec(
        "extract.min_pts_cf",
        "extractMinPtsCF",
        "CF最小邻居点数",
        "CF 参数提取时形成有效邻域所需的最少邻居点数",
        FluentIcon.FILTER,
        "int",
        "个",
    ),
    _NumericParameterSpec(
        "extract.threshold_ratio_cf",
        "extractThresholdRatioCF",
        "CF门限率",
        "CF 参数提取时过滤有效簇的点数比例门限",
        FluentIcon.FILTER,
        "float",
        "%",
        1,
        0.5,
    ),
)

_EXTRACT_PW_SPECS = (
    _NumericParameterSpec(
        "extract.eps_pw",
        "extractEpsilonPW",
        "PW邻域半径",
        "PW 参数提取时的一维聚类邻域半径",
        FluentIcon.FILTER,
        "float",
        "μs",
        2,
        0.01,
    ),
    _NumericParameterSpec(
        "extract.min_pts_pw",
        "extractMinPtsPW",
        "PW最小邻居点数",
        "PW 参数提取时形成有效邻域所需的最少邻居点数",
        FluentIcon.FILTER,
        "int",
        "个",
    ),
    _NumericParameterSpec(
        "extract.threshold_ratio_pw",
        "extractThresholdRatioPW",
        "PW门限率",
        "PW 参数提取时过滤有效簇的点数比例门限",
        FluentIcon.FILTER,
        "float",
        "%",
        1,
        0.5,
    ),
)

_EXTRACT_PRI_SPECS = (
    _NumericParameterSpec(
        "extract.eps_pri",
        "extractEpsilonPRI",
        "PRI邻域半径",
        "PRI 参数提取时的一维聚类邻域半径",
        FluentIcon.FILTER,
        "float",
        "μs",
        2,
        0.01,
    ),
    _NumericParameterSpec(
        "extract.min_pts_pri",
        "extractMinPtsPRI",
        "PRI最小邻居点数",
        "PRI 参数提取时形成有效邻域所需的最少邻居点数",
        FluentIcon.FILTER,
        "int",
        "个",
    ),
    _NumericParameterSpec(
        "extract.threshold_ratio_pri",
        "extractThresholdRatioPRI",
        "PRI门限率",
        "PRI 参数提取时过滤有效簇的点数比例门限",
        FluentIcon.FILTER,
        "float",
        "%",
        1,
        0.5,
    ),
    _NumericParameterSpec(
        "extract.filter_threshold_pri",
        "extractFilterThresholdPRI",
        "PRI过滤门限",
        "PRI 参数提取时过滤过小间隔的时间门限",
        FluentIcon.FILTER,
        "float",
        "μs",
        2,
        0.01,
    ),
    _NumericParameterSpec(
        "extract.harmonic_tolerance_pri",
        "extractHarmonicTolerancePRI",
        "PRI谐波抑制容差",
        "PRI 参数提取时判断谐波关系的容差范围",
        FluentIcon.FILTER,
        "float",
        "μs",
        2,
        0.01,
    ),
)

_MERGE_SPECS = (
    _NumericParameterSpec(
        "merge.placeholder_value",
        "mergePlaceholderValue",
        "合并参数占位值",
        "仅保留全局配置链路，当前合并判别不会读取该值",
        FluentIcon.LINK,
        "float",
        decimals=2,
        single_step=0.01,
    ),
)


class FullSpeedParamsWindow(FluentWidget):
    """编辑一个未冻结全速 Session 的独立参数快照。

    窗口复用全局参数页的字段、文案、单位和输入范围，但所有编辑只写入
    窗口私有草稿；用户点击保存后才通过 ``configSaved`` 提交完整快照。

    Attributes:
        configSaved: 携带完整 ``SessionConfigSnapshot`` 草稿的保存信号。
        parameter_items: 参数路径到 Session 配置项的映射。
        parameter_cards: 参数路径到设置卡的映射。
        left_column_widget: 两栏布局的左列容器。
        right_column_widget: 两栏布局的右列容器。
        save_button: 保存参数并关闭窗口的按钮。
        cancel_button: 放弃草稿并关闭窗口的按钮。
    """

    configSaved = pyqtSignal(object)
    INPUT_BOX_WIDTH = 140

    def __init__(
        self,
        session_id: str,
        display_name: str,
        snapshot: SessionConfigSnapshot,
    ) -> None:
        """初始化全速任务参数窗口。

        Args:
            session_id [str]: 当前窗口绑定的全速 Session ID。
            display_name [str]: 当前 Session 展示名称。
            snapshot [SessionConfigSnapshot]: 打开窗口时的参数快照。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: Session ID 为空时抛出。
        """
        if not session_id.strip():
            raise ValueError("session_id 不能为空")
        super().__init__()
        self.session_id = session_id
        self._draft_snapshot = SessionConfigSnapshot.from_dict(
            snapshot.to_dict()
        )
        self._config_writer = SessionConfigWriter()
        self.parameter_items: dict[str, SessionConfigItem] = {}
        self.parameter_cards: dict[
            str,
            SpinBoxSettingCard | DoubleSpinBoxSettingCard | SwitchSettingCard,
        ] = {}

        self.setObjectName("fullSpeedParamsWindow")
        self.setWindowTitle(f"全速任务参数 - {display_name}")
        self.setWindowIcon(FluentIcon.SETTING.icon())
        self.setMicaEffectEnabled(False)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(1120, 720)
        self.resize(1280, 840)

        self._init_layout(display_name)
        self._unify_input_box_width()
        StyleSheet.SETTING_INTERFACE.apply(self)

    def snapshot(self) -> SessionConfigSnapshot:
        """返回与窗口内部草稿隔离的参数快照副本。

        Returns:
            SessionConfigSnapshot: 当前编辑结果的独立深拷贝。
        """
        return SessionConfigSnapshot.from_dict(self._draft_snapshot.to_dict())

    def _init_layout(self, display_name: str) -> None:
        """创建标题、两栏参数区和底部操作栏。"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 52, 24, 20)
        root_layout.setSpacing(12)

        title_label = SubtitleLabel("全速任务参数", self)
        hint_label = CaptionLabel(
            f"{display_name} · 参数仅作用于当前任务，点击开始后不可修改",
            self,
        )
        root_layout.addWidget(title_label)
        root_layout.addWidget(hint_label)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setObjectName("fullSpeedParamsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.enableTransparentBackground()

        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setObjectName("settingScrollWidget")
        columns_layout = QHBoxLayout(self.content_widget)
        columns_layout.setContentsMargins(8, 8, 8, 16)
        columns_layout.setSpacing(20)

        self.left_column_widget = QWidget(self.content_widget)
        self.left_column_widget.setObjectName("fullSpeedParamsLeftColumn")
        self.right_column_widget = QWidget(self.content_widget)
        self.right_column_widget.setObjectName("fullSpeedParamsRightColumn")
        for column in (
            self.left_column_widget,
            self.right_column_widget,
        ):
            column.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )

        left_layout = QVBoxLayout(self.left_column_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(20)
        right_layout = QVBoxLayout(self.right_column_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(20)

        self.cluster_group = self._create_numeric_group(
            "聚类参数配置",
            _CLUSTER_SPECS,
        )
        self.recognition_group = self._create_recognition_group()
        self.extract_cf_group = self._create_numeric_group(
            "CF参数提取配置",
            _EXTRACT_CF_SPECS,
        )
        self.extract_pw_group = self._create_numeric_group(
            "PW参数提取配置",
            _EXTRACT_PW_SPECS,
        )
        self.extract_pri_group = self._create_numeric_group(
            "PRI参数提取配置",
            _EXTRACT_PRI_SPECS,
        )
        self.merge_group = self._create_numeric_group(
            "合并参数配置",
            _MERGE_SPECS,
        )

        # 按设置卡数量平衡两列高度，同时保持每组内部字段顺序不变。
        left_layout.addWidget(self.cluster_group)
        left_layout.addWidget(self.extract_pri_group)
        left_layout.addStretch(1)
        right_layout.addWidget(self.recognition_group)
        right_layout.addWidget(self.extract_cf_group)
        right_layout.addWidget(self.extract_pw_group)
        right_layout.addWidget(self.merge_group)
        right_layout.addStretch(1)

        columns_layout.addWidget(self.left_column_widget, 1)
        columns_layout.addWidget(self.right_column_widget, 1)
        self.scroll_area.setWidget(self.content_widget)
        root_layout.addWidget(self.scroll_area, 1)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addStretch(1)
        self.cancel_button = PushButton("取消", self)
        self.save_button = PrimaryPushButton("保存参数", self)
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.save_button)
        root_layout.addLayout(action_layout)

        self.cancel_button.clicked.connect(self.close)
        self.save_button.clicked.connect(self._save)

    def _create_recognition_group(self) -> SettingCardGroup:
        """创建识别策略开关及识别数值参数组。"""
        group = SettingCardGroup("识别参数配置", self.content_widget)
        global_item = appConfig.recognizeGreedyStrategy
        strategy_item = SessionConfigItem(
            self._draft_snapshot,
            "recognition.greedy_strategy",
            global_item.defaultValue,
            validator=global_item.validator,
        )
        strategy_card = SwitchSettingCard(
            configItem=None,
            icon=FluentIcon.SEARCH,
            title="识别策略",
            content="开启为贪婪策略；关闭后仅对PA、DTOA均为雷达标签的结果执行严格门限判定",
            parent=group,
        )
        strategy_card.setChecked(bool(strategy_item.value))
        strategy_card.checkedChanged.connect(strategy_item.set)
        strategy_item.valueChanged.connect(strategy_card.setChecked)
        self.parameter_items[strategy_item.path] = strategy_item
        self.parameter_cards[strategy_item.path] = strategy_card
        group.addSettingCard(strategy_card)
        self._add_numeric_cards(group, _RECOGNITION_SPECS)
        return group

    def _create_numeric_group(
        self,
        title: str,
        specs: tuple[_NumericParameterSpec, ...],
    ) -> SettingCardGroup:
        """根据字段描述创建一组 Session 数值参数卡。"""
        group = SettingCardGroup(title, self.content_widget)
        self._add_numeric_cards(group, specs)
        return group

    def _add_numeric_cards(
        self,
        group: SettingCardGroup,
        specs: tuple[_NumericParameterSpec, ...],
    ) -> None:
        """把数值参数描述转换为绑定草稿快照的设置卡。"""
        for spec in specs:
            global_item = getattr(appConfig, spec.config_attr)
            item = SessionConfigItem(
                self._draft_snapshot,
                spec.path,
                global_item.defaultValue,
                validator=global_item.validator,
            )
            if spec.value_type == "int":
                card = SpinBoxSettingCard(
                    configItem=item,
                    icon=spec.icon,
                    title=spec.title,
                    content=spec.content,
                    unit=spec.unit,
                    parent=group,
                    config_writer=self._config_writer,
                )
            else:
                card = DoubleSpinBoxSettingCard(
                    configItem=item,
                    icon=spec.icon,
                    title=spec.title,
                    content=spec.content,
                    unit=spec.unit,
                    decimals=spec.decimals,
                    singleStep=spec.single_step,
                    parent=group,
                    config_writer=self._config_writer,
                )
            self.parameter_items[spec.path] = item
            self.parameter_cards[spec.path] = card
            group.addSettingCard(card)

    def _unify_input_box_width(self) -> None:
        """统一两栏中整数和浮点输入框的宽度。"""
        for spin_box in self.content_widget.findChildren(SpinBox):
            spin_box.setFixedWidth(self.INPUT_BOX_WIDTH)
        for spin_box in self.content_widget.findChildren(DoubleSpinBox):
            spin_box.setFixedWidth(self.INPUT_BOX_WIDTH)

    def _save(self) -> None:
        """提交完整草稿快照，由接收方在持久化成功后关闭窗口。"""
        self.configSaved.emit(self.snapshot())
