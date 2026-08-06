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
from core.models.pulse_batch import PulseBatch
from core.models.recognition_result import (
    ClusterRecognition,
    RecognitionResult,
    SliceRecognitionResult,
)
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.slice_result import PreprocessResult, SingleSlice, SliceResult
from infra.excel_result_exporter import (
    ExcelResultExporter,
    FullSpeedExportData,
)


def _build_export_data(data_format: str = "new") -> FullSpeedExportData:
    """构造类簇 2、4、5、8 且 4、5 合并的导出数据。"""
    points_2 = np.array([[5000.0, 1.0, 90.0, 10.0, 11.0, 0.0]])
    points_4 = np.array([[5001.0, 1.1, 91.0, 11.0, 12.0, 100.0]])
    points_5 = np.array([[5002.0, 1.2, 92.0, 12.0, 13.0, 200.0]])
    points_8 = np.array([[5003.0, 1.3, 93.0, 13.0, 14.0, 300.0]])
    params_2 = ExtractedClusterParams(
        cf_values=[5000.5],
        pw_values=[1.25],
        pri_values=[10.25],
        doa_values=[10.25],
    )
    params_4 = ExtractedClusterParams(
        cf_values=[5001.0],
        pw_values=[1.1],
        pri_values=[10.0],
        doa_values=[11.0],
    )
    params_5 = ExtractedClusterParams(
        cf_values=[5002.0],
        pw_values=[1.2],
        pri_values=[10.0],
        doa_values=[12.0],
    )
    params_8 = ExtractedClusterParams(
        cf_values=[5003.0],
        pw_values=[1.3],
        pri_values=[10.0],
        doa_values=[13.0],
    )
    recognition_2 = ClusterRecognition(
        slice_index=0,
        dim_name="CF",
        cluster_index=2,
        valid_cluster_index=0,
        pa_label=1,
        pa_confidence=0.9,
        dtoa_label=1,
        dtoa_confidence=0.8,
        is_valid=True,
        joint_prob=0.72,
        extracted_params=params_2,
    )
    recognition_4 = ClusterRecognition(
        slice_index=0,
        dim_name="PW",
        cluster_index=4,
        valid_cluster_index=1,
        pa_label=1,
        pa_confidence=0.85,
        dtoa_label=1,
        dtoa_confidence=0.82,
        is_valid=True,
        joint_prob=0.697,
        extracted_params=params_4,
    )
    recognition_5 = ClusterRecognition(
        slice_index=0,
        dim_name="CF",
        cluster_index=5,
        valid_cluster_index=2,
        pa_label=2,
        pa_confidence=0.86,
        dtoa_label=1,
        dtoa_confidence=0.83,
        is_valid=True,
        joint_prob=0.7138,
        extracted_params=params_5,
    )
    recognition_8 = ClusterRecognition(
        slice_index=0,
        dim_name="CF",
        cluster_index=8,
        valid_cluster_index=3,
        pa_label=0,
        pa_confidence=0.95,
        dtoa_label=0,
        dtoa_confidence=0.91,
        is_valid=True,
        joint_prob=0.8645,
        extracted_params=params_8,
    )
    invalid_recognition = ClusterRecognition(
        slice_index=1,
        dim_name="CF",
        cluster_index=3,
        valid_cluster_index=None,
        pa_label=5,
        pa_confidence=0.99,
        dtoa_label=5,
        dtoa_confidence=0.98,
        is_valid=False,
    )
    clusters = [
        ClusterItem(
            cluster_idx=2,
            dim_name="CF",
            points=points_2,
            points_indices=np.array([0]),
            slice_idx=0,
            time_ranges=(0.0, 0.0),
            state=ClusterState.VALID,
        ),
        ClusterItem(
            cluster_idx=4,
            dim_name="PW",
            points=points_4,
            points_indices=np.array([1]),
            slice_idx=0,
            time_ranges=(100.0, 100.0),
            state=ClusterState.VALID,
        ),
        ClusterItem(
            cluster_idx=5,
            dim_name="CF",
            points=points_5,
            points_indices=np.array([2]),
            slice_idx=0,
            time_ranges=(200.0, 200.0),
            state=ClusterState.VALID,
        ),
        ClusterItem(
            cluster_idx=8,
            dim_name="CF",
            points=points_8,
            points_indices=np.array([3]),
            slice_idx=0,
            time_ranges=(300.0, 300.0),
            state=ClusterState.VALID,
        ),
    ]
    merged_points = np.concatenate([points_4, points_5], axis=0)
    invalid_point = np.array([[6000.0, 2.0, 70.0, 30.0, 31.0, 400.0]])
    radar_points = np.concatenate(
        [points_2, points_4, points_5, points_8], axis=0
    )
    slice_points = np.concatenate([radar_points, invalid_point], axis=0)
    raw_points = slice_points.copy()
    # 原始 TOA 与算法归零后的 TOA 不同，用于证明明细文件保存原始值。
    raw_points[:, 5] = np.array([900.0, 1000.0, 1100.0, 1200.0, 1300.0])
    merged = MergedClusterResult(
        merge_index=1,
        slice_index=0,
        strategy_id="test_strategy",
        source_cluster_indices=(4, 5),
        source_dim_names=("PW", "CF"),
        source_point_clouds=(points_4, points_5),
        merged_points=merged_points,
        merged_point_indices=np.array([1, 2]),
        time_range=(100.0, 200.0),
        source_recognitions=(recognition_4, recognition_5),
        merged_recognition=None,
        extracted_params=ExtractedClusterParams(
            cf_values=[5001.0, 5002.0],
            pw_values=[1.1, 1.2],
            pri_values=[10.0],
            doa_values=[11.5],
        ),
    )
    return FullSpeedExportData(
        session_id="session1",
        display_name="测试/全速任务",
        source_path="E:/data/demo.xlsx",
        source_type="excel",
        data_format=data_format,
        data_package_id="package1",
        created_at=datetime(2026, 7, 29, 9, 0),
        raw_batch=PulseBatch(raw_points, "E:/data/demo.xlsx", "excel", 5),
        preprocess_result=PreprocessResult(data=slice_points),
        config_snapshot=SessionConfigSnapshot.default(),
        model_selection=SessionModelSelection("pa.onnx", "dtoa.onnx"),
        slice_result=SliceResult(
            slices=[
                SingleSlice(
                    index=0,
                    data=radar_points,
                    time_range=(0.0, 400.0),
                ),
                SingleSlice(
                    index=1,
                    data=invalid_point,
                    time_range=(400.0, 500.0),
                ),
            ]
        ),
        clustering_result=ClusteringResult(
            {0: SliceClusterResult(slice_idx=0, clusters=clusters)}
        ),
        recognition_result=RecognitionResult(
            {
                0: SliceRecognitionResult(
                    slice_index=0,
                    valid_clusters=[
                        recognition_2,
                        recognition_4,
                        recognition_5,
                        recognition_8,
                    ],
                ),
                1: SliceRecognitionResult(
                    slice_index=1,
                    invalid_clusters=[invalid_recognition],
                ),
            }
        ),
        merge_result=MergeResult(
            {0: SliceMergeResult(slice_index=0, merged_clusters=[merged])}
        ),
    )


def test_excel_exporter_saves_three_files_with_comprehensive_indices(
    tmp_path,
) -> None:
    """导出器应生成三文件并让综合结果与脉冲索引保持一致。"""
    paths = ExcelResultExporter().export(
        _build_export_data(),
        tmp_path,
    )

    assert paths.result_file.exists()
    assert paths.comprehensive_file.exists()
    assert paths.pulse_file.exists()
    assert pd.ExcelFile(paths.result_file).sheet_names == ["雷达结果", "元数据"]
    assert pd.ExcelFile(paths.comprehensive_file).sheet_names == [
        "综合结果",
        "元数据",
    ]
    assert pd.ExcelFile(paths.pulse_file).sheet_names == ["切片_1", "切片_2"]

    result_frame = pd.read_excel(
        paths.result_file,
        sheet_name="雷达结果",
        dtype=str,
    )
    metadata_frame = pd.read_excel(paths.result_file, sheet_name="元数据")
    comprehensive_frame = pd.read_excel(
        paths.comprehensive_file,
        sheet_name="综合结果",
        dtype=str,
    )
    pulse_frame = pd.read_excel(
        paths.pulse_file,
        sheet_name="切片_1",
        dtype={"雷达索引": str},
    )
    invalid_frame = pd.read_excel(
        paths.pulse_file,
        sheet_name="切片_2",
        dtype={"雷达索引": str},
    )
    assert result_frame.columns.tolist() == [
        "切片编号",
        "雷达索引",
        "类簇编号",
        "聚类维度",
        "脉冲数量",
        "PA类别",
        "PA置信度",
        "DTOA类别",
        "DTOA置信度",
        "CF典型值(MHz)",
        "PW典型值(us)",
        "PRI典型值(us)",
        "DOA典型值(度)",
    ]
    assert len(result_frame) == 4
    assert result_frame["类簇编号"].tolist() == ["2", "4", "5", "8"]
    assert result_frame.loc[0, "PA类别"] == "残缺包络"
    assert result_frame.loc[0, "DTOA类别"] == "脉间参差"
    assert result_frame.loc[0, "PA置信度"] == "0.9000"
    assert result_frame.loc[0, "DTOA置信度"] == "0.8000"
    assert "联合置信度" not in result_frame.columns
    assert result_frame.loc[0, "CF典型值(MHz)"] == "5001"
    assert result_frame.loc[0, "PW典型值(us)"] == "1.3"
    assert result_frame.loc[0, "PRI典型值(us)"] == "10.3"
    assert result_frame.loc[0, "DOA典型值(度)"] == "10.3"
    assert metadata_frame.loc[
        metadata_frame["项目"] == "clustering.eps_cf",
        "内容",
    ].tolist() == [2]
    assert "导出说明" not in metadata_frame["类别"].tolist()
    assert comprehensive_frame["类别索引"].tolist() == ["1", "2", "3"]
    assert comprehensive_frame["切片内索引"].tolist() == ["2", "4+5", "8"]
    assert "联合置信度" not in comprehensive_frame.columns
    assert comprehensive_frame.loc[1, "聚类维度"] == "PW+CF"
    assert comprehensive_frame.loc[1, "PA类别"] == "残缺包络+部分包络"
    assert comprehensive_frame.loc[1, "DTOA类别"] == "脉间参差"
    assert comprehensive_frame.loc[1, "PA置信度"] == "——"
    assert comprehensive_frame.loc[1, "DTOA置信度"] == "——"
    assert comprehensive_frame.loc[1, "CF典型值(MHz)"] == "5001、5002"
    assert comprehensive_frame.loc[1, "DOA典型值(度)"] == "11.5"
    assert pulse_frame.columns.tolist() == [
        "雷达索引",
        "CF(MHz)",
        "PW(us)",
        "PA(dB)",
        "DOA(度)",
        "PDOA(度)",
        "TOA(0.1us)",
    ]
    assert pulse_frame["雷达索引"].tolist() == ["1", "2", "2", "3"]
    assert pulse_frame["TOA(0.1us)"].tolist() == [900, 1000, 1100, 1200]
    assert pulse_frame["PDOA(度)"].tolist() == [11, 12, 13, 14]
    assert invalid_frame.loc[0, "雷达索引"] == "invalid"
    assert invalid_frame.loc[0, "TOA(0.1us)"] == 1300
    assert not list(tmp_path.glob("*.tmp.xlsx"))


def test_excel_exporter_replaces_old_format_pdoa_with_placeholder(
    tmp_path,
) -> None:
    """旧 Excel 没有原始 PDOA，明细列不得导出由 DOA 复制的兼容值。"""
    paths = ExcelResultExporter().export(
        _build_export_data(data_format="old"),
        tmp_path,
    )

    first_slice = pd.read_excel(paths.pulse_file, sheet_name="切片_1")
    second_slice = pd.read_excel(paths.pulse_file, sheet_name="切片_2")
    assert first_slice["PDOA(度)"].tolist() == ["——", "——", "——", "——"]
    assert second_slice["PDOA(度)"].tolist() == ["——"]
