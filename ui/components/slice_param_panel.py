"""提供切片参数抽屉的独立内容面板。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    BoolValidator,
    FluentIcon,
    FluentIconBase,
    RangeValidator,
    ScrollArea,
    SwitchSettingCard,
    SettingCardGroup,
)

from app.session_config_item import SessionConfigItem, SessionConfigWriter
from app.app_config import appConfig
from core.models.processing_session import ProcessingSession
from .double_spin_box_setting_card import DoubleSpinBoxSettingCard
from .export_option_card import ExportOptionCard
from .model_selection_card import ModelSelectionCard
from .recognition_strategy_setting_card import RecognitionStrategySettingCard
from .spin_box_setting_card import SpinBoxSettingCard

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _SessionNumericSpec:
    """描述一项绑定 Session 快照的数值设置卡。"""

    path: str
    config_attr: str
    title: str
    content: str
    unit: str | None = None
    decimals: int = 2
    single_step: float = 1.0
    integer: bool = False


_RECOGNITION_SPECS = (
    _SessionNumericSpec(
        "recognition.pa_confidence_threshold",
        "recognizePaConfidenceThreshold",
        "PA置信度门限",
        "严格门限策略中 PA 预测结果必须达到的最低置信度",
        single_step=0.05,
    ),
    _SessionNumericSpec(
        "recognition.pa_confidence_weight",
        "recognizePaConfidenceWeight",
        "PA置信度权重",
        "严格门限策略中 PA 置信度参与联合判别的相对权重",
        single_step=0.05,
    ),
    _SessionNumericSpec(
        "recognition.dtoa_confidence_threshold",
        "recognizeDtoaConfidenceThreshold",
        "DTOA置信度门限",
        "严格门限策略中 DTOA 预测结果必须达到的最低置信度",
        single_step=0.05,
    ),
    _SessionNumericSpec(
        "recognition.dtoa_confidence_weight",
        "recognizeDtoaConfidenceWeight",
        "DTOA置信度权重",
        "严格门限策略中 DTOA 置信度参与联合判别的相对权重",
        single_step=0.05,
    ),
    _SessionNumericSpec(
        "recognition.joint_confidence_threshold",
        "recognizeJointConfidenceThreshold",
        "联合判别门限",
        "严格门限策略中按 PA、DTOA 权重比例归一化后的联合概率门限",
        single_step=0.05,
    ),
)

_EXTRACT_CF_SPECS = (
    _SessionNumericSpec(
        "extract.eps_cf",
        "extractEpsilonCF",
        "CF邻域半径",
        "CF 参数提取时的一维聚类邻域半径",
        unit="MHz",
        single_step=0.01,
    ),
    _SessionNumericSpec(
        "extract.min_pts_cf",
        "extractMinPtsCF",
        "CF最小邻居点数",
        "CF 参数提取时形成有效邻域所需的最少邻居点数",
        unit="个",
        integer=True,
    ),
    _SessionNumericSpec(
        "extract.threshold_ratio_cf",
        "extractThresholdRatioCF",
        "CF门限率",
        "CF 参数提取时过滤有效簇的点数比例门限",
        unit="%",
        decimals=1,
        single_step=0.5,
    ),
)

_EXTRACT_PW_SPECS = (
    _SessionNumericSpec(
        "extract.eps_pw",
        "extractEpsilonPW",
        "PW邻域半径",
        "PW 参数提取时的一维聚类邻域半径",
        unit="μs",
        single_step=0.01,
    ),
    _SessionNumericSpec(
        "extract.min_pts_pw",
        "extractMinPtsPW",
        "PW最小邻居点数",
        "PW 参数提取时形成有效邻域所需的最少邻居点数",
        unit="个",
        integer=True,
    ),
    _SessionNumericSpec(
        "extract.threshold_ratio_pw",
        "extractThresholdRatioPW",
        "PW门限率",
        "PW 参数提取时过滤有效簇的点数比例门限",
        unit="%",
        decimals=1,
        single_step=0.5,
    ),
)

_EXTRACT_PRI_SPECS = (
    _SessionNumericSpec(
        "extract.eps_pri",
        "extractEpsilonPRI",
        "PRI邻域半径",
        "PRI 参数提取时的一维聚类邻域半径",
        unit="μs",
        single_step=0.01,
    ),
    _SessionNumericSpec(
        "extract.min_pts_pri",
        "extractMinPtsPRI",
        "PRI最小邻居点数",
        "PRI 参数提取时形成有效邻域所需的最少邻居点数",
        unit="个",
        integer=True,
    ),
    _SessionNumericSpec(
        "extract.threshold_ratio_pri",
        "extractThresholdRatioPRI",
        "PRI门限率",
        "PRI 参数提取时过滤有效簇的点数比例门限",
        unit="%",
        decimals=1,
        single_step=0.5,
    ),
    _SessionNumericSpec(
        "extract.filter_threshold_pri",
        "extractFilterThresholdPRI",
        "PRI过滤门限",
        "PRI 参数提取时过滤过小间隔的时间门限",
        unit="μs",
        single_step=0.01,
    ),
    _SessionNumericSpec(
        "extract.harmonic_tolerance_pri",
        "extractHarmonicTolerancePRI",
        "PRI谐波抑制容差",
        "PRI 参数提取时判断谐波关系的容差范围",
        unit="μs",
        single_step=0.01,
    ),
)


class SliceParamPanel(QWidget):
    """集中承载当前切片页面的参数设置卡片。

    该组件只负责抽屉内容布局，不创建或继承抽屉。未来与 Session 子配置相关的
    设置卡可继续加入此面板。

    Attributes:
        session: 当前切片页面所属的处理 session。
        auto_recognize_item: 绑定到当前 session 子配置的自动识别设置项。
        auto_recognize_card: 切换切片时自动识别的设置卡。
        clustering_group: 当前 session 聚类参数设置组。
        model_selection_card: 当前页面使用的 PA 与 DTOA 模型选择卡。
        export_path_card: 导出路径与自动保存设置卡。
        drawer_scroll_area: 支持内容溢出的滚动区域。
        drawer_scroll_widget: 滚动区域承载的内容控件。
        drawer_scroll_layout: 提供抽屉内容边距的布局。
        recognition_group: 当前 Session 识别策略及严格门限设置组。
        extract_cf_group: 当前 Session CF 参数提取设置组。
        extract_pw_group: 当前 Session PW 参数提取设置组。
        extract_pri_group: 当前 Session PRI 参数提取设置组。
        merge_group: 当前Session合并参数占位设置组。
        merge_placeholder_card: 绑定Session快照占位字段的设置卡。
        cards_group: 管理可展开卡片高度的无抖动卡片组。
    """

    def __init__(
        self,
        session: ProcessingSession,
        on_config_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """创建抽屉内容卡片并完成纵向布局。

        Args:
            session [ProcessingSession]: 当前页面所属 session，用于读写独立子配置。
            on_config_changed [Callable[[], None] | None]: 子配置变更后的保存回调，默认不回调。
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 模型目录扫描失败时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> panel = SliceParamPanel(ProcessingSession())
            >>> panel.objectName()
            'sliceParamPanel'
        """
        super().__init__(parent)
        self.setObjectName("sliceParamPanel")

        self.session: ProcessingSession = session
        self._on_config_changed = on_config_changed
        self._session_config_writer = SessionConfigWriter()
        self.auto_recognize_item: SessionConfigItem = SessionConfigItem(
            self.session.config_snapshot,
            "business.auto_recognize_next_slice",
            True,
            validator=BoolValidator(),
            on_changed=on_config_changed,
        )
        self.auto_recognize_card: SwitchSettingCard = SwitchSettingCard(
            icon=FluentIcon.PLAY,
            title="自动识别",
            content="切换切片时自动执行识别工作流",
            configItem=None,
            parent=self,
        )
        self.auto_recognize_card.setChecked(bool(self.auto_recognize_item.value))
        self.auto_recognize_card.checkedChanged.connect(self.auto_recognize_item.set)
        self.auto_recognize_item.valueChanged.connect(
            self.auto_recognize_card.setChecked
        )
        self.auto_recognize_item.valueChanged.connect(
            self._log_auto_recognize_changed
        )
        self.model_selection_card: ModelSelectionCard = ModelSelectionCard(
            self,
            initial_model_paths={
                "PA": self.session.model_selection.pa_model_path,
                "DTOA": self.session.model_selection.dtoa_model_path,
            },
        )
        self._sync_initial_model_selection()
        self.model_selection_card.modelChanged.connect(self._on_model_changed)
        self.export_path_card: ExportOptionCard = ExportOptionCard(self)
        self.session_parameter_items: dict[str, SessionConfigItem] = {}
        self.session_parameter_cards: dict[
            str,
            SpinBoxSettingCard | DoubleSpinBoxSettingCard,
        ] = {}
        self.clustering_group: SettingCardGroup = self._create_clustering_group()
        self.recognition_group: SettingCardGroup = self._create_recognition_group()
        self.extract_cf_group: SettingCardGroup = self._create_numeric_group(
            "CF参数提取配置",
            _EXTRACT_CF_SPECS,
            FluentIcon.FILTER,
        )
        self.extract_pw_group: SettingCardGroup = self._create_numeric_group(
            "PW参数提取配置",
            _EXTRACT_PW_SPECS,
            FluentIcon.FILTER,
        )
        self.extract_pri_group: SettingCardGroup = self._create_numeric_group(
            "PRI参数提取配置",
            _EXTRACT_PRI_SPECS,
            FluentIcon.FILTER,
        )
        self.merge_group: SettingCardGroup = self._create_merge_group()

        self._init_layout()

    def _create_clustering_group(self) -> SettingCardGroup:
        """创建绑定当前 session 子配置的聚类参数设置组。

        Args:
            无。

        Returns:
            SettingCardGroup: 包含 CF/PW/DOA 聚类参数卡片的设置组。

        Raises:
            ValueError: 当 session 配置字段路径不存在时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> panel = SliceParamPanel(ProcessingSession())
            >>> panel.clustering_group.titleLabel.text()
            '聚类参数配置'
        """
        group = SettingCardGroup("聚类参数配置", self.drawer_scroll_widget if hasattr(self, "drawer_scroll_widget") else self)
        self.clustering_eps_cf_item = SessionConfigItem(
            self.session.config_snapshot,
            "clustering.eps_cf",
            2.0,
            validator=RangeValidator(0.01, 50.0),
            on_changed=self._on_config_changed,
        )
        self.clustering_min_pts_cf_item = SessionConfigItem(
            self.session.config_snapshot,
            "clustering.min_pts_cf",
            2,
            validator=RangeValidator(1, 9999),
            on_changed=self._on_config_changed,
        )
        self.clustering_eps_pw_item = SessionConfigItem(
            self.session.config_snapshot,
            "clustering.eps_pw",
            0.2,
            validator=RangeValidator(0.01, 10.0),
            on_changed=self._on_config_changed,
        )
        self.clustering_min_pts_pw_item = SessionConfigItem(
            self.session.config_snapshot,
            "clustering.min_pts_pw",
            2,
            validator=RangeValidator(1, 9999),
            on_changed=self._on_config_changed,
        )
        self.clustering_eps_doa_item = SessionConfigItem(
            self.session.config_snapshot,
            "clustering.eps_doa",
            16.8,
            validator=RangeValidator(0.01, 50.0),
            on_changed=self._on_config_changed,
        )
        self.clustering_min_pts_doa_item = SessionConfigItem(
            self.session.config_snapshot,
            "clustering.min_pts_doa",
            2,
            validator=RangeValidator(1, 9999),
            on_changed=self._on_config_changed,
        )
        self.clustering_clip_doa_item = SessionConfigItem(
            self.session.config_snapshot,
            "clustering.clip_threshold_doa",
            95.0,
            validator=RangeValidator(0.0, 100.0),
            on_changed=self._on_config_changed,
        )

        self.clustering_eps_cf_card = DoubleSpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            configItem=self.clustering_eps_cf_item,
            title="CF聚类半径",
            content="DBSCAN 算法中 CF 维度的核心邻域半径容差值",
            unit="MHz",
            decimals=2,
            singleStep=0.01,
            parent=group,
            config_writer=self._session_config_writer,
        )
        self.clustering_min_pts_cf_card = SpinBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            configItem=self.clustering_min_pts_cf_item,
            title="CF核心点最小点数",
            content="DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
            unit="个",
            parent=group,
            config_writer=self._session_config_writer,
        )
        self.clustering_eps_pw_card = DoubleSpinBoxSettingCard(
            icon=FluentIcon.SETTING,
            configItem=self.clustering_eps_pw_item,
            title="PW聚类半径",
            content="DBSCAN 算法中 PW 维度的核心邻域半径容差值",
            unit="μs",
            decimals=2,
            singleStep=0.01,
            parent=group,
            config_writer=self._session_config_writer,
        )
        self.clustering_min_pts_pw_card = SpinBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            configItem=self.clustering_min_pts_pw_item,
            title="PW核心点最小点数",
            content="DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
            unit="个",
            parent=group,
            config_writer=self._session_config_writer,
        )
        self.clustering_eps_doa_card = DoubleSpinBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            configItem=self.clustering_eps_doa_item,
            title="DOA聚类半径",
            content="DBSCAN 算法中 DOA 维度的核心邻域半径容差值",
            unit="°",
            decimals=2,
            singleStep=0.1,
            parent=group,
            config_writer=self._session_config_writer,
        )
        self.clustering_min_pts_doa_card = SpinBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            configItem=self.clustering_min_pts_doa_item,
            title="DOA核心点最小点数",
            content="DBSCAN 算法中构成一个聚类核心对象所需要的最少点数",
            unit="个",
            parent=group,
            config_writer=self._session_config_writer,
        )
        self.clustering_clip_doa_card = DoubleSpinBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            configItem=self.clustering_clip_doa_item,
            title="DOA限幅阈值",
            content="DBSCAN 算法中 DOA 维度的限幅阈值",
            unit="%",
            decimals=2,
            singleStep=1.0,
            parent=group,
            config_writer=self._session_config_writer,
        )

        for card in [
            self.clustering_eps_cf_card,
            self.clustering_min_pts_cf_card,
            self.clustering_eps_pw_card,
            self.clustering_min_pts_pw_card,
            self.clustering_eps_doa_card,
            self.clustering_min_pts_doa_card,
            self.clustering_clip_doa_card,
        ]:
            # 将 session 级参数卡加入同一设置组，保持抽屉中参数结构清晰。
            group.addSettingCard(card)

        return group

    def _create_recognition_group(self) -> SettingCardGroup:
        """创建绑定当前 Session 识别策略和严格门限的设置组。"""
        group = SettingCardGroup("识别参数配置", self)
        global_item = appConfig.recognizeGreedyStrategy
        self.recognition_strategy_item = SessionConfigItem(
            self.session.config_snapshot,
            "recognition.greedy_strategy",
            global_item.defaultValue,
            validator=global_item.validator,
            on_changed=self._on_config_changed,
        )
        self.recognition_strategy_card = RecognitionStrategySettingCard(
            configItem=None,
            icon=FluentIcon.SEARCH,
            title="识别策略",
            content="开关拨向贪婪时忽略门限；拨向严格时启用下方门限与权重",
            parent=group,
        )
        self.recognition_strategy_card.setChecked(
            bool(self.recognition_strategy_item.value)
        )
        self.recognition_strategy_card.checkedChanged.connect(
            self.recognition_strategy_item.set
        )
        self.recognition_strategy_item.valueChanged.connect(
            self.recognition_strategy_card.setChecked
        )
        group.addSettingCard(self.recognition_strategy_card)
        self.session_parameter_items[self.recognition_strategy_item.path] = (
            self.recognition_strategy_item
        )

        strict_cards = self._add_numeric_cards(
            group,
            _RECOGNITION_SPECS,
            FluentIcon.SEARCH,
        )
        self._recognition_strict_cards = strict_cards
        self.recognition_strategy_card.checkedChanged.connect(
            self._sync_recognition_strict_cards_enabled
        )
        self._sync_recognition_strict_cards_enabled(
            self.recognition_strategy_card.isChecked()
        )
        return group

    def _create_numeric_group(
        self,
        title: str,
        specs: tuple[_SessionNumericSpec, ...],
        icon: FluentIconBase,
    ) -> SettingCardGroup:
        """根据描述创建绑定当前 Session 快照的数值设置组。"""
        group = SettingCardGroup(title, self)
        self._add_numeric_cards(group, specs, icon)
        return group

    def _add_numeric_cards(
        self,
        group: SettingCardGroup,
        specs: tuple[_SessionNumericSpec, ...],
        icon: FluentIconBase,
    ) -> tuple[SpinBoxSettingCard | DoubleSpinBoxSettingCard, ...]:
        """将数值描述转换为 Session 设置项和对应设置卡。"""
        cards: list[SpinBoxSettingCard | DoubleSpinBoxSettingCard] = []
        for spec in specs:
            global_item = getattr(appConfig, spec.config_attr)
            item = SessionConfigItem(
                self.session.config_snapshot,
                spec.path,
                global_item.defaultValue,
                validator=global_item.validator,
                on_changed=self._on_config_changed,
            )
            if spec.integer:
                card = SpinBoxSettingCard(
                    configItem=item,
                    icon=icon,
                    title=spec.title,
                    content=spec.content,
                    unit=spec.unit,
                    parent=group,
                    config_writer=self._session_config_writer,
                )
            else:
                card = DoubleSpinBoxSettingCard(
                    configItem=item,
                    icon=icon,
                    title=spec.title,
                    content=spec.content,
                    unit=spec.unit,
                    decimals=spec.decimals,
                    singleStep=spec.single_step,
                    parent=group,
                    config_writer=self._session_config_writer,
                )
            group.addSettingCard(card)
            self.session_parameter_items[spec.path] = item
            self.session_parameter_cards[spec.path] = card
            cards.append(card)
        return tuple(cards)

    def _sync_recognition_strict_cards_enabled(self, greedy: bool) -> None:
        """贪婪策略下禁用仅由严格策略消费的数值卡片。"""
        for card in self._recognition_strict_cards:
            card.setEnabled(not greedy)

    def _create_merge_group(self) -> SettingCardGroup:
        """创建绑定当前Session快照的合并参数占位组。

        当前字段没有业务含义，仅用于验证参数作用域链路。未来出现真实合并
        参数时，应在这里使用 ``SessionConfigItem`` 绑定
        ``session.config_snapshot.merge`` 的实际字段；这些修改只写入当前
        Session，不得修改全局 ``qconfig``。

        Returns:
            SettingCardGroup: 包含单一合并参数占位卡片的设置组。

        Raises:
            ValueError: Session配置字段路径不存在时抛出。

        Example:
            >>> from PyQt6.QtWidgets import QApplication
            >>> app = QApplication.instance() or QApplication([])
            >>> panel = SliceParamPanel(ProcessingSession())
            >>> panel.merge_group.titleLabel.text()
            '合并参数配置'
        """
        group = SettingCardGroup(
            "合并参数配置",
            self.drawer_scroll_widget
            if hasattr(self, "drawer_scroll_widget")
            else self,
        )
        self.merge_placeholder_item: SessionConfigItem = SessionConfigItem(
            self.session.config_snapshot,
            "merge.placeholder_value",
            0.0,
            validator=RangeValidator(0.0, 1.0),
            on_changed=self._on_config_changed,
        )
        self.merge_placeholder_card: DoubleSpinBoxSettingCard = (
            DoubleSpinBoxSettingCard(
                icon=FluentIcon.LINK,
                configItem=self.merge_placeholder_item,
                title="合并参数占位值",
                content="仅保留Session配置链路，当前合并判别不会读取该值",
                decimals=2,
                singleStep=0.01,
                parent=group,
                config_writer=self._session_config_writer,
            )
        )
        group.addSettingCard(self.merge_placeholder_card)
        return group

    def _sync_initial_model_selection(self) -> None:
        """将模型卡片的初始选择复制到当前 session。"""
        self.session.model_selection.pa_model_path = (
            self.model_selection_card.selected_model_path("PA")
        )
        self.session.model_selection.dtoa_model_path = (
            self.model_selection_card.selected_model_path("DTOA")
        )

    def _on_model_changed(self, model_type: str, model_path: str | None) -> None:
        """将模型卡片选择写入当前 session 并触发保存回调。"""
        if model_type == "PA":
            self.session.model_selection.pa_model_path = model_path
        elif model_type == "DTOA":
            self.session.model_selection.dtoa_model_path = model_path
        else:
            return

        if self._on_config_changed:
            self._on_config_changed()

    def _log_auto_recognize_changed(self, new_value: object) -> None:
        """记录当前 session 的自动识别开关变化。"""
        LOGGER.info(
            "更新当前 Session 自动识别开关：%s",
            "开启" if bool(new_value) else "关闭",
            extra={"session_id": self.session.session_id},
        )

    def _init_layout(self) -> None:
        """使用滚动区和无抖动卡片组排列参数设置卡片。"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.drawer_scroll_area: ScrollArea = ScrollArea(self)
        self.drawer_scroll_area.setObjectName("drawerPanelScrollArea")
        self.drawer_scroll_area.setWidgetResizable(True)

        self.drawer_scroll_widget: QWidget = QWidget()
        self.drawer_scroll_widget.setObjectName("drawerPanelContentWidget")
        self.drawer_scroll_layout: QVBoxLayout = QVBoxLayout(
            self.drawer_scroll_widget
        )
        self.drawer_scroll_layout.setContentsMargins(16, 8, 16, 16)
        self.drawer_scroll_layout.setSpacing(8)

        # ExpandLayout 统一管理展开高度，避免多张设置卡互相挤压抖动。
        self.cards_group: SettingCardGroup = SettingCardGroup(
            "额外配置项",
            self.drawer_scroll_widget
        )
        self.cards_group.addSettingCard(self.auto_recognize_card)
        self.cards_group.addSettingCard(self.model_selection_card)
        self.cards_group.addSettingCard(self.export_path_card)

        self.clustering_group.setParent(self.drawer_scroll_widget)
        self.recognition_group.setParent(self.drawer_scroll_widget)
        self.extract_cf_group.setParent(self.drawer_scroll_widget)
        self.extract_pw_group.setParent(self.drawer_scroll_widget)
        self.extract_pri_group.setParent(self.drawer_scroll_widget)
        self.merge_group.setParent(self.drawer_scroll_widget)
        # 额外配置作为最常用的 Session 入口固定在抽屉内容最顶端。
        self.drawer_scroll_layout.addWidget(self.cards_group)
        self.drawer_scroll_layout.addWidget(self.clustering_group)
        self.drawer_scroll_layout.addWidget(self.recognition_group)
        self.drawer_scroll_layout.addWidget(self.extract_cf_group)
        self.drawer_scroll_layout.addWidget(self.extract_pw_group)
        self.drawer_scroll_layout.addWidget(self.extract_pri_group)
        self.drawer_scroll_layout.addWidget(self.merge_group)
        self.drawer_scroll_layout.addStretch(1)
        self.drawer_scroll_area.setWidget(self.drawer_scroll_widget)
        root_layout.addWidget(self.drawer_scroll_area)
