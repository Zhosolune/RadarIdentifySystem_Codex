"""通用脉冲文件导入后台线程。"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import uuid

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.logger import bind_session_log_context, unbind_session_log_context
from core.banding import BAND_LABELS, split_pulse_indices_by_band
from core.models.data_package import DataPackage
from core.models.pulse_batch import COL_PA, PulseBatch
from core.preprocess import preprocess
from infra.parsers import create_pulse_parser

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportExecutionRequest:
    """冻结一次导入任务所需的来源选择。

    Attributes:
        import_id: 导入任务唯一标识，与最终数据包 ID 相互独立。
        file_path: 来源文件路径。
        source_type: 来源类型，如 ``excel`` 或 ``bin``。
        data_format: 来源内部解析规则，如 ``old``、``new`` 或 ``pdw_v1``。
    """

    import_id: str
    file_path: str
    source_type: str
    data_format: str | None = None


@dataclass(frozen=True, slots=True)
class ImportWorkerResult:
    """导入线程终态结果。

    Attributes:
        success: 是否成功完成解析、拆分和预处理。
        packages: 成功生成的只读数据包集合，按 L/S/C 顺序排列。
        message: 成功摘要或失败原因。
    """

    success: bool
    packages: tuple[DataPackage, ...] = ()
    message: str = ""


class ImportWorker(QThread):
    """解析来源文件并按 L/S/C 波段生成独立数据包。"""

    finished_signal = pyqtSignal(str, object)

    def __init__(
        self,
        request: ImportExecutionRequest,
        parent: QObject | None = None,
    ) -> None:
        """初始化导入工作线程。

        Args:
            request [ImportExecutionRequest]: 已冻结的导入任务请求。
            parent [QObject | None]: Qt 父节点。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self._request = request

    def run(self) -> None:
        """执行格式解析、公共波段拆分与逐组预处理。

        Returns:
            None: 结果通过 ``finished_signal`` 发出。

        Raises:
            无。所有异常均转换为失败结果。
        """
        request = self._request
        log_token = bind_session_log_context(request.import_id)
        try:
            LOGGER.debug(
                "开始导入并预处理数据",
                extra={"session_id": request.import_id},
            )
            parser = create_pulse_parser(request.source_type)
            parsed_source = parser.parse(
                request.file_path,
                data_format=request.data_format,
            )
            band_indices = split_pulse_indices_by_band(parsed_source.data)

            packages: list[DataPackage] = []
            for band_key, source_indices in band_indices.items():
                if len(source_indices) == 0:
                    continue

                # 先确认源文件包含该波段，再应用 F26 等格式特有有效性规则。
                source_band_data = parsed_source.data[source_indices]
                source_band_valid = parsed_source.source_valid_mask[source_indices]
                normalized_band_data = source_band_data[source_band_valid]
                amplitude_dropped_pulses = int(
                    (source_band_data[:, COL_PA] == 255).sum()
                )
                package_id = uuid.uuid4().hex
                band_name = BAND_LABELS[band_key]

                raw_batch = PulseBatch(
                    data=normalized_band_data,
                    source_path=parsed_source.source_path,
                    source_type=parsed_source.source_type,
                    total_pulses=len(source_band_data),
                )
                preprocess_result = preprocess(
                    data=raw_batch.data,
                    source_path=raw_batch.source_path,
                    source_type=raw_batch.source_type,
                    slice_length=2_500_000,
                    session_id=package_id,
                    source_total_pulses=raw_batch.total_pulses,
                    source_amplitude_dropped_pulses=(
                        amplitude_dropped_pulses
                    ),
                    band_name=band_name,
                )
                packages.append(
                    DataPackage(
                        package_id=package_id,
                        display_name=f"{Path(request.file_path).name} - {band_name}",
                        raw_batch=raw_batch,
                        preprocess_result=preprocess_result,
                        dashboard_info=preprocess_result.dashboard_info,
                        data_format=request.data_format,
                    )
                )

            if not packages:
                raise ValueError("文件中没有可生成数据包的 L/S/C 波段脉冲")

            total_pulses = sum(
                package.preprocess_result.remaining_pulses
                for package in packages
            )
            message = (
                f"导入成功，生成 {len(packages)} 个波段数据包，"
                f"共 {total_pulses} 条有效脉冲"
            )
            LOGGER.debug(message, extra={"session_id": request.import_id})
            self.finished_signal.emit(
                request.import_id,
                ImportWorkerResult(
                    success=True,
                    packages=tuple(packages),
                    message=message,
                ),
            )
        except Exception as exc:
            LOGGER.error(
                "数据导入失败: %s",
                str(exc),
                extra={"session_id": request.import_id},
            )
            self.finished_signal.emit(
                request.import_id,
                ImportWorkerResult(
                    success=False,
                    message=f"导入失败: {str(exc)}",
                ),
            )
        finally:
            unbind_session_log_context(log_token)
