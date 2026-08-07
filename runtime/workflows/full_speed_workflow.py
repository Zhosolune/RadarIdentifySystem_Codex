"""全速处理线程编排工作流。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypeAlias

from PyQt6.QtCore import QObject, pyqtSlot

from app.app_config import appConfig, qconfig
from app.signal_bus import signal_bus
from core.models.processing_session import ProcessingSession
from core.models.session_config import SessionConfigSnapshot
from core.models.session_model import SessionModelSelection
from runtime.full_speed_session_registry import (
    FullSpeedSessionRegistry,
    FullSpeedStatus,
)
from runtime.threading.full_speed_worker import (
    FullSpeedExecutionRequest,
    FullSpeedWorker,
    FullSpeedWorkerResult,
)


LOGGER = logging.getLogger(__name__)
WorkerType: TypeAlias = FullSpeedWorker


class FullSpeedWorkflow(QObject):
    """并发编排多个相互独立的全速 Session。

    Attributes:
        registry: 全速 Session 注册器。
    """

    def __init__(
        self,
        registry: FullSpeedSessionRegistry,
        parent: QObject | None = None,
    ) -> None:
        """初始化全速处理工作流。

        Args:
            registry [FullSpeedSessionRegistry]: 全速 Session 注册器。
            parent [QObject | None]: Qt 父对象。

        Returns:
            None: 无返回值。
        """
        super().__init__(parent)
        self.registry = registry
        self._workers: dict[str, WorkerType] = {}
        self._user_cancel_requests: set[str] = set()

    def start(self, session_id: str) -> None:
        """启动、取消后重新开始或按冻结参数重试全速 Session。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            None: 无返回值。

        Raises:
            KeyError: Session 不存在时抛出。
            RuntimeError: 相同任务正在运行或已成功时抛出。
            ValueError: 输入、模型或保存目录配置不完整时抛出。
            OSError: 冻结配置持久化失败时抛出。
        """
        existing = self._workers.get(session_id)
        if existing is not None and existing.isRunning():
            raise RuntimeError("该全速任务正在执行")

        session = self.registry.get(session_id)
        if session is None:
            raise KeyError(f"全速 Session 不存在: {session_id}")
        concurrent_limit = max(
            1,
            int(qconfig.get(appConfig.fullSpeedMaxConcurrentTasks)),
        )
        running_count = sum(
            worker.isRunning()
            for worker in self._workers.values()
        )
        if running_count >= concurrent_limit:
            raise RuntimeError(
                "已达到全速任务并发上限"
                f"（{concurrent_limit} 个），请等待当前任务结束"
            )
        self._validate_session(session)
        session = self.registry.begin(session_id)
        request = self._build_request(session)
        worker = FullSpeedWorker(request, parent=self)
        worker.progress_signal.connect(self._on_progress)
        worker.finished_signal.connect(self._on_finished)
        self._workers[session_id] = worker
        signal_bus.full_speed_session_changed.emit(session_id)
        try:
            worker.start()
        except Exception as error:
            self._workers.pop(session_id, None)
            worker.deleteLater()
            self.registry.mark_failed(session_id, str(error))
            signal_bus.full_speed_session_changed.emit(session_id)
            raise

    def cancel(self, session_id: str) -> bool:
        """请求运行中的任务在安全检查点取消。

        Args:
            session_id [str]: 目标 Session ID。

        Returns:
            bool: 已发送取消请求返回 True；当前不可取消返回 False。
        """
        worker = self._workers.get(session_id)
        state = self.registry.state(session_id)
        if (
            worker is None
            or not worker.isRunning()
            or state is None
            or state.status is not FullSpeedStatus.RUNNING
        ):
            return False
        self.registry.mark_cancelling(session_id)
        self._user_cancel_requests.add(session_id)
        worker.request_cancel()
        signal_bus.full_speed_session_changed.emit(session_id)
        return True

    def is_running(self, session_id: str | None = None) -> bool:
        """查询一个或全部全速任务是否正在执行。

        Args:
            session_id [str | None]: 指定 Session ID；为 None 时查询全部。

        Returns:
            bool: 存在符合条件的运行线程时返回 True。
        """
        if session_id is not None:
            worker = self._workers.get(session_id)
            return worker is not None and worker.isRunning()
        return any(worker.isRunning() for worker in self._workers.values())

    def shutdown(self, timeout_ms: int = 30_000) -> bool:
        """请求全部任务停止并等待线程退出。

        Args:
            timeout_ms [int]: 每个线程最长等待毫秒数，默认 30 秒。

        Returns:
            bool: 全部线程均已退出返回 True，否则返回 False。
        """
        workers = list(self._workers.values())
        for worker in workers:
            if worker.isRunning():
                worker.request_cancel()
        all_stopped = True
        for worker in workers:
            if worker.isRunning() and not worker.wait(timeout_ms):
                all_stopped = False
        return all_stopped

    @pyqtSlot(str, str, int, int, int, str, bool)
    def _on_progress(
        self,
        session_id: str,
        stage: str,
        current_slice: int,
        total_slices: int,
        progress: int,
        message: str,
        exporting: bool,
    ) -> None:
        """接收线程进度并同步注册器及主页卡片。"""
        self.registry.update_progress(
            session_id,
            current_stage=stage,
            current_slice=current_slice,
            total_slices=total_slices,
            progress=progress,
            message=message,
            exporting=exporting,
        )
        signal_bus.full_speed_session_changed.emit(session_id)

    @pyqtSlot(str, object)
    def _on_finished(
        self,
        session_id: str,
        result: FullSpeedWorkerResult,
    ) -> None:
        """提交完整结果或记录失败/取消终态。"""
        try:
            if result.success:
                self._commit_success(session_id, result)
                signal_bus.stage_finished.emit(
                    session_id,
                    "full_speed",
                    None,
                )
            elif result.cancelled:
                self.registry.mark_cancelled(
                    session_id,
                    unlock_settings=(
                        session_id in self._user_cancel_requests
                    ),
                )
                signal_bus.stage_failed.emit(
                    session_id,
                    "full_speed",
                    None,
                    "任务已取消",
                )
            else:
                error_message = result.error_message or "未知错误"
                self.registry.mark_failed(session_id, error_message)
                signal_bus.stage_failed.emit(
                    session_id,
                    "full_speed",
                    None,
                    error_message,
                )
        except Exception as error:
            LOGGER.error(
                "提交全速任务结果失败: %s",
                error,
                exc_info=True,
                extra={"session_id": session_id},
            )
            self.registry.mark_failed(session_id, str(error))
        finally:
            self._user_cancel_requests.discard(session_id)
            worker = self._workers.pop(session_id, None)
            if worker is not None:
                worker.deleteLater()
            signal_bus.full_speed_session_changed.emit(session_id)

    def _commit_success(
        self,
        session_id: str,
        result: FullSpeedWorkerResult,
    ) -> None:
        """把线程返回的原子结果写入对应 Session。"""
        if (
            result.slice_result is None
            or result.clustering_result is None
            or result.recognition_result is None
            or result.merge_plan is None
            or result.merge_result is None
            or not result.output_file
        ):
            raise ValueError("全速线程返回的成功结果不完整")
        session = self.registry.get(session_id)
        if session is None:
            raise KeyError(f"全速 Session 不存在: {session_id}")

        with session.lock:
            session.slice_result = result.slice_result
            session.cluster_result = result.clustering_result
            session.recognition_result = result.recognition_result
            session.merge_plan = result.merge_plan
            session.merge_result = result.merge_result
            session.reset_slice_processing_states(
                result.slice_result.slice_count
            )
            for slice_index in range(result.slice_result.slice_count):
                session.mark_slice_cluster_succeeded(slice_index)
                session.mark_slice_recognition_succeeded(slice_index)
                session.mark_slice_merge_succeeded(slice_index)
        self.registry.mark_succeeded(session_id, result.output_file)

    @staticmethod
    def _validate_session(session: ProcessingSession) -> None:
        """校验构造全速执行请求所需的固定输入。"""
        if session.preprocess_result is None:
            raise ValueError("全速 Session 缺少数据池预处理结果")
        if session.raw_batch is None:
            raise ValueError("全速 Session 缺少数据池原始脉冲")
        if not session.config_snapshot.business.export_dir_path.strip():
            raise ValueError("请先设置 Excel 保存目录")
        selection = session.model_selection
        if not selection.pa_model_path or not selection.dtoa_model_path:
            raise ValueError("请先配置 PA 和 DTOA 模型")
        missing_models = [
            model_path
            for model_path in (
                selection.pa_model_path,
                selection.dtoa_model_path,
            )
            if not Path(model_path).is_file()
        ]
        if missing_models:
            raise ValueError(
                f"模型文件不存在: {', '.join(missing_models)}"
            )

    @staticmethod
    def _build_request(
        session: ProcessingSession,
    ) -> FullSpeedExecutionRequest:
        """从 Session 创建与后续 UI 变更隔离的深拷贝快照。"""
        if session.preprocess_result is None or session.raw_batch is None:
            raise ValueError("全速 Session 缺少原始脉冲或预处理结果")
        configured_temp_dir = str(qconfig.get(appConfig.logDir)).strip()
        return FullSpeedExecutionRequest(
            session_id=session.session_id,
            data_package_id=session.data_package_id,
            display_name=session.display_name,
            source_path=session.source_path,
            source_type=session.source_type,
            data_format=session.data_format,
            created_at=session.created_at,
            preprocess_result=session.preprocess_result,
            raw_batch=session.raw_batch,
            config_snapshot=SessionConfigSnapshot.from_dict(
                session.config_snapshot.to_dict()
            ),
            model_selection=SessionModelSelection.from_dict(
                session.model_selection.to_dict()
            ),
            output_dir=session.config_snapshot.business.export_dir_path,
            temp_dir=(
                configured_temp_dir
                or session.config_snapshot.business.export_dir_path
            ),
            compute_device=str(
                qconfig.get(appConfig.fullSpeedComputeDevice)
            ).upper(),
            recognition_workers=max(
                1,
                int(qconfig.get(appConfig.fullSpeedRecognitionWorkers)),
            ),
        )
