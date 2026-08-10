"""应用配置入口。"""

from __future__ import annotations

from pathlib import Path

from qfluentwidgets import (
    BoolValidator,
    ConfigItem,
    OptionsConfigItem,
    OptionsValidator,
    QConfig,
    RangeValidator,
    Theme,
    qconfig,
    setTheme,
    setThemeColor,
)

from utils.paths import get_config_file_path, get_log_dir


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
        str(get_log_dir()),
    )
    logLevel = OptionsConfigItem(
        "System",
        "LogLevel",
        "DEBUG",
        validator=OptionsValidator(["DEBUG", "INFO", "WARN", "ERROR"]),
    )

    # 全速处理性能 ─────────────────────────────────────────────────────────────
    fullSpeedComputeDevice = OptionsConfigItem(
        "performance.fullSpeed",
        "computeDevice",
        "AUTO",
        validator=OptionsValidator(["AUTO", "CPU", "GPU"]),
    )
    fullSpeedMaxConcurrentTasks = ConfigItem(
        "performance.fullSpeed",
        "maxConcurrentTasks",
        2,
        validator=RangeValidator(1, 4),
    )
    fullSpeedRecognitionWorkers = ConfigItem(
        "performance.fullSpeed",
        "recognitionWorkers",
        4,
        validator=RangeValidator(1, 8),
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
    algorithmMinPtsCF = ConfigItem(
        group="algorithm.clustering",
        name="minPtsCF",
        default=2,
        validator=RangeValidator(1, 9999),
    )
    algorithmEpsilonPW = ConfigItem(
        group="algorithm.clustering",
        name="epsilonPW",
        default=0.2,
        validator=RangeValidator(0.01, 10.0),
    )
    algorithmMinPtsPW = ConfigItem(
        group="algorithm.clustering",
        name="minPtsPW",
        default=2,
        validator=RangeValidator(1, 9999),
    )
    algorithmEpsilonDOA = ConfigItem(
        group="algorithm.clustering",
        name="epsilonDOA",
        default=16.8,
        validator=RangeValidator(0.01, 50.0),
    )
    algorithmMinPtsDOA = ConfigItem(
        group="algorithm.clustering",
        name="minPtsDOA",
        default=2,
        validator=RangeValidator(1, 9999),
    )
    algorithmClipThresholdDOA = ConfigItem(
        group="algorithm.clustering",
        name="clipThresholdDOA",
        default=95.0,
        validator=RangeValidator(0.0, 100.0),
    )

    # 识别参数 ─────────────────────────────────────────────────────────────────
    recognizeGreedyStrategy = ConfigItem(
        group="algorithm.recognize",
        name="greedyStrategy",
        default=True,
        validator=BoolValidator(),
    )
    recognizePaConfidenceThreshold = ConfigItem(
        group="algorithm.recognize",
        name="paConfidenceThreshold",
        default=0.5,
        validator=RangeValidator(0.0, 1.0),
    )
    recognizePaConfidenceWeight = ConfigItem(
        group="algorithm.recognize",
        name="paConfidenceWeight",
        default=0.6,
        validator=RangeValidator(0.0, 100.0),
    )
    recognizeDtoaConfidenceThreshold = ConfigItem(
        group="algorithm.recognize",
        name="dtoaConfidenceThreshold",
        default=0.5,
        validator=RangeValidator(0.0, 1.0),
    )
    recognizeDtoaConfidenceWeight = ConfigItem(
        group="algorithm.recognize",
        name="dtoaConfidenceWeight",
        default=0.4,
        validator=RangeValidator(0.0, 100.0),
    )
    recognizeJointConfidenceThreshold = ConfigItem(
        group="algorithm.recognize",
        name="jointConfidenceThreshold",
        default=0.8,
        validator=RangeValidator(0.0, 1.0),
    )

    # 提取参数 ─────────────────────────────────────────────────────────────────
    extractEpsilonCF = ConfigItem(
        group="algorithm.extract",
        name="epsilonCF",
        default=2.0,
        validator=RangeValidator(0.01, 50.0),
    )
    extractMinPtsCF = ConfigItem(
        group="algorithm.extract",
        name="minPtsCF",
        default=4,
        validator=RangeValidator(1, 9999),
    )
    extractThresholdRatioCF = ConfigItem(
        group="algorithm.extract",
        name="thresholdRatioCF",
        default=10.0,
        validator=RangeValidator(0.0, 100.0),
    )
    extractEpsilonPW = ConfigItem(
        group="algorithm.extract",
        name="epsilonPW",
        default=0.2,
        validator=RangeValidator(0.01, 10.0),
    )
    extractMinPtsPW = ConfigItem(
        group="algorithm.extract",
        name="minPtsPW",
        default=4,
        validator=RangeValidator(1, 9999),
    )
    extractThresholdRatioPW = ConfigItem(
        group="algorithm.extract",
        name="thresholdRatioPW",
        default=10.0,
        validator=RangeValidator(0.0, 100.0),
    )
    extractEpsilonPRI = ConfigItem(
        group="algorithm.extract",
        name="epsilonPRI",
        default=0.2,
        validator=RangeValidator(0.01, 10.0),
    )
    extractMinPtsPRI = ConfigItem(
        group="algorithm.extract",
        name="minPtsPRI",
        default=3,
        validator=RangeValidator(1, 9999),
    )
    extractThresholdRatioPRI = ConfigItem(
        group="algorithm.extract",
        name="thresholdRatioPRI",
        default=10.0,
        validator=RangeValidator(0.0, 100.0),
    )
    extractFilterThresholdPRI = ConfigItem(
        group="algorithm.extract",
        name="filterThresholdPRI",
        default=2.0,
        validator=RangeValidator(0.0, 100.0),
    )
    extractHarmonicTolerancePRI = ConfigItem(
        group="algorithm.extract",
        name="harmonicTolerancePRI",
        default=0.1,
        validator=RangeValidator(0.0, 10.0),
    )

    # 合并参数 ─────────────────────────────────────────────────────────────────
    # 当前合并准则仍使用硬编码规则；这里只保留一个配置链路占位，
    # 待出现真实业务参数时删除该字段并按实际参数重新建模。
    mergePlaceholderValue = ConfigItem(
        group="algorithm.merge",
        name="placeholderValue",
        default=0.0,
        validator=RangeValidator(0.0, 1.0),
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
    userModelRootDir = ConfigItem(
        group="model",
        name="userModelRootDir",
        default=str(Path.home() / ".RadarIdentifySystem" / "models"),
    )
    # 旧版单选路径仅用于首次迁移，运行期只读写下方复数列表配置。
    modelPaEnabledPath = ConfigItem(
        group="model",
        name="paEnabledPath",
        default="",
    )
    modelDtoaEnabledPath = ConfigItem(
        group="model",
        name="dtoaEnabledPath",
        default="",
    )
    modelPaEnabledPaths = ConfigItem(
        group="model",
        name="paEnabledPaths",
        default=[],
    )
    modelDtoaEnabledPaths = ConfigItem(
        group="model",
        name="dtoaEnabledPaths",
        default=[],
    )

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

    # 导入数据目录列表（主页面右侧面板中展示）──────────────────────────────────────
    importDataDirs = ConfigItem(
        group="business",
        name="importDataDirs",
        default=[],
    )


appConfig = AppConfig()

appConfig.themeMode.value = Theme.AUTO
# _CONFIG_PATH = Path.home() / ".RadarIdentifySystem" / "config.json"
_CONFIG_PATH = get_config_file_path()
qconfig.load(str(_CONFIG_PATH), appConfig)
