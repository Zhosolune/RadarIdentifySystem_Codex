# RadarIdentifySystem PyQt6 轻量重构总体方案（全 QConfig 版）

## 1. 架构
- `app`：应用生命周期、全局配置、日志、信号总线、样式管理
- `core`：算法与规则（纯业务逻辑）
- `infra`：解析、推理、绘图、线程、导出等基础设施适配
- `ui`：基于 PyQt-Fluent-Widgets 的窗口/页面/组件
- `utils`：通用工具
- `resources`：静态资源（图标、QSS、qrc）
- `config`：配置持久化目录（`config/config.json`）
- `docs`：过程文档与台账

目录基线详见：`docs/目录结构与分层约束.md`。

说明：
- 本项目当前阶段不引入 `db` 层；如后续确有落库需求，再独立评审并增设。

## 2. 执行原则
1. 遵循 YAGNI/KISS，先做最小可用。
2. 可以优化实现，但算法结果必须与旧版等价。
3. 每阶段必须可运行、可回归、可回退。

## 3. UI 技术栈
1. 使用 `PyQt6-Fluent-Widgets` 作为主要 UI 组件库。
2. 使用 `FluentWindow`、`NavigationInterface`、`InfoBar`、`SettingCard` 等组件。
3. 保留 Matplotlib 图表能力，不强制替换为 Fluent 图表。

## 4. 配置系统（单一方案）
全部配置采用 Fluent `QConfig`：
1. 在 `app/config.py` 中集中定义 `ConfigItem` 与默认值。
2. UI 偏好与业务参数都在同一个 `QConfig` 实例中管理。
3. 使用 `ConfigValidator` 做类型/范围/枚举校验。
4. 使用 `qconfig.load("config/config.json", appConfig)` 初始化加载，并通过 `appConfig.save()` 持久化。

说明：
- 不再使用 `ConfigService` / `base.json` / `local.json` 路线。
- 配置分组通过命名空间实现，如 `ui.*`、`algorithm.*`、`merge.*`、`export.*`、`plot.*`。
- `plot.*` 必须覆盖绘图参数持久化：拉伸模式、显示过滤、图序、维度范围、频段绘图策略、合并配色。

## 5. signal_bus
在 `app/signal_bus.py` 管理跨模块事件；模块内逻辑不走总线。
建议事件：
- `config_changed`
- `theme_changed`

## 6. 启动链路
- `main.py`：应用进程入口。
- `app/application.py`：应用初始化与生命周期管理。
- `ui/main_window.py`：主窗口与导航容器。

## 7. 双文档
每阶段都要更新：
1. `docs/重构接口对接手册.md`
2. `docs/重构执行追踪.md`

## 8. 许可证与发布前检查
在发布前必须确认 `PyQt-Fluent-Widgets` 许可策略与分发合规性。

## 9. 分阶段执行
按 `docs/重构阶段索引.md` 的 P00-P12 执行。
可行性评估见：`docs/PyQtFluentWidgets可行性评估.md`。


