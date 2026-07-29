"""数据池模型、持久化和 Session 共享边界测试。"""

from __future__ import annotations

import json

import numpy as np
import pytest

from core.models.dashboard_info import ExcelDashboardInfo
from core.models.data_package import DataPackage
from core.models.processing_session import ProcessingMode, ProcessingSession
from core.models.pulse_batch import PulseBatch
from core.models.slice_result import PreprocessResult
from infra.data_pool_store import DataPoolStore
from runtime.data_pool_registry import DataPoolRegistry


def _build_package(package_id: str = "package-1") -> DataPackage:
    """构造带完整摘要的测试数据包。"""
    raw_data = np.array(
        [
            [5000.0, 1.0, 90.0, 10.0, 11.0, 0.0],
            [5001.0, 1.2, 91.0, 12.0, 13.0, 100.0],
        ]
    )
    processed_data = raw_data.copy()
    dashboard = ExcelDashboardInfo(
        total_pulses=2,
        removed_pulses=0,
        amplitude_dropped_pulses=0,
        duration=100.0,
        band="C波段",
        estimated_slice_count=1,
    )
    return DataPackage(
        package_id=package_id,
        raw_batch=PulseBatch(
            raw_data,
            source_path="E:/data/demo.xlsx",
            source_type="excel",
            total_pulses=2,
        ),
        preprocess_result=PreprocessResult(
            processed_data,
            total_pulses=2,
            time_range=100.0,
            estimated_slice_count=1,
            band="C波段",
            dashboard_info=dashboard,
        ),
        dashboard_info=dashboard,
        data_format="new",
    )


def test_data_package_is_shared_read_only_between_sessions() -> None:
    """同一数据包可创建多个 Session，输入共享且结果槽位独立。"""
    package = _build_package()
    interactive = ProcessingSession.from_data_package(package)
    full_speed = ProcessingSession.from_data_package(
        package,
        processing_mode=ProcessingMode.FULL_SPEED,
    )

    assert interactive.raw_batch is full_speed.raw_batch
    assert interactive.preprocess_result is full_speed.preprocess_result
    assert interactive.data_package_id == full_speed.data_package_id
    assert interactive.slice_result is None
    assert full_speed.slice_result is None
    with pytest.raises(ValueError):
        package.preprocess_result.data[0, 0] = 1.0


def test_data_pool_store_round_trip_and_recovers_from_broken_index(
    tmp_path,
) -> None:
    """数据包往返后保持只读，索引损坏时仍从完整目录恢复。"""
    store = DataPoolStore(tmp_path / "pool")
    package = _build_package()
    store.save_package(package)

    restored = store.load_package(package.package_id)
    assert restored.source_type == "excel"
    assert restored.data_format == "new"
    assert np.array_equal(
        restored.preprocess_result.data,
        package.preprocess_result.data,
    )
    assert not restored.preprocess_result.data.flags.writeable

    (store.root_dir / "index.json").write_text(
        "{broken",
        encoding="utf-8",
    )
    discovered = store.load_all_packages()
    assert [item.package_id for item in discovered] == [package.package_id]


def test_data_pool_registry_blocks_deleting_referenced_package(
    tmp_path,
) -> None:
    """仍被任一 Session 引用的数据包不能从数据池删除。"""
    registry = DataPoolRegistry(DataPoolStore(tmp_path / "pool"))
    package = registry.register(_build_package())

    with pytest.raises(RuntimeError, match="仍被 Session 引用"):
        registry.delete(
            package.package_id,
            referenced_package_ids={package.package_id},
        )

    assert registry.delete(package.package_id)
    assert registry.get(package.package_id) is None
    index_payload = json.loads(
        (registry.store.root_dir / "index.json").read_text(encoding="utf-8")
    )
    assert index_payload["package_ids"] == []
