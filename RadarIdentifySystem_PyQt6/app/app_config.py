"""应用配置入口。"""

from __future__ import annotations

from pathlib import Path

from qfluentwidgets import (
    BoolValidator, ConfigItem, OptionsConfigItem, OptionsValidator, QConfig, RangeValidator,
    qconfig, Theme, setTheme, setThemeColor,
)

from utils.paths import get_config_file_path


class AppConfig(QConfig):
    """全局配置模型。

    功能描述：
        定义项目全部可持久化配置项，作为唯一配置入口。

    参数说明：
        无。

    返回值说明：
        无。

    异常说明：
        无。
    """

    # 日志目录 ─────────────────────────────────────────────────────────────────
    logDir = ConfigItem(
        "System",
        "LogDir",
        str(Path.home() / ".RadarIdentifySystem" / "logs"),
    )

    # 界面缩放 ─────────────────────────────────────────────────────────────────
    dpiScale = OptionsConfigItem(
        "Interface",
        "DpiScale",
        "Auto",
        validator=OptionsValidator([1, 1.25, 1.5, 1.75, 2, "Auto"]),
        restart=True,
    )

    # 聚类参数 ─────────────────────────────────────────────────────────────────
    algorithmEpsilonCF = ConfigItem(
        group="algorithm.clustering",
        name="epsilonCF",
        default=2.0,
        validator=RangeValidator(0.01, 50.0),
    )
    algorithmEpsilonPW = ConfigItem(
        group="algorithm.clustering",
        name="epsilonPW",
        default=0.2,
        validator=RangeValidator(0.01, 10.0),
    )
    algorithmMinPts = ConfigItem(
        group="algorithm.clustering",
        name="minPts",
        default=1,
        validator=RangeValidator(1, 9999),
    )

    # 识别参数 ─────────────────────────────────────────────────────────────────
    recognizeTolerance = ConfigItem(
        group="algorithm.recognize",
        name="tolerance",
        default=0.5,
        validator=RangeValidator(0.01, 100.0),
    )
    recognizeMinConfidence = ConfigItem(
        group="algorithm.recognize",
        name="minConfidence",
        default=0.8,
        validator=RangeValidator(0.0, 1.0),
    )
    recognizeMaxCandidates = ConfigItem(
        group="algorithm.recognize",
        name="maxCandidates",
        default=5,
        validator=RangeValidator(1, 100),
    )

    # 提取参数 ─────────────────────────────────────────────────────────────────
    extractStep = ConfigItem(
        group="algorithm.extract",
        name="step",
        default=1,
        validator=RangeValidator(1, 100),
    )
    extractSmoothWindow = ConfigItem(
        group="algorithm.extract",
        name="smoothWindow",
        default=5,
        validator=RangeValidator(1, 99),
    )
    extractOutlierThreshold = ConfigItem(
        group="algorithm.extract",
        name="outlierThreshold",
        default=3.0,
        validator=RangeValidator(0.1, 10.0),
    )

    # 合并参数 ─────────────────────────────────────────────────────────────────
    mergeTimeDecay = ConfigItem(
        group="algorithm.merge",
        name="timeDecay",
        default=0.9,
        validator=RangeValidator(0.0, 1.0),
    )
    mergeSimThreshold = ConfigItem(
        group="algorithm.merge",
        name="simThreshold",
        default=0.8,
        validator=RangeValidator(0.0, 1.0),
    )
    mergeMaxExtrapolate = ConfigItem(
        group="algorithm.merge",
        name="maxExtrapolate",
        default=3,
        validator=RangeValidator(0, 100),
    )

    mergePriEqualDoaTolerance = ConfigItem(
        group="merge.priEqual",
        name="doaTolerance",
        default=20.0,
        validator=RangeValidator(0.0, 360.0),
    )

    plotScaleMode = OptionsConfigItem(
        group="plot",
        name="scaleMode",
        default="STRETCH",
        validator=OptionsValidator(
            ["STRETCH", "STRETCH_BILINEAR", "STRETCH_NEAREST_PRESERVE"]
        ),
    )
    plotOnlyShowIdentified = OptionsConfigItem(
        group="plot",
        name="onlyShowIdentified",
        default="IDENTIFIED_ONLY",
        validator=OptionsValidator(["ALL", "IDENTIFIED_ONLY"]),
    )
    plotOrder = ConfigItem(
        group="plot",
        name="order",
        default="CF,PW,PA,DTOA,DOA",
    )

    # 业务控制 ─────────────────────────────────────────────────────────────────
    autoRecognizeNextSlice = ConfigItem(
        group="business",
        name="autoRecognizeNextSlice",
        default=True,
        validator=BoolValidator(),
    )
    
    exportDirPath = ConfigItem(
        group="business",
        name="exportDirPath",
        default=str(Path.home() / "Desktop"),
    )
    
    autoExport = ConfigItem(
        group="business",
        name="autoExport",
        default=False,
        validator=BoolValidator(),
    )


appConfig = AppConfig()

appConfig.themeMode.value = Theme.AUTO
# _CONFIG_PATH = Path.home() / ".RadarIdentifySystem" / "config.json"
_CONFIG_PATH = get_config_file_path()
qconfig.load(str(_CONFIG_PATH), appConfig)
