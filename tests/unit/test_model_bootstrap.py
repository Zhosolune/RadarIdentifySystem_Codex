"""模型启用集合、组合缓存与预热行为测试。"""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from app import model_bootstrap
from core.models.session_model import SessionModelSelection


class _FakeQConfig:
    """保存测试配置项值的最小 qconfig 替身。"""

    def __init__(self, values: dict[object, object]) -> None:
        """初始化配置值映射。"""
        self.values = values

    def get(self, item: object) -> object:
        """返回指定配置项当前值。"""
        return self.values.get(item)

    def set(self, item: object, value: object) -> None:
        """写入指定配置项值。"""
        self.values[item] = value


def test_enabled_model_paths_migrate_legacy_single_path(
    monkeypatch: MonkeyPatch,
) -> None:
    """旧版单模型配置应迁移为只含该路径的启用集合。"""
    paths_item = object()
    legacy_item = object()
    fake_config = _FakeQConfig(
        {paths_item: [], legacy_item: r"C:\models\pa-default.onnx"}
    )
    monkeypatch.setattr(model_bootstrap, "qconfig", fake_config)
    monkeypatch.setattr(
        model_bootstrap,
        "_get_enabled_paths_config_item",
        lambda model_type: paths_item,
    )
    monkeypatch.setattr(
        model_bootstrap,
        "_get_legacy_enabled_path_config_item",
        lambda model_type: legacy_item,
    )

    enabled_paths = model_bootstrap.get_enabled_model_paths("PA")

    assert enabled_paths == [r"C:\models\pa-default.onnx"]
    assert fake_config.values[paths_item] == enabled_paths


def test_resolve_enabled_models_preserves_all_existing_candidates(
    monkeypatch: MonkeyPatch,
) -> None:
    """解析启用集合时应保留多个有效候选并剔除已删除路径。"""
    available_paths = [
        r"C:\models\pa-a.onnx",
        r"C:\models\pa-b.onnx",
    ]
    monkeypatch.setattr(
        model_bootstrap,
        "get_enabled_model_paths",
        lambda model_type: [available_paths[1], r"C:\models\deleted.onnx"],
    )
    captured: list[list[str]] = []
    monkeypatch.setattr(
        model_bootstrap,
        "set_enabled_model_paths",
        lambda model_type, paths: captured.append(paths),
    )

    resolved = model_bootstrap.resolve_enabled_models(
        "PA",
        model_files=available_paths,
    )

    assert resolved == [available_paths[1]]
    assert captured == [[available_paths[1]]]


def test_set_model_enabled_updates_only_target_membership(
    monkeypatch: MonkeyPatch,
) -> None:
    """勾选与取消勾选应只增删目标路径，不覆盖其它已启用模型。"""
    pa_a = r"C:\models\pa-a.onnx"
    pa_b = r"C:\models\pa-b.onnx"
    current = [pa_a]
    monkeypatch.setattr(
        model_bootstrap,
        "get_enabled_model_paths",
        lambda model_type: list(current),
    )

    def _capture_paths(model_type: str, paths: list[str]) -> None:
        """保存测试中的最新启用列表。"""
        current[:] = paths

    monkeypatch.setattr(
        model_bootstrap,
        "set_enabled_model_paths",
        _capture_paths,
    )

    assert model_bootstrap.set_model_enabled("PA", pa_b, True) == [pa_a, pa_b]
    assert model_bootstrap.set_model_enabled("PA", pa_a, False) == [pa_b]


def test_inference_service_cache_isolated_by_model_combination(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """不同 PA/DTOA 组合应获得独立服务，同一组合应稳定复用。"""
    created: list[object] = []

    class _FakeInferenceService:
        """记录构造参数的推理服务替身。"""

        def __init__(self, **kwargs: object) -> None:
            """保存单次服务构造参数。"""
            self.kwargs = kwargs
            created.append(self)

    monkeypatch.setattr(
        "infra.onnx_service.OnnxInferenceService",
        _FakeInferenceService,
    )
    model_bootstrap.clear_cached_inference_services()

    try:
        service_a = model_bootstrap.get_cached_inference_service(
            "pa-a.onnx",
            "dtoa-a.onnx",
            str(tmp_path),
        )
        service_a_again = model_bootstrap.get_cached_inference_service(
            "pa-a.onnx",
            "dtoa-a.onnx",
            str(tmp_path),
        )
        service_b = model_bootstrap.get_cached_inference_service(
            "pa-b.onnx",
            "dtoa-b.onnx",
            str(tmp_path),
        )

        assert service_a_again is service_a
        assert service_b is not service_a
        assert len(created) == 2
        runtime_pools = {
            id(service.kwargs["runtime_pool"])
            for service in created
        }
        assert len(runtime_pools) == 1
    finally:
        model_bootstrap.shutdown_model_runtime()


def test_initialize_model_runtime_only_resolves_enabled_configuration(
    monkeypatch: MonkeyPatch,
) -> None:
    """配置初始化不应在 Session 恢复前创建运行池或加载模型。"""
    enabled = {
        "PA": ["pa-a.onnx", "pa-b.onnx"],
        "DTOA": ["dtoa-a.onnx", "dtoa-b.onnx"],
    }
    monkeypatch.setattr(
        model_bootstrap,
        "collect_available_model_files",
        lambda model_type: enabled[model_type],
    )
    monkeypatch.setattr(
        model_bootstrap,
        "resolve_enabled_models",
        lambda model_type, model_files: list(model_files),
    )
    monkeypatch.setattr(
        model_bootstrap,
        "_get_or_create_runtime_pool",
        lambda: (_ for _ in ()).throw(AssertionError("不应创建运行池")),
    )

    mapping = model_bootstrap.initialize_model_runtime(write_log=False)

    assert mapping == enabled


def test_start_preload_uses_session_default_and_remaining_priority(
    monkeypatch: MonkeyPatch,
) -> None:
    """后台预热应按 Session、首项默认和其余启用模型顺序去重。"""
    submitted: list[tuple[str, str]] = []

    class _FakeRuntimePool:
        """记录预热提交顺序的运行池替身。"""

        def preload(self, model_type: str, model_path: str) -> object:
            """记录单模型预热目标。"""
            submitted.append((model_type, model_path))
            return object()

    monkeypatch.setattr(
        model_bootstrap,
        "_get_or_create_runtime_pool",
        lambda: _FakeRuntimePool(),
    )
    enabled = {
        "PA": ["pa-a.onnx", "pa-b.onnx"],
        "DTOA": ["dtoa-a.onnx", "dtoa-b.onnx"],
    }
    selections = [
        SessionModelSelection(
            pa_model_path="pa-b.onnx",
            dtoa_model_path="dtoa-b.onnx",
        ),
        SessionModelSelection(
            pa_model_path="pa-b.onnx",
            dtoa_model_path="dtoa-a.onnx",
        ),
    ]

    model_bootstrap.start_model_runtime_preload(enabled, selections)

    assert submitted == [
        ("PA", "pa-b.onnx"),
        ("DTOA", "dtoa-b.onnx"),
        ("DTOA", "dtoa-a.onnx"),
        ("PA", "pa-a.onnx"),
    ]
    assert len(submitted) == 4


def test_sync_enabled_runtimes_retain_then_preload_candidates(
    monkeypatch: MonkeyPatch,
) -> None:
    """启用集合变化应先淘汰旧索引，再预热当前全部候选。"""
    calls: list[tuple[str, object]] = []

    class _FakeRuntimePool:
        """记录启用集合同步动作的运行池替身。"""

        def retain_enabled(self, model_type: str, paths: list[str]) -> None:
            """记录保留集合。"""
            calls.append(("retain", (model_type, list(paths))))

        def preload(self, model_type: str, path: str) -> object:
            """记录预热目标。"""
            calls.append(("preload", (model_type, path)))
            return object()

    monkeypatch.setattr(model_bootstrap, "_runtime_pool", _FakeRuntimePool())

    model_bootstrap.sync_enabled_model_runtimes(
        "PA",
        ["pa-a.onnx", "pa-b.onnx"],
    )

    assert calls == [
        ("retain", ("PA", ["pa-a.onnx", "pa-b.onnx"])),
        ("preload", ("PA", "pa-a.onnx")),
        ("preload", ("PA", "pa-b.onnx")),
    ]
