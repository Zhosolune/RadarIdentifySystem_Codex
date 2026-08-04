"""ONNX 推理设备选择和线程限制测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch

import infra.onnx_service as onnx_service_module
from infra.onnx_service import OnnxInferenceService


class _FakeSessionOptions:
    """记录 ONNX Session 线程配置。"""

    def __init__(self) -> None:
        """初始化与 ONNX Runtime 同名的配置字段。"""
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None


class _FakeInferenceSession:
    """记录模型 Session 的 Provider 和线程配置。"""

    calls: list[dict[str, object]] = []

    def __init__(
        self,
        model_path: str,
        sess_options: _FakeSessionOptions | None = None,
        providers: list[str] | None = None,
    ) -> None:
        """保存一次伪 Session 构造调用。"""
        self._providers = list(providers or [])
        self.calls.append(
            {
                "model_path": model_path,
                "session_options": sess_options,
                "providers": self._providers,
            }
        )

    def get_providers(self) -> list[str]:
        """返回当前伪 Session 的 Provider 顺序。"""
        return self._providers


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


def test_gpu_preference_uses_available_gpu_and_single_onnx_thread(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """GPU 可用时应优先选用，并限制 ONNX 内部线程。"""
    pa_path, dtoa_path = _model_paths(tmp_path)
    _FakeInferenceSession.calls = []
    _FakeOrt.available_providers = [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    monkeypatch.setattr(onnx_service_module, "ort", _FakeOrt)

    OnnxInferenceService(
        dtoa_model_path=str(dtoa_path),
        pa_model_path=str(pa_path),
        temp_dir=str(tmp_path),
        device_preference="GPU",
        intra_op_num_threads=1,
    )

    assert len(_FakeInferenceSession.calls) == 2
    for call in _FakeInferenceSession.calls:
        assert call["providers"] == [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]
        options = call["session_options"]
        assert options.intra_op_num_threads == 1
        assert options.inter_op_num_threads == 1
        assert options.execution_mode == "sequential"


def test_gpu_preference_falls_back_when_no_gpu_provider_is_available(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """GPU Provider 不可用时应回退 CPU Provider。"""
    pa_path, dtoa_path = _model_paths(tmp_path)
    _FakeInferenceSession.calls = []
    _FakeOrt.available_providers = ["CPUExecutionProvider"]
    monkeypatch.setattr(onnx_service_module, "ort", _FakeOrt)

    OnnxInferenceService(
        dtoa_model_path=str(dtoa_path),
        pa_model_path=str(pa_path),
        temp_dir=str(tmp_path),
        device_preference="GPU",
        intra_op_num_threads=1,
    )

    assert [
        call["providers"] for call in _FakeInferenceSession.calls
    ] == [
        ["CPUExecutionProvider"],
        ["CPUExecutionProvider"],
    ]


def test_interactive_combinations_share_each_underlying_model_session(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """组合预热应按单模型复用底层 Session，避免 PA 与 DTOA 笛卡尔积重复加载。"""
    model_paths = {
        name: tmp_path / f"{name}.onnx"
        for name in ("pa-a", "pa-b", "dtoa-a", "dtoa-b")
    }
    for model_path in model_paths.values():
        model_path.touch()
    _FakeInferenceSession.calls = []
    _FakeOrt.available_providers = ["CPUExecutionProvider"]
    monkeypatch.setattr(onnx_service_module, "ort", _FakeOrt)
    onnx_service_module.clear_shared_model_session_cache()

    for pa_name in ("pa-a", "pa-b"):
        for dtoa_name in ("dtoa-a", "dtoa-b"):
            OnnxInferenceService(
                dtoa_model_path=str(model_paths[dtoa_name]),
                pa_model_path=str(model_paths[pa_name]),
                temp_dir=str(tmp_path),
                reuse_model_sessions=True,
            )

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
