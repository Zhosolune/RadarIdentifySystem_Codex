# 操作日志

## 2026-04-07 16:14
- 操作类型：重构
- 影响文件：`ui/controllers/slice_controller.py`、`ui/controllers/import_controller.py`
- 变更摘要：移除了代码中原本通过修改按钮文本或使用原生 `QMessageBox` 来作为用户交互提示的做法，全面统一替换为使用 `qfluentwidgets.InfoBar`。包括数据导入的成功与失败提示、切片执行的前置拦截提示与成功提示。
- 原因：提升系统界面的视觉一致性与交互体验，遵循全局的交互规范。该规范已被写入核心记忆。
- 测试状态：待手动测试验证

---

## 2026-04-07 16:08
- 操作类型：重构
- 影响文件：`ui/components/slice_action_card.py`、`ui/interfaces/slice_interface.py`、`ui/controllers/import_controller.py`、`ui/controllers/slice_controller.py`
- 变更摘要：根据最新的 UI 控件命名规范（业务词组_组件类型），将代码中不符合规范的简写组件名进行了全局替换。例如 `btn_slice` 变更为 `start_slicing_button`，`chk_adaptive` 变更为 `adaptive_slicing_checkbox`，`btn_import` 变更为 `import_data_button`。
- 原因：保持项目中变量命名的语义化和一致性，提升代码可读性。并将此命名规则写入了智能体的核心记忆中，以便后续生成代码时严格遵守。
- 测试状态：无需测试

---

## 2026-04-07 15:40
- 操作类型：新增与重构
- 影响文件：`ui/components/slice_action_card.py`、`ui/components/__init__.py`、`ui/interfaces/slice_interface.py`、`ui/controllers/slice_controller.py`
- 变更摘要：新建了 `SliceActionCard` 组合卡片组件（包含“开始切片工作流”按钮和“启用自适应切片”复选框）。在 `slice_interface.py` 右侧面板中用该新卡片替换了原有的纯按钮组件，并在 `slice_controller.py` 中更新了业务绑定逻辑，支持读取复选框的配置状态。
- 原因：根据需求将单纯的切片操作按钮升级为带选项的组合卡片，进一步利用 Fluent 风格的 `SimpleCardWidget` 规范化右侧操作面板的 UI 结构，且保持控制器（Controller）逻辑分离。
- 测试状态：待手动测试验证

---

## 2026-04-07 14:07
- 操作类型：修改
- 影响文件：`docs/目录结构与分层约束.md`
- 变更摘要：更新目录基线，将 `infra/plotting.py` 更改为子包结构，新增 `ui/controllers/` 目录用于体现 MVP/MVC 架构分离，并修正 `runtime/workflows` 和 `runtime/threading` 的命名与注释。
- 原因：保持架构文档与实际落地代码的一致性，反映最近几次关于绘图剥离和 UI 逻辑解耦的重构成果。
- 测试状态：无需测试

---

## 2026-04-07 13:57
- 操作类型：重构
- 影响文件：`ui/interfaces/slice_interface.py`、`ui/controllers/import_controller.py`、`ui/controllers/slice_controller.py`
- 变更摘要：将 `slice_interface.py` 中关于“导入数据”和“切片处理”的槽函数与信号监听逻辑剥离，分别迁移至新建的 `ImportController` 和 `SliceController` 中。
- 原因：解决 UI 界面文件因混合布局逻辑与事件处理逻辑导致的臃肿问题，遵循 MVP/MVC 架构规范中的单一职责原则，提高代码的可维护性与可读性。
- 测试状态：待手动测试验证

---

## 2026-04-07 11:17
- 操作类型：重构
- 影响文件：`runtime/threading/import_worker.py`、`runtime/workflows/import_workflow.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：根据 `signal_bus` 的生命周期架构规范，重构了 `ImportWorkflow` 和 `ImportWorker` 的信号机制。`ImportWorker` 的回调改为统一的 `finished_signal`；`ImportWorkflow` 改为使用 `signal_bus.stage_started`、`stage_finished` 与 `stage_failed` 向全局广播状态；UI 层也更新了对应的错误与成功回调监听，分离了错误处理与成功业务逻辑。
- 原因：之前的 `import_workflow` 没有正确遵循全局的 `signal_bus` 生命周期规范，而是通过伪造事件名（如 `"import_error: xxx"`）将失败和成功混用，导致 UI 层监听逻辑混乱且容易出错。本次重构将其与切片工作流（`slice_workflow`）完全对齐。
- 测试状态：待手动测试验证

---

## 2026-04-07 11:13
- 操作类型：新增
- 影响文件：`runtime/threading/import_worker.py`、`runtime/workflows/import_workflow.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：根据现有 `core/preprocess.py` 中的数据处理纯函数，设计并实现了 Excel 数据导入的工作流 (`ImportWorkflow`) 与后台线程 (`ImportWorker`)。修改了 `slice_interface.py` 中测试面板的导入按钮逻辑，现在点击导入会启动导入工作流，不仅能异步读取数据，还会执行数据清洗、时间翻折修正等预处理操作，并且保证整个流程的 session_id 与后续切片一致。
- 原因：之前的直接导入只进行了数据组合而未调用 `core` 中的预处理逻辑。采用 Workflow + Worker 模式后，导入阶段也能避免阻塞主线程，同时完成了真正的“清洗 -> 提取 -> 修正”链路闭环，为后续核心算法的准确性提供保障。
- 测试状态：待手动测试验证

---

## 2026-04-07 09:11
- 操作类型：修改
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：将切片测试界面的数据导入方式从硬编码伪造数据更改为唤起文件选择对话框导入 Excel 文件。
- 原因：支持从本地选择真实的 Excel 雷达信号数据进行切片渲染测试，验证核心算法在真实数据下的表现。临时功能易于删除。
- 测试状态：待手动测试验证

---

## 2026-04-07 08:51
- 操作类型：修改
- 影响文件：`ui/components/slice_dimension_card.py`
- 变更摘要：修复 `RoundedImageLabel.paintEvent` 中 `QPainter` 的资源释放问题，改用 `with QPainter(self) as painter:` 上下文管理器语法。
- 原因：之前的代码中直接实例化了 `QPainter` 对象但未调用 `end()`，可能导致潜在的内存泄漏和资源未正确释放。
- 测试状态：待手动测试验证

---

## 2026-04-03 16:11
- 操作类型：修改
- 影响文件：`ui/components/slice_dimension_card.py`、`resources/qss/dark/slice_interface.qss`、`resources/qss/light/slice_interface.qss`、`docs/operateLog.md`
- 变更摘要：移除 `SliceDimensionCard` 中图像容器的内边距，并将 `RoundedImageLabel` 的圆角参数恢复为 6px 以匹配卡片圆角；同时修改深色和浅色主题的 QSS 样式文件，为 `SimpleCardWidget#sliceImageCard` 添加 1px 的主题色边框（`border: 1px solid --ThemeColorPrimary;`）。
- 原因：用户要求使用主题色边框替代内边距方案，以此更好地适配 Fluent 风格并兼顾多主题表现。
- 测试状态：待手动测试验证

---

## 2026-04-03 16:07
- 操作类型：新增
- 影响文件：`ui/components/slice_dimension_card.py`、`docs/operateLog.md`
- 变更摘要：在 `slice_dimension_card.py` 中新增 `RoundedImageLabel` 类，利用 `QPainter` 与 `QPainterPath` 对显示的 `QPixmap` 实现了圆角裁剪绘制；并修改了切片图像卡片内部布局，增加了 2px 内边距与对应的圆角参数（radius=4）。
- 原因：原 `QLabel` 设置 `setScaledContents(True)` 无法直接保持图像圆角，导致图像呈直角并贴边，视觉不佳。为保持卡片（6px 圆角）与内部图像的视觉一致性，增加内边距与平滑裁剪逻辑。
- 测试状态：待手动测试验证

---

## 2026-04-03 16:03
- 操作类型：修改
- 影响文件：`ui/components/slice_dimension_card.py`、`docs/operateLog.md`
- 变更摘要：为 `SliceDimensionCard` 内部显示图像的 `QLabel` (`image_label`) 设置 `QSizePolicy.Policy.Ignored`。
- 原因：修复展示大尺寸图片时卡片被撑大、大小发生改变的问题，确保组件尺寸稳定性。
- 测试状态：待手动测试验证

---

## 2026-04-03 16:00
- 操作类型：修改
- 影响文件：`ui/components/slice_dimension_card.py`、`ui/interfaces/slice_interface.py`、`docs/operateLog.md`
- 变更摘要：修复 `slice_interface.py` 中 `SliceDimensionCard` 缺少 `setTitle` 方法导致的 AttributeError 报错；为 `SliceDimensionCard` 添加内部 `QLabel` 用于显示图片，并新增 `set_image(QPixmap)` 方法，完善渲染结果更新回调逻辑。
- 原因：之前的切片组件未正确封装图片显示接口，且 UI 界面在更新标题时错误调用了组件的非存在方法。
- 测试状态：待手动测试验证

---

## 2026-04-03 15:51
- 操作类型：重构
- 影响文件：`runtime/workflows/slice_workflow.py`、`runtime/threading/slice_worker.py`、`docs/operateLog.md`
- 变更摘要：根据单一职责与目录约束原则，创建 `runtime/threading` 目录，将切片工作流文件中的 `_SliceWorker` 线程类抽离并移动到 `slice_worker.py` 文件中，确保 workflow 只做编排不掺杂线程类
- 原因：修复先前未严格遵守《目录结构与分层约束》规则的问题，解除编排与后台线程在物理文件上的耦合
- 测试状态：无需测试（重构结构调整）

---

## 2026-04-03 15:16
- 操作类型：新增
- 影响文件：`app/signal_bus.py`、`runtime/workflows/slice_workflow.py`、`ui/interfaces/slice_interface.py`、`docs/operateLog.md`
- 变更摘要：实现切片工作流（独立子线程进行预处理、切片与首个切片图像渲染），在 `slice_interface` 右侧添加测试用的导入与切片触发按钮，并通过全局 `signal_bus` 连接渲染结果展示到左侧组件
- 原因：推进“核心算法 + runtime 编排 + UI 被动展示”的架构闭环验证，避免 UI 直接调用核心业务或执行耗时计算
- 测试状态：待手动测试验证

---

## 2026-04-03 10:34
- 操作类型：重构
- 影响文件：`infra/plotting.py` -> `infra/plotting/` (`types.py`, `utils.py`, `engine.py`, `facades.py`, `exporter.py`, `__init__.py`), `infra/__init__.py`, `docs/plot_manager到新架构映射清单.md`
- 变更摘要：将 `infra/plotting.py` 拆分为 `infra/plotting` 子包，按数据结构、辅助函数、核心渲染、场景门面、导出工具分模块组织，并同步更新了映射文档
- 原因：原 `plotting.py` 文件结构过长，职责混合，拆分子包后模块更清晰，避免后续代码膨胀
- 测试状态：已测试（`python -m compileall infra` 通过，诊断无错误）

---

## 2026-04-03 09:56
- 操作类型：新增
- 影响文件：`infra/plotting.py`、`infra/__init__.py`、`docs/operateLog.md`
- 变更摘要：完成 infra 纯绘图能力实现，新增绘图规格、切片/聚类/预测/合并渲染函数与图像导出接口，并导出为包公共能力
- 原因：落实映射清单中“绘图算法下沉 infra、runtime 仅编排”的分层目标
- 测试状态：已测试（`python -m compileall infra` 通过，诊断无错误）

---

## 2026-04-03 09:54
- 操作类型：修改
- 影响文件：`docs/operateLog.md`
- 变更摘要：开始实现 `infra/plotting.py` 纯绘图功能，准备按映射清单落地数据结构与渲染函数
- 原因：将旧版绘图规则下沉为基础设施层能力，为 runtime 工作流接入提供稳定接口
- 测试状态：无需测试（开发中）

---

## 2026-04-03 09:41
- 操作类型：新增
- 影响文件：`docs/plot_manager到新架构映射清单.md`、`docs/operateLog.md`
- 变更摘要：新增旧版 `plot_manager.py` 到新项目 `core/infra/runtime/ui` 分层的映射清单文档，并给出函数级迁移建议与迁移顺序
- 原因：为后续绘图模块抽离提供稳定的职责边界，避免重构时再次形成“大而全”的绘图管理类
- 测试状态：无需测试（文档新增）

---

## 2026-04-03 09:40
- 操作类型：修改
- 影响文件：`docs/operateLog.md`
- 变更摘要：开始整理旧版 `plot_manager.py` 向新项目架构的职责映射文档
- 原因：为后续绘图模块抽离与重构提供统一迁移清单，避免把旧版绘图器整类平移到新架构
- 测试状态：无需测试（文档整理中）

---

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
