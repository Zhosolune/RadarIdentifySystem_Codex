"""ONNX 单模型运行池、设备选择与真实预热测试。"""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
from pytest import MonkeyPatch

import infra.onnx_runtime_pool as runtime_pool_module
from infra.onnx_runtime_pool import OnnxModelRuntime, OnnxModelRuntimePool
from infra.onnx_service import OnnxInferenceService


class _FakeSessionOptions:
    """记录 ONNX Session 线程配置。"""

    def __init__(self) -> None:
        """初始化与 ONNX Runtime 同名的配置字段。"""
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.enable_mem_pattern = True


class _FakeInferenceSession:
    """记录模型 Session 的 Provider、输入契约和推理调用。"""

    calls: list[dict[str, object]] = []

    def __init__(
        self,
        model_path: str,
        sess_options: _FakeSessionOptions | None = None,
        providers: list[str] | None = None,
    ) -> None:
        """保存一次伪 Session 构造调用。"""
        self._providers = list(providers or [])
        self._input_shape = (
            [1, 1, 80, 400]
            if "pa" in Path(model_path).stem.lower()
            else [1, 1, 250, 500]
        )
        self.run_inputs: list[np.ndarray] = []
        self.calls.append(
            {
                "model_path": model_path,
                "session_options": sess_options,
                "providers": self._providers,
                "session": self,
            }
        )

    def get_providers(self) -> list[str]:
        """返回当前伪 Session 的 Provider 顺序。"""
        return self._providers

    def get_inputs(self) -> list[SimpleNamespace]:
        """返回与 PA 或 DTOA 生产张量一致的输入元数据。"""
        return [
            SimpleNamespace(
                name="input",
                shape=list(self._input_shape),
                type="tensor(float)",
            )
        ]

    def run(
        self,
        output_names: object,
        input_feed: dict[str, np.ndarray],
    ) -> list[np.ndarray]:
        """记录 dummy 输入并返回可供预测后处理使用的伪 logits。"""
        self.run_inputs.append(input_feed["input"])
        return [np.zeros((1, 8), dtype=np.float32)]


class _FakeOrt:
    """提供设备选择测试所需的最小 ONNX Runtime API。"""

    SessionOptions = _FakeSessionOptions
    InferenceSession = _FakeInferenceSession
    ExecutionMode = SimpleNamespace(ORT_SEQUENTIAL="sequential")
    available_providers: list[str] = [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """返回测试指定的可用 Provider。"""
        return list(cls.available_providers)


def _model_paths(tmp_path: Path) -> tuple[Path, Path]:
    """创建两个存在的伪 ONNX 模型文件。"""
    pa_path = tmp_path / "pa.onnx"
    dtoa_path = tmp_path / "dtoa.onnx"
    pa_path.touch()
    dtoa_path.touch()
    return pa_path, dtoa_path


def test_gpu_preference_runs_real_dummy_inference_with_production_shapes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """GPU 可用时应限制线程，并为每个模型执行一次生产形状的 run。"""
    pa_path, dtoa_path = _model_paths(tmp_path)
    _FakeInferenceSession.calls = []
    _FakeOrt.available_providers = [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    monkeypatch.setattr(runtime_pool_module, "ort", _FakeOrt)

    OnnxInferenceService(
        dtoa_model_path=str(dtoa_path),
        pa_model_path=str(pa_path),
        temp_dir=str(tmp_path),
        device_preference="GPU",
        intra_op_num_threads=1,
    )

    assert len(_FakeInferenceSession.calls) == 2
    observed_shapes: set[tuple[int, ...]] = set()
    for call in _FakeInferenceSession.calls:
        assert call["providers"] == [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]
        options = call["session_options"]
        assert options.intra_op_num_threads == 1
        assert options.inter_op_num_threads == 1
        assert options.execution_mode == "sequential"
        session = call["session"]
        assert len(session.run_inputs) == 1
        observed_shapes.add(tuple(session.run_inputs[0].shape))
        assert session.run_inputs[0].dtype == np.float32
    assert observed_shapes == {(1, 1, 80, 400), (1, 1, 250, 500)}


def test_gpu_preference_falls_back_when_no_gpu_provider_is_available(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """GPU Provider 不可用时应回退 CPU Provider。"""
    pa_path, dtoa_path = _model_paths(tmp_path)
    _FakeInferenceSession.calls = []
    _FakeOrt.available_providers = ["CPUExecutionProvider"]
    monkeypatch.setattr(runtime_pool_module, "ort", _FakeOrt)

    OnnxInferenceService(
        dtoa_model_path=str(dtoa_path),
        pa_model_path=str(pa_path),
        temp_dir=str(tmp_path),
        device_preference="GPU",
        intra_op_num_threads=1,
    )

    assert [call["providers"] for call in _FakeInferenceSession.calls] == [
        ["CPUExecutionProvider"],
        ["CPUExecutionProvider"],
    ]


def test_runtime_pool_deduplicates_same_model_future_and_dummy_run(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """同模型并发提交应复用同一 Future，且只加载和预热一次。"""
    pa_path, _ = _model_paths(tmp_path)
    _FakeInferenceSession.calls = []
    _FakeOrt.available_providers = ["CPUExecutionProvider"]
    monkeypatch.setattr(runtime_pool_module, "ort", _FakeOrt)
    runtime_pool = OnnxModelRuntimePool(max_workers=1)

    first = runtime_pool.preload("PA", str(pa_path))
    second = runtime_pool.preload("pa", str(pa_path))
    runtime = first.result(timeout=5)
    worker_threads = list(runtime_pool._executor._threads)
    runtime_pool.shutdown()

    assert second is first
    assert runtime.session is _FakeInferenceSession.calls[0]["session"]
    assert len(_FakeInferenceSession.calls) == 1
    assert len(runtime.session.run_inputs) == 1
    assert worker_threads
    assert all(not thread.is_alive() for thread in worker_threads)


def test_interactive_combinations_share_single_model_runtime_pool(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """多个轻量组合应只创建单模型数量之和的底层 Session。"""
    model_paths = {
        name: tmp_path / f"{name}.onnx"
        for name in ("pa-a", "pa-b", "dtoa-a", "dtoa-b")
    }
    for model_path in model_paths.values():
        model_path.touch()
    _FakeInferenceSession.calls = []
    _FakeOrt.available_providers = ["CPUExecutionProvider"]
    monkeypatch.setattr(runtime_pool_module, "ort", _FakeOrt)
    runtime_pool = OnnxModelRuntimePool(max_workers=1)

    services: list[OnnxInferenceService] = []
    for pa_name in ("pa-a", "pa-b"):
        for dtoa_name in ("dtoa-a", "dtoa-b"):
            services.append(
                OnnxInferenceService(
                    dtoa_model_path=str(model_paths[dtoa_name]),
                    pa_model_path=str(model_paths[pa_name]),
                    temp_dir=str(tmp_path),
                    runtime_pool=runtime_pool,
                )
            )
    runtime_pool.shutdown()

    assert len(services) == 4
    assert len(_FakeInferenceSession.calls) == 4
    assert {
        Path(str(call["model_path"])).name
        for call in _FakeInferenceSession.calls
    } == {
        "pa-a.onnx",
        "pa-b.onnx",
        "dtoa-a.onnx",
        "dtoa-b.onnx",
    }
    assert all(
        len(call["session"].run_inputs) == 1
        for call in _FakeInferenceSession.calls
    )


def test_service_construction_does_not_wait_for_background_model_load(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """交互式组合构造只绑定 Future，不应等待后台模型加载完成。"""
    pa_path, dtoa_path = _model_paths(tmp_path)
    release_loader = Event()

    def _blocking_loader(
        model_type: str,
        model_path: str,
        **kwargs: object,
    ) -> OnnxModelRuntime:
        """等待测试放行后返回最小模型运行时。"""
        release_loader.wait(timeout=5)
        return OnnxModelRuntime(
            model_type=model_type,
            model_path=model_path,
            session=SimpleNamespace(),
            input_name="input",
            input_shape=(1, 1, 1, 1),
            providers=("CPUExecutionProvider",),
        )

    monkeypatch.setattr(
        runtime_pool_module,
        "load_onnx_model_runtime",
        _blocking_loader,
    )
    runtime_pool = OnnxModelRuntimePool(max_workers=1)

    service = OnnxInferenceService(
        dtoa_model_path=str(dtoa_path),
        pa_model_path=str(pa_path),
        temp_dir=str(tmp_path),
        runtime_pool=runtime_pool,
    )

    assert service._dtoa_runtime_future is not None
    assert service._pa_runtime_future is not None
    assert not service._dtoa_runtime_future.done()
    release_loader.set()
    runtime_pool.shutdown()


def test_service_resolves_only_preheated_runtime_from_shared_future(
    tmp_path: Path,
) -> None:
    """识别侧解析模型时应直接取得运行池 Future 中的已预热 Session。"""
    pa_path, dtoa_path = _model_paths(tmp_path)
    session = SimpleNamespace()
    completed: Future[OnnxModelRuntime] = Future()
    completed.set_result(
        OnnxModelRuntime(
            model_type="PA",
            model_path=str(pa_path),
            session=session,
            input_name="input",
            input_shape=(1, 1, 80, 400),
            providers=("CPUExecutionProvider",),
        )
    )

    class _CompletedPool:
        """为两个模型返回同一已完成 Future 的最小运行池。"""

        def preload(
            self,
            model_type: str,
            model_path: str,
        ) -> Future[OnnxModelRuntime]:
            """返回测试预先完成的 Future。"""
            return completed

    service = OnnxInferenceService(
        dtoa_model_path=str(dtoa_path),
        pa_model_path=str(pa_path),
        temp_dir=str(tmp_path),
        runtime_pool=_CompletedPool(),
    )

    assert service._resolve_model_session("PA") is session
    assert service._resolve_model_session("PA") is session
