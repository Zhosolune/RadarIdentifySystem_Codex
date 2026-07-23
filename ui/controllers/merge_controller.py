"""切片页合并流程控制器。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from runtime.workflows.merge_workflow import (
    MergeStrategy,
    MergeWorkflow,
    MergeWorkflowResult,
)

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface


class MergeController(QObject):
    """管理当前切片的规则候选状态并接入合并工作流。

    本控制器只保存可重算的界面候选与浏览索引，不判断业务准则，也不把候选
    写入session。规则计算、目标构造、参数重提取和结果写回均由runtime/core完成。

    Attributes:
        view [SliceInterface]: 当前切片页面视图。
    """

    def __init__(self, view: SliceInterface) -> None:
        """初始化当前 session 的合并控制器。

        Args:
            view [SliceInterface]: 绑定的切片页面视图。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(view)
        self.view = view
        self._workflow = MergeWorkflow(self)
        self._merge_candidates: tuple[tuple[int, ...], ...] = ()
        self._current_candidate_index = 0
        self._connect_signals()
        self.refresh_current_slice_state(reset_index=True)

    def _connect_signals(self) -> None:
        """连接合并操作按钮和识别生命周期信号。"""
        button_bar = self.view.merge_operation_panel.operation_card.button_bar
        button_bar.merge_button.clicked.connect(self._merge_current_candidate)
        button_bar.prev_cluster_button.clicked.connect(self._show_previous_candidate)
        button_bar.next_cluster_button.clicked.connect(self._show_next_candidate)
        button_bar.reset_button.clicked.connect(
            lambda: self.refresh_current_slice_state(reset_index=True)
        )
        signal_bus.stage_started.connect(self._on_stage_started)
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)

    def set_strategy(self, strategy: MergeStrategy) -> None:
        """切换当前页面后续候选计算使用的合并准则。

        Args:
            strategy [MergeStrategy]: 由runtime暴露的可插拔合并准则实现。

        Returns:
            None: 无返回值。

        Raises:
            TypeError: 准则未实现规定接口时由workflow抛出。

        Example:
            该入口供应用装配层或后续策略选择功能调用：

            >>> hasattr(MergeController, "set_strategy")
            True
        """
        self._workflow.set_strategy(strategy)
        self.refresh_current_slice_state(reset_index=True)

    def refresh_current_slice_state(self, reset_index: bool = False) -> None:
        """重算当前切片候选并同步菜单及操作按钮状态。

        Args:
            reset_index [bool]: 是否把候选浏览位置重置到第一组。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        slice_index = self.view._slice_controller.current_slice_index
        self._merge_candidates = self._workflow.find_merge_candidates(
            self.view._session,
            slice_index,
        )
        if reset_index:
            self._current_candidate_index = 0
        elif self._merge_candidates:
            self._current_candidate_index = min(
                self._current_candidate_index,
                len(self._merge_candidates) - 1,
            )
        else:
            self._current_candidate_index = 0
        self._update_controls()

    def _update_controls(self) -> None:
        """根据候选数量和当前位置同步全部合并控制按钮。"""
        has_candidates = bool(self._merge_candidates)
        menu_button = self.view.right_panel.navigation_control_card.merge_menu_button
        # 先取消勾选再禁用，确保横向工作区同步退出合并浏览模式。
        if not has_candidates and menu_button.isChecked():
            menu_button.setChecked(False)
        menu_button.setEnabled(has_candidates)

        button_bar = self.view.merge_operation_panel.operation_card.button_bar
        button_bar.merge_button.setEnabled(has_candidates)
        button_bar.prev_cluster_button.setEnabled(
            has_candidates and self._current_candidate_index > 0
        )
        button_bar.next_cluster_button.setEnabled(
            has_candidates
            and self._current_candidate_index < len(self._merge_candidates) - 1
        )
        button_bar.reset_button.setEnabled(has_candidates)

    def _show_previous_candidate(self) -> None:
        """切换到上一组合并候选。"""
        if self._current_candidate_index > 0:
            self._current_candidate_index -= 1
        self._update_controls()

    def _show_next_candidate(self) -> None:
        """切换到下一组合并候选。"""
        if self._current_candidate_index < len(self._merge_candidates) - 1:
            self._current_candidate_index += 1
        self._update_controls()

    def _merge_current_candidate(self) -> None:
        """执行当前浏览位置对应的规则候选组。"""
        if not self._merge_candidates:
            return
        target_indices = self._merge_candidates[self._current_candidate_index]
        execution = self._workflow.start_strategy_merge_by_indices(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            target_indices,
        )
        self._present_execution(execution)
        if execution.success:
            self.refresh_current_slice_state(reset_index=False)

    def _present_execution(self, execution: MergeWorkflowResult) -> None:
        """把成功执行的合并图像和领域结果交给视图。"""
        if (
            execution.success
            and execution.merge_result is not None
            and execution.rendered_bundle is not None
        ):
            self.view.merge_image_column.update_from_merge(
                execution.rendered_bundle,
                execution.merge_result,
            )

    def _on_stage_started(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
    ) -> None:
        """识别开始时立即失效目标切片的旧候选状态。"""
        if (
            session_id != self.view._session.session_id
            or stage != "identifying"
            or slice_index != self.view._slice_controller.current_slice_index
        ):
            return
        self._merge_candidates = ()
        self._current_candidate_index = 0
        self._update_controls()

    def _on_stage_finished(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
    ) -> None:
        """识别完成后重算当前切片的可合并候选。"""
        if (
            session_id != self.view._session.session_id
            or stage != "identifying"
            or slice_index != self.view._slice_controller.current_slice_index
        ):
            return
        self.refresh_current_slice_state(reset_index=True)

    def _on_stage_failed(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
        _error_message: str,
    ) -> None:
        """识别失败时保持目标切片合并菜单禁用。"""
        if (
            session_id != self.view._session.session_id
            or stage != "identifying"
            or slice_index != self.view._slice_controller.current_slice_index
        ):
            return
        self._merge_candidates = ()
        self._current_candidate_index = 0
        self._update_controls()

    def merge_clusters(
        self,
        cluster_indices: Iterable[int],
    ) -> MergeWorkflowResult:
        """合并当前切片中上层明确指定的识别类。

        Args:
            cluster_indices [Iterable[int]]: 来源簇编号，迭代顺序决定多颜色绘图顺序。

        Returns:
            MergeWorkflowResult: 合并、参数提取和绘图的完整执行结果。

        Raises:
            ValueError: 来源少于两个、包含重复编号或编号结构非法时抛出。

        Example:
            该入口由后续人工选择或合并准则调用：

            >>> hasattr(MergeController, "merge_clusters")
            True
        """
        execution = self._workflow.start_merge_by_indices(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            cluster_indices,
        )
        self._present_execution(execution)
        return execution
