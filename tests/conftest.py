"""测试配置。"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path
import tempfile


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT_TEXT = str(_PROJECT_ROOT)
# 测试收集前固定仓库源码优先级，防止本机环境中的同名包抢先解析。
while _PROJECT_ROOT_TEXT in sys.path:
    sys.path.remove(_PROJECT_ROOT_TEXT)
sys.path.insert(0, _PROJECT_ROOT_TEXT)

# 在任何测试模块导入 app_config/logger 之前隔离用户数据，避免测试污染真实
# LocalAppData，也避免受开发者本机既有配置影响。
_TEST_RUNTIME_ROOT = (
    Path(tempfile.gettempdir()) / f"RadarIdentifySystem-pytest-{os.getpid()}"
)
_TEST_CONFIG_FILE = _TEST_RUNTIME_ROOT / "data" / "config" / "config.json"
if not _TEST_CONFIG_FILE.exists():
    source_config = _PROJECT_ROOT / "config" / "config.json"
    if source_config.is_file():
        config_data = json.loads(source_config.read_text(encoding="utf-8"))
        config_data.setdefault("System", {})["LogDir"] = str(
            _TEST_RUNTIME_ROOT / "data" / "logs"
        )
        _TEST_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TEST_CONFIG_FILE.write_text(
            json.dumps(config_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
os.environ.setdefault(
    "RADAR_IDENTIFY_DATA_ROOT",
    str(_TEST_RUNTIME_ROOT / "data"),
)
os.environ.setdefault(
    "RADAR_IDENTIFY_TEMP_ROOT",
    str(_TEST_RUNTIME_ROOT / "temp"),
)


def pytest_configure() -> None:
    """验证测试使用仓库根目录作为最高优先级导入路径。

    功能描述：
        检查项目根目录位于 `sys.path` 首位，确保测试直接导入仓库源码。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        RuntimeError: 当项目根目录未处于最高导入优先级时抛出。
    """

    if not sys.path or Path(sys.path[0]).resolve() != _PROJECT_ROOT:
        raise RuntimeError("测试必须优先从仓库根目录导入源码")
