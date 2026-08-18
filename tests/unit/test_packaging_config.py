"""依赖锁定与 Windows 打包配置静态测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_uses_local_qfluentwidgets_source() -> None:
    """运行依赖必须覆盖本地组件库依赖且不得再次安装 PyPI 组件库。"""
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = project["project"]["dependencies"]

    assert project["project"]["requires-python"] == ">=3.12,<3.13"
    assert any(value.startswith("PyQt6==") for value in dependencies)
    assert any(value.startswith("PyQt6-Frameless-Window==") for value in dependencies)
    assert any(value.startswith("darkdetect==") for value in dependencies)
    assert not any("Fluent-Widgets" in value for value in dependencies)
    assert (PROJECT_ROOT / "uv.lock").is_file()


def test_default_model_manifest_matches_release_assets() -> None:
    """默认模型清单中的大小和 SHA-256 必须与待打包文件完全一致。"""
    manifest = json.loads(
        (PROJECT_ROOT / "packaging" / "model-manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["schema_version"] == 1
    assert len(manifest["models"]) == 2
    for model in manifest["models"]:
        model_path = PROJECT_ROOT / model["path"]
        content = model_path.read_bytes()
        assert len(content) == model["size"]
        assert hashlib.sha256(content).hexdigest() == model["sha256"]


def test_windows_packaging_keeps_program_and_user_data_separate() -> None:
    """PyInstaller 与 Inno 配置必须采用 onedir 和按用户安装。"""
    spec_text = (
        PROJECT_ROOT / "packaging" / "RadarIdentifySystem.spec"
    ).read_text(encoding="utf-8")
    installer_text = (
        PROJECT_ROOT / "packaging" / "RadarIdentifySystem.iss"
    ).read_text(encoding="utf-8")

    assert 'contents_directory="_internal"' in spec_text
    assert 'console=False' in spec_text
    assert '(str(ROOT / "resources"), "resources")' in spec_text
    assert 'runtime_hooks=[str(ONNXRUNTIME_HOOK)]' in spec_text
    assert "SYSTEM_MSVC_RUNTIME_NAMES" not in spec_text
    assert (
        PROJECT_ROOT
        / "packaging"
        / "runtime_hooks"
        / "preload_onnxruntime.py"
    ).is_file()
    assert "DefaultDirName={localappdata}\\Programs\\{#MyAppName}" in installer_text
    assert "PrivilegesRequired=lowest" in installer_text
    assert "MSVCP140_1.dll" not in installer_text
    assert "[UninstallDelete]" not in installer_text
    assert "{localappdata}\\RadarIdentifySystem" in installer_text
