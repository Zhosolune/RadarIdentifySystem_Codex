"""识别流程核心编排。

功能描述：
    承载单切片 CF→PW→DOA 级联聚类与识别的完整业务规则，包括阶段迁移、
    回收点合并、DOA 复检、最终结果装配以及识别通过类的参数提取调用。
    模块只依赖 ``core`` 内部能力，不感知 Qt/UI/线程，可在无 Qt 环境独立运行。

Example:
    典型的使用场景：
    >>> from core.identify_pipeline import identify_slice, IdentifyPipelineContext
    >>> ctx = IdentifyPipelineContext()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from core.clustering import clip_doa_clusters_by_size, process_dimension_clustering
from core.models.algorithm_params import ClusteringParams, ExtractParams, RecognitionParams
from core.models.cluster_result import ClusterItem, ClusterState, SliceClusterResult
from core.models.pulse_batch import COL_DOA
from core.models.recognition_result import ClusterRecognition, SliceRecognitionResult
from core.params_extract import extract_cluster_params
from core.recognition import InferenceService, recognize_clusters_parallel


# 阶段常量，供上层在异常时判定失败归属。
PHASE_CLUSTERING = "clustering"
PHASE_RECOGNITION = "recognition"


@dataclass
class IdentifyPipelineContext:
    """识别流程执行上下文。

    功能描述：
        用于在流程内部标记当前所处阶段，并在首次进入识别阶段时通过可选回调
        通知外部（例如线程层的进度信号）。上层线程可在流程抛出异常后读取
        ``current_phase`` 来判定失败归属。

    Attributes:
        current_phase [str]: 当前阶段名称，取值为 ``"clustering"`` 或 ``"recognition"``。
        on_recognition_started [Callable[[], None] | None]: 首次进入识别阶段的通知回调。
    """

    current_phase: str = PHASE_CLUSTERING
    on_recognition_started: Callable[[], None] | None = None
    # 内部标记，避免多轮 DOA 复检时重复触发识别阶段回调。
    _recognition_notified: bool = False

    def enter_clustering(self) -> None:
        """标记流程进入聚类阶段。"""
        # 每次进入聚类阶段都重置阶段名，方便异常时定位失败归属。
        self.current_phase = PHASE_CLUSTERING

    def enter_recognition(self) -> None:
        """标记流程进入识别阶段并按需触发一次通知回调。"""
        # 每次进入识别阶段都刷新当前阶段名，供异常路径读取。
        self.current_phase = PHASE_RECOGNITION
        if not self._recognition_notified:
            # 首次进入识别阶段时同步触发通知，避免多轮复检重复刷状态。
            self._recognition_notified = True
            if self.on_recognition_started is not None:
                self.on_recognition_started()


def identify_slice(
    slice_data: Any,
    inference_service: InferenceService,
    cluster_params: ClusteringParams | None = None,
    recognize_params: RecognitionParams | None = None,
    extract_params: ExtractParams | None = None,
    context: IdentifyPipelineContext | None = None,
) -> tuple[SliceClusterResult, SliceRecognitionResult]:
    """编排单切片 CF/PW/DOA 聚类与识别流程。

    功能描述：
        对单个切片依次执行 CF 聚类与识别、CF-DOA 复检、PW 聚类与识别、
        PW-DOA 复检，并把最终有效/无效簇通过 ``IdentifyResultBuilder`` 汇总为
        统一的切片级结果。

    Args:
        slice_data [Any]: 切片对象，需提供 ``index``、``data`` 和 ``time_range`` 字段。
        inference_service [InferenceService]: 推理服务实现，用于 PA/DTOA 识别。
        cluster_params [ClusteringParams | None]: 聚类参数；为 ``None`` 时使用默认参数。
        recognize_params [RecognitionParams | None]: 识别参数；为 ``None`` 时使用默认参数。
        extract_params [ExtractParams | None]: 参数提取配置；为 ``None`` 时使用默认参数。
        context [IdentifyPipelineContext | None]: 流程上下文，用于阶段标记与识别阶段回调；
            为 ``None`` 时内部创建默认上下文。

    Returns:
        tuple[SliceClusterResult, SliceRecognitionResult]: 单切片最终聚类结果与识别结果。

    Raises:
        无显式抛出异常，底层聚类或识别异常会向上透传。

    Example:
        >>> from types import SimpleNamespace
        >>> import numpy as np
        >>> data = SimpleNamespace(index=0, data=np.empty((0, 5)), time_range=(0.0, 1.0))
        >>> cluster_res, rec_res = identify_slice(data, object())
        >>> cluster_res.slice_idx, rec_res.slice_index
        (0, 0)
    """
    cluster_params = cluster_params or ClusteringParams()
    recognize_params = recognize_params or RecognitionParams()
    extract_params = extract_params or ExtractParams()
    context = context or IdentifyPipelineContext()

    points = slice_data.data
    # 空切片直接返回空结果，避免后续聚类函数对空矩阵做无意义处理。
    if len(points) == 0:
        return (
            SliceClusterResult(slice_data.index, [], np.array([]), np.array([])),
            SliceRecognitionResult(slice_data.index, [], []),
        )

    # 创建结果装配器，统一维护最终 cluster_idx、识别记录和回收点索引。
    builder = IdentifyResultBuilder(extract_params)
    # CF维度聚类与识别
    next_cluster_id, pw_input_indices = _process_cf_stage(
        points=points,
        slice_index=slice_data.index,
        time_range=slice_data.time_range,
        builder=builder,
        inference_service=inference_service,
        cluster_params=cluster_params,
        recognize_params=recognize_params,
        context=context,
        start_cluster_id=1,
    )
    # PW维度聚类与识别
    _process_pw_stage(
        points=points,
        slice_index=slice_data.index,
        time_range=slice_data.time_range,
        pw_input_indices=pw_input_indices,
        builder=builder,
        inference_service=inference_service,
        cluster_params=cluster_params,
        recognize_params=recognize_params,
        context=context,
        start_cluster_id=next_cluster_id,
    )

    return _build_slice_results(
        slice_index=slice_data.index,
        points=points,
        builder=builder,
    )


def _process_cf_stage(
    points: np.ndarray,
    slice_index: int,
    time_range: tuple[float, float],
    builder: "IdentifyResultBuilder",
    inference_service: InferenceService,
    cluster_params: ClusteringParams,
    recognize_params: RecognitionParams,
    context: IdentifyPipelineContext,
    start_cluster_id: int,
) -> tuple[int, np.ndarray]:
    """执行 CF 聚类、一次识别和 CF-DOA 复检。"""
    # 进入 CF 聚类阶段，后续若失败则可明确标记为 clustering 阶段失败。
    context.enter_clustering()
    cf_clusters, cf_unprocessed_idx = process_dimension_clustering(
        points=points,
        dim_name="CF",
        dim_idx=0,
        epsilon=cluster_params.eps_cf,
        min_pts=cluster_params.min_pts_cf,
        min_cluster_size=cluster_params.min_cluster_size,
        slice_idx=slice_index,
        time_range=time_range,
        start_cluster_id=start_cluster_id,
    )
    # 预留下一阶段起始簇编号，避免 PW 阶段沿用已分配的临时编号。
    next_cluster_id = start_cluster_id + len(cf_clusters)
    # 对 CF 聚类结果做第一次识别，区分有效簇与无效簇。
    cf_valid, cf_invalid, cf_recognitions, _ = _recognize_clusters(
        clusters=cf_clusters,
        inference_service=inference_service,
        recognize_params=recognize_params,
        start_index=len(builder.valid_recognitions),
        context=context,
    )
    # 对 CF 一次识别通过的簇继续做 DOA 复检，并回收 DOA 失败子簇点。
    cf_doa_recycled_indices = _append_doa_results_for_valid_clusters(
        builder=builder,
        valid_clusters=cf_valid,
        source_recognition_map=_recognition_map(cf_recognitions),
        inference_service=inference_service,
        cluster_params=cluster_params,
        recognize_params=recognize_params,
        context=context,
        recycle_failed_children=True,
    )
    # 合并 CF 阶段未走通的所有点，作为 PW 阶段的输入。
    pw_input_indices = _merge_pw_input_indices(
        cf_unprocessed_idx=cf_unprocessed_idx,
        cf_invalid_clusters=cf_invalid,
        cf_doa_recycled_indices=cf_doa_recycled_indices,
    )
    return next_cluster_id, pw_input_indices


def _process_pw_stage(
    points: np.ndarray,
    slice_index: int,
    time_range: tuple[float, float],
    pw_input_indices: np.ndarray,
    builder: "IdentifyResultBuilder",
    inference_service: InferenceService,
    cluster_params: ClusteringParams,
    recognize_params: RecognitionParams,
    context: IdentifyPipelineContext,
    start_cluster_id: int,
) -> None:
    """执行 PW 聚类、一次识别和 PW-DOA 复检。"""
    # 如果 CF 阶段已经吃掉全部有效点，则无需再进入 PW。
    if len(pw_input_indices) == 0:
        return

    # 从原始切片点集中抽取 PW 需要继续处理的子集。
    pw_points = points[pw_input_indices]
    # 标记重新进入聚类阶段，便于异常时区分失败来源。
    context.enter_clustering()
    pw_clusters, _ = process_dimension_clustering(
        points=pw_points,
        dim_name="PW",
        dim_idx=1,
        epsilon=cluster_params.eps_pw,
        min_pts=cluster_params.min_pts_pw,
        min_cluster_size=cluster_params.min_cluster_size,
        slice_idx=slice_index,
        time_range=time_range,
        start_cluster_id=start_cluster_id,
    )
    for cluster in pw_clusters:
        # PW 输入是回收点子集，需要把局部索引映射回原始切片数据索引。
        cluster.points_indices = pw_input_indices[cluster.points_indices]

    # 对 PW 聚类结果做一次识别，后续再按原始 PW 顺序处理最终输出。
    pw_valid, pw_invalid, pw_recognitions, _ = _recognize_clusters(
        clusters=pw_clusters,
        inference_service=inference_service,
        recognize_params=recognize_params,
        start_index=len(builder.valid_recognitions),
        context=context,
    )
    _append_final_pw_results(
        builder=builder,
        pw_clusters=pw_clusters,
        pw_valid=pw_valid,
        pw_invalid=pw_invalid,
        pw_recognitions=pw_recognitions,
        inference_service=inference_service,
        cluster_params=cluster_params,
        recognize_params=recognize_params,
        context=context,
    )


def _merge_pw_input_indices(
    cf_unprocessed_idx: np.ndarray,
    cf_invalid_clusters: list[ClusterItem],
    cf_doa_recycled_indices: set[int],
) -> np.ndarray:
    """合并 PW 阶段需要继续处理的原始点索引。"""
    # 合并三类输入：CF 未聚类点、CF 一次识别失败簇、CF-DOA 复检失败子簇。
    pw_input_indices = (
        set(int(index) for index in cf_unprocessed_idx.tolist())
        | _collect_cluster_indices(cf_invalid_clusters)
        | cf_doa_recycled_indices
    )
    # 返回排序后的 numpy 索引数组，保证后续 PW 聚类输入稳定可复现。
    return np.array(sorted(pw_input_indices), dtype=int)


def _append_final_pw_results(
    builder: "IdentifyResultBuilder",
    pw_clusters: list[ClusterItem],
    pw_valid: list[ClusterItem],
    pw_invalid: list[ClusterItem],
    pw_recognitions: list[ClusterRecognition],
    inference_service: InferenceService,
    cluster_params: ClusteringParams,
    recognize_params: RecognitionParams,
    context: IdentifyPipelineContext,
) -> None:
    """按 PW 聚类原始顺序追加 PW 识别和 PW-DOA 结果。"""
    # 先构建查询映射，避免在循环中反复线性查找识别结果。
    pw_rec_map = _recognition_map(pw_recognitions)
    pw_valid_map = {cluster.cluster_idx: cluster for cluster in pw_valid}
    pw_invalid_map = {cluster.cluster_idx: cluster for cluster in pw_invalid}
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
        pw_doa_recycled = _append_doa_results_for_valid_clusters(
            builder=builder,
            valid_clusters=[valid_cluster],
            source_recognition_map=pw_rec_map,
            inference_service=inference_service,
            cluster_params=cluster_params,
            recognize_params=recognize_params,
            context=context,
            recycle_failed_children=False,
        )
        builder.recycled_indices.update(pw_doa_recycled)


def _append_doa_results_for_valid_clusters(
    builder: "IdentifyResultBuilder",
    valid_clusters: list[ClusterItem],
    source_recognition_map: dict[int, ClusterRecognition],
    inference_service: InferenceService,
    cluster_params: ClusteringParams,
    recognize_params: RecognitionParams,
    context: IdentifyPipelineContext,
    recycle_failed_children: bool,
) -> set[int]:
    """对一次识别通过的簇执行 DOA 复检并追加最终结果。"""
    recycled_indices: set[int] = set()
    # 按当前簇编号顺序处理，保持最终编号分配和 UI 浏览顺序稳定。
    for cluster in sorted(valid_clusters, key=lambda item: item.cluster_idx):
        source_rec = source_recognition_map.get(cluster.cluster_idx)
        if source_rec is None:
            # 没有找到一次识别记录时，跳过该簇以避免构造不完整最终结果。
            continue

        # 基于父簇点集再次执行 DOA 聚类，判断是否存在需要拆分的方位子类。
        doa_children = _cluster_doa_children(cluster, cluster_params, context)
        if len(doa_children) <= 1:
            # 未拆出多个子簇时，保留父簇作为最终有效结果。
            builder.append_valid(cluster, source_rec)
            continue

        for offset, child in enumerate(doa_children):
            # 临时索引用于本轮复识别结果映射，最终追加时会重新分配连续索引。
            child.cluster_idx = builder.next_cluster_id + offset
        # 对拆出的 DOA 子簇再次识别，筛选真正保留的最终子簇。
        doa_valid, doa_invalid, doa_recognitions, _ = _recognize_clusters(
            clusters=doa_children,
            inference_service=inference_service,
            recognize_params=recognize_params,
            start_index=len(builder.valid_recognitions),
            context=context,
        )
        doa_rec_map = _recognition_map(doa_recognitions)
        for child in doa_valid:
            rec = doa_rec_map.get(child.cluster_idx)
            if rec is not None:
                # 仅把二次识别通过的 DOA 子簇写入最终有效结果。
                builder.append_valid(child, rec)

        for child in doa_invalid:
            rec = doa_rec_map.get(child.cluster_idx)
            if rec is None:
                # 没有识别记录时忽略，避免写入缺失标签的无效簇。
                continue
            if recycle_failed_children:
                # CF 阶段的 DOA 失败子簇不能直接判死，需要回收到 PW 再试一次。
                recycled_indices.update(int(index) for index in child.points_indices)
                continue
            # PW 阶段已经是末轮，DOA 失败子簇直接进入最终无效结果。
            builder.append_invalid(child, rec)
            # 同步记录回收点，避免这些点再被误算成“未处理点”。
            recycled_indices.update(int(index) for index in child.points_indices)

    return recycled_indices


def _cluster_doa_children(
    parent_cluster: ClusterItem,
    cluster_params: ClusteringParams,
    context: IdentifyPipelineContext,
) -> list[ClusterItem]:
    """复用核心单维聚类函数生成 DOA 子簇。"""
    # DOA 子簇生成仍属于聚类阶段，异常时需要按 clustering 归类。
    context.enter_clustering()
    doa_clusters, _ = process_dimension_clustering(
        points=parent_cluster.points,
        dim_name="DOA",
        dim_idx=COL_DOA,
        epsilon=cluster_params.eps_doa,
        min_pts=cluster_params.min_pts_doa,
        min_cluster_size=cluster_params.min_cluster_size,
        slice_idx=parent_cluster.slice_idx,
        time_range=parent_cluster.time_ranges,
        start_cluster_id=parent_cluster.cluster_idx,
    )
    for cluster in doa_clusters:
        # DOA 聚类输入是父簇点集，需要把局部索引映射回原始切片数据索引。
        cluster.points_indices = parent_cluster.points_indices[cluster.points_indices]
    return clip_doa_clusters_by_size(
        clusters=doa_clusters,
        total_points=len(parent_cluster.points),
        clip_threshold_percent=cluster_params.clip_threshold_doa,
    )


def _recognize_clusters(
    clusters: list[ClusterItem],
    inference_service: InferenceService,
    recognize_params: RecognitionParams,
    start_index: int,
    context: IdentifyPipelineContext,
) -> tuple[list[ClusterItem], list[ClusterItem], list[ClusterRecognition], int]:
    """执行簇识别并在首次识别前触发上下文识别阶段回调。"""
    # 标记当前进入识别阶段，供上层在失败时区分状态写回。
    context.enter_recognition()
    return recognize_clusters_parallel(
        clusters,
        inference_service,
        recognize_params,
        start_index,
    )


def _build_slice_results(
    slice_index: int,
    points: np.ndarray,
    builder: "IdentifyResultBuilder",
) -> tuple[SliceClusterResult, SliceRecognitionResult]:
    """根据结果收集器构建单切片最终输出。"""
    # 收集最终有效簇覆盖的原始点索引，用于反推出真正未处理点。
    valid_indices = _collect_valid_indices(builder.clusters)
    # 从全量点中扣除有效点和回收点，剩余部分才是最终未处理点。
    final_unprocessed_idx = sorted(
        set(range(len(points))) - valid_indices - builder.recycled_indices
    )
    # 构造最终聚类结果，供 session 和 UI 直接消费。
    cluster_result = SliceClusterResult(
        slice_idx=slice_index,
        clusters=builder.clusters,
        unprocessed_points=points[final_unprocessed_idx]
        if final_unprocessed_idx
        else np.array([]),
        recycled_points=points[sorted(builder.recycled_indices)]
        if builder.recycled_indices
        else np.array([]),
    )
    # 构造最终识别结果，区分最终有效和最终无效两类识别记录。
    recognition_result = SliceRecognitionResult(
        slice_index=slice_index,
        valid_clusters=builder.valid_recognitions,
        invalid_clusters=builder.invalid_recognitions,
    )
    return cluster_result, recognition_result


def _recognition_map(
    recognitions: list[ClusterRecognition],
) -> dict[int, ClusterRecognition]:
    """按簇索引构建识别记录映射。"""
    # 使用簇编号作为键，供 CF/PW/DOA 各阶段快速回查原识别记录。
    return {rec.cluster_index: rec for rec in recognitions}


def _collect_cluster_indices(clusters: list[ClusterItem]) -> set[int]:
    """收集簇内点在原始切片数据中的索引。"""
    indices: set[int] = set()
    for cluster in clusters:
        # 把簇内所有点索引拍平成集合，供 PW 输入合并使用。
        indices.update(int(index) for index in cluster.points_indices)
    return indices


def _collect_valid_indices(clusters: list[ClusterItem]) -> set[int]:
    """收集最终有效簇点在原始切片数据中的索引。"""
    indices: set[int] = set()
    for cluster in clusters:
        if cluster.state is ClusterState.VALID:
            # 仅统计最终有效簇覆盖的点，用于反推未处理点集合。
            indices.update(int(index) for index in cluster.points_indices)
    return indices


class IdentifyResultBuilder:
    """维护识别流程单切片最终输出的索引和结果列表。

    功能描述：
        该辅助类只负责最终结果装配：为最终保留的有效/无效簇分配连续
        ``cluster_idx``，同步重建 ``ClusterRecognition``，并收集最终回收点索引。

    Attributes:
        clusters [list[ClusterItem]]: 最终展示用聚类簇列表，顺序即 UI 浏览顺序。
        valid_recognitions [list[ClusterRecognition]]: 最终识别通过的识别记录列表。
        invalid_recognitions [list[ClusterRecognition]]: 最终识别未通过的识别记录列表。
        recycled_indices [set[int]]: 最终确认无效并回收的原始切片点索引集合。
        next_cluster_id [int]: 下一个可分配的最终簇编号。
        extract_params [ExtractParams]: 识别通过类的参数提取配置。
    """

    def __init__(self, extract_params: ExtractParams | None = None) -> None:
        """初始化结果收集器。

        Args:
            extract_params [ExtractParams | None]: 参数提取配置；为 None 时使用默认值。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。

        Example:
            >>> builder = IdentifyResultBuilder()
            >>> builder.next_cluster_id
            1
        """
        # 收集最终展示簇列表，顺序即最终浏览顺序。
        self.clusters: list[ClusterItem] = []
        # 收集最终有效识别记录，顺序与最终有效簇编号一致。
        self.valid_recognitions: list[ClusterRecognition] = []
        # 收集最终无效识别记录，供“展示全部聚类结果”模式使用。
        self.invalid_recognitions: list[ClusterRecognition] = []
        # 记录已经被判定为无效并回收的原始点索引。
        self.recycled_indices: set[int] = set()
        # 维护最终连续簇编号，避免中间阶段编号出现空洞。
        self.next_cluster_id: int = 1
        # 保存提取配置，确保最终有效类装配时可同步提取参数。
        self.extract_params = extract_params or ExtractParams()

    def append_valid(
        self,
        cluster: ClusterItem,
        recognition: ClusterRecognition,
    ) -> ClusterRecognition:
        """追加最终有效簇，并重建最终识别记录。

        Args:
            cluster [ClusterItem]: 需要作为最终有效结果保留的簇。
            recognition [ClusterRecognition]: 与该簇对应的最近一次识别记录。

        Returns:
            ClusterRecognition: 按最终簇编号和有效序号重建后的识别记录。

        Raises:
            无显式抛出异常。

        Example:
            >>> builder = IdentifyResultBuilder()
            >>> builder.next_cluster_id
            1
        """
        # 计算当前有效簇在最终有效结果中的顺序编号。
        valid_idx = len(self.valid_recognitions)
        # 最终簇编号只在结果装配阶段分配，避免中间失败子类造成编号空洞。
        cluster.cluster_idx = self.next_cluster_id
        cluster.valid_cluster_idx = valid_idx
        cluster.state = ClusterState.VALID
        cluster.pa_label = recognition.pa_label
        cluster.dtoa_label = recognition.dtoa_label
        cluster.joint_prob = recognition.joint_prob
        # 先把簇对象写入最终簇列表，再同步重建对应识别记录。
        self.clusters.append(cluster)
        # 仅对最终识别通过类提取参数，避免无效类污染后续合并和导出。
        extracted_params = extract_cluster_params(cluster.points, self.extract_params)
        shifted_rec = self._shift_recognition_index(
            recognition,
            new_cluster_index=self.next_cluster_id,
            valid_cluster_index=valid_idx,
            is_valid=True,
            extracted_params=extracted_params,
        )
        self.valid_recognitions.append(shifted_rec)
        # 推进最终簇编号，为下一个最终结果预留编号。
        self.next_cluster_id += 1
        return shifted_rec

    def append_invalid(
        self,
        cluster: ClusterItem,
        recognition: ClusterRecognition,
    ) -> ClusterRecognition:
        """追加最终无效簇，并重建最终识别记录。

        Args:
            cluster [ClusterItem]: 需要作为最终无效结果保留的簇。
            recognition [ClusterRecognition]: 与该簇对应的最近一次识别记录。

        Returns:
            ClusterRecognition: 按最终簇编号重建后的无效识别记录。

        Raises:
            无显式抛出异常。

        Example:
            >>> builder = IdentifyResultBuilder()
            >>> builder.invalid_recognitions
            []
        """
        # 无效簇也进入最终展示列表，供“展示全部聚类结果”模式浏览。
        cluster.cluster_idx = self.next_cluster_id
        cluster.valid_cluster_idx = None
        cluster.state = ClusterState.INVALID
        cluster.pa_label = recognition.pa_label
        cluster.dtoa_label = recognition.dtoa_label
        cluster.joint_prob = recognition.joint_prob
        # 无效簇也要保留到最终簇列表，供全部结果浏览模式使用。
        self.clusters.append(cluster)
        shifted_rec = self._shift_recognition_index(
            recognition,
            new_cluster_index=self.next_cluster_id,
            valid_cluster_index=None,
            is_valid=False,
        )
        self.invalid_recognitions.append(shifted_rec)
        # 无效结果对应点进入回收集合，避免再被标记为未处理点。
        self.recycled_indices.update(int(index) for index in cluster.points_indices)
        # 推进最终簇编号，保持有效/无效簇共用同一套连续编号。
        self.next_cluster_id += 1
        return shifted_rec

    @staticmethod
    def _shift_recognition_index(
        recognition: ClusterRecognition,
        new_cluster_index: int,
        valid_cluster_index: int | None,
        is_valid: bool,
        extracted_params: Any = None,
    ) -> ClusterRecognition:
        """复制识别记录，并替换为最终簇索引与最终有效序号。"""
        # 复制识别记录并重写索引字段，避免修改中间阶段原始识别对象。
        return ClusterRecognition(
            slice_index=recognition.slice_index,
            dim_name=recognition.dim_name,
            cluster_index=new_cluster_index,
            valid_cluster_index=valid_cluster_index,
            pa_label=recognition.pa_label,
            pa_confidence=recognition.pa_confidence,
            dtoa_label=recognition.dtoa_label,
            dtoa_confidence=recognition.dtoa_confidence,
            is_valid=is_valid,
            joint_prob=recognition.joint_prob,
            pa_conf_dict=dict(recognition.pa_conf_dict),
            dtoa_conf_dict=dict(recognition.dtoa_conf_dict),
            extracted_params=extracted_params or recognition.extracted_params,
        )
