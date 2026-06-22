# Session + Workflow + signal_bus 最小契约清单

## 1. 目标与边界
- 目标：在不引入重型框架的前提下，建立“可追踪、可并行、可维护”的处理链路数据治理约束。
- 适用范围：`core/models`、`runtime/state`、`runtime/workflow`、`runtime/events`、`app/signal_bus`、`ui`、`infra` 的交互边界。
- 非目标：本清单不包含算法实现细节、不规定具体 UI 组件、不规定线程池实现方式。

## 2. 状态契约（Session First）
### 2.1 `core/models/processing_session.py`（唯一业务真相）
- 定位：`ProcessingSession` 是单次处理的领域数据容器（Data Carrier），不是管理器。
- 职责：
  - 承载导入到导出全过程产物（raw/preprocess/slice/cluster/recognition/merge/export）。
  - 提供只读便捷属性（例如 `is_sliced`、`slice_count`）。
  - 记录元信息（`session_id`、`source_path`、`created_at`、`stage`）。
- 硬约束：
  - 不持有 Qt/UI/线程引用。
  - 不包含算法调用、流程调度与事件发布逻辑。
  - 不直接发信号，不直接做磁盘 I/O。

### 2.2 `runtime/session_registry.py`（可选，并行时再引入）
- 定位：仅在需要“多 Session 并行/切换”时引入的轻量索引容器。
- 职责：
  - 维护 `session_id -> ProcessingSession` 映射。
  - 提供当前活跃 `current_session_id`。
- 硬约束：
  - 不承载业务字段，不复制 Session 产物。
  - 不参与算法，不替代 Workflow。
- 结论：
  - 单会话阶段可不实现此模块，Workflow 直接驱动单个 Session 即可。

## 3. Stage 迁移契约（流程合法性）
- 允许迁移：
  - `CREATED -> IMPORTED -> PREPROCESSED -> SLICED -> CLUSTERED -> RECOGNIZED -> MERGED -> EXPORTED`
- 禁止跳跃：
  - 未 `IMPORTED` 禁止切片。
  - 未 `SLICED` 禁止聚类。
  - 未 `CLUSTERED` 禁止识别。
  - 未 `RECOGNIZED` 禁止合并。
- 失败语义：
  - 阶段失败不推进 `stage`。
  - 已完成阶段产物不得被失败流程清空。

## 4. Workflow 契约（`runtime/workflow` 主动驱动）
- 定位：Workflow 是流程指挥者，负责阶段推进、调用 `core/infra`、写回 session、发布流程事件。
- 最小接口：
  - `run_import(session, source)`
  - `run_preprocess(session)`
  - `run_slice(session)`
  - `run_cluster(session, params)`
  - `run_recognize(session, params)`
  - `run_merge(session, params)`
  - `run_export(session, target)`
- 写入规则：
  - 仅 Workflow 写 `session.*_result` 与 `session.stage`（禁止 UI 直接写）。
  - UI 只读 Session，不写 Session。
  - Core 函数纯输入输出，不依赖 UI/线程，不持有 Session 引用。

## 5. 事件契约（`runtime/events` + `app/signal_bus`）
- 统一载荷字段：
  - 必带：`session_id`、`stage`、`timestamp`。
  - 选带：`summary`（计数、耗时、关键指标）。
- 事件粒度：
  - `session_created`
  - `stage_started`
  - `stage_finished`
  - `stage_failed`
  - `session_finished`
- 传输原则：
  - 大对象不走事件载荷（事件只传摘要与索引键）。
  - UI 与其他消费者通过 `session_id` 从状态层读取详细数据。

## 6. UI 契约（只读消费层）
- 允许：
  - 发起 Workflow 意图命令（而非直接调用 core）。
  - 订阅 `app/signal_bus` 的流程事件。
  - 基于 `session_id` 拉取只读快照并渲染。
- 禁止：
  - 直接写 `ProcessingSession` 阶段产物。
  - 直接维护流程状态机与业务判定。
  - 保持与 `ProcessingSession` 冲突的“第二份业务真相”。

## 7. 并行契约（最小可扩展）
- 单活跃模式：
  - 仅保留一个 `ProcessingSession` 实例即可，不必引入额外状态容器。
- 多会话模式：
  - 引入轻量会话索引（建议 `runtime/session_registry.py`）。
  - 所有事件必须携带 `session_id`。
  - UI 通过 `session_id` 切换显示上下文。

## 8. 日志契约（可追踪性）
- 日志前缀规范：
  - `[session:{id}] [stage:{name}] ...`
- 必打节点：
  - 阶段开始、阶段完成、阶段失败。
- 失败日志最少字段：
  - `session_id`、阶段名、参数快照、异常摘要。

## 9. 最小落地顺序（建议）
- 第一步：固定 `ProcessingSession` 字段与 `ProcessingStage` 迁移规则。
- 第二步：将流程入口统一收敛到 `runtime/workflow/*`，由 Workflow 直接写 Session。
- 第三步：统一 `runtime/events` 与 `app/signal_bus` 事件载荷结构（以 `session_id` 为主键）。
- 第四步：UI 从“持有状态”改为“只读 Session 快照”。
- 第五步（可选）：并行需求出现后再引入 `runtime/session_registry.py`。

## 10. 验收标准
- 单次处理：每个阶段产物仅出现一处权威写入点（Workflow）。
- 架构一致性：不存在 `ui -> core/infra` 直连调用链。
- 失败可诊断：任意失败可通过 `session_id` 回溯到阶段与参数。
- 可并行扩展：新增第二个会话时，不需要改动现有算法函数签名。
