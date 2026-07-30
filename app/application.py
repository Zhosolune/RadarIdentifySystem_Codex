"""应用级依赖装配。

该模块是运行期注册器和工作流的唯一默认装配入口。UI 只接收已经构造完成
的服务集合，不再推导持久化目录或自行创建底层运行期对象。
"""

from __future__ import annotations

from dataclasses import dataclass

from runtime.data_pool_registry import DataPoolRegistry
from runtime.full_speed_session_registry import FullSpeedSessionRegistry
from runtime.session_coordinator import SessionCoordinator
from runtime.session_registry import SessionRegistry
from runtime.workflows.full_speed_workflow import FullSpeedWorkflow


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    """保存应用生命周期内共享的运行期服务。

    Attributes:
        session_registry: 交互式 Session 注册表。
        data_pool_registry: 数据池注册表。
        full_speed_session_registry: 全速 Session 注册表。
        session_coordinator: Session 生命周期协调器。
        full_speed_workflow: 全速任务工作流。
    """

    session_registry: SessionRegistry
    data_pool_registry: DataPoolRegistry
    full_speed_session_registry: FullSpeedSessionRegistry
    session_coordinator: SessionCoordinator
    full_speed_workflow: FullSpeedWorkflow


def create_application_services(
    *,
    session_registry: SessionRegistry | None = None,
    data_pool_registry: DataPoolRegistry | None = None,
    full_speed_session_registry: FullSpeedSessionRegistry | None = None,
) -> ApplicationServices:
    """构造应用共享的运行期服务。

    自定义交互式注册表时，未显式提供的数据池和全速注册表会使用同一测试或
    嵌入目录，避免意外写入项目默认配置目录。

    Args:
        session_registry [SessionRegistry | None]: 自定义交互式 Session 注册表。
        data_pool_registry [DataPoolRegistry | None]: 自定义数据池注册表。
        full_speed_session_registry [FullSpeedSessionRegistry | None]: 自定义全速注册表。

    Returns:
        ApplicationServices: 完整且共享同一存储根语义的应用服务集合。

    Raises:
        OSError: 默认持久化目录初始化失败时抛出。

    Example:
        >>> services = create_application_services()
        >>> services.session_coordinator.session_registry is services.session_registry
        True
    """
    interactive_registry = session_registry or SessionRegistry()
    session_root = interactive_registry.store.root_dir
    data_pool_root = (
        session_root.parent / "data_pool"
        if session_root.name == "sessions"
        else session_root / "data_pool"
    )
    pool_registry = (
        data_pool_registry
        or DataPoolRegistry.from_root_dir(data_pool_root)
    )
    if not pool_registry.all_packages():
        pool_registry.restore()

    full_speed_registry = (
        full_speed_session_registry
        or FullSpeedSessionRegistry(session_root / "full_speed")
    )
    coordinator = SessionCoordinator(
        interactive_registry,
        pool_registry,
        full_speed_registry,
    )
    return ApplicationServices(
        session_registry=interactive_registry,
        data_pool_registry=pool_registry,
        full_speed_session_registry=full_speed_registry,
        session_coordinator=coordinator,
        full_speed_workflow=FullSpeedWorkflow(full_speed_registry),
    )
