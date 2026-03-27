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
    qconfig,
    setTheme,
    setThemeColor,
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
        validator=OptionsValidator(["STRETCH", "STRETCH_BILINEAR", "STRETCH_NEAREST_PRESERVE"]),
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


def apply_theme_preferences() -> None:
    """应用主题与主题色配置。

    功能描述：
        使用 qfluentwidgets 官方主题接口将配置同步到运行时，并触发内置主题相关信号链路。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        RuntimeError: 当主题应用失败时抛出。
    """

    setTheme(appConfig.get(appConfig.themeMode), save=False)
    setThemeColor(appConfig.get(appConfig.themeColor), save=False)


def load_app_config(config_file: Path | None = None) -> Path:
    """加载应用配置。

    功能描述：
        从配置文件加载配置；当文件不存在时创建默认配置文件，并同步应用主题设置。

    参数说明：
        config_file (Path | None): 目标配置文件路径，默认值为 None。
            为 None 时使用默认路径 `config/config.json`。

    返回值说明：
        Path: 实际使用的配置文件路径。

    异常说明：
        OSError: 当配置目录或配置文件创建失败时抛出。
        ValueError: 当传入路径非法时抛出。
    """

    path = config_file if config_file is not None else get_config_file_path()
    if str(path).strip() == "":
        raise ValueError("配置文件路径不能为空")

    path.parent.mkdir(parents=True, exist_ok=True)
    qconfig.load(str(path), appConfig)
    if not path.exists():
        appConfig.save()

    apply_theme_preferences()
    return path


def save_app_config(config_file: Path | None = None) -> Path:
    """保存应用配置。

    功能描述：
        将内存中的配置状态写入目标配置文件。

    参数说明：
        config_file (Path | None): 目标配置文件路径，默认值为 None。
            为 None 时使用默认路径 `config/config.json`。

    返回值说明：
        Path: 实际写入的配置文件路径。

    异常说明：
        OSError: 当配置文件写入失败时抛出。
        ValueError: 当传入路径非法时抛出。
    """

    path = config_file if config_file is not None else get_config_file_path()
    if str(path).strip() == "":
        raise ValueError("配置文件路径不能为空")

    path.parent.mkdir(parents=True, exist_ok=True)
    appConfig.file = path
    appConfig.save()
    return path
