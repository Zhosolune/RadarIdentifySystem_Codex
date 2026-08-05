"""参数配置界面测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch
from qfluentwidgets import SettingCard, SettingCardGroup, qconfig

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.app_config import appConfig
from ui.components.recognition_strategy_setting_card import (
    RecognitionStrategySettingCard,
)
from ui.interfaces.params_interface import ParamsInterface


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _collect_group_titles(interface: ParamsInterface) -> list[str]:
    """收集参数界面中的配置卡片组标题。"""
    return [
        group.titleLabel.text()
        for group in interface.settingScrollWidget.findChildren(SettingCardGroup)
    ]


def _collect_card_titles(interface: ParamsInterface) -> list[str]:
    """收集参数界面中的配置卡片标题。"""
    return [
        card.titleLabel.text()
        for group in interface.settingScrollWidget.findChildren(SettingCardGroup)
        for card in group.findChildren(SettingCard)
    ]


def test_params_interface_replaces_extract_cards_with_cf_pw_pri_groups() -> None:
    """提取参数配置应替换为 CF、PW、PRI 三组参数卡片。"""
    _app()

    interface = ParamsInterface()
    group_titles = _collect_group_titles(interface)
    card_titles = _collect_card_titles(interface)

    assert "CF参数提取配置" in group_titles
    assert "PW参数提取配置" in group_titles
    assert "PRI参数提取配置" in group_titles
    assert "特征点提取步长" not in card_titles
    assert "平滑滤波窗口大小" not in card_titles
    assert "异常点剔除阈值" not in card_titles

    assert "CF邻域半径" in card_titles
    assert "CF最小邻居点数" in card_titles
    assert "CF门限率" in card_titles
    assert "PW邻域半径" in card_titles
    assert "PW最小邻居点数" in card_titles
    assert "PW门限率" in card_titles
    assert "PRI邻域半径" in card_titles
    assert "PRI最小邻居点数" in card_titles
    assert "PRI门限率" in card_titles
    assert "PRI过滤门限" in card_titles
    assert "PRI谐波抑制容差" in card_titles


def test_extract_parameter_defaults_are_registered() -> None:
    """提取参数默认值应注册到全局配置。"""
    assert qconfig.get(appConfig.extractEpsilonCF) == 2.0
    assert qconfig.get(appConfig.extractMinPtsCF) == 4
    assert qconfig.get(appConfig.extractThresholdRatioCF) == 10.0
    assert qconfig.get(appConfig.extractEpsilonPW) == 0.2
    assert qconfig.get(appConfig.extractMinPtsPW) == 4
    assert qconfig.get(appConfig.extractThresholdRatioPW) == 10.0
    assert qconfig.get(appConfig.extractEpsilonPRI) == 0.2
    assert qconfig.get(appConfig.extractMinPtsPRI) == 3
    assert qconfig.get(appConfig.extractThresholdRatioPRI) == 10.0
    assert qconfig.get(appConfig.extractFilterThresholdPRI) == 2.0
    assert qconfig.get(appConfig.extractHarmonicTolerancePRI) == 0.1


def test_recognition_parameter_group_uses_strategy_and_threshold_cards(
    monkeypatch: MonkeyPatch,
) -> None:
    """识别参数组应显示双侧策略标签并按策略切换严格参数可用状态。"""
    _app()
    # 测试只验证内存状态联动，避免切换全局策略时写入真实用户配置文件。
    monkeypatch.setattr(qconfig, "save", lambda: None)
    interface = ParamsInterface()
    recognize_cards = interface._recognizeGroup.findChildren(SettingCard)

    assert [card.titleLabel.text() for card in recognize_cards] == [
        "识别策略",
        "PA置信度门限",
        "PA置信度权重",
        "DTOA置信度门限",
        "DTOA置信度权重",
        "联合判别门限",
    ]
    strategy_card = recognize_cards[0]
    assert isinstance(strategy_card, RecognitionStrategySettingCard)
    assert strategy_card.strict_label.text() == "严格"
    assert strategy_card.greedy_label.text() == "贪婪"
    assert strategy_card.switchButton.label.isHidden()
    assert strategy_card.isChecked() is True
    assert all(not card.isEnabled() for card in recognize_cards[1:])

    strategy_card.setChecked(False)

    assert all(card.isEnabled() for card in recognize_cards[1:])

    # 恢复全局默认策略，避免影响同进程内后续配置测试。
    strategy_card.setChecked(True)


def test_recognition_parameter_defaults_are_registered() -> None:
    """识别参数默认值应注册到全局配置，并删除旧占位配置。"""
    assert qconfig.get(appConfig.recognizeGreedyStrategy) is True
    assert qconfig.get(appConfig.recognizePaConfidenceThreshold) == 0.5
    assert qconfig.get(appConfig.recognizePaConfidenceWeight) == 0.6
    assert qconfig.get(appConfig.recognizeDtoaConfidenceThreshold) == 0.5
    assert qconfig.get(appConfig.recognizeDtoaConfidenceWeight) == 0.4
    assert qconfig.get(appConfig.recognizeJointConfidenceThreshold) == 0.8
    assert not hasattr(appConfig, "recognizeTolerance")
    assert not hasattr(appConfig, "recognizeMinConfidence")
    assert not hasattr(appConfig, "recognizeMaxCandidates")


def test_merge_parameter_group_contains_only_one_placeholder() -> None:
    """合并参数组应只保留一个明确无业务含义的占位配置项。"""
    _app()
    interface = ParamsInterface()
    merge_cards = interface._mergeGroup.findChildren(SettingCard)

    assert [card.titleLabel.text() for card in merge_cards] == [
        "合并参数占位值"
    ]
    assert qconfig.get(appConfig.mergePlaceholderValue) == 0.0
    assert not hasattr(appConfig, "mergeTimeDecay")
    assert not hasattr(appConfig, "mergeSimThreshold")
    assert not hasattr(appConfig, "mergeMaxExtrapolate")
    assert not hasattr(appConfig, "mergePriEqualDoaTolerance")
