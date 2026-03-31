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

    algorithmEpsilonCF = ConfigItem(
        group="algorithm.clustering",
        name="epsilonCF",
        default=2.0,
        validator=RangeValidator(0.01, 1000.0),
    )
    algorithmEpsilonPW = ConfigItem(
        group="algorithm.clustering",
        name="epsilonPW",
        default=0.2,
        validator=RangeValidator(0.0001, 1000.0),
    )
    algorithmMinPts = ConfigItem(
        group="algorithm.clustering",
        name="minPts",
        default=1,
        validator=RangeValidator(1, 9999),
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
    plotOnlyShowIdentified = ConfigItem(
        group="plot",
        name="onlyShowIdentified",
        default=True,
        validator=BoolValidator(),
    )
    plotOrder = ConfigItem(
        group="plot",
        name="order",
        default="CF,PW,PA,DTOA,DOA",
    )


appConfig = AppConfig()

appConfig.themeMode.value = Theme.AUTO
_CONFIG_PATH = Path.home() / ".RadarIdentifySystem" / "config.json"
qconfig.load(str(_CONFIG_PATH), appConfig)
