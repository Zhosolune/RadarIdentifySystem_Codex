"""切片处理识别流程编排。

功能描述：
    承载单切片 CF→PW→DOA 级联聚类与识别的完整业务规则，包括阶段迁移、
    回收点合并、DOA 复检、最终结果装配以及识别通过类的参数提取调用。
    模块只依赖 ``core`` 内部能力，不感知 Qt/UI/线程，可在无 Qt 环境独立运行。
    可复用的识别阶段算子集中在 ``core.identify_stages``；本模块只承载
    CF→PW→DOA 顺序特有的调度和阶段汇总日志，通过 ``SliceIdentifyPipeline``
    类聚合编排逻辑，供交互式工作流与全速逐片工作流共同复用。

Example:
    典型的使用场景：
    >>> from core.identify_pipeline import SliceIdentifyPipeline
    >>> pipeline = SliceIdentifyPipeline(inference_service=object())
    >>> # cluster_res, rec_res = pipeline.run(slice_data)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from core.clustering import process_dimension_clustering
from core.identify_stages import (
    IdentifyPipelineContext,
    IdentifyResultBuilder,
    IdentifyStageOps,
    PHASE_CLUSTERING,
    PHASE_RECOGNITION,
    build_slice_results,
    merge_stage_input_indices,
    recognition_map,
)
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import ClusterItem, SliceClusterResult
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.recognition import InferenceService


# 对外重新导出阶段常量与依赖，保留原有导入路径不受影响。
__all__ = [
    "PHASE_CLUSTERING",
    "PHASE_RECOGNITION",
    "IdentifyPipelineContext",
    "IdentifyResultBuilder",
    "SliceIdentifyPipeline",
]


# 模块日志器，用于输出识别流程的分层缩进日志。
LOGGER = logging.getLogger(__name__)


class SliceIdentifyPipeline:
    """切片处理识别流程编排。

    功能描述：
        以类的形态封装单切片 CF→PW→DOA 级联识别的编排逻辑。构造时一次性
        注入推理服务、聚类/识别/提取参数与流程上下文，运行时通过 ``run``
        方法完成一次单切片编排，方法内部按顺序调度 CF 主聚类、CF 一次识别、
        CF-DOA 复检、PW 主聚类、PW 一次识别、PW-DOA 复检，并把最终有效/
        无效簇通过 ``IdentifyResultBuilder`` 汇总为切片级结果。

        交互式工作流和全速逐片工作流共享本编排器及
        ``IdentifyStageOps`` 提供的阶段算子。

    Attributes:
        inference_service [InferenceService]: 推理服务实现，用于 PA/DTOA 识别。
        cluster_params [ClusteringParams]: 聚类参数快照。
        recognize_params [RecognitionParams]: 识别参数快照。
        extract_params [ExtractParams]: 参数提取配置。
        context [IdentifyPipelineContext]: 流程执行上下文，用于阶段标记与识别阶段回调。
        recognition_max_workers [int | None]: 簇级识别并发线程上限。
        stage_ops [IdentifyStageOps]: 阶段算子集合，聚合 DOA 复检与识别调用。
    """

    def __init__(
        self,
        inference_service: InferenceService,
        cluster_params: ClusteringParams | None = None,
        recognize_params: RecognitionParams | None = None,
        extract_params: ExtractParams | None = None,
        context: IdentifyPipelineContext | None = None,
        recognition_max_workers: int | None = None,
    ) -> None:
        """初始化切片识别流程编排器。

        Args:
            inference_service [InferenceService]: 推理服务实现。
            cluster_params [ClusteringParams | None]: 聚类参数；为 ``None`` 时使用默认参数。
            recognize_params [RecognitionParams | None]: 识别参数；为 ``None`` 时使用默认参数。
            extract_params [ExtractParams | None]: 参数提取配置；为 ``None`` 时使用默认参数。
            context [IdentifyPipelineContext | None]: 流程上下文；为 ``None`` 时创建默认上下文。
            recognition_max_workers [int | None]: 簇级识别并发线程上限；默认自动推导。
        """
        # 保存注入依赖，供后续每个阶段方法直接读取。
        self.inference_service = inference_service
        # 缺省参数一次性归一化，避免每个阶段方法反复兜底。
        self.cluster_params = cluster_params or ClusteringParams()
        self.recognize_params = recognize_params or RecognitionParams()
        self.extract_params = extract_params or ExtractParams()
        self.context = context or IdentifyPipelineContext()
        self.recognition_max_workers = recognition_max_workers
        # 构造阶段算子对象，聚合 DOA 复检、识别调用等可复用步骤。
        self.stage_ops = IdentifyStageOps(
            inference_service=self.inference_service,
            cluster_params=self.cluster_params,
            recognize_params=self.recognize_params,
            context=self.context,
            recognition_max_workers=self.recognition_max_workers,
        )

    def run(self, slice_data: Any) -> tuple[SliceClusterResult, SliceRecognitionResult]:
        """编排单切片 CF/PW/DOA 聚类与识别流程。

        功能描述：
            对单个切片依次执行 CF 聚类与识别、CF-DOA 复检、PW 聚类与识别、
            PW-DOA 复检，并把最终有效/无效簇通过 ``IdentifyResultBuilder`` 汇总为
            统一的切片级结果。

        Args:
            slice_data [Any]: 切片对象，需提供 ``index``、``data`` 和 ``time_range`` 字段。

        Returns:
            tuple[SliceClusterResult, SliceRecognitionResult]: 单切片最终聚类结果与识别结果。

        Raises:
            无显式抛出异常，底层聚类或识别异常会向上透传。

        Example:
            >>> from types import SimpleNamespace
            >>> import numpy as np
            >>> data = SimpleNamespace(index=0, data=np.empty((0, 6)), time_range=(0.0, 1.0))
            >>> pipeline = SliceIdentifyPipeline(inference_service=object())
            >>> cluster_res, rec_res = pipeline.run(data)
            >>> cluster_res.slice_idx, rec_res.slice_index
            (0, 0)
        """
        points = slice_data.data
        # 空切片直接返回空结果，避免后续聚类函数对空矩阵做无意义处理。
        if len(points) == 0:
            LOGGER.debug(
                "切片 %s 输入点集为空，跳过识别流程",
                slice_data.index,
            )
            return (
                SliceClusterResult(slice_data.index, [], np.array([]), np.array([])),
                SliceRecognitionResult(slice_data.index, [], []),
            )

        # 记录切片入口概览，标出总点数和时间范围。
        LOGGER.debug(
            "切片 %s 识别流程启动，总点数=%d，时间范围=%s",
            slice_data.index,
            len(points),
            slice_data.time_range,
        )

        # 创建结果装配器，统一维护最终 cluster_idx、识别记录和回收点索引。
        builder = IdentifyResultBuilder(self.extract_params)
        # CF 维度聚类与识别
        next_cluster_id, pw_input_indices = self._process_cf_stage(
            points=points,
            slice_index=slice_data.index,
            time_range=slice_data.time_range,
            builder=builder,
            start_cluster_id=1,
        )
        # PW 维度聚类与识别
        self._process_pw_stage(
            points=points,
            slice_index=slice_data.index,
            time_range=slice_data.time_range,
            pw_input_indices=pw_input_indices,
            builder=builder,
            start_cluster_id=next_cluster_id,
        )

        # 输出切片级最终统计，便于快速对齐 UI 显示的最终簇总数。
        LOGGER.debug(
            "切片 %s 识别流程结束：最终簇=%d（有效=%d，无效=%d），回收点=%d",
            slice_data.index + 1,
            len(builder.clusters) + 1,
            len(builder.valid_recognitions),
            len(builder.invalid_recognitions),
            len(builder.recycled_indices),
        )

        return build_slice_results(
            slice_index=slice_data.index,
            points=points,
            builder=builder,
        )

    def _process_cf_stage(
        self,
        points: np.ndarray,
        slice_index: int,
        time_range: tuple[float, float],
        builder: IdentifyResultBuilder,
        start_cluster_id: int,
    ) -> tuple[int, np.ndarray]:
        """执行 CF 聚类、一次识别和 CF-DOA 复检。"""
        # 进入 CF 聚类阶段，后续若失败则可明确标记为 clustering 阶段失败。
        self.context.enter_clustering()
        LOGGER.debug("[CF] 阶段开始，输入点数=%d", len(points))
        cf_clusters, cf_unprocessed_idx = process_dimension_clustering(
            points=points,
            dim_name="CF",
            dim_idx=0,
            epsilon=self.cluster_params.eps_cf,
            min_pts=self.cluster_params.min_pts_cf,
            min_cluster_size=self.cluster_params.min_cluster_size,
            slice_idx=slice_index,
            time_range=time_range,
            start_cluster_id=start_cluster_id,
        )
        # 记录 CF 聚类的簇数量、每簇点数和噪声点数，便于对齐 UI 展示。
        LOGGER.debug(
            "[CF] 聚类结果：%d 个候选簇，未聚类点=%d",
            len(cf_clusters),
            len(cf_unprocessed_idx),
        )
        for cluster in cf_clusters:
            LOGGER.debug(
                "  ├─ CF 簇 %d：点数=%d",
                cluster.cluster_idx,
                cluster.cluster_size,
            )
        # 预留下一阶段起始簇编号，避免 PW 阶段沿用已分配的临时编号。
        next_cluster_id = start_cluster_id + len(cf_clusters)
        # 对 CF 聚类结果做第一次识别，区分有效簇与无效簇。
        cf_valid, cf_invalid, cf_recognitions, _ = self.stage_ops.recognize(
            clusters=cf_clusters,
            start_index=len(builder.valid_recognitions),
        )
        LOGGER.debug(
            "[CF] 一次识别完成：识别通过=%d，识别未通过=%d",
            len(cf_valid),
            len(cf_invalid),
        )
        # 对 CF 一次识别通过的簇继续做 DOA 复检，并回收 DOA 失败子簇点。
        (
            cf_doa_recycled_indices,
            cf_parent_kept,
            cf_doa_passed,
            cf_doa_failed,
        ) = self.stage_ops.append_doa_results(
            builder=builder,
            valid_clusters=cf_valid,
            source_recognition_map=recognition_map(cf_recognitions),
            recycle_failed_children=True,
            parent_dim_name="CF",
        )
        # CF 阶段整体汇总：把 CF 一次识别失败簇、未拆分父簇（直接保留）与 DOA 拆分后的子簇合并计数，
        # 反映 CF 聚类 + DOA 复检后经过识别的最终簇数量。
        cf_stage_passed_total = cf_parent_kept + cf_doa_passed
        cf_stage_failed_total = len(cf_invalid) + cf_doa_failed
        LOGGER.debug(
            "[CF] 阶段整体识别汇总：识别通过=%d（未拆分父簇=%d + DOA 拆分通过=%d），"
            "识别未通过=%d（CF 一次未通过=%d + DOA 拆分未通过=%d）",
            cf_stage_passed_total,
            cf_parent_kept,
            cf_doa_passed,
            cf_stage_failed_total,
            len(cf_invalid),
            cf_doa_failed,
        )
        # 合并 CF 阶段未走通的所有点，作为 PW 阶段的输入。
        pw_input_indices = merge_stage_input_indices(
            unprocessed_idx=cf_unprocessed_idx,
            invalid_clusters=cf_invalid,
            recycled_indices=cf_doa_recycled_indices,
        )
        LOGGER.debug(
            "[CF] 阶段结束，进入 PW 阶段的候选点=%d（CF 未聚类=%d + CF 无效簇点=%d + CF-DOA 回收=%d）",
            len(pw_input_indices),
            len(cf_unprocessed_idx),
            sum(cluster.cluster_size for cluster in cf_invalid),
            len(cf_doa_recycled_indices),
        )
        return next_cluster_id, pw_input_indices

    def _process_pw_stage(
        self,
        points: np.ndarray,
        slice_index: int,
        time_range: tuple[float, float],
        pw_input_indices: np.ndarray,
        builder: IdentifyResultBuilder,
        start_cluster_id: int,
    ) -> None:
        """执行 PW 聚类、一次识别和 PW-DOA 复检。"""
        # 如果 CF 阶段已经吃掉全部有效点，则无需再进入 PW。
        if len(pw_input_indices) == 0:
            LOGGER.debug("[PW] 阶段跳过：CF 阶段已消化全部有效点")
            return

        # 从原始切片点集中抽取 PW 需要继续处理的子集。
        pw_points = points[pw_input_indices]
        # 标记重新进入聚类阶段，便于异常时区分失败来源。
        self.context.enter_clustering()
        LOGGER.debug("[PW] 阶段开始，输入点数=%d", len(pw_points))
        pw_clusters, pw_unprocessed_idx = process_dimension_clustering(
            points=pw_points,
            dim_name="PW",
            dim_idx=1,
            epsilon=self.cluster_params.eps_pw,
            min_pts=self.cluster_params.min_pts_pw,
            min_cluster_size=self.cluster_params.min_cluster_size,
            slice_idx=slice_index,
            time_range=time_range,
            start_cluster_id=start_cluster_id,
        )
        for cluster in pw_clusters:
            # PW 输入是回收点子集，需要把局部索引映射回原始切片数据索引。
            cluster.points_indices = pw_input_indices[cluster.points_indices]
        LOGGER.debug(
            "[PW] 聚类结果：%d 个候选簇，未聚类点=%d",
            len(pw_clusters),
            len(pw_unprocessed_idx),
        )
        for cluster in pw_clusters:
            LOGGER.debug(
                "  ├─ PW 簇 %d：点数=%d",
                cluster.cluster_idx,
                cluster.cluster_size,
            )

        # 对 PW 聚类结果做一次识别，后续再按原始 PW 顺序处理最终输出。
        pw_valid, pw_invalid, pw_recognitions, _ = self.stage_ops.recognize(
            clusters=pw_clusters,
            start_index=len(builder.valid_recognitions),
        )
        LOGGER.debug(
            "[PW] 一次识别完成：识别通过=%d，识别未通过=%d",
            len(pw_valid),
            len(pw_invalid),
        )
        self._append_final_pw_results(
            builder=builder,
            pw_clusters=pw_clusters,
            pw_valid=pw_valid,
            pw_invalid=pw_invalid,
            pw_recognitions=pw_recognitions,
        )
        LOGGER.debug("[PW] 阶段结束")

    def _append_final_pw_results(
        self,
        builder: IdentifyResultBuilder,
        pw_clusters: list[ClusterItem],
        pw_valid: list[ClusterItem],
        pw_invalid: list[ClusterItem],
        pw_recognitions: list[ClusterRecognition],
    ) -> None:
        """按 PW 聚类原始顺序追加 PW 识别和 PW-DOA 结果。"""
        # 先构建查询映射，避免在循环中反复线性查找识别结果。
        pw_rec_map = recognition_map(pw_recognitions)
        pw_valid_map = {cluster.cluster_idx: cluster for cluster in pw_valid}
        pw_invalid_map = {cluster.cluster_idx: cluster for cluster in pw_invalid}
        # 累计 PW 阶段整体识别汇总所需的通过/未通过计数。
        pw_parent_kept_total = 0
        pw_doa_passed_total = 0
        pw_doa_failed_total = 0
        # 按 PW 聚类原始编号顺序输出，保持“展示全部聚类结果”时的浏览顺序稳定。
        for cluster in sorted(pw_clusters, key=lambda item: item.cluster_idx):
            if cluster.cluster_idx in pw_invalid_map:
                rec = pw_rec_map.get(cluster.cluster_idx)
                if rec is not None:
                    # PW 一次识别失败已经处于末轮流程，直接作为最终无效结果。
                    builder.append_invalid(cluster, rec)
                continue

            valid_cluster = pw_valid_map.get(cluster.cluster_idx)
            if valid_cluster is None:
                # 忽略没有识别记录的异常分支，避免污染最终输出。
                continue
            # PW 识别通过簇仍需执行 DOA 检查，保持 CF/PW 两段流程对称。
            (
                pw_doa_recycled,
                pw_parent_kept,
                pw_doa_passed,
                pw_doa_failed,
            ) = self.stage_ops.append_doa_results(
                builder=builder,
                valid_clusters=[valid_cluster],
                source_recognition_map=pw_rec_map,
                recycle_failed_children=False,
                parent_dim_name="PW",
            )
            builder.recycled_indices.update(pw_doa_recycled)
            # 汇总本父簇的 PW 阶段通过/未通过计数。
            pw_parent_kept_total += pw_parent_kept
            pw_doa_passed_total += pw_doa_passed
            pw_doa_failed_total += pw_doa_failed

        # PW 阶段整体识别汇总：包含 PW 一次识别失败簇、未拆分父簇与 DOA 拆分后的子簇。
        pw_stage_passed_total = pw_parent_kept_total + pw_doa_passed_total
        pw_stage_failed_total = len(pw_invalid) + pw_doa_failed_total
        LOGGER.debug(
            "[PW] 阶段整体识别汇总：识别通过=%d（未拆分父簇=%d + DOA 拆分通过=%d），"
            "识别未通过=%d（PW 一次未通过=%d + DOA 拆分未通过=%d）",
            pw_stage_passed_total,
            pw_parent_kept_total,
            pw_doa_passed_total,
            pw_stage_failed_total,
            len(pw_invalid),
            pw_doa_failed_total,
        )
