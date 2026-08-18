"""把旧版运行数据非破坏地迁移到统一 LocalAppData 目录。

迁移属于文件系统适配职责，因此位于 ``infra``。源数据只读，目标已有文件
优先；所有 JSON 路径重写先在 staging 中完成，最后再提交并写入完成标记。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from typing import Final

from utils.paths import AppPaths, get_app_paths


_MIGRATION_VERSION: Final[int] = 1
_MARKER_NAME: Final[str] = ".migration-v1-complete.json"
_STAGING_NAME: Final[str] = ".migration-v1-staging"


@dataclass(frozen=True, slots=True)
class LegacyMigrationResult:
    """描述一次旧数据迁移结果。

    Attributes:
        performed: 本次是否执行了迁移扫描与提交。
        copied_files: 实际复制到新目录的文件数量。
        skipped_files: 因目标已存在而跳过的文件数量。
        marker_file: 迁移完成标记文件。
    """

    performed: bool
    copied_files: int
    skipped_files: int
    marker_file: Path


class LegacyDataMigrator:
    """协调旧版开发目录或用户目录到新布局的一次性迁移。

    Attributes:
        paths: 新版目标路径集合。
        legacy_application_root: 旧版 ``~/.RadarIdentifySystem`` 根目录。
    """

    def __init__(
        self,
        paths: AppPaths | None = None,
        *,
        legacy_application_root: Path | None = None,
    ) -> None:
        """初始化迁移器。

        Args:
            paths [AppPaths | None]: 目标路径，默认读取当前应用路径。
            legacy_application_root [Path | None]: 测试覆盖用旧版用户根目录。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 路径解析失败时抛出。
        """
        self.paths = paths or get_app_paths()
        self.legacy_application_root = (
            legacy_application_root or Path.home() / ".RadarIdentifySystem"
        ).resolve()

    @property
    def marker_file(self) -> Path:
        """返回迁移完成标记路径。"""
        return self.paths.user_data_root / _MARKER_NAME

    def migrate(self) -> LegacyMigrationResult:
        """执行一次非覆盖、非删除的旧数据迁移。

        Returns:
            LegacyMigrationResult: 是否执行及复制、跳过文件统计。

        Raises:
            OSError: staging、复制或原子提交失败时抛出。
            ValueError: 需要重写的旧 JSON 文件内容无效时抛出。
        """
        if self.marker_file.exists():
            return LegacyMigrationResult(False, 0, 0, self.marker_file)

        target_root = self.paths.user_data_root
        staging_root = target_root / _STAGING_NAME
        target_root.mkdir(parents=True, exist_ok=True)
        if staging_root.exists():
            shutil.rmtree(staging_root)
        staging_root.mkdir(parents=True)

        try:
            self._stage_legacy_data(staging_root)
            self._rewrite_staged_paths(staging_root)
            copied, skipped = self._commit_staging(staging_root)
            self._write_marker(copied, skipped)
        except Exception:
            # staging 只包含迁移器本次创建的副本，失败时可安全清理并重试。
            if staging_root.exists():
                shutil.rmtree(staging_root)
            raise

        return LegacyMigrationResult(True, copied, skipped, self.marker_file)

    def _stage_legacy_data(self, staging_root: Path) -> None:
        """按新目录结构把旧数据复制到 staging。"""
        primary_root = (
            self.legacy_application_root
            if self.paths.packaged
            else self.paths.resource_root
        )
        legacy_config = primary_root / "config"
        self._copy_file(legacy_config / "config.json", staging_root / "config" / "config.json")
        self._copy_file(
            legacy_config / "import_file_list.json",
            staging_root / "config" / "import_file_list.json",
        )
        self._copy_file(
            legacy_config / "meta.json",
            staging_root / "config" / "model_meta.json",
        )
        self._copy_tree(primary_root / "logs", staging_root / "logs")
        self._copy_tree(
            self.legacy_application_root / "models",
            staging_root / "models",
        )
        self._copy_tree(
            legacy_config / "data_pool",
            staging_root / "data" / "data_pool",
        )

        legacy_sessions = legacy_config / "sessions"
        self._copy_tree(
            legacy_sessions / "full_speed",
            staging_root / "data" / "sessions" / "full_speed",
        )
        if legacy_sessions.is_dir():
            interactive_target = staging_root / "data" / "sessions" / "interactive"
            for child in legacy_sessions.iterdir():
                if child.name == "full_speed":
                    continue
                if child.is_dir():
                    self._copy_tree(child, interactive_target / child.name)
                elif child.is_file():
                    self._copy_file(child, interactive_target / child.name)

    @staticmethod
    def _copy_file(source: Path, target: Path) -> None:
        """把存在的普通文件复制到 staging。"""
        if not source.is_file() or source.is_symlink():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def _copy_tree(self, source: Path, target: Path) -> None:
        """递归复制目录，忽略符号链接。"""
        if not source.is_dir() or source.is_symlink():
            return
        for source_file in source.rglob("*"):
            if not source_file.is_file() or source_file.is_symlink():
                continue
            self._copy_file(source_file, target / source_file.relative_to(source))

    def _rewrite_staged_paths(self, staging_root: Path) -> None:
        """重写配置、模型元数据和 Session 内部的应用自有路径。"""
        config_file = staging_root / "config" / "config.json"
        if config_file.is_file():
            config = self._load_json_object(config_file)
            system_group = config.setdefault("System", {})
            if isinstance(system_group, dict):
                system_group["LogDir"] = str(self.paths.log_dir)
                system_group["ConfigSchemaVersion"] = 1
            model_group = config.setdefault("model", {})
            if isinstance(model_group, dict):
                model_group["userModelRootDir"] = str(self.paths.user_model_dir)
                self._rewrite_model_config(model_group)
            self._write_json(config_file, config)

        metadata_file = staging_root / "config" / "model_meta.json"
        if metadata_file.is_file():
            metadata = self._load_json_object(metadata_file)
            for group_name in ("names", "remarks"):
                mapping = metadata.get(group_name)
                if isinstance(mapping, dict):
                    metadata[group_name] = {
                        str(self._remap_model_path(path)): value
                        for path, value in mapping.items()
                    }
            self._write_json(metadata_file, metadata)

        sessions_root = staging_root / "data" / "sessions"
        if sessions_root.is_dir():
            for session_file in sessions_root.rglob("session.json"):
                session = self._load_json_object(session_file)
                selection = session.get("model_selection")
                if isinstance(selection, dict):
                    for key in ("pa_model_path", "dtoa_model_path"):
                        selection[key] = self._remap_model_path(selection.get(key))
                self._write_json(session_file, session)

    def _rewrite_model_config(self, model_group: dict[str, object]) -> None:
        """重写全局配置中的单模型和多模型路径。"""
        for single_key, plural_key in (
            ("paEnabledPath", "paEnabledPaths"),
            ("dtoaEnabledPath", "dtoaEnabledPaths"),
        ):
            model_group[single_key] = self._remap_model_path(model_group.get(single_key))
            paths = model_group.get(plural_key)
            if isinstance(paths, list):
                model_group[plural_key] = [self._remap_model_path(path) for path in paths]

    def _remap_model_path(self, raw_path: object) -> object:
        """只改写可证明属于旧内置目录或旧用户目录的模型路径。"""
        if not isinstance(raw_path, str) or not raw_path.strip():
            return raw_path
        source = Path(raw_path).expanduser()
        try:
            resolved_source = source.resolve()
            old_user_models = (self.legacy_application_root / "models").resolve()
            if resolved_source.is_relative_to(old_user_models):
                return str(self.paths.user_model_dir / resolved_source.relative_to(old_user_models))
            old_resource_models = (
                self.paths.resource_root / "resources" / "models"
            ).resolve()
            if resolved_source.is_relative_to(old_resource_models):
                relative = resolved_source.relative_to(old_resource_models)
                return str(self.paths.resources_dir / "models" / relative)
        except OSError:
            return raw_path

        # 旧安装位置无法提前获知；仅在末三级明确为 resources/models/类型，
        # 且当前内置目录存在同名文件时执行唯一映射。
        parts = source.parts
        if len(parts) >= 4 and tuple(part.lower() for part in parts[-4:-2]) == (
            "resources",
            "models",
        ):
            model_type = parts[-2].upper()
            candidate = self.paths.builtin_model_dir(model_type) / source.name
            if candidate.is_file():
                return str(candidate)
        return raw_path

    def _commit_staging(self, staging_root: Path) -> tuple[int, int]:
        """提交 staging 中的缺失文件，目标已有内容保持不变。"""
        copied = 0
        skipped = 0
        for source_file in sorted(path for path in staging_root.rglob("*") if path.is_file()):
            target_file = self.paths.user_data_root / source_file.relative_to(staging_root)
            if target_file.exists():
                skipped += 1
                continue
            target_file.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source_file, target_file)
            copied += 1
        shutil.rmtree(staging_root)
        return copied, skipped

    def _write_marker(self, copied: int, skipped: int) -> None:
        """原子写入迁移完成标记。"""
        marker_data = {
            "migration_version": _MIGRATION_VERSION,
            "completed_at": datetime.now().isoformat(),
            "copied_files": copied,
            "skipped_files": skipped,
        }
        temporary_marker = self.marker_file.with_suffix(".tmp")
        self._write_json(temporary_marker, marker_data)
        os.replace(temporary_marker, self.marker_file)

    @staticmethod
    def _load_json_object(file_path: Path) -> dict[str, object]:
        """读取并要求 JSON 顶层为对象。"""
        try:
            value = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"旧数据 JSON 无效: {file_path}") from error
        if not isinstance(value, dict):
            raise ValueError(f"旧数据 JSON 顶层必须为对象: {file_path}")
        return value

    @staticmethod
    def _write_json(file_path: Path, value: dict[str, object]) -> None:
        """以 UTF-8 和稳定缩进写入 JSON 对象。"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def migrate_legacy_user_data() -> LegacyMigrationResult:
    """使用当前应用路径执行旧数据迁移。

    Returns:
        LegacyMigrationResult: 本次迁移统计。

    Raises:
        OSError: 文件迁移失败时抛出。
        ValueError: 旧 JSON 数据无效时抛出。
    """
    return LegacyDataMigrator().migrate()
