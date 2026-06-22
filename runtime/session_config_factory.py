"""运行期 session 配置快照工厂。"""

from __future__ import annotations

from core.models.session_config import (
    BusinessConfigSnapshot,
    ClusteringConfigSnapshot,
    ExtractConfigSnapshot,
    MergeConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigSnapshot,
)


def create_session_config_from_global() -> SessionConfigSnapshot:
    """从当前全局配置创建独立 session 配置快照。

    功能描述：
        读取 ``app.app_config`` 中的 qconfig 当前值，并复制到纯数据
        ``SessionConfigSnapshot``。返回对象不持有 ConfigItem 或 qconfig 引用，
        后续修改只影响该 session 自身。

    Args:
        无。

    Returns:
        SessionConfigSnapshot: 与当前全局配置等值的独立 session 配置快照。

    Raises:
        无显式抛出异常。

    Example:
        >>> snapshot = create_session_config_from_global()
        >>> isinstance(snapshot, SessionConfigSnapshot)
        True
    """
    # 延迟导入应用配置，避免无配置需求时引入 qconfig 加载副作用。
    from app.app_config import appConfig, qconfig

    return SessionConfigSnapshot(
        clustering=ClusteringConfigSnapshot(
            eps_cf=float(qconfig.get(appConfig.algorithmEpsilonCF)),
            min_pts_cf=int(qconfig.get(appConfig.algorithmMinPtsCF)),
            eps_pw=float(qconfig.get(appConfig.algorithmEpsilonPW)),
            min_pts_pw=int(qconfig.get(appConfig.algorithmMinPtsPW)),
            eps_doa=float(qconfig.get(appConfig.algorithmEpsilonDOA)),
            min_pts_doa=int(qconfig.get(appConfig.algorithmMinPtsDOA)),
            clip_threshold_doa=float(qconfig.get(appConfig.algorithmClipThresholdDOA)),
        ),
        recognition=RecognitionConfigSnapshot(
            tolerance=float(qconfig.get(appConfig.recognizeTolerance)),
            min_confidence=float(qconfig.get(appConfig.recognizeMinConfidence)),
            max_candidates=int(qconfig.get(appConfig.recognizeMaxCandidates)),
        ),
        extract=ExtractConfigSnapshot(
            step=int(qconfig.get(appConfig.extractStep)),
            smooth_window=int(qconfig.get(appConfig.extractSmoothWindow)),
            outlier_threshold=float(qconfig.get(appConfig.extractOutlierThreshold)),
        ),
        merge=MergeConfigSnapshot(
            time_decay=float(qconfig.get(appConfig.mergeTimeDecay)),
            sim_threshold=float(qconfig.get(appConfig.mergeSimThreshold)),
            max_extrapolate=int(qconfig.get(appConfig.mergeMaxExtrapolate)),
            pri_equal_doa_tolerance=float(
                qconfig.get(appConfig.mergePriEqualDoaTolerance)
            ),
        ),
        business=BusinessConfigSnapshot(
            auto_recognize_next_slice=bool(qconfig.get(appConfig.autoRecognizeNextSlice)),
            export_dir_path=str(qconfig.get(appConfig.exportDirPath)),
            auto_export=bool(qconfig.get(appConfig.autoExport)),
        ),
    )
