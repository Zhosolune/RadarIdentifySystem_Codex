"""运行期 session 注册表。"""

from __future__ import annotations

from datetime import datetime

from core.models.processing_session import ProcessingSession
from infra.session_store import SessionStore


class SessionRegistry:
    """维护运行期 session 顺序和活动 session。

    功能描述：
        注册表只保存当前进程内的 ``ProcessingSession`` 对象引用，并通过
        ``SessionStore`` 同步轻量元数据、配置快照和 active session id。
        它不接入 UI、不调度工作流，也不删除或保存任何计算结果存储。

    Attributes:
        store: session 持久化存储。
        active_session_id: 当前活动 session id；没有活动 session 时为 None。
    """

    def __init__(self, store: SessionStore | None = None) -> None:
        """初始化 session 注册表。

        Args:
            store [SessionStore | None]: 持久化存储；为 None 时使用默认 SessionStore。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当默认 SessionStore 初始化目录失败时抛出。

        Example:
            >>> registry = SessionRegistry()
            >>> registry.active_session is None
            True
        """
        self.store = store or SessionStore()
        self._sessions: dict[str, ProcessingSession] = {}
        self.active_session_id: str | None = None

    @property
    def active_session(self) -> ProcessingSession | None:
        """返回当前活动 session 对象。

        Returns:
            ProcessingSession | None: 当前 active 对象；active id 不存在时返回 None。

        Raises:
            无显式抛出异常。

        Example:
            >>> registry = SessionRegistry()
            >>> registry.active_session is None
            True
        """
        if self.active_session_id is None:
            return None
        return self._sessions.get(self.active_session_id)

    def register(
        self,
        session: ProcessingSession,
        persist: bool = True,
    ) -> ProcessingSession:
        """注册 session 并设为 active。

        Args:
            session [ProcessingSession]: 需要注册的 session 对象。
            persist [bool]: 是否同步写入持久化存储，默认为 True。

        Returns:
            ProcessingSession: 已注册的原 session 对象。

        Raises:
            OSError: 当持久化写入失败时抛出。
            ValueError: 当 session_id 非法时由持久化层抛出。

        Example:
            >>> registry = SessionRegistry()
            >>> session = ProcessingSession(session_id="demo")
            >>> registry.register(session, persist=False) is session
            True
        """
        old_last_opened_at = session.last_opened_at
        new_last_opened_at = datetime.now()

        if persist:
            # upsert 只保存 session 内容，active id 由 registry 显式同步。
            session.last_opened_at = new_last_opened_at
            try:
                self.store.upsert_session(session)
                self.store.set_active_session_id(session.session_id)
            except Exception:
                # 持久化未完整成功时恢复调用前对象状态，避免内存先行漂移。
                session.last_opened_at = old_last_opened_at
                raise
        else:
            session.last_opened_at = new_last_opened_at

        self._sessions[session.session_id] = session
        self.active_session_id = session.session_id
        return session

    def restore(self) -> list[ProcessingSession]:
        """从持久化存储恢复全部 session。

        功能描述：
            直接复用 ``SessionStore.load_all_sessions()`` 的容错逻辑，不自行遍历
            索引加载单个 session。active id 只在恢复结果中存在时才生效。

        Args:
            无。

        Returns:
            list[ProcessingSession]: 按持久化索引顺序恢复的 session 列表。

        Raises:
            无显式抛出异常；损坏 session 由 SessionStore 跳过。

        Example:
            >>> registry = SessionRegistry()
            >>> isinstance(registry.restore(), list)
            True
        """
        restored_sessions = self.store.load_all_sessions()
        restored_mapping = {
            session.session_id: session
            for session in restored_sessions
        }

        active_session_id = self.store.load_index().active_session_id
        restored_active_session_id = (
            active_session_id
            if active_session_id in restored_mapping
            else None
        )
        if active_session_id is not None and restored_active_session_id is None:
            self.store.set_active_session_id(None)

        self._sessions = restored_mapping
        self.active_session_id = restored_active_session_id
        return self.all_sessions()

    def get(self, session_id: str) -> ProcessingSession | None:
        """按 id 获取 session。

        Args:
            session_id [str]: 需要查询的 session id。

        Returns:
            ProcessingSession | None: 找到时返回 session 对象，否则返回 None。

        Raises:
            无显式抛出异常。

        Example:
            >>> registry = SessionRegistry()
            >>> registry.get("missing") is None
            True
        """
        return self._sessions.get(session_id)

    def all_sessions(self) -> list[ProcessingSession]:
        """返回当前内存中的全部 session。

        Returns:
            list[ProcessingSession]: 按注册或持久化索引顺序排列的 session 列表。

        Raises:
            无显式抛出异常。

        Example:
            >>> registry = SessionRegistry()
            >>> registry.all_sessions()
            []
        """
        return list(self._sessions.values())

    def activate(self, session_id: str) -> ProcessingSession:
        """激活指定 session。

        Args:
            session_id [str]: 需要设为 active 的 session id。

        Returns:
            ProcessingSession: 被激活的 session 对象。

        Raises:
            KeyError: 当 session_id 不在当前注册表中时抛出。
            OSError: 当持久化写入失败时抛出。
            ValueError: 当 session_id 非法时由持久化层抛出。

        Example:
            >>> registry = SessionRegistry()
            >>> session = ProcessingSession(session_id="demo")
            >>> registry.register(session, persist=False)
            ProcessingSession(id=demo, stage=CREATED, band=None, slices=0, src='')
            >>> registry.activate("demo") is session
            True
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)

        old_last_opened_at = session.last_opened_at
        session.last_opened_at = datetime.now()
        try:
            self.store.upsert_session(session)
            self.store.set_active_session_id(session_id)
        except Exception:
            # 激活持久化失败时恢复打开时间，并保留原 active id。
            session.last_opened_at = old_last_opened_at
            raise

        self.active_session_id = session_id
        return session

    def close(self, session_id: str, delete_persisted: bool = True) -> None:
        """关闭指定 session。

        Args:
            session_id [str]: 需要从内存注册表移除的 session id。
            delete_persisted [bool]: 是否同步删除持久化 session，默认为 True。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当持久化删除或索引写入失败时抛出。
            ValueError: 当 session_id 非法时由持久化层抛出。

        Example:
            >>> registry = SessionRegistry()
            >>> session = ProcessingSession(session_id="demo")
            >>> registry.register(session, persist=False)
            ProcessingSession(id=demo, stage=CREATED, band=None, slices=0, src='')
            >>> registry.close("demo", delete_persisted=False)
            >>> registry.active_session is None
            True
        """
        was_active = self.active_session_id == session_id
        remaining_session_ids = [
            current_session_id
            for current_session_id in self._sessions
            if current_session_id != session_id
        ]
        next_active_session_id = (
            remaining_session_ids[-1]
            if remaining_session_ids
            else None
        )

        if delete_persisted:
            # 仅删除 session 元数据目录，不触碰任何计算结果存储。
            self.store.delete_session(session_id)

        if was_active:
            self.store.set_active_session_id(next_active_session_id)

        self._sessions.pop(session_id, None)
        if was_active:
            self.active_session_id = next_active_session_id
