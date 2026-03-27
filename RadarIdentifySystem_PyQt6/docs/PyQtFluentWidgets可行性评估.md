# PyQt-Fluent-Widgets 可行性评估

## 1. 结论
可行，建议采用。

采用方式：
1. UI 层全面引入 `PyQt6-Fluent-Widgets` 组件。
2. 主题与界面设置使用 `qfluentwidgets` 自带 `QConfig/ConfigItem`。
3. 业务参数同样放入 `app/config.py` 中定义为 `ConfigItem`，统一由 `QConfig` 管理并持久化到 `config/config.json`。

## 2. 依据（官方来源）
1. GitHub 仓库显示该项目支持 Fluent 设计组件，并标注 GPL-3.0 许可。
2. PyPI 的 `PyQt6-Fluent-Widgets` 页面显示可用于 PyQt6。
3. 文档示例显示可用 `setTheme` / `setThemeColor` 配置主题。
4. 文档示例显示 `QConfig + ConfigItem` 可直接管理并持久化设置。

## 3. 风险与约束
1. 许可风险：GPLv3（非商用可用，商用需商业授权）。
2. 安装风险：不能同时安装 PyQt/PySide 多个 Fluent 包（包名同为 `qfluentwidgets`）。
3. 迁移成本：现有大量自定义组件需分批替换，不适合一次性重写。

## 4. 架构建议（重构后）
1. 单一配置源：`app/config.py` + `QConfig`。
2. 按分组管理配置项：`ui.*`、`algorithm.*`、`export.*`。
3. 配置变更统一通过 signal_bus 发 `config_changed`。
4. 保持 `core` 纯业务，线程任务统一在 `infra/threading`。

## 5. 迁移策略（最小风险）
1. 先替换主框架：`MainWindow -> FluentWindow`。
2. 再替换高收益组件：导航、设置页、对话框、通知。
3. 保留已有业务图表与核心流程，避免算法侧受 UI 迁移影响。

## 6. 是否推荐
推荐，但前提是先确认许可证策略（是否涉及商用分发）。
