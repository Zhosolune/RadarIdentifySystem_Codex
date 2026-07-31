"""Session 配置快照到核心算法参数的统一转换器。

本模块是 runtime 层唯一的算法参数转换边界。调用方必须传入所属 Session
的配置快照，不得在任务执行期间重新读取全局 qconfig，从而保证交互式任务
与全速任务继续使用彼此独立的参数副本。

Example:
    >>> from core.models.session_config import SessionConfigSnapshot
    >>> params = build_identify_pipeline_params(SessionConfigSnapshot.default())
    >>> params.clustering.eps_cf
    2.0
"""

from __future__ import annotations

from dataclasses import dataclass

from core.models.algorithm_params import (
    ClusteringParams,
    ExtractParams,
    RecognitionParams,
)
from core.models.session_config import (
    ClusteringConfigSnapshot,
    ExtractConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigSnapshot,
)


@dataclass(frozen=True, slots=True)
class IdentifyPipelineParams:
    """封装一次识别流程使用的完整冻结算法参数。

    Attributes:
        clustering [ClusteringParams]: CF、PW 和 DOA 聚类参数。
        recognition [RecognitionParams]: PA、DTOA 识别策略及门限参数。
        extract [ExtractParams]: 识别通过簇的参数提取配置。
    """

    clustering: ClusteringParams
    recognition: RecognitionParams
    extract: ExtractParams


def build_clustering_params(
    config: ClusteringConfigSnapshot,
) -> ClusteringParams:
    """从 Session 聚类快照构造冻结的核心参数。

    ``min_cluster_size`` 当前不是 Session 可配置项，因此继续使用
    :class:`ClusteringParams` 定义的算法默认值。

    Args:
        config [ClusteringConfigSnapshot]: 单个 Session 的聚类配置快照。

    Returns:
        ClusteringParams: 与传入快照等值且不共享可变状态的聚类参数。

    Raises:
        无显式抛出异常。

    Example:
        >>> from core.models.session_config import ClusteringConfigSnapshot
        >>> build_clustering_params(
        ...     ClusteringConfigSnapshot(eps_cf=3.5)
        ... ).eps_cf
        3.5
    """
    return ClusteringParams(
        eps_cf=config.eps_cf,
        min_pts_cf=config.min_pts_cf,
        eps_pw=config.eps_pw,
        min_pts_pw=config.min_pts_pw,
        eps_doa=config.eps_doa,
        min_pts_doa=config.min_pts_doa,
        clip_threshold_doa=config.clip_threshold_doa,
    )


def build_recognition_params(
    config: RecognitionConfigSnapshot,
) -> RecognitionParams:
    """从 Session 识别快照构造冻结的核心参数。

    Args:
        config [RecognitionConfigSnapshot]: 单个 Session 的识别配置快照。

    Returns:
        RecognitionParams: 与传入快照等值且不共享可变状态的识别参数。

    Raises:
        无显式抛出异常。

    Example:
        >>> from core.models.session_config import RecognitionConfigSnapshot
        >>> build_recognition_params(
        ...     RecognitionConfigSnapshot(greedy_strategy=False)
        ... ).greedy_strategy
        False
    """
    return RecognitionParams(
        greedy_strategy=config.greedy_strategy,
        pa_confidence_threshold=config.pa_confidence_threshold,
        pa_confidence_weight=config.pa_confidence_weight,
        dtoa_confidence_threshold=config.dtoa_confidence_threshold,
        dtoa_confidence_weight=config.dtoa_confidence_weight,
        joint_confidence_threshold=config.joint_confidence_threshold,
    )


def build_extract_params(config: ExtractConfigSnapshot) -> ExtractParams:
    """从 Session 参数提取快照构造冻结的核心参数。

    Args:
        config [ExtractConfigSnapshot]: 单个 Session 的参数提取配置快照。

    Returns:
        ExtractParams: 与传入快照等值且不共享可变状态的提取参数。

    Raises:
        无显式抛出异常。

    Example:
        >>> from core.models.session_config import ExtractConfigSnapshot
        >>> build_extract_params(
        ...     ExtractConfigSnapshot(eps_pri=0.5)
        ... ).eps_pri
        0.5
    """
    return ExtractParams(
        eps_cf=config.eps_cf,
        min_pts_cf=config.min_pts_cf,
        threshold_ratio_cf=config.threshold_ratio_cf,
        eps_pw=config.eps_pw,
        min_pts_pw=config.min_pts_pw,
        threshold_ratio_pw=config.threshold_ratio_pw,
        eps_pri=config.eps_pri,
        min_pts_pri=config.min_pts_pri,
        threshold_ratio_pri=config.threshold_ratio_pri,
        filter_threshold_pri=config.filter_threshold_pri,
        harmonic_tolerance_pri=config.harmonic_tolerance_pri,
    )


def build_identify_pipeline_params(
    snapshot: SessionConfigSnapshot,
) -> IdentifyPipelineParams:
    """从一个 Session 快照构造完整且独立的识别流程参数。

    本函数是纯转换函数：不读取全局配置、不修改传入快照，也不缓存返回值。
    因此不同 Session 即使调用同一函数，仍会获得彼此独立的冻结参数实例。

    Args:
        snapshot [SessionConfigSnapshot]: 当前任务所属 Session 的完整配置快照。

    Returns:
        IdentifyPipelineParams: 聚类、识别和参数提取组成的冻结参数集合。

    Raises:
        无显式抛出异常。

    Example:
        >>> from core.models.session_config import SessionConfigSnapshot
        >>> first = build_identify_pipeline_params(SessionConfigSnapshot.default())
        >>> second = build_identify_pipeline_params(SessionConfigSnapshot.default())
        >>> first is second
        False
    """
    return IdentifyPipelineParams(
        clustering=build_clustering_params(snapshot.clustering),
        recognition=build_recognition_params(snapshot.recognition),
        extract=build_extract_params(snapshot.extract),
    )
