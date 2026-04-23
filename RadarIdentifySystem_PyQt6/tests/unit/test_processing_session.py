import numpy as np

from core.models.processing_session import (
    ProcessingSession,
    ProcessingStage,
    SliceProcessStatus,
)
from core.models.slice_result import SingleSlice, SliceResult


def test_slice_processing_state_tracks_partial_cluster_progress() -> None:
    """测试切片级聚类状态与全局阶段分离。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    session = ProcessingSession()
    session.slice_result = SliceResult(
        slices=[
            SingleSlice(index=0, data=np.empty((0, 5)), time_range=(0.0, 250.0)),
            SingleSlice(index=1, data=np.empty((0, 5)), time_range=(250.0, 500.0)),
        ]
    )

    # 重置切片状态
    session.reset_slice_processing_states(session.slice_count)
    # 推进全局切片阶段
    session.stage = ProcessingStage.SLICED

    # 标记第一片聚类成功
    session.mark_slice_cluster_running(0)
    session.mark_slice_cluster_succeeded(0)

    assert session.is_slice_clustered(0) is True
    assert session.is_slice_clustered(1) is False
    assert session.clustered_slice_count == 1
    assert session.are_all_slices_clustered() is False
    assert session.is_clustered is False
    assert session.stage == ProcessingStage.SLICED


def test_slice_processing_state_requires_all_slices_to_finish() -> None:
    """测试全部切片完成后才视为全量聚类完成。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    session = ProcessingSession()
    session.slice_result = SliceResult(
        slices=[
            SingleSlice(index=0, data=np.empty((0, 5)), time_range=(0.0, 250.0)),
            SingleSlice(index=1, data=np.empty((0, 5)), time_range=(250.0, 500.0)),
        ]
    )

    # 初始化切片状态
    session.reset_slice_processing_states(session.slice_count)

    # 标记全部切片成功
    session.mark_slice_cluster_succeeded(0)
    session.mark_slice_cluster_succeeded(1)

    assert session.clustered_slice_count == 2
    assert session.are_all_slices_clustered() is True
    assert session.is_clustered is True


def test_slice_processing_state_records_failure() -> None:
    """测试切片失败状态与错误消息记录。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    session = ProcessingSession()
    session.reset_slice_processing_states(1)

    # 标记当前切片失败
    session.mark_slice_cluster_failed(0, "mock error")
    slice_state = session.get_slice_processing_state(0)

    assert slice_state.cluster_status == SliceProcessStatus.FAILED
    assert slice_state.last_cluster_error == "mock error"
