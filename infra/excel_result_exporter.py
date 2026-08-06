"""全速处理结果 Excel 导出器。

一次生成“雷达结果”和“原始脉冲明细”两个工作簿。结果工作簿只保存有效
识别结果与冻结配置；脉冲工作簿按切片保存算法预处理前的原始六维数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd

from core.models.cluster_result import ClusteringResult
from core.models.merge_result import MergeResult
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
    "PA类别", "PA置信度", "DTOA类别", "DTOA置信度", "联合置信度",
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
    """一次导出生成的两个工作簿路径。

    Attributes:
        result_file: 雷达结果与元数据工作簿。
        pulse_file: 按切片组织的原始脉冲明细工作簿。
    """

    result_file: Path
    pulse_file: Path


class ExcelResultExporter:
    """将全速处理结果原子保存为两个 Excel 工作簿。"""

    def export(
        self,
        data: FullSpeedExportData,
        output_dir: str | Path,
    ) -> ExcelExportPaths:
        """生成雷达结果工作簿和原始脉冲明细工作簿。

        Args:
            data [FullSpeedExportData]: 已完成全速处理的完整纯结果数据。
            output_dir [str | Path]: 本地保存目录；不存在时自动创建。

        Returns:
            ExcelExportPaths: 结果文件与脉冲明细文件绝对路径。

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
        result_temp = paths.result_file.with_name(
            f".{paths.result_file.stem}.tmp.xlsx"
        )
        pulse_temp = paths.pulse_file.with_name(
            f".{paths.pulse_file.stem}.tmp.xlsx"
        )
        try:
            self._write_result_workbook(data, result_temp)
            self._write_pulse_workbook(data, pulse_temp)
            # 目标名带微秒时间戳；任一替换失败时删除本次产物，避免半套结果。
            result_temp.replace(paths.result_file)
            pulse_temp.replace(paths.pulse_file)
        except Exception:
            for path in (
                result_temp, pulse_temp, paths.result_file, paths.pulse_file
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
        """生成共享任务前缀且不会覆盖历史结果的两个文件路径。"""
        safe_name = _INVALID_FILENAME_CHARS.sub("_", data.display_name).strip(
            " ."
        ) or "全速处理结果"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        prefix = f"{safe_name}_{data.session_id}_{timestamp}"
        return ExcelExportPaths(
            output_dir / f"{prefix}_雷达结果.xlsx",
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
    def _write_pulse_workbook(
        cls,
        data: FullSpeedExportData,
        output_path: Path,
    ) -> None:
        """按切片写入原始脉冲值及其识别雷达索引。"""
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
                    "联合置信度": _format_probability(recognition.joint_prob),
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
    ) -> list[dict[str, Any]]:
        """为单个切片标注有效雷达索引，其余脉冲统一标记 invalid。"""
        radar_indices = np.full(len(raw_points), "invalid", dtype=object)
        cluster_slice = data.clustering_result.slice_results.get(
            current_slice.index
        )
        recognition_slice = data.recognition_result.slice_results.get(
            current_slice.index
        )
        cluster_map = {} if cluster_slice is None else {
            cluster.cluster_idx: cluster for cluster in cluster_slice.clusters
        }
        if recognition_slice is not None:
            for recognition in recognition_slice.valid_clusters:
                if recognition.valid_cluster_index is None:
                    raise ValueError("有效雷达结果缺少切片内雷达索引")
                cluster = cluster_map.get(recognition.cluster_index)
                if cluster is None:
                    raise ValueError(
                        f"切片 {current_slice.index + 1} 缺少类簇 "
                        f"{recognition.cluster_index}"
                    )
                point_indices = np.asarray(cluster.points_indices, dtype=int)
                if np.any(point_indices < 0) or np.any(
                    point_indices >= len(raw_points)
                ):
                    raise ValueError("类簇脉冲索引超出所属切片范围")
                if np.any(radar_indices[point_indices] != "invalid"):
                    raise ValueError("同一脉冲被分配给多个有效雷达结果")
                radar_indices[point_indices] = str(
                    recognition.valid_cluster_index + 1
                )

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
                    max((len(value) for value in values), default=8) + 2,
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
