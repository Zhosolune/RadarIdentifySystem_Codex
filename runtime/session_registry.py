"""运行期 session 注册表。"""

from __future__ import annotations

import threading
from dataclasses import replace
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
        # 串行化内存注册表与 active id 更新，避免并发修改破坏一致性。
        self._lock = threading.RLock()
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
        with self._lock:
            if self.active_session_id is None:
                return None
            return self._sessions.get(self.active_session_id)

    def register(
        self,
        session: ProcessingSession,
        persist: bool = True,
        activate: bool = True,
    ) -> ProcessingSession:
        """注册 session 并设为 active。

        Args:
            session [ProcessingSession]: 需要注册的 session 对象。
            persist [bool]: 是否同步写入持久化存储，默认为 True。
            activate [bool]: 是否同步设为 active session，默认为 True。

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
        with self._lock:
            old_last_opened_at = session.last_opened_at
            new_last_opened_at = datetime.now()
            old_persisted_session = self._load_persisted_session_or_none(
                session.session_id,
            )
            old_active_session_id = self.store.load_index().active_session_id

            if persist:
                # upsert 只保存 session 内容，active id 由 registry 显式同步。
                persisted_session = replace(session, last_opened_at=new_last_opened_at)
                try:
                    self.store.upsert_session(persisted_session)
                    if activate:
                        self.store.set_active_session_id(session.session_id)
                    if self._has_import_cache_payload(session):
                        self.store.save_import_cache(session)
                except Exception:
                    # 持久化未完整成功时恢复磁盘与调用前对象状态。
                    self._restore_persisted_session(
                        session.session_id,
                        old_persisted_session,
                    )
                    self._restore_active_session_id(old_active_session_id)
                    session.last_opened_at = old_last_opened_at
                    raise
            else:
                session.last_opened_at = new_last_opened_at

            session.last_opened_at = new_last_opened_at
            self._sessions[session.session_id] = session
            if activate:
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
        with self._lock:
            restored_sessions = self.store.load_all_sessions()
            for session in restored_sessions:
                # 导入缓存缺失或损坏时保留元数据恢复结果，不阻断页面恢复。
                self.store.load_import_cache(session)
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
        with self._lock:
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
        with self._lock:
            return list(self._sessions.values())

    def persist_session(self, session_id: str) -> ProcessingSession:
        """持久化当前内存中的指定 session。

        Args:
            session_id [str]: 需要保存的 session 唯一标识。

        Returns:
            ProcessingSession: 已写入持久化存储的 session 对象。

        Raises:
            KeyError: 当 session_id 不在当前注册表中时抛出。
            OSError: 当持久化写入失败时抛出。
            ValueError: 当 session_id 非法时由持久化层抛出。

        Example:
            >>> registry = SessionRegistry()
            >>> session = ProcessingSession(session_id="demo")
            >>> registry.register(session, persist=False)
            ProcessingSession(id=demo, stage=CREATED, band=None, slices=0, src='')
            >>> registry.persist_session("demo") is session
            True
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)

            self.store.upsert_session(session)
            if self._has_import_cache_payload(session):
                # 配置保存或重新导入后的显式持久化要同步覆盖导入缓存。
                self.store.save_import_cache(session)
            return session

    def rename(self, session_id: str, display_name: str) -> ProcessingSession:
        """重命名指定 session 并同步持久化。

        Args:
            session_id [str]: 需要重命名的 session 唯一标识。
            display_name [str]: 新的展示名称，去除首尾空白后不能为空。

        Returns:
            ProcessingSession: 已更新名称的 session 对象。

        Raises:
            KeyError: 当 session_id 不在当前注册表中时抛出。
            ValueError: 当 display_name 为空白字符串时抛出。
            OSError: 当持久化写入失败时抛出。
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)

            new_display_name = display_name.strip()
            if not new_display_name:
                raise ValueError("session 名称不能为空")

            old_display_name = session.display_name
            session.display_name = new_display_name
            try:
                self.store.upsert_session(session)
            except Exception:
                # 持久化失败时恢复旧名称，避免内存和磁盘状态分叉。
                session.display_name = old_display_name
                raise

            return session

    def update_metadata(
        self,
        session_id: str,
        display_name: str,
        remark: str,
    ) -> ProcessingSession:
        """更新指定 session 的名称和备注并同步持久化。

        Args:
            session_id [str]: 需要更新元数据的 session 唯一标识。
            display_name [str]: 新的展示名称，去除首尾空白后不能为空。
            remark [str]: 新备注文本；首尾空白会被移除，空文本会保存为“无”。

        Returns:
            ProcessingSession: 已更新元数据的 session 对象。

        Raises:
            KeyError: 当 session_id 不在当前注册表中时抛出。
            ValueError: 当名称为空或备注不是字符串时抛出。
            OSError: 当持久化写入失败时抛出。

        Example:
            >>> registry = SessionRegistry()
            >>> session = ProcessingSession(session_id="demo")
            >>> registry.register(session, persist=False)
            ProcessingSession(id=demo, stage=CREATED, band=None, slices=0, src='')
            >>> registry.update_metadata("demo", "新名称", "备注")
            Traceback (most recent call last):
            ...
            FileNotFoundError: ...
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)

            new_display_name = display_name.strip()
            if not new_display_name:
                raise ValueError("session 名称不能为空")
            new_remark = self._normalize_remark(remark)
            old_display_name = session.display_name
            old_remark = session.remark
            session.display_name = new_display_name
            session.remark = new_remark
            try:
                # 一次 upsert 同步名称和备注，避免分别落盘的半提交。
                self.store.upsert_session(session)
            except Exception:
                # 写盘失败时回滚内存元数据。
                session.display_name = old_display_name
                session.remark = old_remark
                raise

            return session

    def update_remark(self, session_id: str, remark: str) -> ProcessingSession:
        """更新指定 session 的备注并同步持久化。

        Args:
            session_id [str]: 需要更新备注的 session 唯一标识。
            remark [str]: 新备注文本；首尾空白会被移除，空文本会保存为“无”。

        Returns:
            ProcessingSession: 已更新备注的内存 session 对象。

        Raises:
            KeyError: 当 session_id 不在当前注册表中时抛出。
            ValueError: 当备注不是字符串或 session_id 非法时抛出。
            OSError: 当持久化写入失败时抛出。

        Example:
            >>> registry = SessionRegistry()
            >>> session = ProcessingSession(session_id="demo")
            >>> registry.register(session, persist=False)
            ProcessingSession(id=demo, stage=CREATED, band=None, slices=0, src='')
            >>> registry.update_remark("demo", "备注")
            Traceback (most recent call last):
            ...
            FileNotFoundError: ...
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)

            new_remark = self._normalize_remark(remark)
            old_remark = session.remark
            session.remark = new_remark
            try:
                # 由持久化层负责重写 session 元数据，保持磁盘读写入口集中。
                self.store.update_session_remark(session_id, new_remark)
            except Exception:
                # 写盘失败时回滚内存备注，避免 UI 与磁盘状态分叉。
                session.remark = old_remark
                raise

            return session

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
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)

            old_last_opened_at = session.last_opened_at
            new_last_opened_at = datetime.now()
            old_persisted_session = self._load_persisted_session_or_none(session_id)
            old_active_session_id = self.store.load_index().active_session_id
            persisted_session = replace(session, last_opened_at=new_last_opened_at)
            try:
                self.store.upsert_session(persisted_session)
                self.store.set_active_session_id(session_id)
            except Exception:
                # 激活持久化失败时恢复内存与磁盘打开时间，并保留原 active id。
                self._restore_persisted_session(session_id, old_persisted_session)
                self._restore_active_session_id(old_active_session_id)
                session.last_opened_at = old_last_opened_at
                raise

            session.last_opened_at = new_last_opened_at
            self.active_session_id = session_id
            return session

    def set_active_session_id(self, session_id: str | None) -> None:
        """显式同步当前活动 session id。

        Args:
            session_id: 需要写入的活动 session id；传入 None 表示清空活动项。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: 当 session_id 不为 None 且不在当前注册表中时抛出。
            OSError: 当持久化活动 id 写入失败时抛出。
        """
        with self._lock:
            if session_id is not None and session_id not in self._sessions:
                raise KeyError(session_id)

            self.store.set_active_session_id(session_id)
            self.active_session_id = session_id

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
        with self._lock:
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
            persisted_deleted = False
            had_persisted_session = self._can_load_persisted_session(session_id)

            if delete_persisted:
                # 仅删除 session 元数据目录，不触碰任何计算结果存储。
                try:
                    self.store.delete_session(session_id)
                    persisted_deleted = True
                except Exception:
                    if (
                        had_persisted_session
                        and not self._can_load_persisted_session(session_id)
                    ):
                        self._reconcile_after_persisted_close(session_id)
                    raise

            if was_active:
                try:
                    self.store.set_active_session_id(next_active_session_id)
                except Exception:
                    if persisted_deleted:
                        self._reconcile_after_persisted_close(session_id)
                    raise

            self._sessions.pop(session_id, None)
            if was_active:
                self.active_session_id = next_active_session_id

    def _reconcile_after_persisted_close(self, session_id: str) -> None:
        """按磁盘删除结果同步 close 失败后的内存状态。"""
        with self._lock:
            self._sessions.pop(session_id, None)
            persisted_active_session_id = self.store.load_index().active_session_id
            self.active_session_id = (
                persisted_active_session_id
                if persisted_active_session_id in self._sessions
                else None
            )

    def _load_persisted_session_or_none(
        self,
        session_id: str,
    ) -> ProcessingSession | None:
        """读取旧持久化 session，缺失时返回 None。"""
        try:
            return self.store.load_session(session_id)
        except FileNotFoundError:
            return None

    def _restore_persisted_session(
        self,
        session_id: str,
        old_persisted_session: ProcessingSession | None,
    ) -> None:
        """尽力恢复失败写盘前的持久化 session 状态。"""
        try:
            if old_persisted_session is None:
                self.store.delete_session(session_id)
            else:
                self.store.upsert_session(old_persisted_session)
        except Exception:
            # 保留原始异常语义，恢复失败只作为尽力清理结果。
            return

    def _restore_active_session_id(self, old_active_session_id: str | None) -> None:
        """尽力恢复失败写盘前的持久化 active session id。"""
        try:
            self.store.set_active_session_id(old_active_session_id)
        except Exception:
            # 保留原始异常语义，active id 恢复失败只作为尽力清理结果。
            return

    def _can_load_persisted_session(self, session_id: str) -> bool:
        """判断磁盘 session 当前是否仍可加载。"""
        try:
            self.store.load_session(session_id)
        except FileNotFoundError:
            return False
        return True

    def _normalize_remark(self, remark: str) -> str:
        """规范化备注文本，空白备注统一保存为“无”。"""
        if not isinstance(remark, str):
            raise ValueError("session 备注必须是字符串")
        normalized_remark = remark.strip()
        return normalized_remark or "无"

    def _has_import_cache_payload(self, session: ProcessingSession) -> bool:
        """判断 session 是否具备写入导入缓存的最小数据。"""
        return (
            session.raw_batch is not None
            and session.preprocess_result is not None
            and session.dashboard_info is not None
        )
