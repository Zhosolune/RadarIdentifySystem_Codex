"""统一应用路径布局测试。"""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from app.application import create_application_services
from utils.paths import build_app_paths


def test_build_app_paths_separates_program_data_and_temp(tmp_path: Path) -> None:
    """正式版资源、用户数据和临时目录必须属于三个独立根。"""
    install_root = tmp_path / "install"
    resource_root = install_root / "_internal"
    data_root = tmp_path / "local-app-data" / "RadarIdentifySystem"
    temp_root = tmp_path / "temp" / "RadarIdentifySystem"

    paths = build_app_paths(
        packaged=True,
        install_root=install_root,
        resource_root=resource_root,
        data_root=data_root,
        temp_root=temp_root,
    )

    assert paths.app_name == "RadarIdentifySystem"
    assert paths.install_root == install_root.resolve()
    assert paths.resources_dir == resource_root.resolve() / "resources"
    assert paths.builtin_model_dir("PA") == resource_root.resolve() / "resources" / "models" / "PA"
    assert paths.config_file == data_root.resolve() / "config" / "config.json"
    assert paths.log_dir == data_root.resolve() / "logs"
    assert paths.session_dir == data_root.resolve() / "data" / "sessions" / "interactive"
    assert paths.full_speed_session_dir == data_root.resolve() / "data" / "sessions" / "full_speed"
    assert paths.data_pool_dir == data_root.resolve() / "data" / "data_pool"
    assert paths.user_model_dir == data_root.resolve() / "models"
    assert paths.cache_dir == data_root.resolve() / "cache"
    assert paths.runtime_temp_dir.parent == temp_root.resolve()
    assert not paths.config_file.is_relative_to(paths.install_root)
    assert not paths.runtime_temp_dir.is_relative_to(paths.install_root)


def test_development_paths_use_independent_application_name(tmp_path: Path) -> None:
    """源码开发版必须使用独立应用标识且不受当前工作目录影响。"""
    paths = build_app_paths(
        packaged=False,
        data_root=tmp_path / "data",
        resource_root=tmp_path / "source",
        temp_root=tmp_path / "temp",
    )

    assert paths.app_name == "RadarIdentifySystem-Dev"
    assert paths.user_data_root == (tmp_path / "data").resolve()
    assert paths.resource_root == (tmp_path / "source").resolve()


def test_default_application_services_use_three_independent_roots(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """默认装配必须分别注入交互 Session、全速 Session 和数据池目录。"""
    data_root = tmp_path / "app-data"
    monkeypatch.setenv("RADAR_IDENTIFY_DATA_ROOT", str(data_root))

    services = create_application_services()

    assert services.session_registry.store.root_dir == data_root / "data" / "sessions" / "interactive"
    assert (
        services.full_speed_session_registry.session_registry.store.root_dir
        == data_root / "data" / "sessions" / "full_speed"
    )
    assert services.data_pool_registry.store.root_dir == data_root / "data" / "data_pool"
