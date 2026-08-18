"""全速处理 Session 注册器。

注册器只维护全速 Session、配置冻结边界和可展示的执行状态。实际线程调度
由 ``runtime.workflows.full_speed_workflow`` 负责，避免注册表直接依赖 Qt。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
import threading

from core.models.processing_session import (
    ProcessingMode,
    ProcessingSession,
    ProcessingStage,
)
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from infra.session_store import SessionStore
from runtime.session_registry import SessionRegistry
from utils.paths import get_full_speed_session_dir


class FullSpeedStatus(Enum):
    """全速 Session 执行状态。"""

    CONFIGURING = "configuring"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESTARTING = "restarting"
    CANCELLING = "cancelling"
    EXPORTING = "exporting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(slots=True)
class FullSpeedExecutionState:
    """全速 Session 的运行期状态。

    Attributes:
        status: 当前执行状态。
        current_stage: 当前子阶段名称。
        current_slice: 当前处理的 1-based 切片序号。
        total_slices: 切片总数。
        progress: 总进度，范围 0 到 100。
        message: 面向用户的状态说明或错误信息。
        output_dir: 配置中的保存目录。
        output_file: 成功写出的结果文件。
        restart_required: 暂停后设置已改变、必须从头重新执行时为 True。
    """

    status: FullSpeedStatus = FullSpeedStatus.CONFIGURING
    current_stage: str = "等待启动"
    current_slice: int = 0
    total_slices: int = 0
    progress: int = 0
    message: str = "启动时将冻结当前 Session 参数和模型选择"
    output_dir: str = ""
    output_file: str = ""
    restart_required: bool = False


class FullSpeedSessionRegistry:
    """维护独立于交互式 Session 的全速 Session 及执行状态。

    Attributes:
        session_registry: 复用 Session 元数据与配置持久化能力的内部注册器。
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        """初始化全速 Session 注册器。

        Args:
            root_dir [Path | None]: 自定义持久化目录，默认使用
                ``data/sessions/full_speed``。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 持久化目录创建失败时抛出。
        """
        store = SessionStore(root_dir or get_full_speed_session_dir())
        self.session_registry = SessionRegistry(store)
        self._states: dict[str, FullSpeedExecutionState] = {}
        self._lock = threading.RLock()

    def register(self, session: ProcessingSession) -> ProcessingSession:
        """注册一个处于配置状态的全速 Session。

        Args:
            session [ProcessingSession]: 处理模式必须为 FULL_SPEED 的 Session。

        Returns:
            ProcessingSession: 已注册的原 Session。

        Raises:
            ValueError: Session 模式错误时抛出。
            OSError: 持久化失败时抛出。
        """
        if session.processing_mode is not ProcessingMode.FULL_SPEED:
            raise ValueError("全速注册器只接受 FULL_SPEED Session")
        with self._lock:
            self.session_registry.register(session, activate=False)
            self._states[session.session_id] = FullSpeedExecutionState(
                output_dir=session.config_snapshot.business.export_dir_path,
            )
            return session

    def restore(self) -> list[ProcessingSession]:
        """恢复全速 Session，并根据持久化锁定状态重建卡片状态。

        Returns:
            list[ProcessingSession]: 已恢复的全速 Session。
        """
        with self._lock:
            sessions = [
                session
                for session in self.session_registry.restore()
                if session.processing_mode is ProcessingMode.FULL_SPEED
            ]
            self._states = {
                session.session_id: self._build_restored_state(session)
                for session in sessions
            }
            return sessions

    def all_sessions(self) -> list[ProcessingSession]:
        """返回全部全速 Session。

        Returns:
            list[ProcessingSession]: 注册顺序列表。
        """
        return self.session_registry.all_sessions()

    def get(self, session_id: str) -> ProcessingSession | None:
        """按 ID 获取全速 Session。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            ProcessingSession | None: 找到的 Session，不存在时返回 None。
        """
        return self.session_registry.get(session_id)

    def state(self, session_id: str) -> FullSpeedExecutionState | None:
        """按 Session ID 获取不可变视角的运行期状态。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            FullSpeedExecutionState | None: 状态副本，不存在时返回 None。
        """
        with self._lock:
            state = self._states.get(session_id)
            return None if state is None else replace(state)

    def set_output_dir(self, session_id: str, output_dir: str) -> None:
        """在任务首次启动前更新独立保存目录。

        Args:
            session_id [str]: 目标 Session ID。
            output_dir [str]: 用户选择的本地目录。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 不存在时抛出。
            RuntimeError: 配置已冻结时抛出。
            ValueError: 保存目录为空时抛出。
            OSError: Session 配置持久化失败时抛出。
        """
        normalized = output_dir.strip()
        if not normalized:
            raise ValueError("保存目录不能为空")
        with self._lock:
            session = self._require_session(session_id)
            state = self._require_state(session_id)
            self._ensure_settings_editable(
                session,
                state,
                "全速任务参数已冻结，不能修改保存目录",
            )
            previous_output_dir = (
                session.config_snapshot.business.export_dir_path
            )
            session.config_snapshot.business.export_dir_path = normalized
            try:
                self.session_registry.persist_session(session_id)
            except Exception:
                session.config_snapshot.business.export_dir_path = (
                    previous_output_dir
                )
                raise
            state.output_dir = normalized
            self._mark_restart_required(state)

    def set_config_snapshot(
        self,
        session_id: str,
        snapshot: SessionConfigSnapshot,
    ) -> None:
        """在首次启动前更新全速 Session 的算法参数快照。

        参数窗口只负责聚类、识别、提取和合并参数。保存目录等业务配置及
        绘图配置继续沿用 Session 当前值，避免编辑窗口打开期间修改保存目录
        后又被旧草稿覆盖。

        Args:
            session_id [str]: 目标 Session ID。
            snapshot [SessionConfigSnapshot]: 参数窗口提交的完整草稿快照。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 不存在时抛出。
            RuntimeError: 参数已经冻结时抛出。
            OSError: Session 配置持久化失败时抛出。
        """
        submitted = SessionConfigSnapshot.from_dict(snapshot.to_dict())
        with self._lock:
            session = self._require_session(session_id)
            state = self._require_state(session_id)
            self._ensure_settings_editable(
                session,
                state,
                "全速任务参数已冻结，不能修改参数",
            )

            current = session.config_snapshot
            current_copy = SessionConfigSnapshot.from_dict(current.to_dict())
            submitted.business = current_copy.business
            submitted.plot = current_copy.plot
            session.config_snapshot = submitted
            try:
                self.session_registry.persist_session(session_id)
            except Exception:
                # 持久化失败时恢复原对象，避免内存状态与磁盘记录不一致。
                session.config_snapshot = current
                raise
            self._mark_restart_required(state)

    def set_settings(
        self,
        session_id: str,
        snapshot: SessionConfigSnapshot,
        model_selection: SessionModelSelection,
    ) -> None:
        """原子保存未冻结全速 Session 的参数与模型选择。

        参数窗口只编辑算法参数和模型选择。业务配置及绘图配置继续沿用
        Session 当前值，避免窗口打开期间其它入口的修改被旧草稿覆盖。

        Args:
            session_id [str]: 目标 Session ID。
            snapshot [SessionConfigSnapshot]: 参数窗口提交的配置草稿。
            model_selection [SessionModelSelection]: 参数窗口提交的 PA/DTOA 模型草稿。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 不存在时抛出。
            RuntimeError: 参数和模型已经冻结时抛出。
            ValueError: PA 或 DTOA 模型没有有效选择时抛出。
            OSError: Session 配置持久化失败时抛出。
        """
        submitted_snapshot = SessionConfigSnapshot.from_dict(
            snapshot.to_dict()
        )
        submitted_selection = SessionModelSelection.from_dict(
            model_selection.to_dict()
        )
        if not submitted_selection.pa_model_path:
            raise ValueError("请选择 PA 模型")
        if not submitted_selection.dtoa_model_path:
            raise ValueError("请选择 DTOA 模型")

        with self._lock:
            session = self._require_session(session_id)
            state = self._require_state(session_id)
            self._ensure_settings_editable(
                session,
                state,
                "全速任务参数与模型已冻结，不能修改设置",
            )

            current_snapshot = session.config_snapshot
            current_selection = session.model_selection
            current_copy = SessionConfigSnapshot.from_dict(
                current_snapshot.to_dict()
            )
            submitted_snapshot.business = current_copy.business
            submitted_snapshot.plot = current_copy.plot
            session.config_snapshot = submitted_snapshot
            session.model_selection = submitted_selection
            try:
                self.session_registry.persist_session(session_id)
            except Exception:
                # 参数与模型必须同时回滚，避免内存状态与持久化状态不一致。
                session.config_snapshot = current_snapshot
                session.model_selection = current_selection
                raise
            self._mark_restart_required(state)

    def begin(self, session_id: str) -> ProcessingSession:
        """冻结配置并把任务切换为运行状态。

        开始时会持久化 ``full_speed_locked``。失败或中断后的重试继续使用
        冻结快照；暂停现场不能通过本入口重复启动。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            ProcessingSession: 已锁定的 Session。

        Raises:
            KeyError: Session 不存在时抛出。
            RuntimeError: 任务正在执行或已经成功时抛出。
            ValueError: 保存目录未配置时抛出。
            OSError: 锁定状态持久化失败时抛出。
        """
        with self._lock:
            session = self._require_session(session_id)
            state = self._require_state(session_id)
            if state.status in {
                FullSpeedStatus.RUNNING,
                FullSpeedStatus.PAUSING,
                FullSpeedStatus.PAUSED,
                FullSpeedStatus.RESTARTING,
                FullSpeedStatus.CANCELLING,
                FullSpeedStatus.EXPORTING,
            }:
                raise RuntimeError("全速任务正在执行")
            if state.status is FullSpeedStatus.SUCCEEDED:
                raise RuntimeError("全速任务已经完成，不能重复启动")
            output_dir = session.config_snapshot.business.export_dir_path.strip()
            if not output_dir:
                raise ValueError("请先设置 Excel 保存目录")

            if not session.full_speed_locked:
                session.full_speed_locked = True
                self.session_registry.persist_session(session_id)

            self._states[session_id] = FullSpeedExecutionState(
                status=FullSpeedStatus.RUNNING,
                current_stage="准备执行",
                progress=0,
                message="参数与模型已冻结",
                output_dir=output_dir,
            )
            return session

    def update_progress(
        self,
        session_id: str,
        *,
        current_stage: str,
        current_slice: int,
        total_slices: int,
        progress: int,
        message: str,
        exporting: bool = False,
    ) -> None:
        """更新运行中任务的可展示进度。

        Args:
            session_id [str]: 目标 Session ID。
            current_stage [str]: 当前阶段名称。
            current_slice [int]: 当前 1-based 切片序号。
            total_slices [int]: 切片总数。
            progress [int]: 总进度百分比。
            message [str]: 状态说明。
            exporting [bool]: 是否正在保存 Excel。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 或状态不存在时抛出。
            RuntimeError: 任务不在可更新的执行状态时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status in {
                FullSpeedStatus.PAUSING,
                FullSpeedStatus.PAUSED,
                FullSpeedStatus.RESTARTING,
                FullSpeedStatus.CANCELLING,
            }:
                # 暂停请求发出后忽略已排队的旧进度，不能覆盖暂停状态。
                return
            if state.status not in {
                FullSpeedStatus.RUNNING,
                FullSpeedStatus.EXPORTING,
            }:
                raise RuntimeError("当前全速任务不在执行状态")
            state.status = (
                FullSpeedStatus.EXPORTING
                if exporting
                else FullSpeedStatus.RUNNING
            )
            state.current_stage = current_stage
            state.current_slice = max(0, int(current_slice))
            state.total_slices = max(0, int(total_slices))
            state.progress = max(0, min(100, int(progress)))
            state.message = message

    def mark_pausing(self, session_id: str) -> None:
        """记录任务正在等待安全检查点暂停。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
            RuntimeError: 任务当前不在可暂停的运行状态时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status is not FullSpeedStatus.RUNNING:
                raise RuntimeError("当前全速任务不在可暂停状态")
            state.status = FullSpeedStatus.PAUSING
            state.current_stage = "正在暂停"
            state.message = "正在等待当前切片完整处理后暂停"

    def mark_paused(self, session_id: str) -> None:
        """记录 Worker 已经进入安全暂停等待。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
            RuntimeError: 任务没有处于暂停请求状态时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status is not FullSpeedStatus.PAUSING:
                raise RuntimeError("当前全速任务没有等待暂停")
            state.status = FullSpeedStatus.PAUSED
            state.current_stage = "已暂停"
            state.message = "可继续当前处理，或修改设置后重新执行"

    def mark_resumed(self, session_id: str) -> None:
        """把未修改设置的暂停任务恢复为运行状态。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
            RuntimeError: 任务未暂停或设置已改变时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status is not FullSpeedStatus.PAUSED:
                raise RuntimeError("当前全速任务不在暂停状态")
            if state.restart_required:
                raise RuntimeError("设置已修改，请重新执行")
            state.status = FullSpeedStatus.RUNNING
            state.current_stage = "继续执行"
            state.message = "正在使用暂停前的参数继续处理"

    def prepare_restart(self, session_id: str) -> None:
        """在旧暂停 Worker 退出后把任务准备为从头重新执行。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
            RuntimeError: 任务当前没有处于重新执行准备状态时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status is not FullSpeedStatus.RESTARTING:
                raise RuntimeError("当前全速任务不在可重新执行状态")
            state.status = FullSpeedStatus.INTERRUPTED
            state.current_stage = "准备重新执行"
            state.current_slice = 0
            state.total_slices = 0
            state.progress = 0
            state.message = "正在使用当前设置从第一个切片重新执行"
            state.output_file = ""
            state.restart_required = False

    def mark_restarting(self, session_id: str) -> None:
        """锁定暂停任务的交互入口并等待旧 Worker 退出。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
            RuntimeError: 任务当前不是已暂停状态时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status is not FullSpeedStatus.PAUSED:
                raise RuntimeError("当前全速任务不在可重新执行状态")
            state.status = FullSpeedStatus.RESTARTING
            state.current_stage = "正在重新执行"
            state.message = "正在清理暂停现场，随后将从第一个切片开始"

    def mark_cancelling(self, session_id: str) -> None:
        """锁定暂停任务入口并等待 Worker 安全取消。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
            RuntimeError: 任务当前不是已暂停状态时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status not in {
                FullSpeedStatus.PAUSING,
                FullSpeedStatus.PAUSED,
            }:
                raise RuntimeError("当前全速任务不在可取消状态")
            state.status = FullSpeedStatus.CANCELLING
            state.current_stage = "正在取消"
            state.message = "正在终止暂停现场并清理本次运行结果"

    def mark_succeeded(self, session_id: str, output_file: str) -> None:
        """记录成功状态并持久化输出文件。

        Args:
            session_id [str]: 目标 Session ID。
            output_file [str]: 已生成的 Excel 文件路径。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 不存在时抛出。
            OSError: Session 持久化失败时抛出。
        """
        with self._lock:
            session = self._require_session(session_id)
            state = self._require_state(session_id)
            session.stage = ProcessingStage.EXPORTED
            session.exported_file_path = output_file
            self.session_registry.persist_session(session_id)
            state.status = FullSpeedStatus.SUCCEEDED
            state.current_stage = "处理完成"
            state.progress = 100
            state.message = "结果已保存为 Excel"
            state.output_file = output_file

    def mark_failed(self, session_id: str, message: str) -> None:
        """记录任务失败状态。

        Args:
            session_id [str]: 目标 Session ID。
            message [str]: 面向用户的失败原因。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            state.status = FullSpeedStatus.FAILED
            state.current_stage = "处理失败"
            state.message = message

    def mark_interrupted(self, session_id: str) -> None:
        """记录软件停机等内部终止产生的中断状态。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 状态不存在时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            state.status = FullSpeedStatus.INTERRUPTED
            state.current_stage = "执行已中断"
            state.message = "任务已在安全检查点停止，可按冻结参数重试"

    def delete(self, session_id: str) -> None:
        """删除非运行中的全速 Session 及其元数据。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            RuntimeError: 任务正在执行时抛出。
            KeyError: Session 不存在时抛出。
            OSError: 持久化删除失败时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status in {
                FullSpeedStatus.RUNNING,
                FullSpeedStatus.PAUSING,
                FullSpeedStatus.PAUSED,
                FullSpeedStatus.RESTARTING,
                FullSpeedStatus.CANCELLING,
                FullSpeedStatus.EXPORTING,
            }:
                raise RuntimeError("全速任务执行期间不能删除")
            self.session_registry.close(session_id, delete_persisted=True)
            self._states.pop(session_id, None)

    def finalize_cancel(self, session_id: str) -> None:
        """在暂停 Worker 已退出后恢复任务初始状态。

        保留任务元数据、关联数据包、参数、模型选择和保存目录；清理本次运行
        的切片及下游结果，解除执行快照冻结，并清空结果文件引用。磁盘上已经
        生成的 Excel 文件不由本入口删除。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 或状态不存在时抛出。
            RuntimeError: 任务没有处于正在取消状态时抛出。
            OSError: 初始状态持久化失败时抛出。
        """
        with self._lock:
            state = self._require_state(session_id)
            if state.status is not FullSpeedStatus.CANCELLING:
                raise RuntimeError("当前全速任务没有等待安全取消")
            session = self._require_session(session_id)

            # 保留引用以便持久化失败时完整恢复内存状态。
            previous_stage = session.stage
            previous_slice_result = session.slice_result
            previous_cluster_result = session.cluster_result
            previous_slice_states = session.slice_processing_states
            previous_recognition_result = session.recognition_result
            previous_merge_plan = session.merge_plan
            previous_merge_result = session.merge_result
            previous_locked = session.full_speed_locked
            previous_exported_file = session.exported_file_path

            session.reset_to_preprocessed_state()
            session.full_speed_locked = False
            session.exported_file_path = ""
            try:
                self.session_registry.persist_session(session_id)
            except Exception:
                session.stage = previous_stage
                session.slice_result = previous_slice_result
                session.cluster_result = previous_cluster_result
                session.slice_processing_states = previous_slice_states
                session.recognition_result = previous_recognition_result
                session.merge_plan = previous_merge_plan
                session.merge_result = previous_merge_result
                session.full_speed_locked = previous_locked
                session.exported_file_path = previous_exported_file
                raise

            self._states[session_id] = FullSpeedExecutionState(
                output_dir=(
                    session.config_snapshot.business.export_dir_path
                ),
            )

    def referenced_package_ids(self) -> set[str]:
        """返回全速 Session 当前引用的全部数据包 ID。

        Returns:
            set[str]: 被引用的数据包 ID 集合。
        """
        return {
            session.data_package_id
            for session in self.all_sessions()
            if session.data_package_id is not None
        }

    @staticmethod
    def _ensure_settings_editable(
        session: ProcessingSession,
        state: FullSpeedExecutionState,
        frozen_message: str,
    ) -> None:
        """校验配置入口当前可编辑，暂停状态允许覆盖待重启配置。"""
        if (
            session.full_speed_locked
            and state.status is not FullSpeedStatus.PAUSED
        ):
            raise RuntimeError(frozen_message)

    @staticmethod
    def _mark_restart_required(state: FullSpeedExecutionState) -> None:
        """暂停时记录设置变更，阻止旧 Worker 携带旧快照继续。"""
        if state.status is FullSpeedStatus.PAUSED:
            state.restart_required = True
            state.message = "设置已修改，请从第一个切片重新执行"

    def _require_session(self, session_id: str) -> ProcessingSession:
        """读取必需 Session，不存在时抛出。"""
        session = self.session_registry.get(session_id)
        if session is None:
            raise KeyError(f"全速 Session 不存在: {session_id}")
        return session

    def _require_state(self, session_id: str) -> FullSpeedExecutionState:
        """读取必需执行状态，不存在时抛出。"""
        state = self._states.get(session_id)
        if state is None:
            raise KeyError(f"全速 Session 状态不存在: {session_id}")
        return state

    @staticmethod
    def _build_restored_state(
        session: ProcessingSession,
    ) -> FullSpeedExecutionState:
        """根据持久化 Session 构造启动后的卡片状态。"""
        output_dir = session.config_snapshot.business.export_dir_path
        if (
            session.full_speed_locked
            and session.stage is ProcessingStage.EXPORTED
            and session.exported_file_path
            and Path(session.exported_file_path).is_file()
        ):
            return FullSpeedExecutionState(
                status=FullSpeedStatus.SUCCEEDED,
                current_stage="处理完成",
                progress=100,
                message="结果已保存为 Excel",
                output_dir=output_dir,
                output_file=session.exported_file_path,
            )
        if session.full_speed_locked:
            message = (
                "结果文件不存在，可使用已冻结参数重新执行"
                if session.stage is ProcessingStage.EXPORTED
                and session.exported_file_path
                else "可使用已冻结参数重新执行"
            )
            return FullSpeedExecutionState(
                status=FullSpeedStatus.INTERRUPTED,
                current_stage="执行已中断",
                message=message,
                output_dir=output_dir,
            )
        return FullSpeedExecutionState(output_dir=output_dir)
