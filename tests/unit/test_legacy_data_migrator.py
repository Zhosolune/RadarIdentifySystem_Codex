"""旧版用户数据目录迁移测试。"""

from __future__ import annotations

import json
from pathlib import Path

from infra.legacy_data_migrator import LegacyDataMigrator
from utils.paths import build_app_paths


def _write_json(file_path: Path, value: dict[str, object]) -> None:
    """写入测试 JSON 文件。"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_migrator_splits_storage_and_rewrites_owned_model_paths(
    tmp_path: Path,
) -> None:
    """迁移应拆分三类存储并同步重写配置、元数据和两类 Session。"""
    source_root = tmp_path / "source"
    legacy_user_root = tmp_path / "legacy-user"
    target_root = tmp_path / "target"
    pa_name = "default-pa.onnx"
    dtoa_name = "user-dtoa.onnx"
    builtin_pa = source_root / "resources" / "models" / "PA" / pa_name
    user_dtoa = legacy_user_root / "models" / "DTOA" / dtoa_name
    builtin_pa.parent.mkdir(parents=True)
    builtin_pa.write_bytes(b"pa")
    user_dtoa.parent.mkdir(parents=True)
    user_dtoa.write_bytes(b"dtoa")

    _write_json(
        source_root / "config" / "config.json",
        {
            "System": {"LogDir": str(source_root / "logs")},
            "model": {
                "userModelRootDir": str(legacy_user_root / "models"),
                "paEnabledPath": str(builtin_pa),
                "paEnabledPaths": [str(builtin_pa)],
                "dtoaEnabledPath": str(user_dtoa),
                "dtoaEnabledPaths": [str(user_dtoa)],
            },
        },
    )
    _write_json(
        source_root / "config" / "meta.json",
        {"names": {str(user_dtoa): "自定义 DTOA"}, "remarks": {str(user_dtoa): "备注"}},
    )
    _write_json(
        source_root / "config" / "sessions" / "index.json",
        {"schema_version": 1, "sessions": []},
    )
    _write_json(
        source_root / "config" / "sessions" / "interactive-a" / "session.json",
        {
            "model_selection": {
                "pa_model_path": str(builtin_pa),
                "dtoa_model_path": str(user_dtoa),
            }
        },
    )
    _write_json(
        source_root / "config" / "sessions" / "full_speed" / "full-a" / "session.json",
        {
            "model_selection": {
                "pa_model_path": str(builtin_pa),
                "dtoa_model_path": str(user_dtoa),
            }
        },
    )
    _write_json(
        source_root / "config" / "data_pool" / "index.json",
        {"schema_version": 1, "package_ids": []},
    )
    (source_root / "logs").mkdir(parents=True)
    (source_root / "logs" / "old.log").write_text("old", encoding="utf-8")

    paths = build_app_paths(
        packaged=False,
        data_root=target_root,
        resource_root=source_root,
        install_root=source_root,
        temp_root=tmp_path / "temp",
    )
    migrator = LegacyDataMigrator(
        paths,
        legacy_application_root=legacy_user_root,
    )

    result = migrator.migrate()

    migrated_user_dtoa = paths.user_model_dir / "DTOA" / dtoa_name
    assert result.performed is True
    assert migrated_user_dtoa.read_bytes() == b"dtoa"
    assert (paths.session_dir / "index.json").is_file()
    assert (paths.session_dir / "interactive-a" / "session.json").is_file()
    assert (paths.full_speed_session_dir / "full-a" / "session.json").is_file()
    assert (paths.data_pool_dir / "index.json").is_file()
    assert (paths.log_dir / "old.log").is_file()

    config = json.loads(paths.config_file.read_text(encoding="utf-8"))
    assert config["System"]["LogDir"] == str(paths.log_dir)
    assert config["System"]["ConfigSchemaVersion"] == 1
    assert config["model"]["userModelRootDir"] == str(paths.user_model_dir)
    assert config["model"]["paEnabledPath"] == str(builtin_pa)
    assert config["model"]["dtoaEnabledPath"] == str(migrated_user_dtoa)

    metadata = json.loads(paths.model_metadata_file.read_text(encoding="utf-8"))
    assert metadata["names"] == {str(migrated_user_dtoa): "自定义 DTOA"}
    interactive = json.loads(
        (paths.session_dir / "interactive-a" / "session.json").read_text(encoding="utf-8")
    )
    full_speed = json.loads(
        (paths.full_speed_session_dir / "full-a" / "session.json").read_text(encoding="utf-8")
    )
    assert interactive["model_selection"]["dtoa_model_path"] == str(migrated_user_dtoa)
    assert full_speed["model_selection"]["dtoa_model_path"] == str(migrated_user_dtoa)
    assert builtin_pa.read_bytes() == b"pa"
    assert user_dtoa.read_bytes() == b"dtoa"

    second_result = migrator.migrate()
    assert second_result.performed is False


def test_migrator_does_not_overwrite_existing_target_file(tmp_path: Path) -> None:
    """目标已有配置时必须保持目标优先并完成幂等标记。"""
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    legacy_user_root = tmp_path / "legacy-user"
    _write_json(source_root / "config" / "config.json", {"source": True})
    _write_json(target_root / "config" / "config.json", {"target": True})
    paths = build_app_paths(
        packaged=False,
        data_root=target_root,
        resource_root=source_root,
        temp_root=tmp_path / "temp",
    )

    result = LegacyDataMigrator(
        paths,
        legacy_application_root=legacy_user_root,
    ).migrate()

    assert result.skipped_files == 1
    assert json.loads(paths.config_file.read_text(encoding="utf-8")) == {"target": True}
