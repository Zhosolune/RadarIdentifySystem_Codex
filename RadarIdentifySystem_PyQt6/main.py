"""应用主入口模块。"""

from app.application import run


def main() -> int:
    """执行应用启动。

    功能描述：
        调用应用层启动流程并返回进程退出码。

    参数说明：
        无。

    返回值说明：
        int: 应用退出码，`0` 表示正常退出。

    异常说明：
        RuntimeError: 当应用初始化失败时抛出。
        OSError: 当配置或日志目录不可写时抛出。
    """

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
