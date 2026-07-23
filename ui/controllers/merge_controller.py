"""切片页批量合并与独立结果浏览控制器。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject

from app.signal_bus import signal_bus
from runtime.workflows.merge_workflow import (
    MergeBatchWorkflowResult,
    MergeStrategy,
    MergeWorkflow,
    MergeWorkflowResult,
)

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface


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

        # 计划分组与执行结果是两套状态：有计划时允许执行，有结果时允许浏览。
        self._merge_groups: tuple[tuple[int, ...], ...] = ()
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
        """切换后续合并判别使用的准则并重新生成计划。

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
        # 切换策略会失效旧派生数据，当前切片随后立即按新策略重新判别。
        self.refresh_current_slice_state(
            reset_index=True,
            force_plan=True,
        )

    def refresh_current_slice_state(
        self,
        reset_index: bool = False,
        force_plan: bool = False,
    ) -> None:
        """加载当前切片计划和已有独立合并结果。

        Args:
            reset_index [bool]: 是否把结果浏览位置重置到第一项。
            force_plan [bool]: 是否强制重新执行合并判别。

        Returns:
            None: 无返回值。
        """
        slice_index = self.view._slice_controller.current_slice_index
        self._merge_groups = self._workflow.get_merge_groups(
            self.view._session,
            slice_index,
            force=force_plan,
        )
        self._result_count = self._workflow.get_result_count(
            self.view._session,
            slice_index,
        )

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
        """按计划与结果两个独立状态同步全部按钮。"""
        has_plan = bool(self._merge_groups)
        has_results = self._result_count > 0
        menu_button = self.view.right_panel.navigation_control_card.merge_menu_button

        # 合并菜单默认禁用；当前切片存在可执行计划或已有合并结果时才可进入C+D。
        can_open_merge = has_plan or has_results
        if not can_open_merge and menu_button.isChecked():
            menu_button.setChecked(False)
        menu_button.setEnabled(can_open_merge)

        operation_card = self.view.merge_operation_panel.operation_card
        operation_card.set_result_count(
            self._result_count if has_results else None
        )
        button_bar = operation_card.button_bar

        # 完整计划只执行一次；结果导航按钮依据当前浏览位置分别控制。
        button_bar.merge_button.setEnabled(has_plan and not has_results)
        button_bar.prev_cluster_button.setEnabled(
            has_results and self._current_result_index > 0
        )
        button_bar.next_cluster_button.setEnabled(
            has_results
            and self._current_result_index < self._result_count - 1
        )
        button_bar.reset_button.setEnabled(has_results)

    def _execute_merge_plan(self) -> None:
        """一次执行当前切片完整计划中的全部合并分组。"""
        if not self._merge_groups or self._result_count:
            return
        execution = self._workflow.execute_merge_plan(
            self.view._session,
            self.view._slice_controller.current_slice_index,
        )
        self._present_batch_execution(execution)

    def _present_batch_execution(
        self,
        execution: MergeBatchWorkflowResult,
    ) -> None:
        """在整批成功后默认显示第一项结果并保持C+D。"""
        if not execution.success:
            self._update_controls()
            return

        # 批量工作流已一次生成全部结果，界面默认呈现第一组且不退出C+D。
        self._result_count = execution.result_count
        self._current_result_index = 0
        self._present_current_result(reset_visibility=True)
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
        """根据双态复选框重新绘制当前结果而不重新执行合并。"""
        if not self._result_count:
            return
        if visible:
            self._visible_cluster_indices.add(cluster_index)
        else:
            self._visible_cluster_indices.discard(cluster_index)

        # 只把可见簇集合交回runtime重绘，不修改已保存的合并点云和识别结果。
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

    def _on_global_visibility_changed(self, visible: bool) -> None:
        """根据全局三态复选框一次重绘全部来源类别。"""
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

    def _reset_merge_state(self) -> None:
        """清除当前切片合并计划和结果并回到未判别状态。"""
        if not self._result_count:
            return
        self._workflow.reset_merge_state(
            self.view._session,
            self.view._slice_controller.current_slice_index,
        )
        self._merge_groups = ()
        self._result_count = 0
        self._current_result_index = 0
        self._clear_presentation()
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
        """重新识别开始时失效当前切片旧计划和旧展示。"""
        if not self._is_current_identify_event(session_id, stage, slice_index):
            return
        self._merge_groups = ()
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
        """识别完成后立即判别完整合并计划。"""
        if (
            session_id != self.view._session.session_id
            or stage != "identifying"
            or slice_index is None
        ):
            return
        # 即使用户已切换到其它切片，也先为本次完成的切片保存判别计划；
        # 用户稍后返回该切片时无需重新识别或临时等待判别。
        self._workflow.prepare_merge_plan(
            self.view._session,
            slice_index,
            force=True,
        )
        if slice_index != self.view._slice_controller.current_slice_index:
            return
        self.refresh_current_slice_state(
            reset_index=True,
            force_plan=False,
        )

    def _on_stage_failed(
        self,
        session_id: str,
        stage: str,
        slice_index: int | None,
        _error_message: str,
    ) -> None:
        """识别失败时保持当前切片合并入口禁用。"""
        if not self._is_current_identify_event(session_id, stage, slice_index):
            return
        self._merge_groups = ()
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

    def merge_clusters(
        self,
        cluster_indices: Iterable[int],
    ) -> MergeWorkflowResult:
        """兼容上层人工指定来源簇的单组合并入口。

        Args:
            cluster_indices [Iterable[int]]: 原识别类簇编号。

        Returns:
            MergeWorkflowResult: 单组合并结果。
        """
        execution = self._workflow.start_merge_by_indices(
            self.view._session,
            self.view._slice_controller.current_slice_index,
            cluster_indices,
        )
        if execution.success:
            self._result_count = self._workflow.get_result_count(
                self.view._session,
                self.view._slice_controller.current_slice_index,
            )
            self._current_result_index = max(0, self._result_count - 1)
            self._present_current_result(reset_visibility=True)
            self._update_controls()
        return execution
