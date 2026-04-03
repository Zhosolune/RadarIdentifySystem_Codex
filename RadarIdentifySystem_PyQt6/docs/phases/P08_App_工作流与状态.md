# P08 Runtime 工作流与状态层

## 目标
用轻量 workflow + session_state 取代巨型 `DataController`。

## 本阶段新增文件
1. `runtime/state/session_state.py`
2. `runtime/workflow/import_workflow.py`
3. `runtime/workflow/slice_workflow.py`
4. `runtime/workflow/identify_workflow.py`
5. `runtime/workflow/merge_workflow.py`
6. `runtime/workflow/export_workflow.py`
7. `runtime/workflow/fullspeed_workflow.py`
8. `tests/unit/test_runtime_workflow.py`

## 本阶段迁移来源
- `ui/data_controller.py`
- `cores/ThreadWorker.py`（流程编排段）

## 执行步骤
1. 先定义 `SessionState`：
   - 当前文件/波段
   - 当前切片索引
   - 当前有效簇
   - 合并结果
   - 导出状态
2. 各 workflow 仅做：
   - 接收 UI 意图事件
   - 调用 core/infra 能力
   - 通过 signal_bus 发流程事件
3. 各 workflow 只关心一个流程，禁止跨流程修改状态。
4. 将“识别后是否可合并”判定移到 `identify_workflow` 输出。
5. 将“保存状态指纹”统一放 `export_workflow`。
6. 梳理异常策略：workflow 捕获业务异常并统一转 signal_bus 错误事件。
7. 补 workflow 单测：状态变迁断言。

## 验收标准
1. 不再存在单个 2000+ 行控制器。
2. UI 对业务调用收敛到 runtime/workflow 事件入口。
3. 全流程事件可在 signal_bus 中观测。

## 风险与应对
- 风险：状态拆分后遗漏字段。
- 应对：先做状态字典迁移清单，再逐项验证。

## 回退点
- 保留旧控制器适配器以便短期并行。
