"""运行期数据池注册器。"""

from __future__ import annotations

from pathlib import Path
import threading

from core.models.data_package import DataPackage
from infra.data_pool_store import DataPoolStore


class DataPoolRegistry:
    """维护当前进程中的只读数据包及其持久化顺序。

    Attributes:
        store: 数据池持久化适配器。
    """

    def __init__(self, store: DataPoolStore | None = None) -> None:
        """初始化数据池注册器。

        Args:
            store [DataPoolStore | None]: 自定义存储；为 None 时使用默认目录。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 默认数据池目录创建失败时抛出。
        """
        self.store = store or DataPoolStore()
        self._packages: dict[str, DataPackage] = {}
        self._lock = threading.RLock()

    @classmethod
    def from_root_dir(cls, root_dir: Path) -> "DataPoolRegistry":
        """从自定义持久化根目录创建数据池注册器。

        Args:
            root_dir [Path]: 数据池持久化根目录。

        Returns:
            DataPoolRegistry: 绑定该目录的新注册器。

        Raises:
            无显式抛出异常；目录在首次保存时创建。

        Example:
            >>> from pathlib import Path
            >>> registry = DataPoolRegistry.from_root_dir(Path("data_pool"))
            >>> registry.store.root_dir.name
            'data_pool'
        """
        return cls(DataPoolStore(root_dir))

    def register(
        self,
        package: DataPackage,
        *,
        persist: bool = True,
    ) -> DataPackage:
        """注册一个数据包。

        Args:
            package [DataPackage]: 已解析和预处理的数据包。
            persist [bool]: 是否同步持久化，默认 True。

        Returns:
            DataPackage: 已注册的原数据包。

        Raises:
            ValueError: 同一 ID 已注册为另一个对象时抛出。
            OSError: 持久化失败时抛出。
        """
        with self._lock:
            existing = self._packages.get(package.package_id)
            if existing is not None and existing is not package:
                raise ValueError(f"数据包 ID 已存在: {package.package_id}")
            if persist:
                self.store.save_package(package)
            self._packages[package.package_id] = package
            return package

    def register_many(
        self,
        packages: tuple[DataPackage, ...],
    ) -> tuple[DataPackage, ...]:
        """以一次导入任务为边界批量注册多个数据包。

        任一数据包持久化失败时，会删除本批次已经写入或正在写入的数据包，
        防止一次多波段导入只留下部分结果。

        Args:
            packages [tuple[DataPackage, ...]]: 按稳定波段顺序排列的数据包。

        Returns:
            tuple[DataPackage, ...]: 完成注册的原数据包元组。

        Raises:
            ValueError: 批次内 ID 重复或任一 ID 已存在时抛出。
            OSError: 持久化或回滚清理失败时抛出。

        Example:
            >>> registry = DataPoolRegistry()
            >>> registry.register_many(())
            ()
        """
        if not packages:
            return ()

        with self._lock:
            package_ids = [package.package_id for package in packages]
            if len(set(package_ids)) != len(package_ids):
                raise ValueError("批量注册的数据包 ID 不能重复")
            existing_ids = [
                package_id
                for package_id in package_ids
                if package_id in self._packages
            ]
            if existing_ids:
                raise ValueError(f"数据包 ID 已存在: {existing_ids[0]}")

            attempted_ids: list[str] = []
            try:
                for package in packages:
                    # 保存可能在抛错前创建目录，因此先记录 ID 供失败回滚。
                    attempted_ids.append(package.package_id)
                    self.store.save_package(package)
                    self._packages[package.package_id] = package
            except Exception as exc:
                cleanup_errors: list[Exception] = []
                for package_id in reversed(attempted_ids):
                    self._packages.pop(package_id, None)
                    try:
                        self.store.delete_package(package_id)
                    except Exception as cleanup_exc:
                        cleanup_errors.append(cleanup_exc)
                if cleanup_errors:
                    raise OSError("批量注册失败，且部分数据包回滚清理失败") from exc
                raise

            return packages

    def restore(self) -> list[DataPackage]:
        """从磁盘恢复全部数据包。

        Returns:
            list[DataPackage]: 按持久化顺序恢复的数据包。
        """
        with self._lock:
            packages = self.store.load_all_packages()
            self._packages = {
                package.package_id: package
                for package in packages
            }
            return list(packages)

    def get(self, package_id: str) -> DataPackage | None:
        """按 ID 获取数据包。

        Args:
            package_id [str]: 数据包 ID。

        Returns:
            DataPackage | None: 找到的数据包；不存在时返回 None。
        """
        with self._lock:
            return self._packages.get(package_id)

    def all_packages(self) -> list[DataPackage]:
        """返回当前全部数据包。

        Returns:
            list[DataPackage]: 按注册顺序复制的列表。
        """
        with self._lock:
            return list(self._packages.values())

    def delete(
        self,
        package_id: str,
        *,
        referenced_package_ids: set[str] | None = None,
    ) -> bool:
        """删除未被 Session 引用的数据包。

        Args:
            package_id [str]: 目标数据包 ID。
            referenced_package_ids [set[str] | None]: 当前仍被 Session 引用的 ID 集合。

        Returns:
            bool: 成功删除返回 True；数据包不存在返回 False。

        Raises:
            RuntimeError: 数据包仍被任一 Session 引用时抛出。
            OSError: 持久化删除失败时抛出。
        """
        with self._lock:
            if package_id not in self._packages:
                return False
            if package_id in (referenced_package_ids or set()):
                raise RuntimeError("数据包仍被 Session 引用，不能删除")
            self.store.delete_package(package_id)
            self._packages.pop(package_id, None)
            return True
