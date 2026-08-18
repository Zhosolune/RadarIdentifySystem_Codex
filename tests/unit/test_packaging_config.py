"""依赖锁定与 Windows 打包配置静态测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
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
    assert (
        'ROOT / "build" / "packaging" / "RadarIdentifySystem.version.txt"'
        in spec_text
    )
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
    assert "AppId={{7D2B1229-344B-47D8-A931-53B4CF8FE2EA}" in installer_text
    assert "PrivilegesRequired=lowest" in installer_text
    assert "MSVCP140_1.dll" not in installer_text
    assert "[UninstallDelete]" not in installer_text
    assert "[InstallDelete]" in installer_text
    install_delete_section = installer_text.split("[InstallDelete]", maxsplit=1)[1]
    install_delete_section = install_delete_section.split("[", maxsplit=1)[0]
    assert 'Type: filesandordirs; Name: "{app}\\_internal"' in install_delete_section
    assert "{localappdata}\\RadarIdentifySystem" not in install_delete_section
    assert 'Name: "{app}"' not in install_delete_section
    assert "{localappdata}\\RadarIdentifySystem" in installer_text
    assert "procedure CurUninstallStep(UninstallStep: TUninstallStep);" in installer_text


def test_build_script_supports_custom_and_registered_inno_setup() -> None:
    """构建脚本应支持显式路径并自动发现非系统盘的 Inno Setup。"""
    build_text = (PROJECT_ROOT / "packaging" / "build.ps1").read_text(
        encoding="utf-8"
    )

    assert '[string]$IsccPath = ""' in build_text
    assert "function Resolve-InnoSetupCompiler" in build_text
    assert "Inno Setup 6_is1" in build_text
    assert "InstallLocation" in build_text
    assert "Resolve-InnoSetupCompiler -RequestedPath $IsccPath" in build_text
    assert '& $ResolvedIsccPath "/DMyAppVersion=$Version"' in build_text


def test_build_uses_pyproject_as_single_version_source(tmp_path: Path) -> None:
    """构建时应从 pyproject.toml 生成 EXE 与安装器共用的版本。"""
    build_text = (PROJECT_ROOT / "packaging" / "build.ps1").read_text(
        encoding="utf-8"
    )
    installer_text = (
        PROJECT_ROOT / "packaging" / "RadarIdentifySystem.iss"
    ).read_text(encoding="utf-8")
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    version = project["project"]["version"]

    version_module = runpy.run_path(
        str(PROJECT_ROOT / "packaging" / "version_info.py")
    )
    output_file = tmp_path / "RadarIdentifySystem.version.txt"
    generated_version = version_module["generate_version_resource"](
        PROJECT_ROOT / "pyproject.toml",
        output_file,
    )
    resource_text = output_file.read_text(encoding="utf-8")

    assert generated_version == version
    assert f"StringStruct('FileVersion', '{version}')" in resource_text
    assert f"StringStruct('ProductVersion', '{version}')" in resource_text
    assert "[string]$Version" not in build_text
    assert "--project-file" in build_text
    assert "--output-file $VersionResourcePath" in build_text
    assert '#define MyAppVersion "0.1.0"' not in installer_text
    assert not (PROJECT_ROOT / "packaging" / "RadarIdentifySystem.version.txt").exists()
