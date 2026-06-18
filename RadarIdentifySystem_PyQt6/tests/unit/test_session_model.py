from core.models.session_model import SessionModelSelection


def test_session_model_selection_round_trips_dict() -> None:
    """测试模型选择快照可完成字典往返。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    selection = SessionModelSelection(
        pa_model_path="E:/models/pa.pt",
        dtoa_model_path="E:/models/dtoa.pt",
    )

    restored = SessionModelSelection.from_dict(selection.to_dict())

    assert restored == selection


def test_session_model_selection_ignores_unknown_fields() -> None:
    """测试模型选择快照恢复时忽略未知字段。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    restored = SessionModelSelection.from_dict(
        {
            "pa_model_path": "E:/models/pa.pt",
            "unknown": "ignored",
        }
    )

    assert restored.pa_model_path == "E:/models/pa.pt"
    assert restored.dtoa_model_path is None
    assert "unknown" not in restored.to_dict()


def test_session_model_selection_falls_back_for_invalid_payload() -> None:
    """测试模型选择快照对空载荷和非字典载荷安全回退。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    assert SessionModelSelection.from_dict(None) == SessionModelSelection()
    assert SessionModelSelection.from_dict(["E:/models/pa.pt"]) == SessionModelSelection()


def test_session_model_selection_discards_invalid_paths() -> None:
    """测试模型选择快照丢弃非字符串模型路径。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    restored = SessionModelSelection.from_dict(
        {
            "pa_model_path": 123,
            "dtoa_model_path": object(),
        }
    )

    assert restored.pa_model_path is None
    assert restored.dtoa_model_path is None


def test_session_model_selection_normalizes_blank_paths() -> None:
    """测试模型选择快照将空字符串和纯空白路径视为未选择。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    restored = SessionModelSelection.from_dict(
        {
            "pa_model_path": "",
            "dtoa_model_path": "   ",
        }
    )

    assert restored.pa_model_path is None
    assert restored.dtoa_model_path is None
