"""测试配置。"""

from __future__ import annotations

import sys
from pathlib import Path


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
