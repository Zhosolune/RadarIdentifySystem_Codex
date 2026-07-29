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
