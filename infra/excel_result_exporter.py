"""全速处理结果 Excel 导出器。

导出器接收纯结果模型并生成单个 ``.xlsx`` 文件，不依赖 Qt、线程或界面。
识别结果和合并结果写入独立工作表，合并结果保留来源簇编号，不修改或替代
原识别结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Iterable

import pandas as pd

from core.models.cluster_result import ClusteringResult
from core.models.merge_result import MergeResult
from core.models.recognition_result import RecognitionResult
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from core.models.slice_result import SliceResult


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RECOGNITION_COLUMNS = [
    "切片编号",
    "类簇编号",
    "有效类编号",
    "聚类维度",
    "识别结论",
    "脉冲数量",
    "PA类别",
    "PA置信度",
    "DTOA类别",
    "DTOA置信度",
    "联合置信度",
    "CF典型值(MHz)",
    "PW典型值(us)",
    "PRI典型值(us)",
    "DOA典型值(度)",
    "TOA起点(0.1us)",
    "TOA终点(0.1us)",
]
_MERGE_COLUMNS = [
    "切片编号",
    "合并结果编号",
    "合并策略",
    "来源类簇编号",
    "来源聚类维度",
    "脉冲数量",
    "CF典型值(MHz)",
    "PW典型值(us)",
    "PRI典型值(us)",
    "DOA典型值(度)",
    "TOA起点(0.1us)",
    "TOA终点(0.1us)",
]


@dataclass(frozen=True, slots=True)
class FullSpeedExportData:
    """一次全速处理 Excel 保存所需的完整数据。

    Attributes:
        session_id: 全速 Session 唯一标识。
        display_name: Session 展示名称。
        source_path: 数据包原始来源路径。
        source_type: 数据包来源类型。
        data_package_id: 数据池数据包 ID。
        created_at: Session 创建时间。
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
    data_package_id: str | None
    created_at: datetime
    config_snapshot: SessionConfigSnapshot
    model_selection: SessionModelSelection
    slice_result: SliceResult
    clustering_result: ClusteringResult
    recognition_result: RecognitionResult
    merge_result: MergeResult


class ExcelResultExporter:
    """将全速处理结果原子保存为 Excel 工作簿。"""

    def export(
        self,
        data: FullSpeedExportData,
        output_dir: str | Path,
    ) -> Path:
        """生成任务信息、识别结果和合并结果工作表。

        Args:
            data [FullSpeedExportData]: 已完成全速处理的纯结果数据。
            output_dir [str | Path]: 本地保存目录；不存在时自动创建。

        Returns:
            Path: 成功生成的 Excel 文件绝对路径。

        Raises:
            ValueError: 保存目录为空时抛出。
            OSError: 目录创建、临时文件替换或清理失败时抛出。
            ImportError: pandas Excel 引擎不可用时抛出。

        Example:
            >>> exporter = ExcelResultExporter()
            >>> exporter.__class__.__name__
            'ExcelResultExporter'
        """
        if not str(output_dir).strip():
            raise ValueError("Excel 保存目录不能为空")

        target_dir = Path(output_dir).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._build_output_path(data, target_dir)
        temp_path = output_path.with_name(f".{output_path.stem}.tmp.xlsx")

        task_frame = pd.DataFrame(
            self._build_task_rows(data),
            columns=["项目", "内容"],
        )
        recognition_frame = pd.DataFrame(
            self._build_recognition_rows(data),
            columns=_RECOGNITION_COLUMNS,
        )
        merge_frame = pd.DataFrame(
            self._build_merge_rows(data),
            columns=_MERGE_COLUMNS,
        )

        try:
            with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
                task_frame.to_excel(writer, sheet_name="任务信息", index=False)
                recognition_frame.to_excel(
                    writer,
                    sheet_name="识别结果",
                    index=False,
                )
                merge_frame.to_excel(writer, sheet_name="合并结果", index=False)
                self._format_workbook(writer)
            temp_path.replace(output_path)
        except Exception:
            # 仅清理本次任务生成的同目录临时文件，不触碰已有结果。
            if temp_path.exists():
                temp_path.unlink()
            raise
        return output_path

    @staticmethod
    def _build_output_path(
        data: FullSpeedExportData,
        output_dir: Path,
    ) -> Path:
        """生成不会覆盖历史结果的文件路径。"""
        safe_name = _INVALID_FILENAME_CHARS.sub("_", data.display_name).strip(
            " ."
        )
        if not safe_name:
            safe_name = "全速处理结果"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return output_dir / (
            f"{safe_name}_{data.session_id}_{timestamp}.xlsx"
        )

    @staticmethod
    def _build_task_rows(data: FullSpeedExportData) -> list[tuple[str, Any]]:
        """构造任务审计信息行。"""
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
        return [
            ("Session ID", data.session_id),
            ("数据包 ID", data.data_package_id or ""),
            ("Session 名称", data.display_name),
            ("来源文件", data.source_path),
            ("来源类型", data.source_type),
            ("Session 创建时间", data.created_at.isoformat(timespec="seconds")),
            ("结果保存时间", datetime.now().isoformat(timespec="seconds")),
            ("切片数量", data.slice_result.slice_count),
            ("有效识别类数量", valid_count),
            ("无效识别类数量", invalid_count),
            ("合并结果数量", merge_count),
            ("PA 模型", data.model_selection.pa_model_path or ""),
            ("DTOA 模型", data.model_selection.dtoa_model_path or ""),
            (
                "冻结参数",
                json.dumps(
                    data.config_snapshot.to_dict(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        ]

    @staticmethod
    def _build_recognition_rows(
        data: FullSpeedExportData,
    ) -> list[dict[str, Any]]:
        """构造有效与无效识别结果行。"""
        rows: list[dict[str, Any]] = []
        for slice_index in sorted(data.recognition_result.slice_results):
            recognition_slice = data.recognition_result.slice_results[
                slice_index
            ]
            cluster_slice = data.clustering_result.slice_results.get(
                slice_index
            )
            cluster_map = (
                {}
                if cluster_slice is None
                else {
                    cluster.cluster_idx: cluster
                    for cluster in cluster_slice.clusters
                }
            )
            recognitions = [
                *recognition_slice.valid_clusters,
                *recognition_slice.invalid_clusters,
            ]
            for recognition in recognitions:
                cluster = cluster_map.get(recognition.cluster_index)
                params = recognition.extracted_params
                time_range = (
                    cluster.time_ranges
                    if cluster is not None
                    else (None, None)
                )
                rows.append(
                    {
                        "切片编号": slice_index + 1,
                        "类簇编号": recognition.cluster_index,
                        "有效类编号": (
                            ""
                            if recognition.valid_cluster_index is None
                            else recognition.valid_cluster_index + 1
                        ),
                        "聚类维度": recognition.dim_name,
                        "识别结论": "有效" if recognition.is_valid else "无效",
                        "脉冲数量": (
                            0 if cluster is None else cluster.cluster_size
                        ),
                        "PA类别": recognition.pa_label,
                        "PA置信度": recognition.pa_confidence,
                        "DTOA类别": recognition.dtoa_label,
                        "DTOA置信度": recognition.dtoa_confidence,
                        "联合置信度": recognition.joint_prob,
                        "CF典型值(MHz)": _format_values(
                            () if params is None else params.cf_values
                        ),
                        "PW典型值(us)": _format_values(
                            () if params is None else params.pw_values
                        ),
                        "PRI典型值(us)": _format_values(
                            () if params is None else params.pri_values
                        ),
                        "DOA典型值(度)": _format_values(
                            () if params is None else params.doa_values
                        ),
                        "TOA起点(0.1us)": time_range[0],
                        "TOA终点(0.1us)": time_range[1],
                    }
                )
        return rows

    @staticmethod
    def _build_merge_rows(
        data: FullSpeedExportData,
    ) -> list[dict[str, Any]]:
        """构造独立合并结果行并保留来源类簇引用。"""
        rows: list[dict[str, Any]] = []
        for slice_index in sorted(data.merge_result.slice_results):
            slice_result = data.merge_result.slice_results[slice_index]
            for result in slice_result.merged_clusters:
                rows.append(
                    {
                        "切片编号": slice_index + 1,
                        "合并结果编号": result.merge_index,
                        "合并策略": result.strategy_id,
                        "来源类簇编号": "、".join(
                            str(index)
                            for index in result.source_cluster_indices
                        ),
                        "来源聚类维度": "、".join(result.source_dim_names),
                        "脉冲数量": len(result.merged_points),
                        "CF典型值(MHz)": _format_values(
                            result.extracted_params.cf_values
                        ),
                        "PW典型值(us)": _format_values(
                            result.extracted_params.pw_values
                        ),
                        "PRI典型值(us)": _format_values(
                            result.extracted_params.pri_values
                        ),
                        "DOA典型值(度)": _format_values(
                            result.extracted_params.doa_values
                        ),
                        "TOA起点(0.1us)": result.time_range[0],
                        "TOA终点(0.1us)": result.time_range[1],
                    }
                )
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
                width = min(60, max((len(value) for value in values), default=8) + 2)
                worksheet.column_dimensions[
                    column_cells[0].column_letter
                ].width = width


def _format_values(values: Iterable[float]) -> str:
    """把参数值列表格式化为 Excel 单元格文本。"""
    normalized = [f"{float(value):g}" for value in values]
    return "、".join(normalized) if normalized else "——"
