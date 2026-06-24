"""Session 管理面板控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, Qt
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

from app.signal_bus import signal_bus
from ui.dialogs.rename_session_dialog import RenameSessionDialog

if TYPE_CHECKING:
    from ui.components.session_manager_panel import SessionManagerPanel
    from ui.main_window import MainWindow


class SessionManagerController(QObject):
    """Session 管理面板控制器。

    负责桥接主页 Session 管理面板与主窗口的动态页面生命周期能力：
    处理启用、关闭、重命名、删除和跳转动作，并同步提示消息。

    Attributes:
        view: 绑定的 Session 管理面板实例。
        main_window: 持有动态 Session 页面能力的主窗口实例。
    """

    def __init__(self, view: SessionManagerPanel, main_window: MainWindow) -> None:
        """初始化 Session 管理面板控制器。

        Args:
            view: 绑定的 Session 管理面板实例。
            main_window: 主窗口实例，负责页面创建、销毁与导航切换。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        super().__init__(main_window)
        self.view = view
        self.main_window = main_window
        self._connect_signals()

    def _connect_signals(self) -> None:
        """连接 Session 管理面板动作信号。"""
        # 连接启用页面请求。
        self.view.sessionEnableRequested.connect(self._on_session_enable_requested)
        # 连接关闭页面请求。
        self.view.sessionCloseRequested.connect(self._on_session_close_requested)
        # 连接重命名请求。
        self.view.sessionRenameRequested.connect(self._on_session_rename_requested)
        # 连接删除请求。
        self.view.sessionDeleteRequested.connect(self._on_session_delete_requested)
        # 连接页面跳转请求。
        self.view.sessionJumpRequested.connect(self.main_window.activate_session_interface)

    def _on_session_enable_requested(self, session_id: str) -> None:
        """处理“启用 Session 页面”请求。"""
        session = self.main_window.session_registry.get(session_id)
        if session is None:
            return
        if self.main_window.session_interface(session_id) is not None:
            # 已启用页面时仅刷新详情状态。
            self.main_window.refresh_session_manager_panel(selected_session_id=session_id)
            return

        try:
            # 重置到预处理完成状态，清空旧产物避免聚类图像残留。
            session.reset_to_preprocessed_state()
            # 创建动态页面但不立即跳转。
            self.main_window.create_session_interface(session, activate=False)
        except Exception as exc:
            self._show_top_warning("启用失败", str(exc))
            return

        self.main_window.refresh_session_manager_panel(selected_session_id=session_id)
        self._show_top_success("已启用", f"Session {session.display_name} 已启用，可继续跳转进入。")

    def _on_session_close_requested(self, session_id: str) -> None:
        """处理“关闭 Session 页面”请求。"""
        session = self.main_window.session_registry.get(session_id)
        if session is None:
            return
        if self.main_window.session_interface(session_id) is None:
            # 页面已关闭时仅刷新详情状态。
            self.main_window.refresh_session_manager_panel(selected_session_id=session_id)
            return

        try:
            # 关闭动态页面但保留注册表和卡片数据。
            self.main_window.close_session_interface(session_id)
            if self.main_window.session_registry.active_session_id == session_id:
                # 清空已关闭页面的活跃状态。
                self.main_window.session_registry.set_active_session_id(None)
        except Exception as exc:
            self._show_top_warning("关闭失败", str(exc))
            return

        self.main_window.refresh_session_manager_panel(selected_session_id=session_id)
        signal_bus.session_closed.emit(session_id)
        self._show_top_success("已关闭", f"Session {session.display_name} 的切片处理页面已关闭。")

    def _on_session_rename_requested(self, session_id: str) -> None:
        """处理“重命名 Session”请求。"""
        session = self.main_window.session_registry.get(session_id)
        if session is None:
            return

        dialog = RenameSessionDialog(session.display_name, self.main_window)
        if not dialog.exec():
            return

        new_name = dialog.get_session_name().strip()
        if not new_name:
            self._show_top_warning("名称无效", "Session 名称不能为空。")
            return
        if new_name == session.display_name:
            return

        try:
            # 同步更新注册表和导航文案。
            self.main_window.session_registry.rename(session_id, new_name)
            self.main_window.set_session_navigation_text(session_id, new_name)
        except Exception as exc:
            self._show_top_warning("重命名失败", str(exc))
            return

        self.main_window.refresh_session_manager_panel(selected_session_id=session_id)
        signal_bus.session_metadata_changed.emit(session_id)
        self._show_top_success("已重命名", f"Session 已更新为 {new_name}。")

    def _on_session_delete_requested(self, session_id: str) -> None:
        """处理“删除 Session”请求。"""
        session = self.main_window.session_registry.get(session_id)
        if session is None:
            return

        # 弹出删除确认框，避免误删持久化数据。
        message_box = MessageBox(
            "删除 Session",
            f"确认删除 Session：{session.display_name}？\n该操作会删除持久化记录。",
            self.main_window,
        )
        message_box.yesButton.setText("删除")
        message_box.cancelButton.setText("取消")
        if not message_box.exec():
            return

        try:
            # 先移除动态页面，再删除注册表与持久化数据。
            self.main_window.close_session_interface(session_id)
            if self.main_window.session_registry.active_session_id == session_id:
                self.main_window.session_registry.set_active_session_id(None)
            self.main_window.session_registry.close(session_id, delete_persisted=True)
        except Exception as exc:
            self._show_top_warning("删除失败", str(exc))
            return

        self.main_window.refresh_session_manager_panel(
            selected_session_id=self.main_window.session_registry.active_session_id
        )
        signal_bus.session_closed.emit(session_id)
        self._show_top_success("已删除", f"Session {session.display_name} 已删除。")

    def _show_top_success(self, title: str, content: str) -> None:
        """在窗口顶部居中显示成功消息条。"""
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self.main_window,
        )

    def _show_top_warning(self, title: str, content: str) -> None:
        """在窗口顶部居中显示警告消息条。"""
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self.main_window,
        )
