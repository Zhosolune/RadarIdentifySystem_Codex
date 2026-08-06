"""全速处理结果 Excel 导出器。

一次生成“雷达结果”“综合结果”和“原始脉冲明细”三个工作簿。雷达结果
保留合并前的有效识别结果，综合结果用合并类替换其来源子类，脉冲工作簿按
综合类别索引保存算法预处理前的原始六维数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
from typing import Any, Iterable, Literal
import unicodedata

import numpy as np
import pandas as pd

from core.models.cluster_result import ClusterItem, ClusteringResult
from core.models.extraction_result import ExtractedClusterParams
from core.models.merge_result import MergeResult, MergedClusterResult
from core.models.pulse_batch import (
    COL_CF,
    COL_DOA,
    COL_PA,
    COL_PDOA,
    COL_PW,
    COL_TOA,
    PulseBatch,
)
from core.models.recognition_result import (
    ClusterRecognition,
    DTOA_LABEL_NAMES,
    PA_LABEL_NAMES,
    RecognitionResult,
)
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.slice_result import PreprocessResult, SingleSlice, SliceResult


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESULT_COLUMNS = [
    "切片编号", "雷达索引", "类簇编号", "聚类维度", "脉冲数量",
    "PA类别", "PA置信度", "DTOA类别", "DTOA置信度",
    "CF典型值(MHz)", "PW典型值(us)", "PRI典型值(us)", "DOA典型值(度)",
]
_COMPREHENSIVE_COLUMNS = [
    "切片编号", "类别索引", "切片内索引", "聚类维度", "脉冲数量",
    "PA类别", "PA置信度", "DTOA类别", "DTOA置信度",
    "CF典型值(MHz)", "PW典型值(us)", "PRI典型值(us)", "DOA典型值(度)",
]
_PULSE_COLUMNS = [
    "雷达索引", "CF(MHz)", "PW(us)", "PA(dB)", "DOA(度)",
    "PDOA(度)", "TOA(0.1us)",
]


@dataclass(frozen=True, slots=True)
class FullSpeedExportData:
    """一次全速处理 Excel 保存所需的完整数据。

    Attributes:
        session_id: 全速 Session 唯一标识。
        display_name: Session 展示名称。
        source_path: 数据包原始来源路径。
        source_type: 数据包来源类型。
        data_format: 来源数据格式，例如 Excel 的 ``old`` / ``new``。
        data_package_id: 数据池数据包 ID。
        created_at: Session 创建时间。
        raw_batch: 归一化导入后、算法预处理前的原始六维脉冲。
        preprocess_result: 清洗及 TOA 翻折修复后的算法输入。
        config_snapshot: 首次启动时冻结的参数快照。
        model_selection: 首次启动时冻结的模型选择。
        slice_result: 本次执行的切片结果。
        clustering_result: 各切片聚类结果。
        recognition_result: 各切片识别与参数提取结果。
        merge_result: 与识别结果独立保存的合并结果。
    """

    session_id: str
    display_name: str
    source_path: str
    source_type: str
    data_format: str | None
    data_package_id: str | None
    created_at: datetime
    raw_batch: PulseBatch
    preprocess_result: PreprocessResult
    config_snapshot: SessionConfigSnapshot
    model_selection: SessionModelSelection
    slice_result: SliceResult
    clustering_result: ClusteringResult
    recognition_result: RecognitionResult
    merge_result: MergeResult


@dataclass(frozen=True, slots=True)
class ExcelExportPaths:
    """一次导出生成的三个工作簿路径。

    Attributes:
        result_file: 雷达结果与元数据工作簿。
        comprehensive_file: 合并替换子类后的综合结果与元数据工作簿。
        pulse_file: 按切片组织的原始脉冲明细工作簿。
    """

    result_file: Path
    comprehensive_file: Path
    pulse_file: Path


@dataclass(frozen=True, slots=True)
class _ComprehensiveClass:
    """记录一个切片内最终保留的单类或合并类。"""

    slice_index: int
    category_index: int
    source_cluster_indices: tuple[int, ...]
    source_dim_names: tuple[str, ...]
    point_indices: tuple[int, ...]
    source_recognitions: tuple[ClusterRecognition, ...]
    result_recognition: ClusterRecognition | None
    extracted_params: ExtractedClusterParams | None

    @property
    def is_merged(self) -> bool:
        """返回当前类别是否由多个来源类簇合并得到。"""
        return len(self.source_cluster_indices) > 1


class ExcelResultExporter:
    """将全速处理结果原子保存为三个 Excel 工作簿。"""

    def export(
        self,
        data: FullSpeedExportData,
        output_dir: str | Path,
    ) -> ExcelExportPaths:
        """生成雷达结果、综合结果和原始脉冲明细工作簿。

        Args:
            data [FullSpeedExportData]: 已完成全速处理的完整纯结果数据。
            output_dir [str | Path]: 本地保存目录；不存在时自动创建。

        Returns:
            ExcelExportPaths: 三个结果文件的绝对路径。

        Raises:
            ValueError: 保存目录为空或原始数据无法与算法切片对齐时抛出。
            OSError: 目录创建、临时文件替换或清理失败时抛出。
            ImportError: pandas Excel 引擎不可用时抛出。

        Example:
            >>> ExcelResultExporter().__class__.__name__
            'ExcelResultExporter'
        """
        if not str(output_dir).strip():
            raise ValueError("Excel 保存目录不能为空")
        target_dir = Path(output_dir).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        paths = self._build_output_paths(data, target_dir)
        comprehensive_slices = self._build_comprehensive_slices(data)
        result_temp = paths.result_file.with_name(
            f".{paths.result_file.stem}.tmp.xlsx"
        )
        comprehensive_temp = paths.comprehensive_file.with_name(
            f".{paths.comprehensive_file.stem}.tmp.xlsx"
        )
        pulse_temp = paths.pulse_file.with_name(
            f".{paths.pulse_file.stem}.tmp.xlsx"
        )
        try:
            self._write_result_workbook(data, result_temp)
            self._write_comprehensive_workbook(
                data,
                comprehensive_slices,
                comprehensive_temp,
            )
            self._write_pulse_workbook(
                data,
                comprehensive_slices,
                pulse_temp,
            )
            # 目标名带微秒时间戳；任一替换失败时删除本次产物，避免半套结果。
            result_temp.replace(paths.result_file)
            comprehensive_temp.replace(paths.comprehensive_file)
            pulse_temp.replace(paths.pulse_file)
        except Exception:
            for path in (
                result_temp,
                comprehensive_temp,
                pulse_temp,
                paths.result_file,
                paths.comprehensive_file,
                paths.pulse_file,
            ):
                if path.exists():
                    path.unlink()
            raise
        return paths

    @staticmethod
    def _build_output_paths(
        data: FullSpeedExportData,
        output_dir: Path,
    ) -> ExcelExportPaths:
        """生成共享任务前缀且不会覆盖历史结果的三个文件路径。"""
        safe_name = _INVALID_FILENAME_CHARS.sub("_", data.display_name).strip(
            " ."
        ) or "全速处理结果"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = f"{safe_name}_{data.session_id}_{timestamp}"
        return ExcelExportPaths(
            output_dir / f"{prefix}_雷达结果.xlsx",
            output_dir / f"{prefix}_综合结果.xlsx",
            output_dir / f"{prefix}_脉冲明细.xlsx",
        )

    @classmethod
    def _write_result_workbook(
        cls,
        data: FullSpeedExportData,
        output_path: Path,
    ) -> None:
        """写入雷达结果和可读元数据两个工作表。"""
        result_frame = pd.DataFrame(
            cls._build_result_rows(data), columns=_RESULT_COLUMNS
        )
        metadata_frame = pd.DataFrame(
            cls._build_metadata_rows(data), columns=["类别", "项目", "内容"]
        )
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            result_frame.to_excel(writer, sheet_name="雷达结果", index=False)
            metadata_frame.to_excel(writer, sheet_name="元数据", index=False)
            cls._format_workbook(writer)

    @classmethod
    def _write_comprehensive_workbook(
        cls,
        data: FullSpeedExportData,
        comprehensive_slices: dict[int, tuple[_ComprehensiveClass, ...]],
        output_path: Path,
    ) -> None:
        """写入合并替换来源子类后的综合结果和元数据工作表。"""
        result_frame = pd.DataFrame(
            cls._build_comprehensive_rows(comprehensive_slices),
            columns=_COMPREHENSIVE_COLUMNS,
        )
        metadata_frame = pd.DataFrame(
            cls._build_metadata_rows(data), columns=["类别", "项目", "内容"]
        )
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            result_frame.to_excel(writer, sheet_name="综合结果", index=False)
            metadata_frame.to_excel(writer, sheet_name="元数据", index=False)
            cls._format_workbook(writer)

    @classmethod
    def _write_pulse_workbook(
        cls,
        data: FullSpeedExportData,
        comprehensive_slices: dict[int, tuple[_ComprehensiveClass, ...]],
        output_path: Path,
    ) -> None:
        """按切片写入原始脉冲值及其最终综合类别索引。"""
        raw_slices = cls._build_raw_slice_data(data)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            if not data.slice_result.slices:
                pd.DataFrame(columns=_PULSE_COLUMNS).to_excel(
                    writer, sheet_name="无切片", index=False
                )
            for current_slice in data.slice_result.slices:
                pulse_frame = pd.DataFrame(
                    cls._build_pulse_rows(
                        data,
                        current_slice,
                        raw_slices[current_slice.index],
                        comprehensive_slices.get(current_slice.index, ()),
                    ),
                    columns=_PULSE_COLUMNS,
                )
                pulse_frame.to_excel(
                    writer,
                    sheet_name=f"切片_{current_slice.index + 1}",
                    index=False,
                )
            cls._format_workbook(writer)

    @staticmethod
    def _build_metadata_rows(
        data: FullSpeedExportData,
    ) -> list[tuple[str, str, Any]]:
        """构造任务、模型、统计及冻结参数元数据行。"""
        valid_count = sum(
            len(result.valid_clusters)
            for result in data.recognition_result.slice_results.values()
        )
        invalid_count = sum(
            len(result.invalid_clusters)
            for result in data.recognition_result.slice_results.values()
        )
        merge_count = sum(
            len(result.merged_clusters)
            for result in data.merge_result.slice_results.values()
        )
        rows: list[tuple[str, str, Any]] = [
            ("任务信息", "Session ID", data.session_id),
            ("任务信息", "数据包 ID", data.data_package_id or ""),
            ("任务信息", "Session 名称", data.display_name),
            ("任务信息", "来源文件", data.source_path),
            ("任务信息", "来源类型", data.source_type),
            ("任务信息", "数据格式", data.data_format or ""),
            (
                "任务信息", "Session 创建时间",
                data.created_at.isoformat(timespec="seconds"),
            ),
            (
                "任务信息", "结果保存时间",
                datetime.now().isoformat(timespec="seconds"),
            ),
            ("结果统计", "切片数量", data.slice_result.slice_count),
            ("结果统计", "有效识别类数量", valid_count),
            ("结果统计", "无效识别类数量", invalid_count),
            ("结果统计", "合并结果数量", merge_count),
            ("输入统计", "原始脉冲数量", data.raw_batch.n_pulses),
            (
                "输入统计", "预处理过滤脉冲数量",
                data.preprocess_result.filtered_pulses,
            ),
            ("模型配置", "PA 模型", data.model_selection.pa_model_path or ""),
            (
                "模型配置", "DTOA 模型",
                data.model_selection.dtoa_model_path or "",
            ),
        ]
        for name, value in _flatten_mapping(data.config_snapshot.to_dict()):
            rows.append(("参数配置", name, value))
        return rows

    @staticmethod
    def _build_result_rows(
        data: FullSpeedExportData,
    ) -> list[dict[str, Any]]:
        """仅构造各切片有效识别雷达结果行。"""
        rows: list[dict[str, Any]] = []
        for slice_index in sorted(data.recognition_result.slice_results):
            recognition_slice = data.recognition_result.slice_results[slice_index]
            cluster_slice = data.clustering_result.slice_results.get(slice_index)
            cluster_map = {} if cluster_slice is None else {
                cluster.cluster_idx: cluster for cluster in cluster_slice.clusters
            }
            for recognition in recognition_slice.valid_clusters:
                cluster = cluster_map.get(recognition.cluster_index)
                params = recognition.extracted_params
                rows.append({
                    "切片编号": slice_index + 1,
                    "雷达索引": "" if recognition.valid_cluster_index is None
                    else recognition.valid_cluster_index + 1,
                    "类簇编号": recognition.cluster_index,
                    "聚类维度": recognition.dim_name,
                    "脉冲数量": 0 if cluster is None else cluster.cluster_size,
                    "PA类别": PA_LABEL_NAMES.get(
                        recognition.pa_label,
                        f"未知类别{recognition.pa_label}",
                    ),
                    "PA置信度": _format_probability(
                        recognition.pa_confidence
                    ),
                    "DTOA类别": DTOA_LABEL_NAMES.get(
                        recognition.dtoa_label,
                        f"未知类别{recognition.dtoa_label}",
                    ),
                    "DTOA置信度": _format_probability(
                        recognition.dtoa_confidence
                    ),
                    "CF典型值(MHz)": _format_values(
                        () if params is None else params.cf_values,
                        decimal_places=0,
                    ),
                    "PW典型值(us)": _format_values(
                        () if params is None else params.pw_values,
                        decimal_places=1,
                    ),
                    "PRI典型值(us)": _format_values(
                        () if params is None else params.pri_values,
                        decimal_places=1,
                    ),
                    "DOA典型值(度)": _format_values(
                        () if params is None else params.doa_values,
                        decimal_places=1,
                    ),
                })
        return rows

    @classmethod
    def _build_comprehensive_slices(
        cls,
        data: FullSpeedExportData,
    ) -> dict[int, tuple[_ComprehensiveClass, ...]]:
        """构造剔除合并来源子类并连续编号的切片级最终类别。"""
        slice_map = {item.index: item for item in data.slice_result.slices}
        result: dict[int, tuple[_ComprehensiveClass, ...]] = {}
        for slice_index, current_slice in sorted(slice_map.items()):
            recognition_slice = data.recognition_result.slice_results.get(
                slice_index
            )
            cluster_slice = data.clustering_result.slice_results.get(
                slice_index
            )
            valid_recognitions = (
                ()
                if recognition_slice is None
                else tuple(recognition_slice.valid_clusters)
            )
            recognition_map = {
                recognition.cluster_index: recognition
                for recognition in valid_recognitions
            }
            if len(recognition_map) != len(valid_recognitions):
                raise ValueError(
                    f"切片 {slice_index + 1} 存在重复的有效类簇编号"
                )
            cluster_map = {} if cluster_slice is None else {
                cluster.cluster_idx: cluster for cluster in cluster_slice.clusters
            }
            pending_classes: list[_ComprehensiveClass] = []
            consumed_clusters: set[int] = set()
            merge_slice = data.merge_result.slice_results.get(slice_index)
            merged_clusters = (
                () if merge_slice is None else tuple(merge_slice.merged_clusters)
            )
            for merged in merged_clusters:
                pending_classes.append(
                    cls._build_merged_class(
                        current_slice,
                        merged,
                        recognition_map,
                        cluster_map,
                        consumed_clusters,
                    )
                )
            for cluster_index, recognition in recognition_map.items():
                if cluster_index in consumed_clusters:
                    continue
                cluster = cluster_map.get(cluster_index)
                if cluster is None:
                    raise ValueError(
                        f"切片 {slice_index + 1} 缺少类簇 {cluster_index}"
                    )
                point_indices = cls._normalize_point_indices(
                    cluster.points_indices,
                    current_slice.pulse_count,
                    f"切片 {slice_index + 1} 类簇 {cluster_index}",
                )
                pending_classes.append(
                    _ComprehensiveClass(
                        slice_index=slice_index,
                        category_index=0,
                        source_cluster_indices=(cluster_index,),
                        source_dim_names=(recognition.dim_name,),
                        point_indices=point_indices,
                        source_recognitions=(recognition,),
                        result_recognition=recognition,
                        extracted_params=recognition.extracted_params,
                    )
                )
            pending_classes.sort(
                key=lambda item: min(item.source_cluster_indices)
            )
            result[slice_index] = tuple(
                _ComprehensiveClass(
                    slice_index=item.slice_index,
                    category_index=category_index,
                    source_cluster_indices=item.source_cluster_indices,
                    source_dim_names=item.source_dim_names,
                    point_indices=item.point_indices,
                    source_recognitions=item.source_recognitions,
                    result_recognition=item.result_recognition,
                    extracted_params=item.extracted_params,
                )
                for category_index, item in enumerate(
                    pending_classes,
                    start=1,
                )
            )
        return result

    @classmethod
    def _build_merged_class(
        cls,
        current_slice: SingleSlice,
        merged: MergedClusterResult,
        recognition_map: dict[int, ClusterRecognition],
        cluster_map: dict[int, ClusterItem],
        consumed_clusters: set[int],
    ) -> _ComprehensiveClass:
        """校验一个合并结果并转换为未编号的最终类别。"""
        if merged.slice_index != current_slice.index:
            raise ValueError("合并结果与所属切片索引不一致")
        source_indices = tuple(sorted(merged.source_cluster_indices))
        if len(source_indices) < 2 or len(set(source_indices)) != len(
            source_indices
        ):
            raise ValueError("合并结果的来源类簇编号不合法")
        if consumed_clusters.intersection(source_indices):
            raise ValueError("同一有效类簇被多个合并结果重复使用")

        source_recognitions: list[ClusterRecognition] = []
        source_dim_names: list[str] = []
        expected_point_indices: list[int] = []
        for cluster_index in source_indices:
            recognition = recognition_map.get(cluster_index)
            cluster = cluster_map.get(cluster_index)
            if recognition is None or cluster is None:
                raise ValueError(
                    f"切片 {current_slice.index + 1} 的合并来源类簇 "
                    f"{cluster_index} 不是有效识别结果"
                )
            source_recognitions.append(recognition)
            source_dim_names.append(recognition.dim_name)
            expected_point_indices.extend(
                cls._normalize_point_indices(
                    cluster.points_indices,
                    current_slice.pulse_count,
                    f"切片 {current_slice.index + 1} 类簇 {cluster_index}",
                )
            )
        if len(set(expected_point_indices)) != len(expected_point_indices):
            raise ValueError("合并来源类簇包含重复脉冲")
        merged_point_indices = cls._normalize_point_indices(
            merged.merged_point_indices,
            current_slice.pulse_count,
            f"切片 {current_slice.index + 1} 合并结果",
        )
        if sorted(expected_point_indices) != sorted(merged_point_indices):
            raise ValueError("合并结果脉冲索引与来源类簇不一致")
        consumed_clusters.update(source_indices)
        return _ComprehensiveClass(
            slice_index=current_slice.index,
            category_index=0,
            source_cluster_indices=source_indices,
            source_dim_names=tuple(source_dim_names),
            point_indices=merged_point_indices,
            source_recognitions=tuple(source_recognitions),
            result_recognition=merged.merged_recognition,
            extracted_params=merged.extracted_params,
        )

    @staticmethod
    def _normalize_point_indices(
        point_indices: Iterable[int],
        pulse_count: int,
        context: str,
    ) -> tuple[int, ...]:
        """把点索引规范为元组并校验其切片边界。"""
        normalized = tuple(
            int(value) for value in np.asarray(point_indices).reshape(-1)
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"{context} 包含重复脉冲索引")
        if any(value < 0 or value >= pulse_count for value in normalized):
            raise ValueError(f"{context} 的脉冲索引超出所属切片范围")
        return normalized

    @staticmethod
    def _build_comprehensive_rows(
        comprehensive_slices: dict[int, tuple[_ComprehensiveClass, ...]],
    ) -> list[dict[str, Any]]:
        """构造按最终类别连续编号的综合结果行。"""
        rows: list[dict[str, Any]] = []
        for slice_index in sorted(comprehensive_slices):
            for item in comprehensive_slices[slice_index]:
                params = item.extracted_params
                display_recognitions = (
                    (item.result_recognition,)
                    if item.result_recognition is not None
                    else item.source_recognitions
                )
                confidence_recognition = item.result_recognition
                rows.append({
                    "切片编号": slice_index + 1,
                    "类别索引": item.category_index,
                    "切片内索引": "+".join(
                        str(value) for value in item.source_cluster_indices
                    ),
                    "聚类维度": _combine_text_values(
                        item.source_dim_names
                    ),
                    "脉冲数量": len(item.point_indices),
                    "PA类别": _combine_recognition_labels(
                        display_recognitions,
                        label_kind="pa",
                    ),
                    "PA置信度": (
                        "——"
                        if confidence_recognition is None
                        else _format_probability(
                            confidence_recognition.pa_confidence
                        )
                    ),
                    "DTOA类别": _combine_recognition_labels(
                        display_recognitions,
                        label_kind="dtoa",
                    ),
                    "DTOA置信度": (
                        "——"
                        if confidence_recognition is None
                        else _format_probability(
                            confidence_recognition.dtoa_confidence
                        )
                    ),
                    "CF典型值(MHz)": _format_values(
                        () if params is None else params.cf_values,
                        decimal_places=0,
                    ),
                    "PW典型值(us)": _format_values(
                        () if params is None else params.pw_values,
                        decimal_places=1,
                    ),
                    "PRI典型值(us)": _format_values(
                        () if params is None else params.pri_values,
                        decimal_places=1,
                    ),
                    "DOA典型值(度)": _format_values(
                        () if params is None else params.doa_values,
                        decimal_places=1,
                    ),
                })
        return rows

    @staticmethod
    def _build_raw_slice_data(
        data: FullSpeedExportData,
    ) -> dict[int, np.ndarray]:
        """用算法切片掩码提取同一批行的原始六维值。"""
        # 预处理只会删除 PA=255 行并修改 TOA，先按相同删除规则恢复行对齐。
        raw_after_pa_filter = data.raw_batch.data[
            data.raw_batch.data[:, COL_PA] != 255
        ]
        processed = data.preprocess_result.data
        if len(raw_after_pa_filter) != len(processed):
            raise ValueError("原始脉冲与预处理结果行数不一致，无法可靠导出原始值")
        if not np.array_equal(
            raw_after_pa_filter[:, :COL_TOA],
            processed[:, :COL_TOA],
            equal_nan=True,
        ):
            raise ValueError("原始脉冲与预处理结果行顺序不一致，无法可靠建立映射")

        raw_slices: dict[int, np.ndarray] = {}
        processed_toa = processed[:, COL_TOA]
        for current_slice in data.slice_result.slices:
            start, end = current_slice.time_range
            mask = (processed_toa >= start) & (processed_toa < end)
            if not np.array_equal(
                processed[mask], current_slice.data, equal_nan=True
            ):
                raise ValueError(
                    f"切片 {current_slice.index + 1} 与预处理结果无法可靠对齐"
                )
            raw_slices[current_slice.index] = raw_after_pa_filter[mask]
        return raw_slices

    @staticmethod
    def _build_pulse_rows(
        data: FullSpeedExportData,
        current_slice: SingleSlice,
        raw_points: np.ndarray,
        comprehensive_classes: tuple[_ComprehensiveClass, ...],
    ) -> list[dict[str, Any]]:
        """为单个切片标注最终类别索引，其余脉冲统一标记 invalid。"""
        radar_indices = np.full(len(raw_points), "invalid", dtype=object)
        for item in comprehensive_classes:
            point_indices = np.asarray(item.point_indices, dtype=int)
            if np.any(radar_indices[point_indices] != "invalid"):
                raise ValueError("同一脉冲被分配给多个综合结果")
            radar_indices[point_indices] = str(item.category_index)

        rows: list[dict[str, Any]] = []
        for radar_index, point in zip(radar_indices, raw_points, strict=True):
            rows.append({
                "雷达索引": radar_index,
                "CF(MHz)": point[COL_CF],
                "PW(us)": point[COL_PW],
                "PA(dB)": point[COL_PA],
                "DOA(度)": point[COL_DOA],
                "PDOA(度)": (
                    "——"
                    if data.data_format == "old"
                    else point[COL_PDOA]
                ),
                "TOA(0.1us)": point[COL_TOA],
            })
        return rows

    @staticmethod
    def _format_workbook(writer: pd.ExcelWriter) -> None:
        """设置冻结标题、筛选和受限自适应列宽。"""
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            if worksheet.max_row >= 1 and worksheet.max_column >= 1:
                worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                values = [
                    "" if cell.value is None else str(cell.value)
                    for cell in column_cells
                ]
                width = min(
                    60,
                    max(
                        (_excel_text_width(value) for value in values),
                        default=8,
                    ) + 2,
                )
                worksheet.column_dimensions[
                    column_cells[0].column_letter
                ].width = width


def _flatten_mapping(
    payload: dict[str, Any],
    prefix: str = "",
) -> list[tuple[str, Any]]:
    """把嵌套配置字典展开为稳定的点分路径和值。"""
    rows: list[tuple[str, Any]] = []
    for key, value in payload.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            rows.extend(_flatten_mapping(value, name))
        else:
            rows.append((name, value))
    return rows


def _combine_text_values(values: Iterable[str]) -> str:
    """按首次出现顺序合并非空文本并去重。"""
    unique_values = tuple(dict.fromkeys(value for value in values if value))
    return "+".join(unique_values) if unique_values else "——"


def _excel_text_width(value: str) -> int:
    """估算 Excel 中英文混排文本的可见字符宽度。"""
    return sum(
        2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        for character in value
    )


def _combine_recognition_labels(
    recognitions: Iterable[ClusterRecognition],
    label_kind: Literal["pa", "dtoa"],
) -> str:
    """把一个或多个识别标签转换为实际业务类别名称。"""
    if label_kind == "pa":
        labels = (
            PA_LABEL_NAMES.get(
                recognition.pa_label,
                f"未知类别{recognition.pa_label}",
            )
            for recognition in recognitions
        )
    else:
        labels = (
            DTOA_LABEL_NAMES.get(
                recognition.dtoa_label,
                f"未知类别{recognition.dtoa_label}",
            )
            for recognition in recognitions
        )
    return _combine_text_values(labels)


def _format_values(
    values: Iterable[float],
    decimal_places: int,
) -> str:
    """按结果表格规则格式化参数值列表。"""
    normalized = [
        _format_decimal(value, decimal_places)
        for value in values
    ]
    return "、".join(normalized) if normalized else "——"


def _format_probability(value: float) -> str:
    """按结果表格规则把置信度格式化为四位小数。"""
    rounded = _rounded_decimal(value, decimal_places=4)
    return "0" if rounded == Decimal("0") else f"{rounded:.4f}"


def _format_decimal(value: float, decimal_places: int) -> str:
    """使用 ROUND_HALF_UP 保留指定小数位。"""
    rounded = _rounded_decimal(value, decimal_places)
    if rounded == Decimal("0"):
        rounded = Decimal("0")
    return f"{rounded:.{decimal_places}f}"


def _rounded_decimal(value: float, decimal_places: int) -> Decimal:
    """返回按展示精度量化后的 Decimal。"""
    quantizer = (
        Decimal("1")
        if decimal_places == 0
        else Decimal(f"1e-{decimal_places}")
    )
    return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)
