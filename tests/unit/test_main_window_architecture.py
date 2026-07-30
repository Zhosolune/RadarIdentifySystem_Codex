"""主窗口职责边界与应用装配回归测试。"""

from __future__ import annotations

import ast
from pathlib import Path

from app.application import create_application_services
from infra.session_store import SessionStore
from runtime.session_registry import SessionRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_main_window_does_not_import_core_or_infra() -> None:
    """主窗口不得重新直接依赖核心模型或基础设施实现。"""
    source = (PROJECT_ROOT / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )
    module = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert "core" not in imported_roots
    assert "infra" not in imported_roots
    assert ".store.root_dir" not in source
    assert "QFileDialog" not in source
    assert "ExcelResultExporter" not in source


def test_application_services_own_related_storage_roots(tmp_path: Path) -> None:
    """应用装配入口应统一派生数据池和全速 Session 的测试目录。"""
    session_registry = SessionRegistry(SessionStore(tmp_path / "sessions"))

    services = create_application_services(
        session_registry=session_registry,
    )

    assert (
        services.data_pool_registry.store.root_dir
        == tmp_path / "data_pool"
    )
    assert (
        services.full_speed_session_registry.session_registry.store.root_dir
        == tmp_path / "sessions" / "full_speed"
    )
    assert (
        services.session_coordinator.session_registry
        is services.session_registry
    )
