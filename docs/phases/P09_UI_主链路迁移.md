# P09 UI 主链路迁移（Fluent 主框架）

## 目标
迁移主交互闭环，确保“导入->切片->识别->结果展示”在 PyQt6 + Fluent 下可用。

## 本阶段重点
1. `MainWindow` 切到 `FluentWindow`。
2. 使用 `NavigationInterface` 重建主导航。
3. 保留图表区（Matplotlib）并与 Fluent 布局融合。
4. 主界面参数读写统一走 `appConfig`。
5. 将 `plot.scaleMode`、`plot.onlyShowIdentified`、`plot.order` 应用到绘图展示链路。
