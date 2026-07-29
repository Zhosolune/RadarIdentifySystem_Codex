"""全速处理 Excel 结果保存测试。"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from core.models.cluster_result import (
    ClusterItem,
    ClusterState,
    ClusteringResult,
    SliceClusterResult,
)
from core.models.extraction_result import ExtractedClusterParams
from core.models.merge_result import (
    MergeResult,
    MergedClusterResult,
    SliceMergeResult,
)
from core.models.recognition_result import (
    ClusterRecognition,
    RecognitionResult,
    SliceRecognitionResult,
)
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.slice_result import SingleSlice, SliceResult
from infra.excel_result_exporter import (
    ExcelResultExporter,
    FullSpeedExportData,
)


def _build_export_data() -> FullSpeedExportData:
    """构造包含原识别结果和独立合并结果的导出数据。"""
    points_a = np.array(
        [
            [5000.0, 1.0, 90.0, 10.0, 11.0, 0.0],
            [5000.0, 1.0, 91.0, 10.0, 11.0, 100.0],
        ]
    )
    points_b = np.array(
        [
            [5001.0, 1.1, 92.0, 11.0, 12.0, 200.0],
            [5001.0, 1.1, 93.0, 11.0, 12.0, 300.0],
        ]
    )
    params_a = ExtractedClusterParams(
        cf_values=[5000.0],
        pw_values=[1.0],
        pri_values=[10.0],
        doa_values=[10.0],
    )
    params_b = ExtractedClusterParams(
        cf_values=[5001.0],
        pw_values=[1.1],
        pri_values=[10.0],
        doa_values=[11.0],
    )
    recognition_a = ClusterRecognition(
        slice_index=0,
        dim_name="CF",
        cluster_index=1,
        valid_cluster_index=0,
        pa_label=1,
        pa_confidence=0.9,
        dtoa_label=1,
        dtoa_confidence=0.8,
        is_valid=True,
        joint_prob=0.72,
        extracted_params=params_a,
    )
    recognition_b = ClusterRecognition(
        slice_index=0,
        dim_name="PW",
        cluster_index=2,
        valid_cluster_index=1,
        pa_label=1,
        pa_confidence=0.85,
        dtoa_label=1,
        dtoa_confidence=0.82,
        is_valid=True,
        joint_prob=0.697,
        extracted_params=params_b,
    )
    clusters = [
        ClusterItem(
            cluster_idx=1,
            dim_name="CF",
            points=points_a,
            points_indices=np.array([0, 1]),
            slice_idx=0,
            time_ranges=(0.0, 100.0),
            state=ClusterState.VALID,
        ),
        ClusterItem(
            cluster_idx=2,
            dim_name="PW",
            points=points_b,
            points_indices=np.array([2, 3]),
            slice_idx=0,
            time_ranges=(200.0, 300.0),
            state=ClusterState.VALID,
        ),
    ]
    merged_points = np.concatenate([points_a, points_b], axis=0)
    merged = MergedClusterResult(
        merge_index=1,
        slice_index=0,
        strategy_id="test_strategy",
        source_cluster_indices=(1, 2),
        source_dim_names=("CF", "PW"),
        source_point_clouds=(points_a, points_b),
        merged_points=merged_points,
        merged_point_indices=np.array([0, 1, 2, 3]),
        time_range=(0.0, 300.0),
        source_recognitions=(recognition_a, recognition_b),
        merged_recognition=None,
        extracted_params=ExtractedClusterParams(
            cf_values=[5000.0, 5001.0],
            pw_values=[1.0, 1.1],
            pri_values=[10.0],
            doa_values=[10.5],
        ),
    )
    return FullSpeedExportData(
        session_id="session1",
        display_name="测试/全速任务",
        source_path="E:/data/demo.xlsx",
        source_type="excel",
        data_package_id="package1",
        created_at=datetime(2026, 7, 29, 9, 0),
        config_snapshot=SessionConfigSnapshot.default(),
        model_selection=SessionModelSelection("pa.onnx", "dtoa.onnx"),
        slice_result=SliceResult(
            slices=[
                SingleSlice(
                    index=0,
                    data=merged_points,
                    time_range=(0.0, 300.0),
                )
            ]
        ),
        clustering_result=ClusteringResult(
            {0: SliceClusterResult(slice_idx=0, clusters=clusters)}
        ),
        recognition_result=RecognitionResult(
            {
                0: SliceRecognitionResult(
                    slice_index=0,
                    valid_clusters=[recognition_a, recognition_b],
                )
            }
        ),
        merge_result=MergeResult(
            {0: SliceMergeResult(slice_index=0, merged_clusters=[merged])}
        ),
    )


def test_excel_exporter_saves_recognition_and_merge_results_separately(
    tmp_path,
) -> None:
    """工作簿应保留原识别类，并在独立表中记录合并来源。"""
    output_path = ExcelResultExporter().export(
        _build_export_data(),
        tmp_path,
    )

    assert output_path.exists()
    assert output_path.suffix == ".xlsx"
    workbook = pd.ExcelFile(output_path)
    assert workbook.sheet_names == ["任务信息", "识别结果", "合并结果"]

    recognition_frame = pd.read_excel(output_path, sheet_name="识别结果")
    merge_frame = pd.read_excel(output_path, sheet_name="合并结果")
    assert recognition_frame["类簇编号"].tolist() == [1, 2]
    assert merge_frame.loc[0, "来源类簇编号"] == "1、2"
    assert merge_frame.loc[0, "合并策略"] == "test_strategy"
    assert not list(tmp_path.glob("*.tmp.xlsx"))
