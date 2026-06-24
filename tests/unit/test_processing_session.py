from datetime import datetime

import numpy as np

from core.models.processing_session import (
    ProcessingSession,
    ProcessingStage,
    SliceProcessStatus,
)
from core.models.slice_result import SingleSlice, SliceResult


def test_processing_session_owns_metadata_and_snapshots() -> None:
    """ProcessingSession 应持有 session 级元数据与快照。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    session = ProcessingSession(source_path="E:/data/a.xlsx", source_type="excel")

    assert session.display_name == "a.xlsx"
    assert session.config_snapshot is not None
    assert session.model_selection.pa_model_path is None
    assert isinstance(session.last_opened_at, datetime)
    assert session.restored_from_store is False


def test_processing_session_defaults_are_session_local() -> None:
    """ProcessingSession 默认展示名和快照对象应保持会话隔离。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    first_session = ProcessingSession()
    second_session = ProcessingSession()

    assert first_session.display_name == f"Session {first_session.session_id}"
    assert first_session.config_snapshot is not second_session.config_snapshot
    assert first_session.model_selection is not second_session.model_selection

    # 修改一个 session 的快照，不应影响另一个 session。
    first_session.config_snapshot.clustering.eps_cf = 9.0
    first_session.model_selection.pa_model_path = "E:/models/pa.pt"

    assert second_session.config_snapshot.clustering.eps_cf != 9.0
    assert second_session.model_selection.pa_model_path is None


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


def test_reset_to_imported_clears_downstream_products() -> None:
    """关闭再启用时应清空导入后所有产物并回退到 IMPORTED。

    Args:
        无。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    session = ProcessingSession()
    # 模拟导入完成后推进到聚类阶段。
    session.stage = ProcessingStage.CLUSTERED
    session.slice_result = SliceResult(
        slices=[
            SingleSlice(index=0, data=np.empty((0, 5)), time_range=(0.0, 250.0)),
        ]
    )
    session.reset_slice_processing_states(1)

    # 执行重置。
    session.reset_to_imported()

    # 保留导入产物，清空下游。
    assert session.stage == ProcessingStage.IMPORTED
    assert session.preprocess_result is None
    assert session.slice_result is None
    assert session.cluster_result is None
    assert session.slice_processing_states == {}
    assert session.recognition_result is None
    assert session.merge_result is None
