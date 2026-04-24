"""运行时算法参数组装器。"""

from __future__ import annotations

from core.models.algorithm_params import (
    ClusteringParams,
    RecognitionParams,
    ExtractParams,
    MergeParams,
)


def get_clustering_params() -> ClusteringParams:
    """从全局配置获取聚类参数对象。

    功能描述：
        读取 `app.app_config` 中的聚类配置项，并转换为 `ClusteringParams`
        数据对象，供 runtime 层向 core 层传递统一的参数契约。

    Args:
        无。

    Returns:
        ClusteringParams: 聚类参数对象。

    Raises:
        无。
    """
    # 延迟导入配置模块，避免在无配置需求时引入应用层副作用。
    from app.app_config import appConfig, qconfig

    # 组装聚类参数对象。
    return ClusteringParams(
        eps_cf=float(qconfig.get(appConfig.algorithmEpsilonCF)),
        eps_pw=float(qconfig.get(appConfig.algorithmEpsilonPW)),
        min_pts=int(qconfig.get(appConfig.algorithmMinPts)),
    )


def get_recognition_params() -> RecognitionParams:
    """从全局配置获取识别参数对象。

    功能描述：
        读取识别阶段配置项，并转换为 `RecognitionParams` 数据对象，
        供后续识别工作流与核心算法统一消费。

    Args:
        无。

    Returns:
        RecognitionParams: 识别参数对象。

    Raises:
        无。
    """
    # 延迟导入配置模块。
    from app.app_config import appConfig, qconfig

    # 组装识别参数对象。
    return RecognitionParams(
        tolerance=float(qconfig.get(appConfig.recognizeTolerance)),
        min_confidence=float(qconfig.get(appConfig.recognizeMinConfidence)),
        max_candidates=int(qconfig.get(appConfig.recognizeMaxCandidates)),
    )


def get_extract_params() -> ExtractParams:
    """从全局配置获取提取参数对象。

    功能描述：
        读取提取阶段配置项，并转换为 `ExtractParams` 数据对象，
        供后续提取工作流与核心算法统一消费。

    Args:
        无。

    Returns:
        ExtractParams: 提取参数对象。

    Raises:
        无。
    """
    # 延迟导入配置模块。
    from app.app_config import appConfig, qconfig

    # 组装提取参数对象。
    return ExtractParams(
        step=int(qconfig.get(appConfig.extractStep)),
        smooth_window=int(qconfig.get(appConfig.extractSmoothWindow)),
        outlier_threshold=float(qconfig.get(appConfig.extractOutlierThreshold)),
    )


def get_merge_params() -> MergeParams:
    """从全局配置获取合并参数对象。

    功能描述：
        读取合并阶段配置项，并转换为 `MergeParams` 数据对象，
        供后续合并工作流与核心算法统一消费。

    Args:
        无。

    Returns:
        MergeParams: 合并参数对象。

    Raises:
        无。
    """
    # 延迟导入配置模块。
    from app.app_config import appConfig, qconfig

    # 组装合并参数对象。
    return MergeParams(
        time_decay=float(qconfig.get(appConfig.mergeTimeDecay)),
        sim_threshold=float(qconfig.get(appConfig.mergeSimThreshold)),
        max_extrapolate=int(qconfig.get(appConfig.mergeMaxExtrapolate)),
        pri_equal_doa_tolerance=float(qconfig.get(appConfig.mergePriEqualDoaTolerance)),
    )
