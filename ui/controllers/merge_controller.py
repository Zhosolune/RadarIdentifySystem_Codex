"""切片页批量合并与独立结果浏览控制器。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from runtime.workflows.merge_workflow import (
    MergeStrategy,
    MergeWorkflow,
)

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface


LOGGER = logging.getLogger(__name__)


class MergeController(QObject):
    """管理切片合并计划、批量执行、结果浏览和来源显隐。"""

    def __init__(self, view: SliceInterface) -> None:
        """初始化合并控制器。

        Args:
            view [SliceInterface]: 绑定的切片页面视图。

        Returns:
            None: 无返回值。
        """
        super().__init__(view)
        self.view = view
        self._workflow = MergeWorkflow(self)

        # 判别状态、计划分组和执行结果分开维护，空计划也要区别于尚未判别。
        self._merge_groups: tuple[tuple[int, ...], ...] = ()
        self._merge_judged: bool = False
        self._result_count = 0
        self._current_result_index = 0
        self._visible_cluster_indices: set[int] = set()
        self._connect_signals()
        self.refresh_current_slice_state(reset_index=True)

    def _connect_signals(self) -> None:
        """连接批量合并、结果导航、显隐控制和识别生命周期信号。"""
        operation_card = self.view.merge_operation_panel.operation_card
        button_bar = operation_card.button_bar
        button_bar.merge_button.clicked.connect(self._execute_merge_plan)
        button_bar.prev_cluster_button.clicked.connect(self._show_previous_result)
        button_bar.next_cluster_button.clicked.connect(self._show_next_result)
        button_bar.reset_button.clicked.connect(self._reset_merge_state)
        operation_card.category_display_card.visibility_changed.connect(
            self._on_category_visibility_changed
        )
        operation_card.global_visibility_changed.connect(
            self._on_global_visibility_changed
        )
        signal_bus.stage_started.connect(self._on_stage_started)
        signal_bus.stage_finished.connect(self._on_stage_finished)
        signal_bus.stage_failed.connect(self._on_stage_failed)

    def set_strategy(self, strategy: MergeStrategy) -> None:
        """切换后续合并判别使用的准则并失效旧计划。

        Args:
            strategy [MergeStrategy]: 新准则实例。

        Returns:
            None: 无返回值。
        """
        self._workflow.switch_strategy(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            strategy,
        )
        # 新策略实例可能仅调整了参数而保持同一ID；先失效旧计划，再由刷新流程后台重判。
        self.refresh_current_slice_state(reset_index=True)

    def refresh_current_slice_state(
        self,
        reset_index: bool = False,
    ) -> None:
        """加载当前切片派生状态，并在需要时启动后台候选判别。

        Args:
            reset_index [bool]: 是否把结果浏览位置重置到第一项。

        Returns:
            None: 无返回值。
        """
        slice_index = self.view._slice_controller.current_slice_index
        session = self.view._session
        LOGGER.debug(
            "开始刷新当前切片合并状态: slice_index=%d, reset_index=%s, "
            "is_recognized=%s",
            slice_index,
            reset_index,
            session.is_slice_recognized(slice_index),
            extra={"session_id": session.session_id},
        )
        self._merge_groups = self._workflow.get_prepared_merge_groups(
            session,
            slice_index,
        )
        self._merge_judged = self._workflow.has_prepared_merge_plan(
            session,
            slice_index,
        )
        self._result_count = self._workflow.get_result_count(
            session,
            slice_index,
        )
        slice_state = session.get_slice_processing_state(slice_index)
        LOGGER.debug(
            "已读取当前切片合并派生状态: slice_index=%d, "
            "merge_judged=%s, prepared_groups=%s, result_count=%d, "
            "merge_judgment_suppressed=%s",
            slice_index,
            self._merge_judged,
            self._merge_groups,
            self._result_count,
            slice_state.merge_judgment_suppressed,
            extra={"session_id": session.session_id},
        )

        # 当前切片完成识别但尚无计划时，在后台执行候选判别；菜单保持禁用，
        # 直到策略明确返回至少一个可合并分组。
        if (
            session.is_slice_recognized(slice_index)
            and not self._result_count
            and not self._merge_judged
            and not self._workflow.is_judging()
            and not slice_state.merge_judgment_suppressed
            and slice_state.last_merge_error is None
        ):
            self._workflow.request_merge_plan(session, slice_index)

        # 切片切换或识别完成时从第一项开始；普通刷新则尽量保留当前浏览位置。
        if reset_index:
            self._current_result_index = 0
        elif self._result_count:
            self._current_result_index = min(
                self._current_result_index,
                self._result_count - 1,
            )
        else:
            self._current_result_index = 0

        if self._result_count:
            self._present_current_result(reset_visibility=True)
        else:
            self._clear_presentation()
        self._update_controls()

    def _update_controls(self) -> None:
        """按识别、判别计划和执行结果三个状态同步全部按钮。"""
        slice_index = self.view._slice_controller.current_slice_index
        session = self.view._session
        is_recognized = session.is_slice_recognized(slice_index)
        has_results = self._result_count > 0
        merge_running = self._workflow.is_running()
        merge_judging = self._workflow.is_judging()
        has_candidates = bool(self._merge_groups)
        menu_button = self.view.right_panel.navigation_control_card.merge_menu_button
        previous_enabled = menu_button.isEnabled()
        previous_checked = menu_button.isChecked()

        # 菜单只在当前切片存在策略候选或已有结果时开放，识别完成本身不再等价于可合并。
        can_open_merge = has_candidates or has_results
        if has_results:
            activation_reason = "当前切片已有合并结果"
        elif has_candidates:
            activation_reason = "当前切片存在策略判定的可合并类"
        elif merge_judging:
            activation_reason = "当前切片正在后台判别可合并类"
        elif is_recognized:
            activation_reason = "当前切片已识别但没有可合并类"
        else:
            activation_reason = "当前切片未识别且没有合并结果"
        LOGGER.debug(
            "开始合并菜单可用性判别: slice_index=%d, "
            "规则=has_candidates OR has_results, is_recognized=%s, "
            "has_candidates=%s, has_results=%s, merge_judged=%s, "
            "prepared_group_count=%d, prepared_groups=%s, result_count=%d, "
            "merge_judging=%s, merge_running=%s, previous_enabled=%s, "
            "previous_checked=%s",
            slice_index,
            is_recognized,
            has_candidates,
            has_results,
            self._merge_judged,
            len(self._merge_groups),
            self._merge_groups,
            self._result_count,
            merge_judging,
            merge_running,
            previous_enabled,
            previous_checked,
            extra={"session_id": session.session_id},
        )
        if not can_open_merge and menu_button.isChecked():
            menu_button.setChecked(False)
        menu_button.setEnabled(can_open_merge)
        LOGGER.debug(
            "合并菜单可用性判别完成: slice_index=%d, can_open_merge=%s, "
            "activation_reason=%s, enabled=%s, checked=%s, "
            "checked_was_forced_off=%s",
            slice_index,
            can_open_merge,
            activation_reason,
            menu_button.isEnabled(),
            menu_button.isChecked(),
            previous_checked and not can_open_merge,
            extra={"session_id": session.session_id},
        )

        operation_card = self.view.merge_operation_panel.operation_card
        if has_results:
            displayed_count: int | None = self._result_count
        elif self._merge_judged and not self._merge_groups:
            # 空计划表示已经判别但没有候选；None则明确表示尚未判别。
            displayed_count = 0
        else:
            displayed_count = None
        operation_card.set_result_count(displayed_count)
        button_bar = operation_card.button_bar

        # 合并按钮只执行后台已经判定的完整计划，不在点击时重新选择来源类。
        button_bar.merge_button.setEnabled(
            has_candidates
            and not has_results
            and not merge_judging
            and not merge_running
        )
        button_bar.prev_cluster_button.setEnabled(
            has_results and not merge_running and self._current_result_index > 0
        )
        button_bar.next_cluster_button.setEnabled(
            has_results
            and not merge_running
            and self._current_result_index < self._result_count - 1
        )
        button_bar.reset_button.setEnabled(
            not merge_running and (has_results or self._merge_judged)
        )
        LOGGER.debug(
            "合并操作按钮状态同步完成: slice_index=%d, merge_enabled=%s, "
            "previous_enabled=%s, next_enabled=%s, reset_enabled=%s, "
            "displayed_result_count=%s",
            slice_index,
            button_bar.merge_button.isEnabled(),
            button_bar.prev_cluster_button.isEnabled(),
            button_bar.next_cluster_button.isEnabled(),
            button_bar.reset_button.isEnabled(),
            displayed_count,
            extra={"session_id": session.session_id},
        )

    def _execute_merge_plan(self) -> None:
        """启动当前策略的后台判别与整批合并任务。"""
        slice_index = self.view._slice_controller.current_slice_index
        if (
            self._result_count
            or self._workflow.is_running()
            or self._workflow.is_judging()
            or not self._merge_groups
            or not self.view._session.is_slice_recognized(slice_index)
        ):
            return
        # 策略判别也属于合并任务，由Worker与点云、参数、绘图计算一并执行。
        started = self._workflow.execute_merge_plan(
            self.view._session,
            slice_index,
        )
        self._update_controls()

    def _show_previous_result(self) -> None:
        """显示上一项已生成的独立合并结果。"""
        if self._current_result_index > 0:
            self._current_result_index -= 1
            self._present_current_result(reset_visibility=True)
        self._update_controls()

    def _show_next_result(self) -> None:
        """显示下一项已生成的独立合并结果。"""
        if self._current_result_index < self._result_count - 1:
            self._current_result_index += 1
            self._present_current_result(reset_visibility=True)
        self._update_controls()

    def _present_current_result(self, *, reset_visibility: bool) -> None:
        """同步当前结果的图像、类别复选框和参数表。"""
        # 切换合并结果时恢复全部来源可见；同一结果内显隐刷新则沿用当前集合。
        visible_indices = None if reset_visibility else self._visible_cluster_indices
        presentation = self._workflow.render_result(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            self._current_result_index,
            visible_indices,
        )
        if reset_visibility:
            self._visible_cluster_indices = {
                category.cluster_index for category in presentation.categories
            }

        # runtime一次返回完整呈现模型，UI不直接读取core合并结果或调用绘图层。
        self.view.merge_image_column.update_images(
            presentation.images,
            presentation.title,
        )
        self.view.merge_operation_panel.operation_card.set_categories(
            tuple(
                (category.cluster_index, category.color)
                for category in presentation.categories
            ),
            checked_indices=tuple(
                category.cluster_index
                for category in presentation.categories
                if category.visible
            ),
        )
        self.view.merge_operation_panel.result_table_card.update_rows(
            presentation.table_rows
        )

    def _on_category_visibility_changed(
        self,
        cluster_index: int,
        visible: bool,
    ) -> None:
        """根据双态复选框刷新当前图像和参数而不重新执行合并。"""
        if not self._result_count:
            return
        if visible:
            self._visible_cluster_indices.add(cluster_index)
        else:
            self._visible_cluster_indices.discard(cluster_index)

        # 只把可见簇集合交回runtime重绘并重提取参数，不修改已保存的合并结果。
        presentation = self._workflow.render_result(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            self._current_result_index,
            self._visible_cluster_indices,
        )
        self.view.merge_image_column.update_images(
            presentation.images,
            presentation.title,
        )
        self.view.merge_operation_panel.result_table_card.update_rows(
            presentation.table_rows
        )

    def _on_global_visibility_changed(self, visible: bool) -> None:
        """根据全局三态复选框一次刷新全部来源图像和参数。"""
        if not self._result_count:
            return
        category_card = (
            self.view.merge_operation_panel.operation_card.category_display_card
        )
        self._visible_cluster_indices = (
            set(category_card.category_checkboxes) if visible else set()
        )
        presentation = self._workflow.render_result(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            self._current_result_index,
            self._visible_cluster_indices,
        )
        self.view.merge_image_column.update_images(
            presentation.images,
            presentation.title,
        )
        self.view.merge_operation_panel.result_table_card.update_rows(
            presentation.table_rows
        )

    def _reset_merge_state(self) -> None:
        """清除当前切片合并计划和结果并回到未判别状态。"""
        if not self._result_count and not self._merge_judged:
            return
        # 未来合并面板提供真实参数时，应在重置成功后复制
        # ``session.config_snapshot.merge`` 形成控制器私有临时草稿；该草稿仅在
        # 当前合并面板激活周期存在，重新合并时冻结为MergeParams传给runtime，
        # 离开面板、切换切片或重新识别时销毁，且绝不写回Session快照或全局配置。
        self._workflow.reset_merge_state(
            self.view._session,
            self.view._slice_controller.current_slice_index,
        )
        self._merge_groups = ()
        self._merge_judged = False
        self._result_count = 0
        self._current_result_index = 0
        self._clear_presentation()
        # 重置后来源识别结果仍存在，立即后台重判，菜单仅在仍有候选时重新激活。
        self._workflow.request_merge_plan(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            force=True,
        )
        self._update_controls()

    def _clear_presentation(self) -> None:
        """清空当前切片的合并结果展示状态。"""
        self._visible_cluster_indices.clear()
        self.view.merge_image_column.clear_images()
        operation_card = self.view.merge_operation_panel.operation_card
        operation_card.clear_categories()
        operation_card.set_result_count(None)
        self.view.merge_operation_panel.result_table_card.clear_rows()

    def _on_stage_started(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
    ) -> None:
        """响应识别失效或合并线程启动事件。"""
        LOGGER.debug(
            "收到阶段开始事件并检查合并菜单状态: event_session_id=%s, "
            "event_stage=%s, event_slice_index=%s, current_slice_index=%d",
            session_id,
            stage,
            slice_index,
            self.view._slice_controller.current_slice_index,
            extra={"session_id": self.view._session.session_id},
        )
        if self._is_current_merge_event(session_id, stage, slice_index):
            # 工作流已持有线程引用，立即禁用合并、导航和重置按钮。
            self._update_controls()
            return
        if self._is_current_merge_judging_event(session_id, stage):
            self._update_controls()
            return
        if not self._is_current_identify_event(session_id, stage, slice_index):
            LOGGER.debug(
                "忽略阶段开始事件的合并菜单更新: event_session_id=%s, "
                "event_stage=%s, event_slice_index=%s, "
                "原因=不是当前Session当前切片的识别事件",
                session_id,
                stage,
                slice_index,
                extra={"session_id": self.view._session.session_id},
            )
            return
        self._merge_groups = ()
        self._merge_judged = False
        self._result_count = 0
        self._current_result_index = 0

        # 新识别代次开始后，旧计划和旧结果均不可继续展示或执行。
        self._clear_presentation()
        self._update_controls()

    def _on_stage_finished(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
    ) -> None:
        """响应识别完成或合并线程成功事件。"""
        current_session_id = self.view._session.session_id
        current_slice_index = self.view._slice_controller.current_slice_index
        LOGGER.debug(
            "收到阶段完成事件并开始合并菜单激活判别: event_session_id=%s, "
            "event_stage=%s, event_slice_index=%s, current_slice_index=%d",
            session_id,
            stage,
            slice_index,
            current_slice_index,
            extra={"session_id": current_session_id},
        )
        if session_id != current_session_id:
            LOGGER.debug(
                "忽略阶段完成事件的合并菜单激活判别: "
                "event_session_id=%s, 原因=事件不属于当前Session",
                session_id,
                extra={"session_id": current_session_id},
            )
            return
        if stage == "merge_judging":
            # 任一切片判别完成后刷新当前展示切片；若用户已切片，会继续为新切片发起判别。
            self.refresh_current_slice_state(reset_index=True)
            return
        if stage == "merging":
            if slice_index != current_slice_index:
                LOGGER.debug(
                    "忽略合并完成事件: event_slice_index=%s, "
                    "current_slice_index=%d, 原因=不是当前展示切片",
                    slice_index,
                    current_slice_index,
                    extra={"session_id": current_session_id},
                )
                return
            # 工作流已经完成原子写回并清理线程，主线程只重读派生状态和呈现数据。
            self.refresh_current_slice_state(reset_index=True)
            return
        if stage != "identifying":
            LOGGER.debug(
                "忽略阶段完成事件的合并菜单激活判别: event_stage=%s, "
                "原因=事件不是identifying阶段",
                stage,
                extra={"session_id": current_session_id},
            )
            return
        if slice_index is None:
            LOGGER.debug(
                "忽略阶段完成事件的合并菜单激活判别: "
                "原因=事件没有切片索引",
                extra={"session_id": current_session_id},
            )
            return
        if slice_index != current_slice_index:
            LOGGER.debug(
                "忽略阶段完成事件的合并菜单激活判别: "
                "event_slice_index=%d, current_slice_index=%d, "
                "原因=识别完成的不是当前展示切片",
                slice_index,
                current_slice_index,
                extra={"session_id": current_session_id},
            )
            return
        LOGGER.debug(
            "识别完成事件通过合并菜单激活前置校验: slice_index=%d, "
            "后续动作=读取已有计划和结果并按识别状态同步按钮",
            slice_index,
            extra={"session_id": current_session_id},
        )
        self.refresh_current_slice_state(reset_index=True)
        menu_button = (
            self.view.right_panel.navigation_control_card.merge_menu_button
        )
        LOGGER.debug(
            "识别完成后的合并菜单激活流程结束: slice_index=%d, "
            "merge_menu_enabled=%s, merge_menu_checked=%s, "
            "merge_judged=%s, prepared_groups=%s, result_count=%d",
            slice_index,
            menu_button.isEnabled(),
            menu_button.isChecked(),
            self._merge_judged,
            self._merge_groups,
            self._result_count,
            extra={"session_id": current_session_id},
        )

    def _on_stage_failed(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
        _error_message: str,
    ) -> None:
        """响应识别失败或合并线程失败事件。"""
        LOGGER.debug(
            "收到阶段失败事件并检查合并菜单状态: event_session_id=%s, "
            "event_stage=%s, event_slice_index=%s, error=%s",
            session_id,
            stage,
            slice_index,
            _error_message,
            extra={"session_id": self.view._session.session_id},
        )
        if self._is_current_merge_event(session_id, stage, slice_index):
            # 失败结果已由工作流记录；刷新后允许用户调整策略或重试。
            self.refresh_current_slice_state()
            return
        if self._is_current_merge_judging_event(session_id, stage):
            self.refresh_current_slice_state()
            return
        if not self._is_current_identify_event(session_id, stage, slice_index):
            LOGGER.debug(
                "忽略阶段失败事件的合并菜单更新: 原因=不是当前Session当前切片的识别事件",
                extra={"session_id": self.view._session.session_id},
            )
            return
        self._merge_groups = ()
        self._merge_judged = False
        self._result_count = 0
        self._current_result_index = 0
        self._clear_presentation()
        self._update_controls()

    def _is_current_identify_event(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
    ) -> bool:
        """判断生命周期事件是否属于当前会话和切片。"""
        return (
            session_id == self.view._session.session_id
            and stage == "identifying"
            and slice_index == self.view._slice_controller.current_slice_index
        )

    def _is_current_merge_event(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
    ) -> bool:
        """判断生命周期事件是否属于当前会话和切片的合并任务。"""
        return (
            session_id == self.view._session.session_id
            and stage == "merging"
            and slice_index == self.view._slice_controller.current_slice_index
        )

    def _is_current_merge_judging_event(
        self,
        session_id: str,
        stage: str,
    ) -> bool:
        """判断生命周期事件是否属于当前会话的合并候选判别。"""
        return (
            session_id == self.view._session.session_id
            and stage == "merge_judging"
        )
