"""全速 Session 面板控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

from app.signal_bus import signal_bus
from runtime.full_speed_session_registry import (
    FullSpeedSessionRegistry,
    FullSpeedStatus,
)
from runtime.session_coordinator import SessionCoordinator
from runtime.workflows.full_speed_workflow import FullSpeedWorkflow
from ui.components.full_speed_params_window import FullSpeedParamsWindow

if TYPE_CHECKING:
    from core.models.session_config import SessionConfigSnapshot
    from core.models.session_model import SessionModelSelection
    from ui.components.full_speed_session_panel import FullSpeedSessionPanel


class FullSpeedSessionController(QObject):
    """连接全速 Session 面板、参数窗口和运行期工作流。

    Attributes:
        view: 全速 Session 面板。
        coordinator: Session 生命周期协调器。
        registry: 全速 Session 注册表。
        workflow: 全速任务工作流。
    """

    def __init__(
        self,
        view: FullSpeedSessionPanel,
        coordinator: SessionCoordinator,
        registry: FullSpeedSessionRegistry,
        workflow: FullSpeedWorkflow,
        parent: QWidget,
    ) -> None:
        """初始化全速 Session 控制器。

        Args:
            view [FullSpeedSessionPanel]: 需要绑定的全速 Session 面板。
            coordinator [SessionCoordinator]: Session 生命周期协调器。
            registry [FullSpeedSessionRegistry]: 全速 Session 注册表。
            workflow [FullSpeedWorkflow]: 全速任务工作流。
            parent [QWidget]: 对话框和消息条所属的顶层窗口。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.view = view
        self.coordinator = coordinator
        self.registry = registry
        self.workflow = workflow
        self._message_parent = parent
        self._param_windows: dict[str, FullSpeedParamsWindow] = {}
        self._connect_signals()

    def _connect_signals(self) -> None:
        """连接全速 Session 面板和生命周期信号。"""
        self.view.outputDirectoryRequested.connect(self.select_output_directory)
        self.view.parametersRequested.connect(self.open_parameters)
        self.view.startRequested.connect(self.start_session)
        self.view.pauseRequested.connect(self.toggle_pause_session)
        self.view.deleteRequested.connect(self.delete_session)
        self.view.openOutputRequested.connect(self.open_output)
        signal_bus.full_speed_session_changed.connect(self.refresh_panel)
        signal_bus.session_registered.connect(self._on_session_registered)

    def restore_sessions(self) -> list[str]:
        """恢复全速 Session 卡片并重新挂接数据池输入。

        Returns:
            list[str]: 成功恢复的全速 Session ID。
        """
        sessions = self.coordinator.restore_full_speed_sessions()
        self.refresh_panel()
        return [session.session_id for session in sessions]

    def refresh_panel(self, selected_session_id: str | None = None) -> None:
        """刷新全速 Session 卡片列表。

        Args:
            selected_session_id [str | None]: 刷新后优先选中的 Session ID。

        Returns:
            None: 无返回值。
        """
        sessions = self.registry.all_sessions()
        states = {
            session.session_id: state
            for session in sessions
            if (state := self.registry.state(session.session_id)) is not None
        }
        self.view.set_sessions(
            sessions,
            states,
            selected_session_id=selected_session_id,
        )

    def select_output_directory(self, session_id: str) -> None:
        """为配置中或已暂停的全速 Session 选择独立保存目录。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.registry.get(session_id)
        if session is None:
            self._show_warning("设置失败", "全速 Session 不存在")
            return

        output_dir = QFileDialog.getExistingDirectory(
            self._message_parent,
            "选择全速处理 Excel 保存目录",
            session.config_snapshot.business.export_dir_path,
        )
        if not output_dir:
            return
        try:
            self.registry.set_output_dir(session_id, output_dir)
        except Exception as error:
            self._show_warning("设置失败", str(error))
            return
        self.refresh_panel(session_id)

    def open_parameters(self, session_id: str) -> None:
        """打开配置中或已暂停全速 Session 的参数编辑窗口。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.registry.get(session_id)
        if session is None:
            self._show_warning("设置失败", "全速 Session 不存在")
            return
        state = self.registry.state(session_id)
        if (
            session.full_speed_locked
            and (
                state is None
                or state.status is not FullSpeedStatus.PAUSED
            )
        ):
            self._show_warning(
                "参数已冻结",
                "请先暂停全速任务，再修改参数",
            )
            return

        existing = self._param_windows.get(session_id)
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return

        window = FullSpeedParamsWindow(
            session_id,
            session.display_name,
            session.config_snapshot,
            session.model_selection,
        )
        window.settingsSaved.connect(
            lambda snapshot, selection, target_id=session_id: (
                self.save_settings(target_id, snapshot, selection)
            )
        )
        window.destroyed.connect(
            lambda _object=None, target_id=session_id, target=window: (
                self._release_param_window(target_id, target)
            )
        )
        self._param_windows[session_id] = window
        window.show()
        window.raise_()
        window.activateWindow()

    def save_settings(
        self,
        session_id: str,
        snapshot: SessionConfigSnapshot,
        model_selection: SessionModelSelection,
    ) -> None:
        """保存参数窗口提交的配置快照与模型选择。

        Args:
            session_id [str]: 目标全速 Session ID。
            snapshot [SessionConfigSnapshot]: 参数窗口提交的配置快照。
            model_selection [SessionModelSelection]: 参数窗口提交的模型选择快照。

        Returns:
            None: 无返回值。
        """
        try:
            self.registry.set_settings(
                session_id,
                snapshot,
                model_selection,
            )
        except Exception as error:
            self._show_warning("设置保存失败", str(error))
            return

        window = self._param_windows.get(session_id)
        if window is not None:
            window.close()
        self.refresh_panel(session_id)
        state = self.registry.state(session_id)
        paused_and_changed = (
            state is not None
            and state.status is FullSpeedStatus.PAUSED
            and state.restart_required
        )
        InfoBar.success(
            title="设置已保存",
            content=(
                "设置已修改，请点击“重新执行”从第一个切片开始。"
                if paused_and_changed
                else "当前全速 Session 将使用这组参数和模型执行。"
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1800,
            parent=self._message_parent,
        )

    def start_session(self, session_id: str) -> None:
        """启动任务，或终止暂停现场后使用当前设置重新执行。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.registry.get(session_id)
        if session is None:
            self._show_warning("启动失败", "全速 Session 不存在")
            return
        try:
            state = self.registry.state(session_id)
            if not session.config_snapshot.business.export_dir_path.strip():
                self.select_output_directory(session_id)
                if not session.config_snapshot.business.export_dir_path.strip():
                    return
            if state is not None and state.status is FullSpeedStatus.PAUSED:
                if not self.workflow.restart_paused(session_id):
                    raise RuntimeError("当前暂停任务无法重新执行")
            else:
                self.workflow.start(session_id)
            params_window = self._param_windows.get(session_id)
            if params_window is not None:
                params_window.close()
        except Exception as error:
            self._show_warning("启动失败", str(error))
            self.refresh_panel(session_id)

    def toggle_pause_session(self, session_id: str) -> None:
        """根据当前状态暂停任务或从原执行现场继续。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        state = self.registry.state(session_id)
        if state is None:
            self._show_warning("操作失败", "全速 Session 不存在")
            return
        if state.status is FullSpeedStatus.RUNNING:
            succeeded = self.workflow.pause(session_id)
            title = "无法暂停"
            message = "当前任务不在可暂停的执行阶段"
        elif state.status is FullSpeedStatus.PAUSED:
            succeeded = self.workflow.resume(session_id)
            title = "无法继续"
            message = (
                "设置已修改，请点击“重新执行”让新设置生效"
                if state.restart_required
                else "当前任务无法从暂停现场继续"
            )
        else:
            succeeded = False
            title = "操作失败"
            message = "当前任务不支持暂停或继续"
        if not succeeded:
            self._show_warning(
                title,
                message,
            )

    def delete_session(self, session_id: str) -> None:
        """确认后删除停止任务，或安全终止暂停现场后删除。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        session = self.registry.get(session_id)
        if session is None:
            return
        state = self.registry.state(session_id)
        paused_hint = (
            "暂停处理现场将先终止并清理。"
            if state is not None and state.status is FullSpeedStatus.PAUSED
            else ""
        )
        dialog = MessageBox(
            "删除全速 Session",
            f"确认删除“{session.display_name}”吗？{paused_hint}"
            "已生成的 Excel 文件不会删除。",
            self._message_parent,
        )
        if not dialog.exec():
            return
        try:
            if not self.workflow.delete(session_id):
                raise RuntimeError("当前全速任务仍在执行，暂时不能删除")
        except Exception as error:
            self._show_warning("删除失败", str(error))
            return

        params_window = self._param_windows.get(session_id)
        if params_window is not None:
            params_window.close()
        self.refresh_panel()

    def open_output(self, session_id: str) -> None:
        """使用系统默认程序打开全速任务结果。

        Args:
            session_id [str]: 目标全速 Session ID。

        Returns:
            None: 无返回值。
        """
        state = self.registry.state(session_id)
        if state is None or not state.output_file:
            self._show_warning("无法打开", "当前任务还没有结果文件")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(state.output_file)):
            self._show_warning(
                "无法打开",
                f"请手动访问：{state.output_file}",
            )

    def prepare_close(self) -> bool:
        """停止运行任务并关闭参数窗口。

        Returns:
            bool: 可以继续关闭主窗口时返回 True；任务尚未停止时返回 False。
        """
        if self.workflow.is_running() and not self.workflow.shutdown():
            self._show_warning(
                "正在停止任务",
                "仍有全速任务处于单片计算中，请稍后再次关闭。",
            )
            return False
        for window in list(self._param_windows.values()):
            window.close()
        return True

    def _on_session_registered(self, session_id: str) -> None:
        """新注册对象属于全速体系时刷新任务面板。"""
        if self.registry.get(session_id) is not None:
            self.refresh_panel(session_id)

    def _release_param_window(
        self,
        session_id: str,
        window: FullSpeedParamsWindow,
    ) -> None:
        """释放已关闭的参数窗口引用。"""
        if self._param_windows.get(session_id) is window:
            self._param_windows.pop(session_id, None)

    def _show_warning(self, title: str, content: str) -> None:
        """在主窗口顶部显示全速任务提示。"""
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self._message_parent,
        )
