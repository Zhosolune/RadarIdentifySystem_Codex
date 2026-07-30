"""交互式 Session 管理面板控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

from app.signal_bus import signal_bus
from runtime.session_coordinator import ProcessingSession, SessionCoordinator
from ui.dialogs.rename_session_dialog import RenameSessionDialog

if TYPE_CHECKING:
    from ui.components.session_manager_panel import SessionManagerPanel
    from ui.interfaces.slice_interface import SliceInterface
    from ui.main_window import MainWindow


class SessionManagerController(QObject):
    """桥接交互式 Session 生命周期与动态页面宿主。

    Attributes:
        view: Session 管理面板。
        page_host: 动态 Session 页面宿主。
        coordinator: Session 运行期协调器。
    """

    def __init__(
        self,
        view: SessionManagerPanel,
        page_host: MainWindow,
        coordinator: SessionCoordinator,
    ) -> None:
        """初始化 Session 管理控制器。

        Args:
            view [SessionManagerPanel]: Session 管理面板。
            page_host [MainWindow]: 负责动态页面挂载、移除和导航的主窗口。
            coordinator [SessionCoordinator]: Session 运行期协调器。

        Returns:
            None: 无返回值。
        """
        super().__init__(page_host)
        self.view = view
        self.page_host = page_host
        self.coordinator = coordinator
        self._connect_signals()

    def _connect_signals(self) -> None:
        """连接 Session 管理面板动作信号。"""
        self.view.sessionEnableRequested.connect(self._on_session_enable_requested)
        self.view.sessionCloseRequested.connect(self._on_session_close_requested)
        self.view.sessionRenameRequested.connect(self._on_session_rename_requested)
        self.view.sessionDeleteRequested.connect(self._on_session_delete_requested)
        self.view.sessionJumpRequested.connect(self.activate_session)

    def add_prepared_session(
        self,
        session: ProcessingSession,
        *,
        activate: bool = False,
    ) -> SliceInterface:
        """注册已准备完成的交互式 Session 并创建动态页面。

        页面先创建、Session 后持久化；持久化失败时回滚本次页面，保持 UI
        与磁盘状态一致。

        Args:
            session [ProcessingSession]: 已包含输入和配置快照的交互式 Session。
            activate [bool]: 注册成功后是否立即进入动态页面。

        Returns:
            SliceInterface: 绑定该 Session 的动态页面。

        Raises:
            OSError: Session 持久化失败时抛出。
            ValueError: Session 模式或 ID 非法时抛出。
        """
        interface_existed = self.page_host.session_interface(
            session.session_id
        ) is not None
        interface = self.page_host.create_session_interface(
            session,
            activate=False,
        )
        try:
            self.coordinator.register_interactive_session(session)
        except Exception:
            if not interface_existed:
                self.page_host.close_session_interface(session.session_id)
            raise

        signal_bus.session_registered.emit(session.session_id)
        if activate:
            self.activate_session(session.session_id)
        else:
            self.page_host.show_home_interface()
            self.refresh_panel(selected_session_id=session.session_id)
        return interface

    def add_session_from_import(
        self,
        session: ProcessingSession,
        *,
        activate: bool = False,
    ) -> SliceInterface:
        """刷新旧导入 Session 配置后注册并创建动态页面。

        Args:
            session [ProcessingSession]: 旧导入入口提交的交互式 Session。
            activate [bool]: 注册成功后是否立即进入动态页面。

        Returns:
            SliceInterface: 绑定该 Session 的动态页面。

        Raises:
            OSError: Session 持久化失败时抛出。
            ValueError: Session 模式或 ID 非法时抛出。
        """
        self.coordinator.prepare_imported_interactive_session(session)
        return self.add_prepared_session(session, activate=activate)

    def restore_sessions(self) -> list[str]:
        """恢复交互式 Session 的动态页面并保持启动页为主页。

        Returns:
            list[str]: 成功恢复的 Session ID。
        """
        restored_ids: list[str] = []
        for session in self.coordinator.restore_interactive_sessions():
            self.page_host.create_session_interface(session, activate=False)
            restored_ids.append(session.session_id)
        self.page_host.show_home_interface()
        self.refresh_panel(selected_session_id=None)
        return restored_ids

    def refresh_panel(
        self,
        selected_session_id: str | None = None,
    ) -> None:
        """刷新 Session 管理器列表。

        Args:
            selected_session_id [str | None]: 刷新后优先选中的 Session ID。

        Returns:
            None: 无返回值。
        """
        preferred_session_id = (
            selected_session_id
            or self.view.current_session_id()
            or self.coordinator.active_session_id
        )
        self.view.set_sessions(
            self.coordinator.all_interactive_sessions(),
            selected_session_id=preferred_session_id,
            enabled_session_ids=self.page_host.enabled_session_ids(),
        )

    def activate_session(self, session_id: str) -> None:
        """激活指定 Session 并切换到对应动态页面。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            None: 无返回值。
        """
        if self.page_host.session_interface(session_id) is None:
            return
        if self.coordinator.get_interactive_session(session_id) is not None:
            self.coordinator.activate_interactive_session(session_id)
            self.refresh_panel(selected_session_id=session_id)
            signal_bus.session_activated.emit(session_id)
        self.page_host.show_session_interface(session_id)

    def _on_session_enable_requested(self, session_id: str) -> None:
        """处理“启用 Session 页面”请求。"""
        session = self.coordinator.get_interactive_session(session_id)
        if session is None:
            return
        if self.page_host.session_interface(session_id) is not None:
            self.refresh_panel(selected_session_id=session_id)
            return
        try:
            self.coordinator.reset_interactive_session_for_enable(session_id)
            self.page_host.create_session_interface(session, activate=False)
        except Exception as exc:
            self._show_top_warning("启用失败", str(exc))
            return
        self.refresh_panel(selected_session_id=session_id)
        self._show_top_success(
            "已启用",
            f"Session {session.display_name} 已启用，可继续跳转进入。",
        )

    def _on_session_close_requested(self, session_id: str) -> None:
        """处理“关闭 Session 页面”请求。"""
        session = self.coordinator.get_interactive_session(session_id)
        if session is None:
            return
        if self.page_host.session_interface(session_id) is None:
            self.refresh_panel(selected_session_id=session_id)
            return
        try:
            self.page_host.close_session_interface(session_id)
            self.coordinator.clear_active_interactive_session(session_id)
        except Exception as exc:
            self._show_top_warning("关闭失败", str(exc))
            return
        self.refresh_panel(selected_session_id=session_id)
        signal_bus.session_closed.emit(session_id)
        self._show_top_success(
            "已关闭",
            f"Session {session.display_name} 的切片处理页面已关闭。",
        )

    def _on_session_rename_requested(self, session_id: str) -> None:
        """处理 Session 名称和备注编辑请求。"""
        session = self.coordinator.get_interactive_session(session_id)
        if session is None:
            return
        dialog = RenameSessionDialog(
            session.display_name,
            session.remark,
            self.page_host,
        )
        if not dialog.exec():
            return

        new_name = dialog.get_session_name().strip()
        if not new_name:
            self._show_top_warning("名称无效", "Session 名称不能为空。")
            return
        new_remark = dialog.get_remark()
        if (
            new_name == session.display_name
            and new_remark.strip() == session.remark
        ):
            return
        try:
            self.coordinator.update_interactive_metadata(
                session_id,
                new_name,
                new_remark,
            )
            self.page_host.set_session_navigation_text(session_id, new_name)
        except Exception as exc:
            self._show_top_warning("信息更新失败", str(exc))
            return
        self.refresh_panel(selected_session_id=session_id)
        signal_bus.session_metadata_changed.emit(session_id)
        self._show_top_success(
            "信息已更新",
            f"Session {session.display_name} 的信息已更新。",
        )

    def _on_session_delete_requested(self, session_id: str) -> None:
        """处理“删除 Session”请求。"""
        session = self.coordinator.get_interactive_session(session_id)
        if session is None:
            return
        message_box = MessageBox(
            "删除 Session",
            f"确认删除 Session：{session.display_name}？\n该操作会删除持久化记录。",
            self.page_host,
        )
        message_box.yesButton.setText("删除")
        message_box.cancelButton.setText("取消")
        if not message_box.exec():
            return
        try:
            self.page_host.close_session_interface(session_id)
            self.coordinator.delete_interactive_session(session_id)
        except Exception as exc:
            self._show_top_warning("删除失败", str(exc))
            return
        self.refresh_panel(
            selected_session_id=self.coordinator.active_session_id
        )
        signal_bus.session_closed.emit(session_id)
        self._show_top_success(
            "已删除",
            f"Session {session.display_name} 已删除。",
        )

    def _show_top_success(self, title: str, content: str) -> None:
        """在窗口顶部显示成功消息条。"""
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self.page_host,
        )

    def _show_top_warning(self, title: str, content: str) -> None:
        """在窗口顶部显示警告消息条。"""
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self.page_host,
        )
