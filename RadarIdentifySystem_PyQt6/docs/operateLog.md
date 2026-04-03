# 操作日志

## 2026-04-02 17:23
- 操作类型：重构
- 影响文件：`app/logger.py`、`main.py`、`core/preprocess.py`、`core/slicing.py`、`ui/main_window.py`、`ui/interfaces/setting_interface.py`、`app/application.py`、`docs/operateLog.md`
- 变更摘要：按“core 使用标准 logging、app/logger 仅负责配置、main 显式初始化”方案统一所有日志使用点并移除 `get_logger` 依赖
- 原因：消除 core 对 app/Qt 的反向耦合，保证无 Qt 环境下核心算法可独立运行
- 测试状态：待测试（`python -m compileall .` 已通过，`pytest` 模块缺失）

---

## 2026-04-02 16:40
- 操作类型：修改
- 影响文件：`docs/Session_Workflow_signal_bus_最小契约清单.md`、`docs/operateLog.md`
- 变更摘要：按“Session 被动、Workflow 主动”原则移除 `SessionState` 必选设计，改为并行场景可选 `runtime/session_registry.py`
- 原因：与当前架构取舍保持一致，避免单会话阶段过度设计
- 测试状态：无需测试（文档修订）

---

## 2026-04-02 16:30
- 操作类型：修改
- 影响文件：`docs/Session_Workflow_signal_bus_最小契约清单.md`、`docs/operateLog.md`
- 变更摘要：将契约清单从 `app/workflows + app/events` 修正为当前基线 `runtime/workflow + runtime/events + app/signal_bus`，补充 `SessionState` 分层职责与架构一致性验收项
- 原因：用户反馈清单与当前架构不一致，需要按《目录结构与分层约束》对齐
- 测试状态：无需测试（文档修订）

---

## 2026-04-02 16:25
- 操作类型：新增
- 影响文件：`docs/Session_Workflow_signal_bus_最小契约清单.md`、`docs/operateLog.md`
- 变更摘要：新增 Session + Workflow + signal_bus 最小契约清单文档，明确数据容器、流程驱动、事件通信和 UI 只读边界
- 原因：为后续重构提供统一的数据生命周期治理约束，避免过早引入重型实现
- 测试状态：无需测试（文档新增）

---

## 2026-04-02 14:22
- 操作类型：新增
- 影响文件：`core/models/processing_session.py`、`core/models/__init__.py`
- 变更摘要：新增 ProcessingSession 数据容器与 ProcessingStage 阶段枚举
- 原因：为工作流层提供随行数据背包，取代全局 DataManager 方案，天然支持并行多包处理
- 测试状态：已测试（多实例独立性、属性查询验证通过）

---

## 2026-04-02 11:22
- 操作类型：新增
- 影响文件：docs/operateLog.md（本文件）
- 变更摘要：创建操作日志，记录重构执行状态
- 原因：按规则要求建立操作追踪文件
- 测试状态：无需测试

---

## 当前重构状态总览

### 已完成阶段
- **P00**（进行中）：目录基线冻结、Fluent 可行性评估、台账初始化 ✅
- **P01**（进行中）：main.py / app_config / signal_bus / style_sheet / resource_rc / main_window / paths.py 落地，已过启动验证 ✅
- **P02**（进行中）：events.py (7个dataclass) / signal_bus (15个信号) / test_signal_bus.py 落地 ✅（pytest 待正式安装）

### ✅ P03 完成（2026-04-02 11:30）
- `core/models/pulse_batch.py` — PulseBatch 输入数据契约
- `core/models/slice_result.py` — PreprocessResult / SliceResult 输出数据契约
- `core/models/__init__.py` — 包导出
- `core/data/preprocess.py` — clean_pa / fix_toa_flip / detect_band / preprocess 纯函数
- `core/data/slicing.py` — slice_by_toa / slice_from_preprocess 纯函数（修复单脉冲边界 bug）
- `core/data/__init__.py` — 包导出
- `tests/unit/test_core_preprocess.py` — 19 用例全通过
- `tests/unit/test_core_slicing.py` — 11 用例全通过

**关键修复**：`slice_by_toa` 在 t_min==t_max（单脉冲/TOA 全等）时，`np.arange` 只生成单点无法循环；修复方式：`if len(boundaries) < 2: boundaries = [t_min, t_min+step]`

### 待开始阶段
- **P04**（下一步）: 核心聚类流程（`core/clustering/`），来源：`cores/cluster_processor.py` + `cores/roughly_clustering.py`
- P05: 识别与参数提取
- P06: 合并规则
- P07: infra 适配层
- P08: Runtime 工作流
- P09-P12: UI / 线程 / 打包


---

## 2026-04-02 16:10
- 操作类型：重构
- 影响文件：
  - `docs/目录结构与分层约束.md`
  - `docs/重构执行追踪.md`
  - `docs/重构接口对接手册.md`
  - `docs/配置系统设计.md`
  - `docs/功能对齐矩阵.md`
  - `docs/PyQt6重构总体规划.md`
  - `docs/PyQtFluentWidgets可行性评估.md`
  - `docs/风险清单.md`
  - `docs/重构阶段索引.md`
  - `docs/phases/P00_重构约束与台账.md`
  - `docs/phases/P01_工程骨架与入口.md`
  - `docs/phases/P02_全局信号总线.md`
  - `docs/phases/P07_Infra_适配层迁移.md`
  - `docs/phases/P08_App_工作流与状态.md`
  - `docs/phases/P10_UI_高级功能迁移.md`
  - `docs/phases/P11_全速处理与线程治理.md`
- 变更摘要：统一文档架构基线为 `runtime` 顶层，明确 `workflow/threading/events` 归属，并将配置入口统一修正为 `app/app_config.py`。
- 原因：落实新架构决策（`ui -> runtime -> core`，`runtime -> infra`，`app` 仅承担应用壳层能力）。
- 测试状态：无需测试（文档一致性检视已完成）

---
