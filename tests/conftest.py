"""测试配置。"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path
import tempfile


# 在任何测试模块导入 app_config/logger 之前隔离用户数据，避免测试污染真实
# LocalAppData，也避免受开发者本机既有配置影响。
_TEST_RUNTIME_ROOT = (
    Path(tempfile.gettempdir()) / f"RadarIdentifySystem-pytest-{os.getpid()}"
)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
    """初始化测试导入路径。

    功能描述：
        将项目根目录加入 `sys.path`，确保测试可直接导入各一级包。

    参数说明：
        无。

    返回值说明：
        None: 无返回值。

    异常说明：
        OSError: 当路径解析失败时抛出。
    """

    project_root = Path(__file__).resolve().parents[1]
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
