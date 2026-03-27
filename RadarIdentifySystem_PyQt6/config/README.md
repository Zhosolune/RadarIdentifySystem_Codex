# 配置目录说明

当前目录用于存放运行时配置文件。

当前方案：
1. 全部配置使用 `app/config.py` 中的 `QConfig`。
2. 配置持久化文件固定为 `config/config.json`。
3. 运行时只维护这一份配置文件，不再保留 `base/local` 双配置路线。

说明：
- `config/config.json` 可由应用首次启动自动生成。
- 若后续新增配置项，必须先更新 `app/config.py` 与 `docs/配置系统设计.md`。
