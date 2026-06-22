"""主页 session 管理面板。"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton, SimpleCardWidget

from core.models.processing_session import ProcessingSession


class SessionManagerPanel(SimpleCardWidget):
    """展示当前运行期 session 列表。

    Attributes:
        sessionActivated: 请求激活指定 session 的信号。
        sessionCloseRequested: 请求关闭指定 session 的信号，当前最小实现暂不暴露按钮。
    """

    sessionActivated = pyqtSignal(str)
    sessionCloseRequested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """初始化 session 管理面板。

        Args:
            parent [QWidget | None]: 父级控件，默认值为 ``None``。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.session_titles()
            []
        """
        super().__init__(parent)
        self.setObjectName("sessionManagerPanel")
        self._sessions: list[ProcessingSession] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        self._show_empty_state()

    def set_sessions(self, sessions: list[ProcessingSession]) -> None:
        """刷新 session 列表。

        Args:
            sessions [list[ProcessingSession]]: 需要显示的 session 列表。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.set_sessions([])
            >>> panel.session_titles()
            []
        """
        self._sessions = list(sessions)
        self._clear_layout()
        if not self._sessions:
            self._show_empty_state()
            return

        for session in self._sessions:
            button = PushButton(session.display_name, self)
            button.clicked.connect(
                lambda _checked=False, sid=session.session_id: self.sessionActivated.emit(sid)
            )
            self._layout.addWidget(button)

    def session_titles(self) -> list[str]:
        """返回当前显示的 session 标题。

        Returns:
            list[str]: 当前面板持有的 session 展示标题。

        Raises:
            无显式抛出异常。

        Example:
            >>> panel = SessionManagerPanel()
            >>> panel.session_titles()
            []
        """
        return [session.display_name for session in self._sessions]

    def _clear_layout(self) -> None:
        """清空当前布局中的所有子控件。"""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_empty_state(self) -> None:
        """显示空 session 提示。"""
        self._layout.addWidget(BodyLabel("暂无 Session", self))
