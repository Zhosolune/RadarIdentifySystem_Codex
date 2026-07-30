"""Session 生命周期与数据池关联的运行期协调器。

该模块集中处理两类 Session 的创建、注册、恢复、持久化和数据包挂接，
避免 UI 直接修改核心 Session 状态或感知底层存储结构。
"""

from __future__ import annotations

from core.models.processing_session import (
    ProcessingMode,
    ProcessingSession,
    ProcessingStage,
)
from runtime.data_pool_registry import DataPoolRegistry
from runtime.full_speed_session_registry import FullSpeedSessionRegistry
from runtime.session_config_factory import (
    create_session_config_from_global,
    create_session_model_selection_from_global,
)
from runtime.session_registry import SessionRegistry

__all__ = ["ProcessingMode", "ProcessingSession", "SessionCoordinator"]


class SessionCoordinator:
    """协调数据池、交互式 Session 与全速 Session 的运行期生命周期。

    Attributes:
        session_registry: 交互式 Session 注册表。
        data_pool_registry: 只读数据包注册表。
        full_speed_session_registry: 全速 Session 注册表。
    """

    def __init__(
        self,
        session_registry: SessionRegistry,
        data_pool_registry: DataPoolRegistry,
        full_speed_session_registry: FullSpeedSessionRegistry,
    ) -> None:
        """初始化 Session 协调器。

        Args:
            session_registry [SessionRegistry]: 交互式 Session 注册表。
            data_pool_registry [DataPoolRegistry]: 数据池注册表。
            full_speed_session_registry [FullSpeedSessionRegistry]: 全速 Session 注册表。

        Returns:
            None: 无返回值。
        """
        self.session_registry = session_registry
        self.data_pool_registry = data_pool_registry
        self.full_speed_session_registry = full_speed_session_registry

    @property
    def active_session_id(self) -> str | None:
        """返回当前交互式活动 Session ID。

        Returns:
            str | None: 活动 Session ID；当前没有活动 Session 时返回 None。
        """
        return self.session_registry.active_session_id

    def build_session_from_data_package(
        self,
        package_id: str,
        processing_mode: ProcessingMode,
        display_name: str,
        remark: str,
    ) -> ProcessingSession:
        """从数据池构造尚未注册的完整 Session。

        Args:
            package_id [str]: 来源数据包 ID，必须已存在于数据池。
            processing_mode [ProcessingMode]: 交互式或全速处理模式。
            display_name [str]: Session 展示名称。
            remark [str]: Session 备注。

        Returns:
            ProcessingSession: 已绑定输入、配置快照和模型快照的 Session。

        Raises:
            KeyError: 数据包不存在时抛出。
        """
        package = self.data_pool_registry.get(package_id)
        if package is None:
            raise KeyError(f"数据包不存在: {package_id}")

        session = ProcessingSession.from_data_package(
            package,
            processing_mode=processing_mode,
            display_name=display_name,
            remark=remark,
        )
        session.config_snapshot = create_session_config_from_global()
        session.model_selection = create_session_model_selection_from_global()
        if processing_mode is ProcessingMode.FULL_SPEED:
            # 全速流水线固定包含结果导出，快照必须如实反映该业务行为。
            session.config_snapshot.business.auto_export = True
        return session

    def prepare_imported_interactive_session(
        self,
        session: ProcessingSession,
    ) -> None:
        """为旧导入入口提交的交互式 Session 刷新全局配置快照。

        Args:
            session [ProcessingSession]: 尚未注册的交互式 Session。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: Session 不是交互式模式时抛出。
        """
        if session.processing_mode is not ProcessingMode.SLICE_INTERACTIVE:
            raise ValueError("导入入口只接受交互式 Session")
        session.config_snapshot = create_session_config_from_global()

    def register_interactive_session(
        self,
        session: ProcessingSession,
    ) -> ProcessingSession:
        """持久化注册交互式 Session，保持当前活动 Session 不变。

        Args:
            session [ProcessingSession]: 已准备完成的交互式 Session。

        Returns:
            ProcessingSession: 已注册的原 Session。

        Raises:
            ValueError: Session 模式错误或 ID 非法时抛出。
            OSError: 持久化失败时抛出。
        """
        if session.processing_mode is not ProcessingMode.SLICE_INTERACTIVE:
            raise ValueError("交互式注册表只接受 INTERACTIVE Session")
        return self.session_registry.register(session, activate=False)

    def register_full_speed_session(
        self,
        session: ProcessingSession,
    ) -> ProcessingSession:
        """持久化注册全速 Session。

        Args:
            session [ProcessingSession]: 已准备完成的全速 Session。

        Returns:
            ProcessingSession: 已注册的原 Session。

        Raises:
            ValueError: Session 模式错误时抛出。
            OSError: 持久化失败时抛出。
        """
        return self.full_speed_session_registry.register(session)

    def restore_interactive_sessions(self) -> list[ProcessingSession]:
        """恢复可重新挂接数据池输入的交互式 Session。

        Returns:
            list[ProcessingSession]: 成功恢复输入关联的 Session 列表。
        """
        restored: list[ProcessingSession] = []
        for session in self.session_registry.restore():
            if session.data_package_id is not None and not self._attach_data_package_input(
                session
            ):
                continue
            restored.append(session)
        return restored

    def restore_full_speed_sessions(self) -> list[ProcessingSession]:
        """恢复可重新挂接数据池输入的全速 Session。

        Returns:
            list[ProcessingSession]: 成功恢复输入关联的全速 Session 列表。
        """
        sessions = self.full_speed_session_registry.all_sessions()
        if not sessions:
            sessions = self.full_speed_session_registry.restore()
        return [
            session
            for session in sessions
            if self._attach_data_package_input(session)
        ]

    def get_interactive_session(
        self,
        session_id: str,
    ) -> ProcessingSession | None:
        """按 ID 返回交互式 Session。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            ProcessingSession | None: 找到的 Session；不存在时返回 None。
        """
        return self.session_registry.get(session_id)

    def all_interactive_sessions(self) -> list[ProcessingSession]:
        """返回全部交互式 Session。

        Returns:
            list[ProcessingSession]: 当前注册顺序的 Session 列表。
        """
        return self.session_registry.all_sessions()

    def persist_interactive_session(
        self,
        session_id: str,
    ) -> ProcessingSession:
        """持久化指定交互式 Session。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            ProcessingSession: 已持久化的 Session。

        Raises:
            KeyError: Session 不存在时抛出。
            OSError: 持久化失败时抛出。
        """
        return self.session_registry.persist_session(session_id)

    def activate_interactive_session(self, session_id: str) -> ProcessingSession:
        """激活指定交互式 Session。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            ProcessingSession: 已激活的 Session。

        Raises:
            KeyError: Session 不存在时抛出。
        """
        return self.session_registry.activate(session_id)

    def clear_active_interactive_session(self, session_id: str) -> None:
        """当目标为当前活动 Session 时清空活动状态。

        Args:
            session_id [str]: 可能处于活动状态的 Session ID。

        Returns:
            None: 无返回值。
        """
        if self.session_registry.active_session_id == session_id:
            self.session_registry.set_active_session_id(None)

    def reset_interactive_session_for_enable(self, session_id: str) -> ProcessingSession:
        """重置交互式 Session，使关闭的页面可重新启用。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            ProcessingSession: 已重置的 Session。

        Raises:
            KeyError: Session 不存在时抛出。
        """
        session = self.session_registry.get(session_id)
        if session is None:
            raise KeyError(f"Session 不存在: {session_id}")
        session.reset_to_preprocessed_state()
        return session

    def update_interactive_metadata(
        self,
        session_id: str,
        display_name: str,
        remark: str,
    ) -> ProcessingSession:
        """更新交互式 Session 名称和备注。

        Args:
            session_id [str]: Session 唯一标识。
            display_name [str]: 新展示名称。
            remark [str]: 新备注。

        Returns:
            ProcessingSession: 已更新并持久化的 Session。

        Raises:
            KeyError: Session 不存在时抛出。
            ValueError: 名称无效时抛出。
            OSError: 持久化失败时抛出。
        """
        return self.session_registry.update_metadata(
            session_id,
            display_name,
            remark,
        )

    def delete_interactive_session(self, session_id: str) -> None:
        """删除交互式 Session 及其持久化记录。

        Args:
            session_id [str]: Session 唯一标识。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 持久化删除失败时抛出。
        """
        self.clear_active_interactive_session(session_id)
        self.session_registry.close(session_id, delete_persisted=True)

    def referenced_data_package_ids(self) -> set[str]:
        """返回两类 Session 当前引用的全部数据包 ID。

        Returns:
            set[str]: 被交互式或全速 Session 引用的数据包 ID 集合。
        """
        interactive_ids = {
            session.data_package_id
            for session in self.session_registry.all_sessions()
            if session.data_package_id is not None
        }
        return (
            interactive_ids
            | self.full_speed_session_registry.referenced_package_ids()
        )

    def _attach_data_package_input(self, session: ProcessingSession) -> bool:
        """把恢复 Session 重新挂接到数据池只读输入。"""
        if session.data_package_id is None:
            return False
        package = self.data_pool_registry.get(session.data_package_id)
        if package is None:
            return False

        session.raw_batch = package.raw_batch
        session.preprocess_result = package.preprocess_result
        session.dashboard_info = package.dashboard_info
        # 已成功导出的全速记录只恢复审计状态和结果路径，其余 Session
        # 从可重新执行的预处理阶段继续。
        if (
            session.processing_mode is not ProcessingMode.FULL_SPEED
            or session.stage is not ProcessingStage.EXPORTED
        ):
            session.stage = ProcessingStage.PREPROCESSED
        return True
