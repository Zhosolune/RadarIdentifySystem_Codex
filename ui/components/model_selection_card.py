"""提供当前切片页面使用的 PA 与 DTOA 模型选择卡。"""

from __future__ import annotations

import os
from collections.abc import Mapping

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import ComboBox, ExpandGroupSettingCard, FluentIcon

from app.model_bootstrap import (
    get_display_name,
    get_enabled_model_paths,
)


class ModelSelectionCard(ExpandGroupSettingCard):
    """保存当前切片页面的 PA 与 DTOA 模型选择。

    下拉项只读取模型管理页勾选的启用模型。初始化优先恢复调用方传入的
    Session 快照，用户后续选择只保存在当前组件实例中，不会修改全局配置。

    Attributes:
        modelChanged: 模型选择变化信号，依次传递模型类型和模型路径。
        pa_model_combo: PA 模型下拉框。
        dtoa_model_combo: DTOA 模型下拉框。
    """

    modelChanged = pyqtSignal(str, object)

    def __init__(
        self,
        parent: QWidget | None = None,
        initial_model_paths: Mapping[str, str | None] | None = None,
    ) -> None:
        """创建两个模型下拉框并恢复当前 Session 模型快照。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。
            initial_model_paths [Mapping[str, str | None] | None]: 当前 Session 的 PA、DTOA 模型路径。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 扫描用户模型目录失败时抛出。

        Example:
            >>> card = ModelSelectionCard()
            >>> card.selected_model_path("PA") is None or isinstance(card.selected_model_path("PA"), str)
            True
        """
        super().__init__(
            icon=FluentIcon.ROBOT,
            title="模型选择",
            content="为当前 Session 选择 PA 与 DTOA 模型",
            parent=parent,
        )
        self.setObjectName("modelSelectionCard")
        self._model_paths: dict[str, list[str]] = {}
        self._selected_paths: dict[str, str | None] = {"PA": None, "DTOA": None}
        initial_paths = initial_model_paths or {}
        self._initial_model_paths: dict[str, str | None] = {
            "PA": initial_paths.get("PA"),
            "DTOA": initial_paths.get("DTOA"),
        }

        self.pa_model_combo: ComboBox = self._create_model_combo("PA")
        self.dtoa_model_combo: ComboBox = self._create_model_combo("DTOA")
        self.addGroup(FluentIcon.APPLICATION, "PA 模型", None, self.pa_model_combo)
        self.addGroup(FluentIcon.APPLICATION, "DTOA 模型", None, self.dtoa_model_combo)

    def selected_model_path(self, model_type: str) -> str | None:
        """返回指定模型类型在当前卡片实例中的选择路径。

        Args:
            model_type [str]: 模型类型，支持 ``PA`` 或 ``DTOA``，不区分大小写。

        Returns:
            str | None: 当前实例选中的模型文件路径；无可用模型时返回 ``None``。

        Raises:
            ValueError: 模型类型不是 ``PA`` 或 ``DTOA``。

        Example:
            >>> card = ModelSelectionCard()
            >>> card.selected_model_path("DTOA") is None or isinstance(card.selected_model_path("DTOA"), str)
            True
        """
        normalized_type = model_type.upper()
        if normalized_type not in self._selected_paths:
            raise ValueError(f"不支持的模型类型: {model_type}")
        return self._selected_paths[normalized_type]

    def _create_model_combo(self, model_type: str) -> ComboBox:
        """创建并初始化指定类型的模型下拉框。"""
        combo = ComboBox(self)
        self._reload_model_combo(
            model_type,
            combo,
            preferred_path=self._initial_model_paths[model_type],
            emit_change=False,
        )
        combo.currentIndexChanged.connect(
            lambda index, current_type=model_type: self._on_model_changed(
                current_type,
                index,
            )
        )
        return combo

    def refresh_enabled_models(self, model_type: str) -> None:
        """按最新启用列表刷新指定类型下拉框并保留 Session 当前选择。

        Args:
            model_type [str]: 发生候选集合变化的模型类型。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        normalized_type = model_type.upper()
        combo_mapping = {
            "PA": self.pa_model_combo,
            "DTOA": self.dtoa_model_combo,
        }
        combo = combo_mapping.get(normalized_type)
        if combo is None:
            return
        self._reload_model_combo(
            normalized_type,
            combo,
            preferred_path=self._selected_paths[normalized_type],
            emit_change=True,
        )

    def _reload_model_combo(
        self,
        model_type: str,
        combo: ComboBox,
        preferred_path: str | None,
        emit_change: bool,
    ) -> None:
        """重建单个模型下拉框并在必要时发布有效选择变化。"""
        previous_path = self._selected_paths[model_type]
        model_paths = get_enabled_model_paths(model_type)
        self._model_paths[model_type] = model_paths
        combo.blockSignals(True)
        combo.clear()
        combo.addItems([get_display_name(path, model_type) for path in model_paths])

        if not model_paths:
            combo.setEnabled(False)
            self._selected_paths[model_type] = None
            combo.blockSignals(False)
            if emit_change and previous_path is not None:
                self.modelChanged.emit(model_type, None)
            return

        combo.setEnabled(True)
        normalized_preferred_path = (
            os.path.normpath(preferred_path) if preferred_path else None
        )
        selected_index = (
            model_paths.index(normalized_preferred_path)
            if normalized_preferred_path in model_paths
            else 0
        )
        combo.setCurrentIndex(selected_index)
        selected_path = model_paths[selected_index]
        self._selected_paths[model_type] = selected_path
        combo.blockSignals(False)
        if emit_change and selected_path != previous_path:
            self.modelChanged.emit(model_type, selected_path)

    def _on_model_changed(self, model_type: str, index: int) -> None:
        """将下拉框变化保存到当前卡片实例。"""
        model_paths = self._model_paths[model_type]
        if not 0 <= index < len(model_paths):
            return

        selected_path = model_paths[index]
        self._selected_paths[model_type] = selected_path
        self.modelChanged.emit(model_type, selected_path)
