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
        min_pts_cf=int(qconfig.get(appConfig.algorithmMinPtsCF)),
        eps_pw=float(qconfig.get(appConfig.algorithmEpsilonPW)),
        min_pts_pw=int(qconfig.get(appConfig.algorithmMinPtsPW)),
        eps_doa=float(qconfig.get(appConfig.algorithmEpsilonDOA)),
        min_pts_doa=int(qconfig.get(appConfig.algorithmMinPtsDOA)),
        clip_threshold_doa=float(qconfig.get(appConfig.algorithmClipThresholdDOA)),
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
        eps_cf=float(qconfig.get(appConfig.extractEpsilonCF)),
        min_pts_cf=int(qconfig.get(appConfig.extractMinPtsCF)),
        threshold_ratio_cf=float(qconfig.get(appConfig.extractThresholdRatioCF)),
        eps_pw=float(qconfig.get(appConfig.extractEpsilonPW)),
        min_pts_pw=int(qconfig.get(appConfig.extractMinPtsPW)),
        threshold_ratio_pw=float(qconfig.get(appConfig.extractThresholdRatioPW)),
        eps_pri=float(qconfig.get(appConfig.extractEpsilonPRI)),
        min_pts_pri=int(qconfig.get(appConfig.extractMinPtsPRI)),
        threshold_ratio_pri=float(qconfig.get(appConfig.extractThresholdRatioPRI)),
        filter_threshold_pri=float(qconfig.get(appConfig.extractFilterThresholdPRI)),
        harmonic_tolerance_pri=float(
            qconfig.get(appConfig.extractHarmonicTolerancePRI)
        ),
    )


def get_merge_params() -> MergeParams:
    """从全局配置获取合并参数占位值对象。

    功能描述：
        当前仅贯通全局配置到runtime值对象的占位链路，不得把该字段用于
        合并判别。未来存在真实业务参数时，应改为从调用方指定作用域读取：
        首次判别读取Session快照，重置后的当次判别读取面板临时副本。

    Args:
        无。

    Returns:
        MergeParams: 合并参数对象。

    Raises:
        无。
    """
    # 延迟导入配置模块。
    from app.app_config import appConfig, qconfig

    # 该入口只服务全局配置预览；合并工作流不得绕过Session快照调用它。
    return MergeParams(
        placeholder_value=float(qconfig.get(appConfig.mergePlaceholderValue)),
    )
