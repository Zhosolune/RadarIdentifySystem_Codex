"""切片页合并流程控制器。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject

from core.merge import MergeTarget
from runtime.workflows.merge_workflow import MergeWorkflow, MergeWorkflowResult

if TYPE_CHECKING:
    from ui.interfaces.slice_interface import SliceInterface


class MergeController(QObject):
    """把明确的来源簇目标接入合并工作流和图像列。

    本控制器不判断哪些类应该合并。后续人工选择或合并准则只需调用
    ``merge_clusters()``，无需了解参数提取、session 写回和绘图细节。

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
        target = MergeTarget(
            slice_index=self.view._slice_controller.current_slice_index,
            cluster_indices=tuple(int(index) for index in cluster_indices),
        )
        execution = self._workflow.start_merge(self.view._session, target)
        if (
            execution.success
            and execution.merge_result is not None
            and execution.rendered_bundle is not None
        ):
            self.view.merge_image_column.update_from_merge(
                execution.rendered_bundle,
                execution.merge_result,
            )
        return execution
