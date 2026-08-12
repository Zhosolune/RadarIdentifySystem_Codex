"""数据池文件持久化适配器。

每个数据包在独立目录中保存元数据和压缩数组，数据池索引只记录稳定的
``package_id`` 顺序。Session 只保存数据包引用，不再重复保存输入数组。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import shutil
import threading
from typing import Any

import numpy as np

from core.models.data_package import DataPackage
from core.models.dashboard_info import PulseDashboardInfo
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
from utils.paths import get_data_pool_dir


_DATA_POOL_SCHEMA_VERSION = 1
_WINDOWS_INVALID_FILENAME_CHARS = set('<>:"|?*')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class DataPoolStore:
    """持久化数据池索引、元数据和脉冲数组。

    Attributes:
        root_dir: 数据池根目录。
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        """初始化数据池存储。

        Args:
            root_dir [Path | None]: 自定义根目录；为 None 时使用应用配置目录。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 根目录创建失败时抛出。
        """
        # 构造和只读恢复不应产生磁盘写入；首次保存时再创建数据池目录。
        self.root_dir = root_dir or get_data_pool_dir(create=False)
        self._lock = threading.RLock()

    def save_package(self, package: DataPackage) -> None:
        """新增或更新一个数据包。

        Args:
            package [DataPackage]: 需要持久化的数据包。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 目录或文件写入失败时抛出。
            ValueError: 数据包 ID 不安全或摘要缺失时抛出。
        """
        with self._lock:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            package_dir = self._package_dir(package.package_id)
            package_dir.mkdir(parents=True, exist_ok=True)
            if package.dashboard_info is None:
                raise ValueError("数据包缺少仪表盘摘要，无法持久化")

            metadata = {
                "schema_version": _DATA_POOL_SCHEMA_VERSION,
                "package_id": package.package_id,
                "display_name": package.display_name,
                "source_path": package.source_path,
                "source_type": package.source_type,
                "created_at": package.created_at.isoformat(),
                "data_format": package.data_format,
                "raw_batch": {
                    "source_path": package.raw_batch.source_path,
                    "source_type": package.raw_batch.source_type,
                    "total_pulses": package.raw_batch.total_pulses,
                },
                "preprocess_result": {
                    "total_pulses": package.preprocess_result.total_pulses,
                    "filtered_pulses": package.preprocess_result.filtered_pulses,
                    "amplitude_dropped_pulses": (
                        package.preprocess_result.amplitude_dropped_pulses
                    ),
                    "toa_flip_count": package.preprocess_result.toa_flip_count,
                    "time_range": package.preprocess_result.time_range,
                    "estimated_slice_count": (
                        package.preprocess_result.estimated_slice_count
                    ),
                    "band": package.preprocess_result.band,
                },
                "dashboard_info": asdict(package.dashboard_info),
            }
            # 先写数组再写元数据；新数据包任一步失败都不会形成“有元数据但
            # 缺少数组”的可见条目，索引始终在二者成功后最后提交。
            self._write_arrays_atomic(
                package_dir / "pulse_data.npz",
                package.raw_batch.data,
                package.preprocess_result.data,
            )
            self._write_json_atomic(package_dir / "metadata.json", metadata)

            package_ids = self._read_index()
            if package.package_id not in package_ids:
                package_ids.append(package.package_id)
            self._write_index(package_ids)

    def load_package(self, package_id: str) -> DataPackage:
        """读取一个完整数据包。

        Args:
            package_id [str]: 数据包唯一标识。

        Returns:
            DataPackage: 恢复并重新冻结数组的数据包。

        Raises:
            FileNotFoundError: 元数据或数组文件不存在时抛出。
            ValueError: ID、版本或元数据结构不合法时抛出。
            OSError: 文件读取失败时抛出。
        """
        with self._lock:
            if not self.root_dir.exists():
                raise FileNotFoundError(f"数据池不存在: {self.root_dir}")
            package_dir = self._package_dir(package_id)
            metadata_path = package_dir / "metadata.json"
            data_path = package_dir / "pulse_data.npz"
            if not metadata_path.exists() or not data_path.exists():
                raise FileNotFoundError(f"数据包不存在或不完整: {package_id}")

            metadata = self._read_json(metadata_path)
            if int(metadata.get("schema_version", 0)) != _DATA_POOL_SCHEMA_VERSION:
                raise ValueError("不支持的数据池缓存版本")
            if metadata.get("package_id") != package_id:
                raise ValueError("数据包元数据 ID 与目录不一致")

            with np.load(data_path, allow_pickle=False) as arrays:
                raw_data = np.array(arrays["raw_data"])
                preprocess_data = np.array(arrays["preprocess_data"])

            dashboard = self._build_dashboard(metadata["dashboard_info"])
            raw_payload = metadata["raw_batch"]
            preprocess_payload = metadata["preprocess_result"]
            raw_batch = PulseBatch(
                data=raw_data,
                source_path=str(raw_payload["source_path"]),
                source_type=str(raw_payload["source_type"]),
                total_pulses=int(raw_payload["total_pulses"]),
            )
            preprocess_result = PreprocessResult(
                data=preprocess_data,
                total_pulses=int(preprocess_payload["total_pulses"]),
                filtered_pulses=int(preprocess_payload["filtered_pulses"]),
                amplitude_dropped_pulses=int(
                    preprocess_payload.get(
                        "amplitude_dropped_pulses",
                        dashboard.amplitude_dropped_pulses,
                    )
                ),
                toa_flip_count=int(preprocess_payload["toa_flip_count"]),
                time_range=float(preprocess_payload["time_range"]),
                estimated_slice_count=int(
                    preprocess_payload["estimated_slice_count"]
                ),
                band=preprocess_payload["band"],
                dashboard_info=dashboard,
            )
            return DataPackage(
                package_id=package_id,
                display_name=str(metadata["display_name"]),
                source_path=str(metadata["source_path"]),
                source_type=str(metadata["source_type"]),
                created_at=datetime.fromisoformat(str(metadata["created_at"])),
                data_format=metadata.get("data_format"),
                raw_batch=raw_batch,
                preprocess_result=preprocess_result,
                dashboard_info=dashboard,
            )

    def load_all_packages(self) -> list[DataPackage]:
        """按索引顺序恢复全部有效数据包。

        Returns:
            list[DataPackage]: 可正常读取的数据包列表；损坏条目会被跳过。

        Raises:
            无显式抛出异常。
        """
        packages: list[DataPackage] = []
        indexed_ids = self._read_index()
        # 索引损坏或一次写入中断时仍可从完整数据包目录恢复，避免数据在主页
        # “消失”；索引顺序优先，未入索引目录按名称稳定追加。
        package_ids = [
            *indexed_ids,
            *(
                package_id
                for package_id in self._discover_package_ids()
                if package_id not in indexed_ids
            ),
        ]
        for package_id in package_ids:
            try:
                packages.append(self.load_package(package_id))
            except (OSError, KeyError, TypeError, ValueError):
                continue
        return packages

    def delete_package(self, package_id: str) -> None:
        """删除指定数据包目录和索引条目。

        Args:
            package_id [str]: 需要删除的数据包 ID。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 目录删除或索引写入失败时抛出。
            ValueError: 数据包 ID 不安全时抛出。
        """
        with self._lock:
            if not self.root_dir.exists():
                return
            package_dir = self._package_dir(package_id)
            if package_dir.exists():
                shutil.rmtree(package_dir)
            self._write_index(
                current_id
                for current_id in self._read_index()
                if current_id != package_id
            )

    def _read_index(self) -> list[str]:
        """读取数据池索引，缺失或损坏时返回空列表。"""
        index_path = self.root_dir / "index.json"
        if not index_path.exists():
            return []
        try:
            payload = self._read_json(index_path)
            if int(payload.get("schema_version", 0)) != _DATA_POOL_SCHEMA_VERSION:
                return []
            package_ids = payload.get("package_ids", [])
            if not isinstance(package_ids, list):
                return []
            return [
                self._validate_package_id(package_id)
                for package_id in package_ids
                if isinstance(package_id, str)
            ]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return []

    def _write_index(self, package_ids: Any) -> None:
        """原子写入数据池索引。"""
        self._write_json_atomic(
            self.root_dir / "index.json",
            {
                "schema_version": _DATA_POOL_SCHEMA_VERSION,
                "package_ids": list(package_ids),
            },
        )

    def _discover_package_ids(self) -> list[str]:
        """扫描包含完整元数据的安全数据包目录。"""
        if not self.root_dir.exists():
            return []
        package_ids: list[str] = []
        for child in sorted(self.root_dir.iterdir(), key=lambda path: path.name):
            if not child.is_dir() or not (child / "metadata.json").is_file():
                continue
            try:
                package_id = self._validate_package_id(child.name)
                metadata = self._read_json(child / "metadata.json")
                if metadata.get("package_id") != package_id:
                    continue
                package_ids.append(package_id)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return package_ids

    @staticmethod
    def _build_dashboard(payload: dict[str, Any]) -> PulseDashboardInfo:
        """从持久化字典恢复 Excel 仪表盘摘要。"""
        return PulseDashboardInfo(
            total_pulses=int(payload["total_pulses"]),
            removed_pulses=int(payload["removed_pulses"]),
            amplitude_dropped_pulses=int(
                payload["amplitude_dropped_pulses"]
            ),
            duration=float(payload["duration"]),
            band=payload["band"],
            estimated_slice_count=int(payload["estimated_slice_count"]),
        )

    def _package_dir(self, package_id: str) -> Path:
        """生成并校验数据包目录路径。"""
        safe_package_id = self._validate_package_id(package_id)
        root = self.root_dir.resolve()
        package_dir = (self.root_dir / safe_package_id).resolve()
        try:
            package_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError("数据包目录不能位于数据池之外") from exc
        if package_dir == root:
            raise ValueError("数据包目录不能等于数据池根目录")
        return package_dir

    @staticmethod
    def _validate_package_id(package_id: str) -> str:
        """校验数据包 ID 可安全用作单层目录名。"""
        if not isinstance(package_id, str) or not package_id:
            raise ValueError("package_id 必须是非空字符串")
        if package_id in {".", ".."}:
            raise ValueError("package_id 不能为空或相对路径")
        if package_id.rstrip(" .") != package_id:
            raise ValueError("package_id 不能以空格或点结尾")
        if any(ord(char) < 32 for char in package_id):
            raise ValueError("package_id 不能包含控制字符")
        if any(char in _WINDOWS_INVALID_FILENAME_CHARS for char in package_id):
            raise ValueError("package_id 包含 Windows 非法字符")
        if package_id.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise ValueError("package_id 不能使用 Windows 保留设备名")
        package_path = Path(package_id)
        if (
            package_path.is_absolute()
            or package_path.drive
            or package_path.root
            or package_path.name != package_id
        ):
            raise ValueError("package_id 必须是单段相对目录名")
        return package_id

    @staticmethod
    def _read_json(file_path: Path) -> dict[str, Any]:
        """读取 JSON 字典。"""
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise ValueError("JSON 根节点必须是字典")
        return payload

    @staticmethod
    def _write_json_atomic(file_path: Path, payload: dict[str, Any]) -> None:
        """通过同目录临时文件原子写入 JSON。"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        temp_path.replace(file_path)

    @staticmethod
    def _write_arrays_atomic(
        file_path: Path,
        raw_data: np.ndarray,
        preprocess_data: np.ndarray,
    ) -> None:
        """通过同目录临时文件原子写入压缩数组。"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        with temp_path.open("wb") as file:
            np.savez_compressed(
                file,
                raw_data=raw_data,
                preprocess_data=preprocess_data,
            )
        temp_path.replace(file_path)
