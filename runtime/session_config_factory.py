"""运行期 session 配置快照工厂。"""

from __future__ import annotations

from core.models.session_config import (
    BusinessConfigSnapshot,
    ClusteringConfigSnapshot,
    ExtractConfigSnapshot,
    MergeConfigSnapshot,
    PlotConfigSnapshot,
    RecognitionConfigSnapshot,
    SessionConfigSnapshot,
)
from core.models.session_model import SessionModelSelection


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
            greedy_strategy=bool(qconfig.get(appConfig.recognizeGreedyStrategy)),
            pa_confidence_threshold=float(
                qconfig.get(appConfig.recognizePaConfidenceThreshold)
            ),
            pa_confidence_weight=float(
                qconfig.get(appConfig.recognizePaConfidenceWeight)
            ),
            dtoa_confidence_threshold=float(
                qconfig.get(appConfig.recognizeDtoaConfidenceThreshold)
            ),
            dtoa_confidence_weight=float(
                qconfig.get(appConfig.recognizeDtoaConfidenceWeight)
            ),
            joint_confidence_threshold=float(
                qconfig.get(appConfig.recognizeJointConfidenceThreshold)
            ),
        ),
        extract=ExtractConfigSnapshot(
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
        ),
        merge=MergeConfigSnapshot(
            placeholder_value=float(
                qconfig.get(appConfig.mergePlaceholderValue)
            ),
        ),
        business=BusinessConfigSnapshot(
            auto_recognize_next_slice=bool(qconfig.get(appConfig.autoRecognizeNextSlice)),
            export_dir_path=str(qconfig.get(appConfig.exportDirPath)),
            auto_export=bool(qconfig.get(appConfig.autoExport)),
        ),
        plot=PlotConfigSnapshot(
            only_show_identified=str(qconfig.get(appConfig.plotOnlyShowIdentified)),
            scale_mode=str(qconfig.get(appConfig.plotScaleMode)),
        ),
    )


def create_session_model_selection_from_global() -> SessionModelSelection:
    """从当前启用模型创建独立 Session 模型快照。

    Args:
        无。

    Returns:
        SessionModelSelection: 当前 PA、DTOA 启用模型路径的独立值对象。

    Raises:
        ValueError: 模型类型配置不受支持时由模型注册逻辑抛出。

    Example:
        >>> selection = create_session_model_selection_from_global()
        >>> isinstance(selection, SessionModelSelection)
        True
    """
    from app.model_bootstrap import get_enabled_model_path

    return SessionModelSelection(
        pa_model_path=get_enabled_model_path("PA"),
        dtoa_model_path=get_enabled_model_path("DTOA"),
    )
