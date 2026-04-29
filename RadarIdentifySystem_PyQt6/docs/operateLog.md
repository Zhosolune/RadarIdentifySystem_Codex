# 变更记录

- 时间：2026-04-29 15:06
- 操作类型：重构
- 影响文件：
  - `ui/controllers/identify_controller.py`
  - `runtime/workflows/identify_workflow.py`
  - `runtime/threading/identify_worker.py`
- 变更摘要：消除参数透传链——控制器不再从 runtime 获取参数再回传给 workflow，改为 IdentifyWorker 内部自行调用 `get_clustering_params()`/`get_recognition_params()` 获取运行参数。
- 原因：UI 层不应关心 runtime 参数组装，消除无效透传让 workflow/worker 入口更简洁，职责更内聚。
- 测试状态：已测试（`python -m py_compile` 通过）

- 时间：2026-04-29 14:45
- 操作类型：重构
- 影响文件：
  - `core/clustering.py`
  - `runtime/threading/identify_worker.py`
- 变更摘要：将跨维度聚类-识别编排函数从 `core/clustering.py` 迁移至 `runtime/threading/identify_worker.py` 中的私有方法 `_cluster_and_recognize_slice`，`core` 仅保留单维度纯算法。
- 原因：编排逻辑（CF→识别→PW→识别→组装）属于业务调度职责，不适合放在 `core` 纯算法层，应归入 `runtime` 执行层。
- 测试状态：已测试（诊断通过，`python -m py_compile` 通过）

- 时间：2026-04-29 11:43
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
- 变更摘要：将模型卡片备注预览改为单行显示，换行和多余空白统一压平成空格，tooltip 继续保留原始多段文本格式。
- 原因：修复短多行备注在卡片中显示为“一行半”且被截断的问题，同时保留省略号提示与完整备注浏览能力。
- 测试状态：已测试（诊断通过，`python -m py_compile` 通过）

- 时间：2026-04-29 11:14
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
- 变更摘要：将模型卡片备注标签的悬浮提示切换为组件库 `ToolTipFilter + ToolTipPosition.TOP` 方案。
- 原因：统一备注提示的 Fluent 风格，避免继续显示 Qt 原生系统提示样式。
- 测试状态：已测试（诊断通过，`python -m py_compile` 通过）

- 时间：2026-04-29 11:12
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
- 变更摘要：计划将模型卡片备注标签的原生 `setToolTip()` 用法替换为组件库提示方案。
- 原因：统一备注悬浮提示的视觉风格，避免继续使用 Qt 原生提示样式。
- 测试状态：待测试

- 时间：2026-04-29 10:57
- 操作类型：重构
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/components/model_list_page.py`
  - `ui/components/__init__.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：将模型管理页重构为 `SegmentedWidget + QStackedWidget` 结构，新增 PA/DTOA 独立列表页组件，并让控制器按页面分别渲染模型列表。
- 原因：对齐组件库官方推荐的顶部导航切页模式，降低界面层与列表容器的耦合度，为后续独立扩展两类模型页面预留结构。
- 测试状态：已测试（诊断通过，`python -m py_compile` 通过）

- 时间：2026-04-29 10:52
- 操作类型：重构
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/components/__init__.py`
  - `ui/components/model_list_page.py`
- 变更摘要：计划将模型管理页重构为 `SegmentedWidget + QStackedWidget` 结构，并抽离 PA/DTOA 独立列表页组件。
- 原因：对齐组件库官方推荐的顶部导航切页模式，消除当前“分段控件仅作为筛选开关”的结构偏差。
- 测试状态：待测试

- 时间：2026-04-29 10:14
- 操作类型：修改
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
  - `ui/controllers/model_manager_controller.py`
- 变更摘要：在模型管理页新增用户模型目录设置卡，并确保系统默认模型卡片在列表中始终置顶显示。
- 原因：补齐用户模型根目录的页面入口，形成目录配置闭环，同时强化系统默认模型的展示优先级。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-29 10:09
- 操作类型：重构
- 影响文件：
  - `app/app_config.py`
  - `app/model_bootstrap.py`
  - `runtime/workflows/identify_workflow.py`
  - `config/config.json`
- 变更摘要：将模型配置收敛为“用户模型根目录 + 两个启用模型路径”，删除多目录与运行时重复路径配置。
- 原因：按单根目录闭环模型管理，避免目录列表与运行时路径双份状态，统一由根目录推导 `PA`/`DTOA` 子目录。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-29 09:38
- 操作类型：重构
- 影响文件：
  - `infra/model_registry.py`
  - `app/model_bootstrap.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/components/model_item_card.py`
  - `ui/components/scrolling_name_label.py`
  - `ui/components/__init__.py`
  - `config/meta.json`
- 变更摘要：移除模型元数据中的旧启用状态结构并清理历史数据；将滚动名称标签抽离为独立组件；删除控制器中的重复初始化逻辑。
- 原因：按当前架构收敛职责边界，避免启用状态双源维护，并将可复用 UI 能力下沉到独立组件。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-29 09:25
- 操作类型：重构
- 影响文件：
  - `main.py`
  - `app/app_config.py`
  - `app/model_bootstrap.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/controllers/identify_controller.py`
  - `ui/components/model_item_card.py`
- 变更摘要：修复模型卡片名称不显示问题；将启用模型状态收敛到配置系统管理，并在启动阶段完成初始化与运行时路径同步。
- 原因：避免名称组件因缺少尺寸提示导致不可见，并消除模型启用状态在配置与注册表之间双源维护的复杂度。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-29 09:03
- 操作类型：修改
- 影响文件：
  - `ui/controllers/model_manager_controller.py`
  - `ui/components/model_item_card.py`
- 变更摘要：模型启用日志补充展示名称并在启动后记录当前启用模型快照；模型名称区域增加最大宽度限制，超长时自动滚动显示。
- 原因：提升模型启用日志可读性，并优化长名称模型在卡片中的展示效果。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-29 08:52
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/dialogs/import_model_dialog.py`
  - `ui/dialogs/edit_model_remark_dialog.py`
  - `infra/model_registry.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：模型卡片第二行改为显示可编辑备注；导入模型时支持填写备注；命令栏新增“编辑备注”按钮并持久化保存备注信息。
- 原因：按交互需求移除文件路径展示，改为承载用户可维护的模型说明信息，提升模型管理可读性。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-28 17:28
- 操作类型：重构
- 影响文件：
  - `infra/model_registry.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/components/model_item_card.py`
- 变更摘要：将模型元数据文件迁移至 `config/meta.json` 并兼容旧路径；模型列表改为“系统内置目录 + 用户目录”联合加载；系统内置模型固定显示“系统默认”且禁止重命名/删除；导入模型改为写入用户目录。
- 原因：满足“系统默认模型只读、默认启用、打包后用户模型可写”的部署与交互要求，避免向安装目录写入数据。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-28 16:28
- 操作类型：重构
- 影响文件：
  - `infra/model_registry.py` (由 `utils/model_registry.py` 移动)
  - `ui/controllers/model_manager_controller.py`
  - `ui/controllers/identify_controller.py`
- 变更摘要：将模型元数据注册表 `model_registry.py` 从 `utils` 目录移动到 `infra` 目录，并更新相关引用。
- 原因：根据项目架构规范，`utils` 仅存放无业务语义的通用工具，而 `model_registry.py` 负责 PA/DTOA 模型状态及别名的持久化（文件读写与业务语义强绑定），属于存储与适配层，故归入 `infra`。
- 测试状态：已测试（通过静态引用检查）

- 时间：2026-04-28 11:55
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：修复单选按钮与后续内容间距过大问题，收紧主布局和左侧子布局间距，并将 `modelEnableButton` 的主题最小宽度从 58px 调整为 16px。
- 原因：定位到间距异常由主题 QSS 的最小宽度与布局间距叠加导致，单改控件固定宽度无法生效。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-28 11:43
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
- 变更摘要：移除模型启用开关组件并改为 `RadioButton`，同时将启用控件布局位置调整到卡片最左侧。
- 原因：按最新交互要求简化启用控件样式并强化“单选启用”语义。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-28 11:36
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
- 变更摘要：修正启用开关仍显示文字问题（清空 on/off 文案并固定宽度），并新增命令栏占位容器以保证命令栏隐藏时仍保留布局位置。
- 原因：修复模型卡片视觉细节偏差，确保交互状态与布局稳定性符合预期。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-28 11:26
- 操作类型：修改
- 影响文件：
  - `ui/components/model_item_card.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：将模型启用控件由 `TogglePushButton` 调整为无文字 `SwitchButton`，开关改为常显；命令栏保留悬浮显示；移除命令栏悬浮变红效果与模型卡片启用态高亮样式。
- 原因：优化交互可读性与视觉克制性，按最新反馈简化卡片状态表达。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-28 10:41
- 操作类型：重构
- 影响文件：
  - `ui/components/model_item_card.py`
  - `ui/controllers/model_manager_controller.py`
  - `utils/model_registry.py`
  - `ui/controllers/identify_controller.py`
  - `runtime/workflows/identify_workflow.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：新增模型启用开关与悬浮显隐交互，增加启用态卡片样式与主题适配，落地“PA/DTOA 各仅一个启用模型”约束，并在开始识别前增加启用完整性校验与右下角提示。
- 原因：满足模型管理交互升级需求，并保证识别流程使用明确且一致的启用模型配置。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 17:18
- 操作类型：重构
- 影响文件：
  - `ui/components/model_item_card.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/dialogs/delete_model_dialog.py`
- 变更摘要：将重命名与删除弹窗触发逻辑从卡片组件迁移到控制器，弹窗父对象统一为模型管理子界面，并新增删除确认对话框。
- 原因：修复弹窗仅在卡片区域显示的问题，落实“交互由控制器统一编排”的分层约束。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 17:12
- 操作类型：重构
- 影响文件：
  - `ui/components/model_item_card.py`
  - `ui/controllers/model_manager_controller.py`
  - `ui/dialogs/rename_model_dialog.py`
- 变更摘要：修复模型卡片均分布局问题；新增基于 `MessageBoxBase` 的重命名对话框并支持回车确认；增强删除逻辑对 Windows 只读权限异常的兜底处理。
- 原因：满足模型管理交互一致性要求并修复删除模型时的“拒绝访问”问题。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 16:59
- 操作类型：重构
- 影响文件：
  - `ui/components/model_item_card.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：清理模型项卡片内联样式，改为对象名与动态属性驱动的 QSS 样式，并补齐明暗主题下名称、路径与类型徽标配色。
- 原因：遵循“禁止内联样式”规范，并确保同一组件在浅色/深色主题下均有完整样式定义。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 16:51
- 操作类型：修改
- 影响文件：
  - `ui/controllers/model_manager_controller.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：移除模型空状态文案的内联样式，改为对象名 + QSS 统一管理，并保留顶部留白。
- 原因：遵循“禁止内联样式”的项目规则，避免控制器中混入样式实现细节。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 16:33
- 操作类型：新增
- 影响文件：
  - `app/style_sheet.py`
  - `ui/interfaces/model_manager_interface.py`
  - `resources/qss/light/model_manager_interface.qss`
  - `resources/qss/dark/model_manager_interface.qss`
- 变更摘要：新增模型管理页面专用样式表入口与明暗主题 QSS 文件，并将模型列表滚动区域背景设置为透明。
- 原因：按界面样式隔离要求为模型管理页提供独立样式能力，避免复用设置页样式造成耦合。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 16:26
- 操作类型：修改
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
  - `ui/controllers/model_manager_controller.py`
- 变更摘要：删除模型管理页刷新按钮及其控制器绑定逻辑，保留分段切换和导入后自动刷新模型列表。
- 原因：刷新按钮已无实际业务价值，简化交互入口并减少冗余控制逻辑。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 16:21
- 操作类型：重构
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
- 变更摘要：在用户当前改动基础上修复模型管理页面结构，恢复为“先初始化组件，再 `_initWidget()`，并在 `_initWidget()` 内统一执行 `_initLayout()` 与 `_connectSignalToSlot()`”的组织方式。
- 原因：修复页面结构混乱导致的布局不完整问题，并与 `setting_interface.py` 的初始化组织风格保持一致。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-27 15:45
- 操作类型：重构
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
- 变更摘要：重构模型管理页面布局为“整页不滚动 + 列表区域独立滚动”，并使用 `SettingCardGroup` + `PrimaryPushSettingCard` 承载导入模型入口，同时缩小模型卡片间距。
- 原因：按最新交互要求统一设置页风格，避免整页滚动带来的操作区域位移问题，提升模型列表浏览体验。
- 测试状态：待测试

- 时间：2026-04-27 15:00
- 操作类型：重构与修复
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
  - `ui/controllers/model_manager_controller.py`
  - `utils/model_registry.py`
- 变更摘要：移除模型管理界面的 `FolderListSettingCard` 多目录配置，改为直接固定读取并写入 `resources/models/PA` 和 `resources/models/DTOA` 目录；修复 `model_registry.py` 中 `meta.json` 保存路径层级错误的问题。
- 原因：简化模型管理逻辑，响应用户对“为什么选中目录后还不等点击刷新按钮模型列表就已经出来”及“逻辑混乱”的反馈；修正资源路径使其准确落在 `RadarIdentifySystem_PyQt6/resources` 目录下。
- 测试状态：待测试

- 时间：2026-04-27 14:40
- 操作类型：重构
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
  - `ui/controllers/model_manager_controller.py` (新增)
- 变更摘要：根据职责独立原则，将 `ModelManagerInterface` 中的业务逻辑和事件槽函数抽离至新创建的 `ModelManagerController` 中。
- 原因：遵循 MVP 模式的 Controller 架构约束，UI 界面代码（View）只负责布局、组件拼装和渲染，Controller 负责处理模型加载、导入、删除及重命名等核心交互逻辑。
- 测试状态：待测试

- 时间：2026-04-27 14:30
- 操作类型：重构与新增
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
  - `ui/components/model_item_card.py`
  - `ui/dialogs/import_model_dialog.py` (新增)
  - `utils/model_registry.py` (新增)
- 变更摘要：调整模型管理逻辑，PA和DTOA目录配置卡片不再隐藏；新增导入对话框并将模型统一存入 `resources/models` 对应目录；引入 `ModelRegistry` 实现模型虚拟重命名。
- 原因：根据用户需求，使配置卡片常驻显示，优化模型导入的 UI 交互，并通过元数据映射表管理重命名，避免直接修改物理源文件。
- 测试状态：待测试

- 时间：2026-04-27 14:15
- 操作类型：修改
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
- 变更摘要：补充 ModelManagerInterface 类及其所有方法的规范文档注释。
- 原因：遵循项目代码规范，确保方法具备 Google 风格的 docstring，增强代码可读性与可维护性。
- 测试状态：无需测试

- 时间：2026-04-27 13:58
- 操作类型：修复
- 影响文件：
  - `ui/interfaces/model_manager_interface.py`
- 变更摘要：修复 `ModelManagerInterface` 初始化时由于 `SegmentedWidget` 未指定默认选中项而导致的 `AttributeError: 'NoneType' object has no attribute 'routeKey'` 崩溃问题。
- 原因：`qfluentwidgets` 中的 `SegmentedWidget` 默认情况下 `currentItem()` 可能为空，需要调用 `setCurrentItem` 或使用安全的 `currentRouteKey()` 并在为空时给定默认值。
- 测试状态：已测试

- 时间：2026-04-27 13:45
- 操作类型：重构与修改
- 影响文件：
  - `app/app_config.py`
  - `ui/interfaces/model_manager_interface.py`
  - `ui/components/model_item_card.py` (新增)
- 变更摘要：将模型卡片提取为独立组件`ModelItemCard`存入`ui/components`，并为模型管理引入支持多目录的`FolderListSettingCard`以替换单目录卡片。
- 原因：修复之前违背组件需单独建文件并放置于`ui/components`约束的问题；响应用户对选取和管理多个模型目录的真实意图。
- 测试状态：待测试

- 时间：2026-04-27 13:32
- 操作类型：新增与修改
- 影响文件：
  - `app/app_config.py`
  - `ui/interfaces/model_manager_interface.py` (新增)
  - `ui/main_window.py`
- 变更摘要：新增模型管理页面，负责 PA 和 DTOA 模型的目录选择、列表展示与重命名、删除功能。
- 原因：支持多模型架构下的独立模型管理能力，提供可视化的模型文件管理。
- 测试状态：待测试

- 时间：2026-04-24 14:15
- 操作类型：新增
- 影响文件：
  - `core/models/recognition_result.py`
  - `core/models/__init__.py`
  - `core/models/processing_session.py`
- 变更摘要：搭建识别阶段核心数据模型（`RecognitionResult`）。
- 原因：响应新架构识别功能迁移要点，提前完成识别模型契约与依赖倒置（DI）准备。
- 测试状态：待测试

- 时间：2026-04-24 15:50
- 操作类型：修复
- 影响文件：
  - `core/clustering.py`
- 变更摘要：修复在实例化 `SliceRecognitionResult` 时的传参错误，将 `slice_idx` 修正为正确的属性名 `slice_index`。
- 原因：数据模型 `SliceRecognitionResult` 定义中的属性名为 `slice_index`，而调用方错误地使用了 `slice_idx`，导致发生 `TypeError: got an unexpected keyword argument` 异常。
- 测试状态：待测试

- 时间：2026-04-24 14:04
- 操作类型：修改
- 影响文件：
  - `runtime/threading/identify_worker.py`
- 变更摘要：在识别线程启动聚类时新增聚类参数快照日志，记录 `eps_cf`、`eps_pw`、`min_pts`、`min_cluster_size` 与 `slice_index`。
- 原因：提升聚类问题排查能力，明确每次聚类运行的实际参数。
- 测试状态：已测试（文件诊断通过）

- 时间：2026-04-24 13:58
- 操作类型：修改
- 影响文件：
  - `ui/interfaces/params_interface.py`
- 变更摘要：新增输入框统一宽度常量与 `_unifyInputBoxWidth()` 方法，统一参数页 `SpinBox` 与 `DoubleSpinBox` 的固定宽度。
- 原因：解决参数配置界面中不同输入框视觉长度不一致的问题，提升界面整齐性。
- 测试状态：已测试（文件诊断通过）

- 时间：2026-04-24 11:39
- 操作类型：新增与修改
- 影响文件：
  - `docs/算法参数对象规则.md`（新增）
  - `docs/配置系统设计.md`
- 变更摘要：新增“算法参数对象规则”文档，系统化约束参数对象的分层位置、命名方式、配置读取 API、调用链和禁用项，并在配置系统设计文档中补充交叉引用。
- 原因：将新落地的参数对象方案沉淀为长期规则，避免后续识别、提取、合并流程继续回退到长签名或跨层直接读配置。
- 测试状态：已测试（文档诊断通过）

- 时间：2026-04-24 11:34
- 操作类型：修改
- 影响文件：
  - `runtime/algorithm_params.py`
  - `ui/controllers/identify_controller.py`
  - `ui/controllers/slice_controller.py`
- 变更摘要：将运行时参数组装函数统一重命名为 `get_clustering_params`、`get_recognition_params`、`get_extract_params`、`get_merge_params`，并同步更新调用点。
- 原因：精简方法命名，提升调用处可读性，避免函数名过长。
- 测试状态：已测试（诊断通过）

- 时间：2026-04-24 11:24
- 操作类型：修改
- 影响文件：
  - `runtime/algorithm_params.py`
  - `ui/controllers/slice_controller.py`
- 变更摘要：将新增参数组装器中的配置读取方式从直接访问 `ConfigItem.value` 统一改为使用组件库 `qconfig.get(...)`，并同步修正一个业务开关读取点。
- 原因：保持配置系统用法与组件库规范一致，避免直接读取值带来的接口风格不统一问题。
- 测试状态：已测试（诊断通过，`py_compile` 通过）

- 时间：2026-04-24 11:12
- 操作类型：重构
- 影响文件：
  - `core/models/algorithm_params.py`（新增）
  - `core/models/__init__.py`
  - `runtime/algorithm_params.py`（新增）
  - `core/clustering.py`
  - `runtime/workflows/identify_workflow.py`
  - `runtime/threading/identify_worker.py`
  - `ui/controllers/identify_controller.py`
  - `ui/controllers/slice_controller.py`
  - `tests/unit/test_core_clustering.py`
- 变更摘要：新增聚类/识别/提取/合并四类算法参数数据对象，并将聚类链路重构为“runtime 从 `appConfig` 组装 `ClusteringParams`，workflow/worker/core 统一传递单一参数对象”，收敛长函数签名且保持 `core` 不依赖应用配置层。
- 原因：降低多阶段算法参数透传的维护复杂度，同时遵守 `core` 不反向依赖 `app` 的分层约束。
- 测试状态：待测试（静态诊断已通过，`python -m pytest tests/unit/test_core_clustering.py` 因环境缺少 `pytest` 未执行）

- 时间：2026-04-24 09:39
- 操作类型：修改
- 影响文件：
  - `docs/operateLog.md`
- 变更摘要：补充一次架构评估记录，结论为 `core` 不建议直接依赖 `app/app_config.py`；当前“UI/Workflow 读取配置后透传，core 保留默认参数”的方案在复杂度与分层之间更平衡，后续如需继续降复杂度，优先考虑在 `runtime` 增加轻量参数组装层，而不是让 `core` 反向依赖 `app`。
- 原因：用户要求评估 `core` 直接读取全局配置的可行性，并比较不直连配置时的参数应用复杂度，需要将分析结论留痕，便于后续中断恢复。
- 测试状态：无需测试

- 时间：2026-04-23 17:33
- 操作类型：修改
- 影响文件：
  - `ui/components/double_spin_box_setting_card.py`
  - `ui/interfaces/params_interface.py`
- 变更摘要：为 `DoubleSpinBoxSettingCard` 扩展了 `decimals` 和 `singleStep` 初始化参数，以控制显示精度和步长。并在 `params_interface` 实例化这些卡片时，为所有浮点参数设置了合理的精度和微调步长（如置信度等设为两位小数，步长0.05；脉宽聚类半径设为三位小数，步长0.01）。
- 原因：提升用户体验与配置严谨性（让不同量级的浮点参数拥有合适的步进手感和显示精度）。
- 测试状态：已测试

- 时间：2026-04-23 16:52
- 操作类型：重构与删除
- 影响文件：
  - `app/app_config.py`
  - `ui/components/spin_box_setting_card.py`（新增）
  - `ui/components/double_spin_box_setting_card.py`（新增）
  - `ui/interfaces/params_interface.py`
  - `ui/components/cluster_param_card.py`（删除）
  - `ui/components/recognize_param_card.py`（删除）
  - `ui/components/extract_param_card.py`（删除）
  - `ui/components/merge_param_card.py`（删除）
- 变更摘要：删除了使用 GroupHeaderCardWidget 创建的挤压布局卡片，改用更规范的 SettingCardGroup。同时新增 `SpinBoxSettingCard` 与 `DoubleSpinBoxSettingCard`，以结合 `CompactSpinBox` 系列组件，并将这些参数配置（识别、提取、合并参数）真实地添加到了全局 `app_config.py` 中。
- 原因：用户体验与架构一致性（GroupHeaderCardWidget 视觉不佳且易受挤压，转而使用与设置界面一致的标准 SettingCard 体系，实现双向绑定与自动校验）。
- 测试状态：已测试

- 时间：2026-04-23 16:38
- 操作类型：修复
- 影响文件：
  - `ui/interfaces/params_interface.py`
  - `ui/components/cluster_param_card.py`
  - `ui/components/recognize_param_card.py`
  - `ui/components/extract_param_card.py`
  - `ui/components/merge_param_card.py`
- 变更摘要：修复 `GroupHeaderCardWidget` 挤压显示不全的问题。将 `params_interface` 的主布局从 `ExpandLayout` 更改为标准 `QVBoxLayout` 并设置顶部对齐与伸缩因子，同时移除了四个卡片组件中 `LineEdit` 错误的预设父级绑定。
- 原因：技术原因（`ExpandLayout` 机制与 `GroupHeaderCardWidget` 的高度自动推断存在冲突，导致组件被压扁，需恢复标准的尺寸管理布局）。
- 测试状态：待测试

- 时间：2026-04-23 15:53
- 操作类型：重构与新增
- 影响文件：
  - `ui/components/cluster_param_card.py`（新增）
  - `ui/components/recognize_param_card.py`（新增）
  - `ui/components/extract_param_card.py`（新增）
  - `ui/components/merge_param_card.py`（新增）
  - `ui/interfaces/params_interface.py`
- 变更摘要：引入组件库官方 `GroupHeaderCardWidget` 布局方式，将参数配置界面的配置项重构为四个独立的卡片组件（聚类、识别、提取、合并参数），每个组件内部包含3个输入框的垂直分组布局。
- 原因：代码规范与组件化（符合 UI 层组件分离解耦规范，提升界面可维护性与扩展性）。
- 测试状态：已测试

- 时间：2026-04-23 15:13
- 操作类型：新增与修改
- 影响文件：
  - `ui/interfaces/params_interface.py`（原 config_interface.py，重命名并修改类名为 ParamsInterface）
  - `ui/main_window.py`
- 变更摘要：新增参数配置独立界面，在其中添加了聚类算法参数与业务控制开关；并在主窗口侧边栏底部（设置选项上方）添加其导航入口。
- 原因：业务原因（提供一个集中的业务算法参数配置界面）。
- 测试状态：已测试

- 时间：2026-04-23 15:03
- 操作类型：重构与删除
- 影响文件：
  - `runtime/workflows/render_workflow.py`（删除）
  - `runtime/threading/render_worker.py`（删除）
  - `app/signal_bus.py`
  - `ui/controllers/slice_controller.py`
  - `ui/controllers/identify_controller.py`
- 变更摘要：移除渲染后台工作流与 LRU 图像缓存机制，将 UI 的图像加载改为直接同步调用底层绘图门面。
- 原因：业务/技术原因（消除过度设计，底层矩阵运算极快，同步渲染可避免线程开销与复杂的异步状态同步问题）。
- 测试状态：已测试

- 时间：2026-04-23 14:16
- 操作类型：重构
- 影响文件：
  - `ui/controllers/identify_controller.py`（新增）
  - `ui/controllers/slice_controller.py`
  - `ui/interfaces/slice_interface.py`
- 变更摘要：将识别（聚类）相关的 UI 交互逻辑与图像渲染控制从 `SliceController` 剥离，新建独立的 `IdentifyController`。
- 原因：业务原因（遵循单一职责原则，分离切片与识别逻辑，降低控制器的耦合度）。
- 测试状态：已测试

- 时间：2026-04-23 12:28
- 操作类型：重构
- 影响文件：
  - `app/signal_bus.py`
  - `runtime/workflows/import_workflow.py`
  - `runtime/workflows/slice_workflow.py`
  - `runtime/workflows/identify_workflow.py`
  - `ui/controllers/import_controller.py`
  - `ui/controllers/slice_controller.py`
- 变更摘要：扩展生命周期信号统一携带 `slice_index`，使 UI 提示与日志定位到具体切片。
- 原因：技术原因（按切片识别后需要更精确的事件上下文，同时保持事件协议统一）。
- 测试状态：已测试

- 时间：2026-04-23 12:03
- 操作类型：重构
- 影响文件：
  - `core/models/processing_session.py`
  - `runtime/threading/import_worker.py`
  - `runtime/threading/slice_worker.py`
  - `runtime/threading/identify_worker.py`
  - `runtime/threading/render_worker.py`
  - `ui/controllers/slice_controller.py`
  - `tests/unit/test_processing_session.py`
- 变更摘要：将会话状态模型改为“全局阶段 + 切片级局部状态”，并同步调整聚类工作流、渲染判定与界面显示逻辑。
- 原因：技术原因（按切片独立识别后，单一全局枚举无法准确表达局部进度）。
- 测试状态：已测试

- 时间：2026-04-22 16:58
- 操作类型：重构与修复
- 影响文件：
  - `core/models/processing_session.py`
  - `runtime/threading/import_worker.py`
  - `runtime/threading/slice_worker.py`
  - `runtime/threading/identify_worker.py`
  - `runtime/threading/render_worker.py`
  - `runtime/workflows/render_workflow.py`
  - `core/clustering.py`
  - `ui/controllers/import_controller.py`
  - `ui/controllers/slice_controller.py`
  - `runtime/workflows/import_workflow.py`
  - `runtime/workflows/slice_workflow.py`
  - `runtime/workflows/identify_workflow.py`
  - `tests/unit/test_core_slicing.py`
  - `tests/unit/test_core_clustering.py`
- 变更摘要：修复了多项核心隐患：引入线程安全锁以解决 Session 并发读写问题，改为协作式终止渲染线程，修复 DTOA 首元素异常计算，增加 UI 工作流状态自检机制，改用全局配置替代硬编码聚类参数，并补充了核心切片与聚类算法单元测试。
- 原因：技术原因（线程安全、资源泄漏、计算逻辑错误、异常恢复缺失、测试覆盖不足）。
- 测试状态：已测试

## 2026-04-22 11:05
- 操作类型：修改
- 影响文件：`runtime/threading/render_worker.py`
- 变更摘要：在抛出异常（如 `ValueError`、`RuntimeError`）之前，增加了 `LOGGER.error` 语句以记录带有 `session_id` 上下文的错误日志。
- 原因：提升系统的可观测性，确保异常在导致任务中断前能被完整记录下来，方便后续排查。
- 测试状态：无需测试

## 2026-04-22 10:55
- 操作类型：重构
- 影响文件：`runtime/threading/render_worker.py`、`runtime/workflows/render_workflow.py`、`ui/controllers/slice_controller.py`
- 变更摘要：在后台渲染工作线程和工作流中，引入了 `is_cluster_render: bool` 显式标志位来控制执行路径（切片图像渲染 vs 聚类类别图像渲染），替换了原来通过隐式判断 `cluster_index == -1` 来做分支路由的“魔法数字”逻辑。
- 原因：避免魔法数字的使用，使得代码接口的意图更加直白、安全且不易出错，提高了可维护性。
- 测试状态：待测试
- 操作类型：重构/修改
- 影响文件：`app/signal_bus.py`、`runtime/threading/render_worker.py`、`runtime/workflows/render_workflow.py`、`runtime/threading/identify_worker.py`、`runtime/workflows/identify_workflow.py`、`ui/controllers/slice_controller.py`
- 变更摘要：
  1. 统一渲染策略：在 `RenderWorker` 与 `RenderWorkflow` 中增加了 `cluster_index` 参数支持，使单类别的聚类图像渲染也能利用后台渲染线程，从而避免在 `SliceController` 中直接在主线程调用渲染门面。
  2. 控制器重构：将 `SliceController._on_stage_finished` 重构为一个仅负责路由的分发中心，将各阶段具体的处理逻辑提取到了如 `_handle_slicing_finished` 等专属私有方法中，防止其代码无限膨胀。
  3. 调整识别流程：修改 `IdentifyWorker` 使其不再遍历所有切片进行聚类，而是仅接收一个特定的 `slice_index`，实现“点击一次识别仅对当前正在查看的切片执行聚类”。
- 原因：提升 UI 线程响应性；改善控制器代码的可读性与可维护性；更符合用户交互预期（按需分片识别）。
- 测试状态：待测试

## 2026-04-22 10:25
- 操作类型：新增/修改
- 影响文件：`core/models/cluster_result.py`、`core/models/processing_session.py`、`core/params_extract.py`、`core/clustering.py`、`runtime/threading/identify_worker.py`、`runtime/workflows/identify_workflow.py`、`ui/controllers/slice_controller.py`、`requirements.txt`
- 变更摘要：实现识别功能的第一阶段：级联聚类算法迁移与UI绑定。定义了聚类结果的3种状态结构（PENDING/VALID/INVALID），在 `core` 层实现了基于 DBSCAN 的 CF 和 PW 维度级联聚类与 DTOA 周期校验。在 `runtime` 层新增了识别工作流和线程，并在 `SliceController` 中绑定了“开始识别”按钮，实现了聚类结果特征图像在中间列的展示与导航。
- 原因：根据新架构约束迁移旧项目的雷达信号聚类与特征图像展示逻辑，打通了“点击按钮 -> 聚类分析 -> 图像回显”的闭环，暂不包含深度学习识别推理。
- 测试状态：待测试

## 2026-04-22 09:45
- 操作类型：新增/重构
- 影响文件：`runtime/threading/render_worker.py`（新增）、`runtime/workflows/render_workflow.py`（新增）、`ui/controllers/slice_controller.py`、`runtime/threading/slice_worker.py`
- 变更摘要：实现了基于按需后台渲染与 LRU 内存缓存的切片切换（上一片/下一片）功能。在 `SliceController` 中引入了容量为 50 的 `OrderedDict` 图像缓存，并将具体的渲染任务抽离为独立的 `RenderWorkflow` 和 `RenderWorker`。
- 原因：支持快速无缝的相邻切片回看，避免每次翻页重新耗时计算绘图。同时遵守架构约束，将渲染缓存作为视图模型保存在 UI 控制层，不污染 `core` 的业务模型。
- 测试状态：已测试（诊断检查通过）

## 2026-04-22 09:31
- 操作类型：修复
- 影响文件：`runtime/threading/slice_worker.py`、`runtime/threading/import_worker.py`
- 变更摘要：
  1. 修复了预处理逻辑在导入和切片流程中被重复执行的问题。移除了 `slice_worker.py` 中重复调用 `preprocess` 的逻辑，直接从 `session.preprocess_result` 中读取之前导入阶段产生的数据。
  2. 修复了导入工作流中手动硬编码组装 numpy 列索引可能错位的问题。引入 `pulse_batch.py` 中的 `COL_CF`、`COL_PW`、`COL_DOA` 等常量，通过精确的索引赋值保证了基础输入数组的物理顺序正确。
- 原因：避免性能浪费（预处理是极重的计算）；保证列索引结构的一致性，防止因硬编码 `np.column_stack` 的顺序变化引发下游核心算法的索引越界或读取错列。
- 测试状态：待手动测试验证

## 2026-04-21 17:55
- 操作类型：重构
- 影响文件：`core/preprocess.py`、`core/slicing.py`、`runtime/threading/import_worker.py`、`runtime/threading/slice_worker.py`
- 变更摘要：为 `core` 层的算法函数（如 `preprocess`、`slice_by_toa`）增加 `session_id: str = "-"` 参数，并在内部日志调用中使用该参数；在 `runtime` 层的 worker 线程调用时显式透传当前会话的 `session_id`。
- 原因：用户要求在 `core` 中也显示真实的 `session_id`。由于仅传递字符串标识，没有引入对 `ProcessingSession` 对象的反向依赖，因此在保证严格分层的前提下，换取了全链路（从 UI 点击到底层数据切片）高一致性的日志可观测性。
- 测试状态：已测试（诊断检查通过）

## 2026-04-21 17:48
- 操作类型：修改
- 影响文件：`app/logger.py`、`core/preprocess.py`、`core/slicing.py`
- 变更摘要：日志格式中的 `[file]` 字段切换为项目根相对的点分路径（示例：`runtime.threading.slice_worker`，不含 `.py`）；同时移除 `core` 模块日志消息中重复的函数名前缀（如 `slice_by_toa:`、`preprocess:`）。
- 原因：按用户要求提升日志可读性，避免函数名在 `[function]` 与 `message` 中重复展示。
- 测试状态：已测试（诊断检查通过）

## 2026-04-21 17:44
- 操作类型：修改
- 影响文件：`app/logger.py`、`core/preprocess.py`、`core/slicing.py`
- 变更摘要：开始按最新要求调整日志显示字段：`[file]` 改为项目根路径点分格式（无 `.py` 后缀），并清理 message 中重复的函数名前缀。
- 原因：满足用户对日志可读性的一致性要求，减少冗余信息。
- 测试状态：待测试

## 2026-04-21 17:22
- 操作类型：重构
- 影响文件：`app/logger.py`、`runtime/threading/slice_worker.py`、`runtime/threading/import_worker.py`、`runtime/workflows/import_workflow.py`、`runtime/workflows/slice_workflow.py`、`core/preprocess.py`、`core/slicing.py`、`main.py`、`ui/interfaces/setting_interface.py`
- 变更摘要：将日志输出统一为 `[date time] [level] [session_id] [file] [function] message`。移除了复杂的拦截式格式化逻辑，改为标准 `logging.Formatter` 固定模板，并逐条修改现有日志调用：在有会话上下文时显式传入 `extra={"session_id": xxx}`，无会话时统一传入 `extra={"session_id": "-"}`。
- 原因：按用户要求采用“直接改日志语句”的简单方案，保持日志级别全大写，同时仅调整字段顺序并补充 `session_id` 与函数名字段，避免额外隐式拦截带来的维护复杂度。
- 测试状态：待手动测试验证

## 2026-04-21 17:50
- 操作类型：重构/移动
- 影响文件：`infra/plotting/image_scaler.py` -> `ui/adapters/image_scaler.py`、`ui/components/slice_dimension_card.py`
- 变更摘要：将 `image_scaler.py` 从 `infra/plotting/` 移动到了新创建的 `ui/adapters/` 目录下，并更新了导入路径。
- 原因：重新审视了分层架构契约（`ui -> runtime -> infra`）。`image_scaler.py` 本质上是一个纯粹的 Qt 视图渲染辅助函数，用于解决 UI 控件放大时的显示效果，不涉及底层基础设施，因此放在 `infra` 层违反了 UI 不能直接依赖 Infra 的契约。为了遵守严格分层，且避免使用容易引起层级混淆的 `ui/utils`，采纳了用户建议的 `adapters`（适配器）概念，将其归类为 UI 层的专属显示适配工具。
- 测试状态：待手动测试验证

## 2026-04-21 17:45
- 操作类型：重构/移动
- 影响文件：`ui/utils/image_scaler.py` -> `infra/plotting/image_scaler.py`、`ui/components/slice_dimension_card.py`
- 变更摘要：响应用户反馈，将用于处理图像拉伸与插值算法的 `image_scaler.py` 模块从 `ui/utils/` 移动到了 `infra/plotting/` 目录下。同时删除了已清空的 `ui/utils` 目录。
- 原因：考虑到项目中已经存在根级别的 `utils/` 目录，再次创建 `ui/utils/` 容易引起目录层级的混淆。此外，`image_scaler.py` 中虽然处理的是 `QImage` 的渲染逻辑，但其核心本质是基于 NumPy 的图像重采样算法，将其归类为绘图（plotting）基础设施（`infra/plotting`）的一部分在架构上更为合理，能够更好地保持基础设施层的内聚性。
- 测试状态：待手动测试验证

## 2026-04-21 17:40
- 操作类型：重构/修复
- 影响文件：`ui/utils/image_scaler.py`（新增）、`ui/components/slice_dimension_card.py`、`ui/controllers/slice_controller.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：排查了新架构下绘图模糊的原因，发现是因为 `SliceDimensionCard` 中硬编码了 `SmoothTransformation` (双线性滤波)，导致 1 像素的点被虚化。新建了 `ui/utils/image_scaler.py` 图像拉伸算法模块，将旧版本的三种图像展示方式（STRETCH 原始拉伸、STRETCH_BILINEAR 双线性插值、STRETCH_NEAREST_PRESERVE 最近邻保留）以纯 Python/NumPy 向量化加速的方式移植到了新架构中。同时重构了 `RoundedImageLabel` 以支持内部图片按尺寸和模式进行缓存缩放，并接入了全局配置 `appConfig.plotScaleMode` 实现动态切换。
- 原因：原先为了支持圆角抗锯齿硬编码了平滑缩放，这会破坏仅有单像素点宽度的离散散点图的可视性（使其模糊）。通过补齐并升级原有的三种自定义缩放算法，兼顾了不同用户的观测需求，并将纯展示逻辑代码收敛到正确的 `ui/utils` 工具目录内。
- 测试状态：待手动测试验证

## 2026-04-21 17:30
- 操作类型：重构
- 影响文件：`core/models/slice_result.py`、`core/slicing.py`、`runtime/threading/slice_worker.py`、`tests/unit/test_core_slicing.py`
- 变更摘要：重构了切片结果的数据结构。引入了 `SingleSlice` 数据类，用于表示单个切片，包含 `index`（索引）、`data`（脉冲数据）和 `time_range`（时间范围）。`SliceResult` 类现已更新，其 `slices` 属性变更为包含 `SingleSlice` 对象列表，而不再是使用两个平行的 `slices` 和 `time_ranges` 列表。
- 原因：根据用户需求，将单个切片的数据和元数据（如索引、时间范围）封装到一个内聚的对象 (`SingleSlice`) 中。这种面向对象的设计更符合直觉，提高了代码的可读性和维护性，避免了之前维护两个平行列表时可能出现的索引不一致问题。
- 测试状态：待手动测试验证

## 2026-04-11 17:48
- 操作类型：UI/修复
- 影响文件：`resources/images/icons/*.svg` (8个方向箭头文件)、`fix_svgs.py`
- 变更摘要：更新了用于生成轮廓化多边形的 Python 脚本（`fix_svgs.py`），将其内部预设的 SVG `path d` 属性替换为了使用 `stroke-width=2`（加粗）渲染并重新轮廓化后的多边形数据。重新执行脚本覆盖了原有的 8 个 SVG 图标文件。
- 原因：由于上一步将线条描边（stroke）转化为多边形填充（fill）时，采用了标准的 1.5 像素粗细，导致在特定的 DPI 缩放或渲染引擎下，视觉上显得过于单薄和纤细。本次将其重新按照加粗样式（相当于 stroke-width=2.0）进行几何换算，以增强透明按钮图标的视觉存在感。
- 测试状态：请确保执行了资源重编译（如 `pyrcc` 或 `pyside6-rcc`）后测试

## 2026-04-11 17:42
- 操作类型：UI/修复
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：在透明图标按钮的实例化代码中，使用了 `CustomIcon.xxx.colored(themeColor(), QColor("white"))` 替代了之前的 `.icon(color=...)` 或默认枚举引用。
- 原因：用户提出在深色模式下图标不应该继续保持主题色，而应该恢复成白色的需求。`PyQt6-Fluent-Widgets` 的 `FluentIconBase` 提供了 `.colored(lightColor, darkColor)` 方法，它专门用于生成在浅色模式和深色模式下分别呈现不同自定义颜色的自适应图标 (`ColoredFluentIcon`)。如此配置后，浅色模式下图标呈现主题色，深色模式下自动变为纯白色，实现了完美的视觉平衡。
- 测试状态：待手动测试验证

## 2026-04-11 17:35
- 操作类型：UI/修复
- 影响文件：`resources/images/icons/*.svg` (8个方向箭头文件)、`ui/interfaces/slice_interface.py`
- 变更摘要：编写 Python 脚本将 `ChevronLeft`、`ChevronRight`、`ChevronsLeft`、`ChevronsRight` 这 8 个（包含黑白模式）由于原先使用 `<path stroke="#000000" />` 绘制的 Lucide 开放线条 SVG 文件，重写为等效的 `<path fill="#000000" />` （轮廓化描边后的多边形填充格式）。并在 UI 代码中重新启用了 `.icon(color=themeColor())`。
- 原因：用户希望这些透明按钮的图标能响应全局的主题色。由于 `qfluentwidgets` 底层 `SvgIconEngine` 的机制是暴力替换 `fill` 属性，对于仅使用 `stroke`（线条）绘制的 SVG，它会错误地填充线条闭合的内部区域。为了迎合该机制，将图标源文件“轮廓化”（Stroke to Path），使得原本的线条本身变成实心多边形，从而完美支持 `qfluentwidgets` 的 `color` 滤镜渲染。
- 测试状态：请确保执行了资源重编译（如 `pyrcc` 或 `pyside6-rcc`）后测试

## 2026-04-11 17:22
- 操作类型：UI/修复
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：撤销了上一版本中对 `CustomIcon` 使用 `color=themeColor()` 的着色操作。将四个翻页按钮的图标重新恢复为默认的 `CustomIcon.xxx`。
- 原因：用户反馈使用 `.icon(color=...)` 后，SVG 图标不仅线条颜色没变，反而出现了区域填充的问题，且失去了跟随系统深浅色主题自动切换颜色的能力。这是因为 `qfluentwidgets` 的图标着色机制通常依赖特定的 SVG 内部结构（如特定的 `path fill` 属性）。我们现有的 `CustomIcon` 已经通过枚举重写了 `path()` 方法，内部直接加载了预先画好的黑/白两个物理 `.svg` 文件，自带完美的主题切换能力。强行加 `color` 滤镜反而会破坏这种机制，故予以回退。
- 测试状态：待手动测试验证

## 2026-04-11 17:15
- 操作类型：UI/重构
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：在实例化四个 `TransparentToolButton` 翻页按钮时，通过调用 `CustomIcon.xxx.icon(color=themeColor())`，将原先黑白配色的默认图标渲染为了当前应用配置的全局主题色（Theme Color）。
- 原因：用户希望标题两侧的翻页控制按钮更加醒目并融入主题系统。`qfluentwidgets` 的枚举图标底层支持在生成 `QIcon` 时通过 `color` 参数进行染色，直接应用 `themeColor()` 可以完美使图标颜色与软件的 Primary 按钮以及高亮色保持绝对一致。
- 测试状态：待手动测试验证

## 2026-04-11 17:08
- 操作类型：UI/重构
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：调整了切片和类别标题两侧的 `TransparentToolButton` 尺寸。将按钮的固定大小（FixedSize）设为 25×25，并将内部图标大小（IconSize）设为 20×20。
- 原因：根据用户反馈，默认的透明按钮和图标尺寸可能偏大，影响标题区域的紧凑和精致感。通过显式限制组件库图标按钮的长宽像素，使其在布局中显得更加协调与秀气。
- 测试状态：待手动测试验证

## 2026-04-11 17:02
- 操作类型：UI/重构
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：在标题两侧的透明翻页按钮上，补充了组件库专属的 `ToolTipFilter`（悬浮提示过滤器），并设置了 `ToolTipPosition.TOP`（顶部显示）和 1000ms 的悬浮延迟显示。
- 原因：原先直接使用的 `setToolTip()` 只会触发 Qt 原生的系统级黑底/白底悬浮提示，不符合 Fluent Design 规范。引入 `ToolTipFilter` 可使其悬浮提示变为带有圆角、阴影及半透明效果的现代样式，保持全应用 UI 风格的一致性。
- 测试状态：待手动测试验证

## 2026-04-11 16:58
- 操作类型：UI/重构
- 影响文件：`ui/components/navigation_control_card.py`、`ui/interfaces/slice_interface.py`、`ui/controllers/slice_controller.py`
- 变更摘要：在 `newUI` 分支上对切片处理界面的导航控件进行了结构调整。删除了 `navigation_control_card.py` 中底部的“上一片/下一片”、“上一类/下一类”等按钮；在 `slice_interface.py` 中，为左侧切片标题和中间类别标题的两侧分别添加了基于组件库 `TransparentToolButton` 的透明图标按钮（使用现有的 `CustomIcon` 方向箭头）；并在 `slice_controller.py` 中重新绑定了这四个新按钮的占位点击事件。
- 原因：根据用户需求，将切换片和类别的操作入口从右侧面板底部直接移动到对应的展示区标题两侧，不仅使右侧操作面板更加精简，也使得用户的视觉焦点更集中，操作更直观（“所见即所控”）。透明按钮在常态下无背景，完美融入标题栏的视觉效果中。
- 测试状态：待手动测试验证

## 2026-04-11 16:45
- 操作类型：新增文档
- 影响文件：`docs/多页面多模型架构设计指南.md`
- 变更摘要：根据用户关于未来实现“多页面切片分析”以及“子页面使用不同小体积模型进行识别”的需求，编写并归档了相关的架构设计与资源管理指南。
- 原因：在不修改任何代码的前提下，提前规划好未来多标签页/多文件的技术选型（坚决采用多线程、引入全局模型字典缓存池、实施基于 QThreadPool 的并发限制以及大矩阵数据的懒加载策略），确保目前的 `Session + Workflow` 架构能够平滑过渡到复杂场景。
- 测试状态：无需测试

## 2026-04-11 16:40
- 操作类型：排查与文档更新
- 影响文件：`docs/配置系统设计.md`
- 变更摘要：对全项目进行了 `ConfigItem.value` 错误赋值用法的全局排查。确认目前代码中（除了在 `qconfig.load` 之前的默认值初始化外）已经不存在直接给 `.value` 赋值而导致无法持久化的问题。同时修正了 `docs/配置系统设计.md` 中的文档说明，明确要求写入配置必须使用 `qconfig.set(item, value)`，严禁直接使用 `item.value = value`。
- 原因：巩固并验证上一步关于 `PyQt6-Fluent-Widgets` 配置系统的修复成果，防止未来在业务代码或文档参考中再次引入“直接赋值不触发序列化与信号”的错误用法。
- 测试状态：无需测试

## 2026-04-11 16:37
- 操作类型：修复
- 影响文件：`ui/components/plot_option_card.py`
- 变更摘要：修复了绘图选项配置（`plotOnlyShowIdentified` 和 `plotScaleMode`）无法持久化保存到本地 `config.json` 的问题。将下拉框选项改变时直接赋值 `config_item.value = value` 的错误做法，修改为调用 `qfluentwidgets.qconfig.set(config_item, value)`。
- 原因：在 `PyQt6-Fluent-Widgets` 框架中，直接修改 `ConfigItem.value` 不会触发配置文件的序列化写入，也不会发射 `valueChanged` 信号，必须使用 `qconfig.set()` API 才能完成完整的状态同步与持久化。同时已将此规则记录至核心记忆中。
- 测试状态：已测试

## 2026-04-10 15:46
- 操作类型：重构
- 影响文件：`ui/main_window.py`
- 变更摘要：在主窗口新增全局按钮光标统一机制，应用启动后递归扫描所有 `QAbstractButton` 并设置为手指样式；同时通过应用级事件过滤器监听 `Show/Polish/ChildAdded` 事件，对组件库延迟创建的按钮自动补齐手指光标。
- 原因：组件库部分按钮会在运行期动态创建，或在主题刷新后重置光标，仅靠一次性遍历无法覆盖全部按钮。通过“初始化批量设置 + 事件过滤器兜底”的双层机制，确保所有按钮始终保持手指指针。
- 测试状态：已测试（`python -m py_compile ui/main_window.py`）

## 2026-04-10 14:05
- 操作类型：重构
- 影响文件：`ui/components/navigation_control_card.py`、`ui/components/main_action_card.py` (删除)、`ui/interfaces/slice_interface.py`、`ui/components/__init__.py`、`ui/controllers/slice_controller.py`
- 变更摘要：删除了 `main_action_card.py` 组件，将其内部的“开始切片”、“开始识别”按钮以及“自适应切片”复选框迁移至了 `NavigationControlCard` 的顶部。同时，将 `NavigationControlCard` 中的所有导航相关按钮（上一类、下一片等）从自定义的 `ActionButtonCard` 全部降级替换为组件库标准的 `PushButton` 和 `PrimaryPushButton`。同步更新了相关界面的引用以及控制器中的事件绑定。
- 原因：根据用户需求，通过聚合操作面板减少界面的碎片化组件，提升控制卡片的集成度。使用组件库内置的 `PushButton` 替代自定义按钮，避免了复杂的自定义 `paintEvent` 带来的样式维护成本和状态冲突，直接享受组件库最原生的深浅色主题支持与边缘抗锯齿。
- 测试状态：待手动测试验证

## 2026-04-10 11:43
- 操作类型：修复
- 影响文件：`ui/components/action_button_widget.py`、`resources/qss/light/slice_interface.qss`、`resources/qss/dark/slice_interface.qss`
- 变更摘要：恢复了 `action_button_widget.py` 中 `ActionButtonCard.paintEvent` 原有的硬编码绘制逻辑（未修改 L10 的类定义）；同时将 `slice_interface.qss` 中针对 `#actionButtonCard` 的常态背景和边框设为透明，并大幅降低了 hover 和 pressed 状态的背景色透明度（且不写死边框）。
- 原因：由于用户明确要求不可修改 `ActionButtonCard` 当前 `paintEvent` 及其实现的硬编码逻辑（底层一直在画一个自带默认样式和抗锯齿边框的底座），因此在外部 QSS 中再去指定边框和不透明背景必定会与之发生边缘冲突（多出一圈颜色）。为了让响应效果只发生在内部，策略变为：通过 QSS 给 hover/pressed 状态叠加一层极为轻薄的透明黑色/白色遮罩，常态保持透明。这样悬浮/按下时的颜色仅仅是“罩”在原生硬编码的背景之上，不仅避免了画双层边框的重影，还保留了原始样式的细腻抗锯齿。
- 测试状态：待手动测试验证

## 2026-04-10 11:39
- 操作类型：修复
- 影响文件：`ui/components/action_button_widget.py`、`resources/qss/light/slice_interface.qss`、`resources/qss/dark/slice_interface.qss`
- 变更摘要：删除了 `ActionButtonCard` 中 `paintEvent` 里用于硬编码绘制背景和边框的代码，仅保留 `QStyleOption` 结合 `drawPrimitive` 承接 QSS 的渲染。将对应的默认背景色和边框颜色完全移交到了深浅色的 `slice_interface.qss` 中定义。
- 原因：修复 Hover/Pressed 状态下出现双层边框或颜色溢出的问题。此前，我们在代码里手动通过 `painter.drawRoundedRect` 绘制了一层默认背景和边框，同时 QSS 也在根据伪状态（`:hover`, `:pressed`）绘制背景和边框。这两层绘制由于抗锯齿边缘（Antialiasing）和缩放差异无法完全重合，从而导致“多了一圈颜色”。通过将常态样式也统一交由 QSS 接管，保证了同一图层的单一控制源，完美解决了重影问题。
- 测试状态：待手动测试验证

## 2026-04-10 10:36
- 操作类型：重构
- 影响文件：`ui/interfaces/slice_interface.py`、`resources/qss/light/slice_interface.qss`、`resources/qss/dark/slice_interface.qss`
- 变更摘要：移除了 `slice_interface.py` 中关于 `ScrollArea` 及 `scroll_content_widget` 的硬编码 `setStyleSheet`，统一将 `background: transparent` 的样式配置迁移到了对应主题的 QSS 资源文件中。
- 原因：遵守“业务逻辑与样式分离”的最佳实践，不在代码中显示写入 QSS。通过对 `#rightPanelScrollArea` 和 `#scrollContentWidget` 设置专属样式，确保了代码整洁性以及主题控制的一致性。
- 测试状态：待手动测试验证

## 2026-04-10 10:31
- 操作类型：修复
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：修复右侧面板引入 `ScrollArea` 后导致的 Qt 布局层级错误和背景变白问题。创建了一个独立的 `QWidget` 作为滚动内容容器（`scroll_content_widget`），将原有的布局设置于其上，并通过 `setWidget()` 传入 `ScrollArea`；同时强制设置了 `ScrollArea` 及其视口的 QSS 为透明背景和无边框。
- 原因：此前，我们在界面重构中混入了 `ScrollArea` 组件，但误用了 `QVBoxLayout(self.right_panel_scroll_area)` 的写法，将布局直接挂载在了滚动区域本身，而不是它的内容组件上。更致命的是，组件库的 `ScrollArea` 在深色模式下具有自带的不透明背景色（`#f3f3f3`），从而彻底掩盖了底层深色背景，造成大面积泛白。通过更正 Qt 原生的 `setWidget()` 结构体系，并显示注入 `background: transparent` 样式到视口，从根源上修复了这块“白色背景”的顽疾。
- 测试状态：待手动测试验证

## 2026-04-10 10:12
- 操作类型：修复
- 影响文件：`ui/components/jitter_free_container.py`
- 变更摘要：在 `JitterFreeCardGroup` 中将重写的 `paintEvent` 逻辑清空（仅保留 `pass`）。
- 原因：修复深色模式下卡片背景变白的问题。之前的判断有误：原生的 `SettingCardGroup` 的父类其实就是最基础的 `QWidget`，而 `qfluentwidgets` 默认给它的样式表确实是透明的（`background-color: transparent;`）。当我们自作聪明地在 `paintEvent` 中调用 `QStyleOption` 和 `drawPrimitive` 时，反而在某些系统环境（或 Qt 版本）下强制触发了 `PE_Widget` 的不透明默认底色绘制（在深色模式下表现为了反色的白色）。直接将其 `paintEvent` 设为 `pass` 可以完美放空绘制机制，使背景完全透明，从而暴露下层的颜色。
- 测试状态：待手动测试验证

## 2026-04-10 08:57
- 操作类型：重构
- 影响文件：`ui/interfaces/slice_interface.py`、`ui/components/plot_control_card.py`(删除)、`ui/components/plot_option_card.py` (重命名)、`ui/components/redraw_option_card.py` (重命名)、`ui/components/__init__.py`、`ui/controllers/slice_controller.py`
- 变更摘要：
  1. 将 `plot_option_widget.py` 和 `redraw_option_widget.py` 重命名为对应的 `_card.py` 结尾，并更新其内部类名为 `PlotOptionCard` 和 `RedrawOptionCard`。
  2. 删除了作为冗余包装的 `plot_control_card.py` 及其组件类。
  3. 在 `slice_interface.py` 中，实例化了一个全局统一的 `JitterFreeCardGroup` （变量名：`cards_group`）放置于右侧面板。
  4. 将原本散落的所有操作卡片（`MainActionCard`、`NavigationControlCard`、`PlotOptionCard`、`RedrawOptionCard`、`ExportOptionCard`）全部作为子卡片（`addSettingCard`）统一添加到了这个 `cards_group` 容器中。
  5. 更新了控制器 `slice_controller.py` 中引用重绘信号层级结构的属性名，从 `view.plot_control_card.redraw_option_card` 简化为 `view.redraw_option_card`。
- 原因：为了最彻底地解决界面抖动问题，并保持视觉上所有卡片间距的高度一致。将所有卡片都视为独立的 `SettingCard` 并将它们统一归拢在同一个 `SettingCardGroup` 的内部布局管辖下，不再在外部手动混合嵌套不同类型的容器和布局管理器，从根本上实现了统一而平滑的排版与动画计算。
- 测试状态：待手动测试验证

## 2026-04-10 08:35
- 操作类型：修复
- 影响文件：`ui/interfaces/slice_interface.py`、`ui/components/plot_control_card.py`、`ui/components/__init__.py`、`ui/components/jitter_free_container.py` (新建)
- 变更摘要：
  1. 回退了上一次试图在最外层直接使用 `ExpandLayout` 的重构尝试，恢复为 `QVBoxLayout` 并恢复了 `addStretch(1)` 的调用。
  2. 重新引入了 `JitterFreeCardGroup` 无抖动包装器类。
  3. 将具有折叠动画的组件（`PlotControlCard` 中的绘图与重绘卡片、`ExportOptionCard`）分别重新包裹在 `JitterFreeCardGroup` 内部。
- 原因：修复右侧面板所有组件挤压重叠的严重布局 Bug。`qfluentwidgets.ExpandLayout` 是专为 `SettingCard` 设计的内部布局，它在执行 `__doLayout` 计算高度时，依赖于子卡片能够立刻提供有效高度，并不具备通用布局（如 `QVBoxLayout`）在初始化时处理普通 QWidget 的弹性空间和大小提示（sizeHint）的能力。如果强行用它来装载普通控件，就会导致它们在初始化时高度计算失败而全部挤在一起。因此，通过自定义外壳（仅隐藏标题和间距）将其局限在特定的设置卡片外部是目前既能消除抖动又能保证其余控件正常排版的唯一完美解。
- 测试状态：待手动测试验证

## 2026-04-10 08:32
- 操作类型：修复
- 影响文件：`ui/interfaces/slice_interface.py`
- 变更摘要：删除了在 `ExpandLayout` 上调用的 `addStretch(1)` 方法。
- 原因：修复程序启动时抛出 `AttributeError: 'ExpandLayout' object has no attribute 'addStretch'` 的奔溃错误。`qfluentwidgets.ExpandLayout` 是一个自定义的布局类，内部通过 `addWidget` 和重写布局逻辑来消除抖动，但它并没有继承/实现原生 `QVBoxLayout` 的 `addStretch` 方法。外层的 `right_layout` (是 `QVBoxLayout`) 已经保留了 `addStretch(1)`，可以起到将其推向顶部的作用，内部不再需要。
- 测试状态：待手动测试验证

## 2026-04-10 08:29
- 操作类型：重构
- 影响文件：`ui/interfaces/slice_interface.py`、`ui/components/plot_control_card.py`、`ui/components/__init__.py`、`ui/components/jitter_free_container.py` (删除)
- 变更摘要：
  1. 移除了之前引入的 `JitterFreeCardGroup` 包装器类及其关联文件。
  2. 在 `slice_interface.py` 中，将右侧包裹所有业务面板组件的主卡片 (`right_panel_card`) 的内部布局，从普通的 `QVBoxLayout` 直接替换为了 `qfluentwidgets.ExpandLayout`。
  3. 在 `plot_control_card.py` 中，移除了原有的卡片组包装，直接将 `PlotControlCard` 的布局设为 `ExpandLayout`，并将绘图和重绘选项卡加入其中。
- 原因：根据进一步优化思路，既然 `ExpandLayout` 是消除折叠/展开时重绘抖动的核心机制，那么直接将其应用在产生抖动的最外层/局部容器上即可，无需再套一层带有组标题的 `SettingCardGroup` （即便隐藏了标题）。这不仅消除了抖动，还使得布局层级更加扁平和清晰。
- 测试状态：待手动测试验证

## 2026-04-09 17:36
- 操作类型：重构与修复
- 影响文件：`ui/components/jitter_free_container.py`、`ui/components/__init__.py`、`ui/components/plot_control_card.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：
  1. 深入调研 `qfluentwidgets` 中消除 `ExpandGroupSettingCard` 展开抖动的机制，提取并封装了一个专用的 `JitterFreeCardGroup` 无抖动容器（继承自 `SettingCardGroup`）。该容器隐藏了原生的组标题，并移除了内部硬编码产生的 46px（包含 spacing）额外高度占位。
  2. 在 `plot_control_card.py` 中，将用户临时使用的 `SettingCardGroup` 替换为新创建的 `JitterFreeCardGroup`，从而既消除了展开抖动，又清除了多余的组标题空白占位。
  3. 在 `slice_interface.py` 中，将右侧面板底部的导出路径设置卡（`ExportOptionCard`）也包裹在 `JitterFreeCardGroup` 内，以彻底解决其在全局 `QVBoxLayout` 中展开和折叠时的视觉抖动问题。
- 原因：修复由于在带有 `addStretch` 的 `QVBoxLayout` 内直接嵌套多个折叠卡片带来的重绘抖动问题。通过专用容器屏蔽默认标题，实现了干净的布局包裹。
- 测试状态：已测试

## 2026-04-09 16:48
- 操作类型：修复
- 影响文件：`ui/components/export_option_card.py`
- 变更摘要：
  1. 修复了修改导出路径时抛出 `AttributeError: 'ExportOptionCard' object has no attribute 'setContent'` 的问题，将 `self.setContent(new_path)` 修改为正确的 `self.card.setContent(new_path)`（调用内部的 `HeaderSettingCard` 的方法）。
  2. 修复了自动保存状态标签位置错位的问题，将标签从展开区域的 `self.viewLayout` 移动到主卡片头部的 `self.card.hBoxLayout` 中。
  3. 修复了拨动自动保存开关时全局配置不生效的问题，将直接对 `value` 赋值修改为使用 `qfluentwidgets.qconfig.set(appConfig.autoExport, is_checked)` 以正确触发配置持久化和信号同步。对路径保存配置也进行了同等修复。
- 原因：修复新编写的 `ExpandGroupSettingCard` 派生类内部对第三方组件库结构调用不当以及配置管理 API 误用导致的三个 Bug，确保功能正常运行。
- 测试状态：待手动测试验证

## 2026-04-09 16:27
- 操作类型：重构
- 影响文件：`ui/components/export_option_card.py`
- 变更摘要：修复了 `ExpandGroupSettingCard` 内部子项添加方式的问题。将直接调用 `addGroupWidget` 添加 `SwitchSettingCard` 的做法，重构为使用 `addGroup` 方法结合原生的 `SwitchButton`，从而使得内部展开列表符合标准的折叠卡片UI规范（左侧图标和描述，右侧是控制组件）。
- 原因：`ExpandGroupSettingCard` 作为容器，其内部展开项应该通过自带的 `addGroup` 方法来组装包含图标、标题、内容描述以及原生交互控件的组合行，而不是简单粗暴地将另一个完整的卡片组件（如 `SwitchSettingCard`）直接塞进去，否则会导致UI层级和视觉效果上的错乱。
- 测试状态：待手动测试验证

---

## 2026-04-09 16:20
- 操作类型：重构
- 影响文件：`ui/components/export_option_widget.py`、`ui/components/__init__.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：
  1. 新建 `ui/components/export_option_widget.py`，将刚才编写在 `slice_interface.py` 中的“保存选项”（`ExpandGroupSettingCard`）及其子控件（更改路径按钮、自动保存开关、动态状态标签）和所有相关的配置绑定槽函数逻辑（如选择文件夹对话框等）全部迁移封装进这个独立的类中。
  2. 在 `ui/components/__init__.py` 中对外暴露了 `ExportOptionWidget`。
  3. 在 `slice_interface.py` 中清理了所有的旧代码，直接实例化调用 `ExportOptionWidget`，进一步精简了页面层代码，使其更加专注于布局结构。
- 原因：根据用户要求，为了保持代码整洁和组件化规范，将功能内聚且带有自身交互逻辑的卡片抽取为独立组件。
- 测试状态：待手动测试验证

---

## 2026-04-09 16:15
- 操作类型：重构与修改
- 影响文件：`app/custom_icon.py`、`app/app_config.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：
  1. 重构了 `custom_icon.py` 的路径获取方式，不再使用 `os.path` 拼凑本地文件系统路径，而是改为直接通过 Qt QRC 资源系统读取（例如 `:/RadarIdentifySystem/images/icons/...`）。
  2. 在 `app_config.py` 中新增 `autoExport` 布尔类型配置项（默认 `False`），用于管理业务控制模块中的“自动保存”选项状态。
  3. 修改了 `slice_interface.py` 中的导出路径设置卡，将其从单一的 `PushSettingCard` 升级为 `ExpandGroupSettingCard`（标题为“保存选项”）。
     - 主卡片：使用 `content` 显示当前路径，并在最右侧（通过动态操作 `viewLayout`）插入了一个 `QLabel` 显示“已启用自动保存”或“未启用自动保存”的状态文字。
     - 展开组项 1：添加了一个“选择文件夹”的普通 `PushButton`（点击依然会调起文件选择器并更新配置）。
     - 展开组项 2：添加了一个“自动保存”的 `SwitchSettingCard`（绑定至 `autoExport` 全局配置）。
     - 通过绑定 `autoExport` 配置的 `valueChanged` 信号，使得自动保存状态文本能够随着开关操作实时同步。
- 原因：根据用户指示，为了打包和跨平台运行的稳定性应使用已建立好的 `.qrc` 资源；同时为了丰富业务保存选项，将“选择路径”和“自动保存开关”收纳整合在一个统一的折叠卡片中。
- 测试状态：待手动测试验证

---

## 2026-04-09 15:42
- 操作类型：新增与修改
- 影响文件：`app/custom_icon.py`、`ui/components/action_button_widget.py`、`ui/components/navigation_control_card.py`
- 变更摘要：
  1. 新建 `app/custom_icon.py`，实现 `CustomIcon` 类继承自 `FluentIconBase`，通过重写 `path(self, theme)` 方法实现 SVG 图标针对深浅模式（`black/white`）的自动切换。
  2. 在 `ui/components/action_button_widget.py` 中增加对 `FluentIconBase` 的类型兼容支持（`icon: FluentIconBase | FluentIcon`）。
  3. 在 `ui/components/navigation_control_card.py` 中将上/下一类、上/下一片的图标替换为了自定义的 `CustomIcon.CHEVRONS_LEFT/RIGHT` 以及 `CustomIcon.CHEVRON_LEFT/RIGHT`。
- 原因：根据用户需求，将导航控制卡片内的方向箭头替换为指定目录（`resources/images/icons`）下的自定义 SVG 图标，同时兼容 `qfluentwidgets` 的深浅色主题自动切换规范。
- 测试状态：待手动测试验证

---

## 2026-04-09 12:30
- 操作类型：修复
- 影响文件：`resources/qss/light/slice_interface.qss`、`resources/qss/dark/slice_interface.qss`
- 变更摘要：提取了 `qfluentwidgets` 组件库底层 `SimpleCardWidget` 的原生硬编码颜色值，并在 QSS 中对 `#actionButtonCard` 进行了精确的替换。
  - **浅色模式**：背景色调整为 `rgba(255, 255, 255, 170)`，边框统一调整为 `1px solid rgba(0, 0, 0, 12)`。
  - **深色模式**：背景色调整为 `rgba(255, 255, 255, 13)`，边框统一调整为 `1px solid rgba(0, 0, 0, 48)`。
- 原因：之前通过肉眼估算的边框及背景色 rgba 参数不够精确，导致用户感知悬浮按钮的边框依然比设置卡的细且浅。通过检索第三方库源码（`card_widget.py`），获取了最精确的 0-255 色彩数值。
- 测试状态：待手动测试验证

---

## 2026-04-09 12:20
- 操作类型：修改
- 影响文件：`ui/components/action_button_widget.py`、`resources/qss/light/slice_interface.qss`、`resources/qss/dark/slice_interface.qss`
- 变更摘要：
  1. 将 `ActionButtonCard` 的父类从普通的 `CardWidget` 更改为了 `SimpleCardWidget`，这与 `SettingCard`（底层也是 `SimpleCardWidget`）的组件家族渊源更加贴近。
  2. 在 `ActionButtonCard` 中重写了 `paintEvent`，屏蔽了父类的默认绘制（防止其默认的边框影响我们的自定义样式）。
  3. 在 `light` 和 `dark` 两个主题的 QSS 样式表中，补充了对 `#actionButtonCard`（普通状态悬浮按钮）的详细颜色定义，包含其 `background-color`、`border` 以及 `hover/pressed` 交互状态，确保了它的边框颜色深浅与粗细与同页面的设置卡（`SettingCard`）完全一致。
- 原因：用户反馈操作按钮组件的边框颜色比设置卡（`SettingCard`）更浅且更细。原有的 `CardWidget` 对边框和背景的硬编码导致外观与组件库标准设置卡不完全同步，通过统一继承基类并用统一的 QSS 参数管理予以解决。
- 测试状态：待手动测试验证

---

## 2026-04-09 12:00
- 操作类型：修复
- 影响文件：`ui/components/action_button_widget.py`
- 变更摘要：在 `PrimaryActionButtonCard` 中覆盖了继承自组件库 `CardWidget` 的 `paintEvent` 方法。使用 `QStyleOption` 配合原生 `drawPrimitive` 进行背景的纯净渲染。
- 原因：用户反馈“主题色按钮仿佛盖了一层蒙版”。经过排查，`qfluentwidgets` 提供的 `CardWidget` 在底层的 `paintEvent` 中会默认硬编码绘制一层半透明的背景和边框，导致我们在 QSS 中设置的背景色与底层原生的半透明背景色进行了混合（叠加），看起来就像盖了一层灰色的蒙版。覆盖 `paintEvent` 阻断了底层默认行为，使得颜色直接受 QSS 控制，恢复了纯正的主题色。
- 测试状态：待手动测试验证

---

## 2026-04-09 11:57
- 操作类型：新增与修改
- 影响文件：`ui/components/action_button_widget.py`、`resources/qss/light/slice_interface.qss`、`resources/qss/dark/slice_interface.qss`、`ui/components/main_action_card.py`
- 变更摘要：
  1. 丰富了 `action_button_widget.py` 组件库，基于现有的 `ActionButtonCard` 派生了主题色的按钮组件 `PrimaryActionButtonCard`。
  2. 覆写了 `ActionButtonCard` 的 `enterEvent`、`leaveEvent`、`mousePressEvent` 和 `mouseReleaseEvent`，引入并管理了 `isHover` 和 `isPressed` 属性，用于触发 QSS 的动态样式刷新（`style().polish(self)`）。
  3. 考虑到深浅色主题适配，在 `PrimaryActionButtonCard` 中监听了 `qconfig.themeChanged` 信号，在浅色模式下应用白色图标（保证对比深色主色背景），在深色模式下应用黑色图标（保证对比浅色主色背景）。
  4. 在深浅两套 `slice_interface.qss` 样式表文件中统一添加了对 `#primaryActionButtonCard` 的悬浮、点击等状态定义（颜色取自 `--ThemeColorPrimary`、`--ThemeColorLight1` 等变量）。
  5. 将 `main_action_card.py` 中原本普通的“开始识别”按钮（`ActionButtonCard`）替换为新的 `PrimaryActionButtonCard`。
- 原因：根据用户需求提供高亮的主题色悬浮操作按钮组件。由于原生 `qfluentwidgets` 的 `CardWidget` 对于 QSS 伪状态（如 `:hover`）的支持存在局限性或被硬编码覆盖，故采用了结合动态属性和手动抛光（`polish`）的方式重构以完美贴合 QSS 管理机制。
- 测试状态：待手动测试验证

---

## 2026-04-09 11:35
- 操作类型：重构
- 影响文件：`ui/components/action_button_widget.py`
- 变更摘要：移除了 `ActionButtonCard` 中的自定义 `clicked` 信号定义以及对 `mouseReleaseEvent` 的重写逻辑。
- 原因：排查发现 `qfluentwidgets` 提供的基础组件 `CardWidget` 本身已经内置并暴露了 `clicked` 信号，之前子类中自行定义和触发信号属于重复实现，不仅多余，还导致了由于双重触发引发的“警告弹窗出现两次”的 bug。
- 测试状态：待手动测试验证

---

## 2026-04-09 11:31
- 操作类型：修改
- 影响文件：`ui/components/action_button_widget.py`
- 变更摘要：修复了 `ActionButtonCard` 组件中 `mouseReleaseEvent` 触发两次或非预期点击信号的问题，通过增加 `if e.button() == Qt.MouseButton.LeftButton:` 的条件判断，确保只有在鼠标左键松开时才发射 `clicked` 信号。
- 原因：排查发现开始切片按钮的警告触发两次并非由于控制器重复绑定了信号，而是由于自定义的悬浮按钮卡片（`ActionButtonCard` 继承自 `CardWidget`）在重写 `mouseReleaseEvent` 时没有限制鼠标按键类型。这导致鼠标操作（例如右键或释放过程中的多次事件捕获）被无差别地当做点击事件广播，从而触发了两次逻辑。
- 测试状态：待手动测试验证

---

## 2026-04-09 11:22
- 操作类型：重构
- 影响文件：`ui/components/main_action_widget.py`、`ui/controllers/slice_controller.py`
- 变更摘要：
  1. 重构了主操作组件（`main_action_widget.py`），使用之前抽离的自定义悬浮按钮 `ActionButtonCard` 替换了原有的普通按钮和带下拉菜单的拆分按钮（`PrimarySplitPushButton` 和 `PrimaryPushButton`）。
  2. 取消了按钮内的下拉菜单选项，将“自适应切片”功能独立出来，使用组件库自带的 `CheckBox` 复选框添加到按钮下方的布局中。
  3. 修改了 `slice_controller.py` 的处理逻辑，现在不再通过按钮的文本获取切片模式，而是直接读取新增复选框 `adaptive_slicing_checkbox` 的选中状态，并对相关绑定的变量名进行了调整以匹配更新后的控件树。
- 原因：根据用户需求，使主操作区的按钮风格与导航控制区的悬浮卡片按钮保持一致，并通过独立的复选框让自适应切片功能的启用状态更加直观。
- 测试状态：待手动测试验证

---

## 2026-04-09 10:16
- 操作类型：重构
- 影响文件：`ui/interfaces/slice_interface.py`、`ui/components/main_action_widget.py`、`ui/components/navigation_control_widget.py`、`ui/components/plot_control_widget.py`、`ui/components/__init__.py`、`ui/controllers/slice_controller.py`
- 变更摘要：
  1. 取消了右侧操作面板各个独立组件（主操作组件、导航控制组件、绘图控制组件）的 `SimpleCardWidget` 继承，将它们重构为普通的 `QWidget`。
  2. 对这些组件所属的文件进行了重命名（将 `_card` 后缀改为 `_widget`），并更新了 `__init__.py` 的导出声明。
  3. 在 `slice_interface.py` 的右侧面板中，引入了一个整体的 `SimpleCardWidget`（变量名：`right_panel_card`），用它统一包裹了导入按钮、切片信息、主操作组件、导航组件、绘图组件以及导出路径设置卡片。
  4. 同步更新了控制器 `slice_controller.py` 中引用的组件实例属性名称。
- 原因：根据用户要求，为了在视觉上提供更好的卡片层级和统一的区域感，不再让每个小组件各自拥有卡片背景，而是使用一个大卡片包裹右侧所有操作项。
- 测试状态：待手动测试验证

---

## 2026-04-09 09:59
- 操作类型：新增
- 影响文件：`app/app_config.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：
  1. 在全局配置 `app_config.py` 中新增 `exportDirPath` 配置项，默认路径为用户的桌面目录，用于持久化管理导出的保存路径。
  2. 在 `slice_interface.py` 右侧面板中新增了基于 `PushSettingCard` 的“保存/导出路径”设置卡片。
  3. 为该设置卡添加了选择文件夹的功能：点击按钮弹出 `QFileDialog.getExistingDirectory` 对话框，并双向绑定了全局配置项，使得选中路径可以自动展示并持久化存储。
- 原因：根据用户需求补充保存路径设置入口，使用标准组件维持应用风格一致，且统一接入全局配置以支持跨组件、跨生命周期的状态管理。
- 测试状态：待手动测试验证

---

## 2026-04-09 09:51
- 操作类型：修改
- 影响文件：`ui/components/redraw_option_card.py`
- 变更摘要：将重绘选项卡（`RedrawOptionCard`）的父类从 `SimpleCardWidget` 重构为 `SettingCard`，调整为 `qfluentwidgets` 设置卡组件的通用样式（带有图标、标题和描述描述），并将输入框和重绘按钮添加到右侧 `hBoxLayout` 中。
- 原因：根据用户需求，使界面样式与应用内的其他设置卡（如自动识别选项等）保持视觉上的一致性。
- 测试状态：待手动测试验证

---

## 2026-04-08 17:28
- 操作类型：新增与修改
- 影响文件：`ui/components/redraw_option_card.py`、`ui/components/plot_control_card.py`、`ui/components/__init__.py`
- 变更摘要：
  1. 新增 `RedrawOptionCard`（重绘选项卡），包含指定切片编号的整数输入框（`LineEdit` + `QIntValidator`，约束为≥1）和主题色的“重绘”按钮，支持对外发射带切片编号的 `redraw_requested` 信号。
  2. 修改 `plot_control_card.py` 布局：修复并更新了内部类的导入（如相对导入 `PlotOptionCard`）和类文档注释，将 `RedrawOptionCard` 实例化并添加进卡片的垂直布局容器中。
  3. 更新 `ui/components/__init__.py`，暴露 `RedrawOptionCard` 供外部使用。
- 原因：根据最新规划补充重绘功能，方便通过编号直接回溯或重绘画布图像，进一步完善界面右侧控制面板的操作覆盖范围，并且使用组件化嵌套保持卡片结构整洁。
- 测试状态：待手动测试验证

---

## 2026-04-08 16:57
- 操作类型：新增与重构
- 影响文件：`app/app_config.py`、`ui/components/plot_control_card.py`、`ui/components/__init__.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：
  1. 在全局配置 `app_config.py` 中新增 `plotOnlyShowIdentified` 和 `plotScaleMode` 配置项（属于 `business` 组），用于持久化管理绘图参数。
  2. 新增 `PlotControlCard` 组件，使用 `ExpandGroupSettingCard` 包裹两个带下拉框设置的子卡片（图像展示模式、图像绘制模式）。
  3. 将该组件注册导出并在 `slice_interface.py` 的右侧面板中应用。
  4. 实现配置项与下拉框双向同步（`currentIndexChanged` 绑定 `QConfig` 写入，`valueChanged` 绑定下拉框索引更新）。
- 原因：根据用户需求，提供可视化的绘图参数控制界面，同时结合全局配置系统实现状态持久化与解耦，完善 Fluent Design 界面体验。
- 测试状态：待手动测试验证

---

## 2026-04-08 16:12
- 操作类型：重构
- 影响文件：`app/app_config.py`、`ui/components/navigation_control_card.py`、`ui/controllers/slice_controller.py`
- 变更摘要：
  1. 在全局配置 `app_config.py` 中新增 `autoRecognizeNextSlice` 配置项（属于 `business` 组），用于持久化管理业务逻辑。
  2. 重构了 `navigation_control_card.py`：将四个导航按钮替换为自定义的 `NavButtonCard`（继承自 `ElevatedCardWidget`），使其成为可悬浮交互的正方形按钮并居中排列在第一行；将原本的复选框替换为 `SwitchSettingCard`（开关设置卡），绑定了全局配置项，占据第二行。
  3. 修改了 `slice_controller.py`，从直接读取 UI 复选框状态改为读取 `appConfig.autoRecognizeNextSlice.value`。
- 原因：提升界面的精致度，利用 `ElevatedCardWidget` 增加按钮的立体悬浮感；利用 `SwitchSettingCard` 提供更直观的配置说明和开关体验；配置与 UI 解耦，使“自动识别”状态可以持久化保存。
- 测试状态：待手动测试验证

---

## 2026-04-08 11:09
- 操作类型：修改
- 影响文件：`ui/components/navigation_control_card.py`、`ui/interfaces/slice_interface.py`
- 变更摘要：
  1. 重构了导航控制卡片布局：将“上一类”、“下一类”、“上一片”、“下一片”导航按钮合并到同一行，并将“自动识别”复选框移动到下方；为四个导航按钮添加了对应的 `FluentIcon` (左右箭头和左右实心三角)。
  2. 修改了 `slice_interface.py` 中右侧面板的布局约束，添加了 `setMaximumWidth(400)` 以防止卡片被拉伸得过宽。
  3. 将“重置切片”按钮从导航卡片中提取出来，改为主题色按钮 `PrimaryPushButton` 并命名为“重置当前切片”，放置在右侧面板布局的最底部且靠右对齐。
- 原因：优化 UI 布局和视觉表现，解决组件在全屏下被拉伸失真的问题。同时将重置操作突出显示并分离出高频的导航操作区域，防止误触。
- 测试状态：待手动测试验证

---

## 2026-04-08 10:04
- 操作类型：重构
- 影响文件：`ui/components/main_action_card.py` (新增)、`ui/components/navigation_control_card.py` (新增)、`ui/components/slice_proc_card.py` (删除)、`ui/components/recognition_proc_card.py` (删除)、`ui/interfaces/slice_interface.py`、`ui/controllers/slice_controller.py`、`ui/components/__init__.py`
- 变更摘要：根据用户要求重构了右侧操作面板的卡片布局和命名。将原有的切片和识别卡片重组为“主操作卡片（MainActionCard）”和“导航控制卡片（NavigationControlCard）”。“主操作卡片”现在包含“开始切片”和“开始识别”按钮；“导航控制卡片”包含自动识别复选框以及所有的切片与类别切换导航按钮。
- 原因：原有的按“切片”和“识别”阶段划分卡片的方式在视觉和操作逻辑上不够紧凑，重新划分为“主操作（触发计算）”和“导航（切换查看数据）”两部分，更符合用户在测试验证时的心智模型和操作连贯性。
- 测试状态：待手动测试验证

---

## 2026-04-08 09:46
- 操作类型：修改
- 影响文件：`ui/components/slice_proc_card.py`、`ui/controllers/slice_controller.py`
- 变更摘要：将切片操作卡片中的普通 `PrimaryPushButton` 替换为 `PrimarySplitPushButton`。为拆分按钮添加了“开始切片”与“自适应切片”两个下拉选项菜单。在控制器中适配了拆分按钮的事件逻辑，使其根据当前按钮显示的文本状态来决定执行何种模式。
- 原因：支持多模式操作入口，让界面交互更为丰富和灵活，符合 Fluent Design 组件库的高级用法设计。
- 测试状态：待手动测试验证

---

## 2026-04-07 17:33
- 操作类型：修改
- 影响文件：`ui/dialogs/processing_dialog.py`
- 变更摘要：将阻塞式处理动画对话框 `ProcessingDialog` 中的 `IndeterminateProgressBar`（不确定进度条）替换为 `IndeterminateProgressRing`（不确定进度环）。重新设计了内部布局，使进度环与文字（标题与详情）呈现更美观的水平居中排列。
- 原因：进度环在视觉上比横向进度条更加紧凑和现代化，更符合 Fluent Design 的全局加载动画规范，提升整体美观度。
- 测试状态：待手动测试验证

---

## 2026-04-07 17:10
- 操作类型：新增与重构
- 影响文件：`ui/components/recognition_proc_card.py`、`ui/components/__init__.py`、`ui/dialogs/processing_dialog.py`、`ui/interfaces/slice_interface.py`、`ui/controllers/slice_controller.py`、`ui/controllers/import_controller.py`
- 变更摘要：
  1. 新增 `RecognitionProcCard` 识别处理卡片，包含主题色识别按钮、类别导航、切片导航、重置及自动识别复选框。
  2. 新增全局阻塞式动画对话框 `ProcessingDialog`，集成不确定进度条。
  3. 将新组件应用到切片右侧操作面板。
  4. 修改了导入和切片工作流控制器，在发起工作流时弹启动画遮罩，结束时关闭。
- 原因：丰富切片阶段所需的操作区界面以供后续接入识别算法；通过统一的阻塞式对话框增强长耗时任务（导入、切片）期间的用户体验，防止错误连点。
- 测试状态：待手动测试验证

---

## 2026-04-07 16:14
- 操作类型：重构
- 影响文件：`ui/controllers/slice_controller.py`、`ui/controllers/import_controller.py`
- 变更摘要：移除了代码中原本通过修改按钮文本或使用原生 `QMessageBox` 来作为用户交互提示的做法，全面统一替换为使用 `qfluentwidgets.InfoBar`。包括数据导入的成功与失败提示、切片执行的前置拦截提示与成功提示。
- 原因：提升系统界面的视觉一致性与交互体验，遵循全局的交互规范。该规范已被写入核心记忆。
- 测试状态：待手动测试验证

---

## 2026-04-07 16:08
- 操作类型：重构
- 影响文件：`ui/components/slice_slice_proc_card.py`、`ui/interfaces/slice_interface.py`、`ui/controllers/import_controller.py`、`ui/controllers/slice_controller.py`
- 变更摘要：根据最新的 UI 控件命名规范（业务词组_组件类型），将代码中不符合规范的简写组件名进行了全局替换。例如 `btn_slice` 变更为 `start_slicing_button`，`chk_adaptive` 变更为 `adaptive_slicing_checkbox`，`btn_import` 变更为 `import_data_button`。
- 原因：保持项目中变量命名的语义化和一致性，提升代码可读性。并将此命名规则写入了智能体的核心记忆中，以便后续生成代码时严格遵守。
- 测试状态：无需测试

---

## 2026-04-07 15:40
- 操作类型：新增与重构
- 影响文件：`ui/components/slice_slice_proc_card.py`、`ui/components/__init__.py`、`ui/interfaces/slice_interface.py`、`ui/controllers/slice_controller.py`
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
