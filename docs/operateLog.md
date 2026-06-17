# 操作记录

## 2026-06-16 00:00
- 操作类型：[修改]
- 影响文件：
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\components\import_dashboard_panel.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\interfaces\home_interface.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\controllers\home_controller.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\resources\qss\light\home_interface.qss
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\resources\qss\dark\home_interface.qss
- 变更摘要：准备将解析前仪表盘默认指标卡替换为懒加载骨架占位，并将指标卡改为最多 5 列均分宽度。
- 原因：解析数据之前不应显示默认仪表盘卡片；固定卡片宽度不利于流式布局适配。
- 计划：
  - [x] 检查当前仪表盘面板、主页默认数据入口和组件库流式布局能力。
  - [x] 增加仪表盘骨架占位控件，默认显示占位而非指标卡。
  - [x] 使用自适应流式布局让指标卡每行最多 5 张并均分可用宽度。
  - [x] 移除主页启动时的默认仪表盘数据注入。
  - [x] 补充浅色/深色主题骨架样式。
  - [x] 运行语法级校验。
- 已完成内容：已确认仪表盘展示逻辑位于 import_dashboard_panel.py；已移除 home_interface.py 中的默认占位指标注入；已在解析开始时清空旧仪表盘并回到骨架占位；已补充浅色/深色骨架样式。
- 待完成内容：因当前环境缺少 PyQt6，Qt 运行态冒烟未完成。
- 测试状态：[已测试] 2026-06-16 16:29 已运行 python -m py_compile；导入冒烟因 ModuleNotFoundError: No module named 'PyQt6' 未完成。

## 2026-06-16 16:38
- 操作类型：[修改]
- 影响文件：
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\components\import_dashboard_panel.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\interfaces\home_interface.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\resources\qss\light\home_interface.qss
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\resources\qss\dark\home_interface.qss
- 变更摘要：准备调浅仪表盘骨架颜色，并修复首页右侧面板中文件列表与仪表盘重叠问题。
- 原因：骨架灰度过深；当前固定高度组合可能导致纵向空间不足时内容互相挤压。
- 计划：
  - [x] 排查仪表盘、文件列表、数据目录卡在主页中的高度约束。
  - [x] 调浅浅色和深色主题骨架颜色。
  - [x] 增加仪表盘高度，避免骨架或指标布局被压缩。
  - [x] 修改文件列表卡片高度策略，使其在滚动内容中撑满剩余空间。
  - [x] 确认数据目录设置卡不被强行拉伸或挤压。
  - [x] 运行语法级校验。
- 已完成内容：已将骨架色改为 0.12 透明度；已将仪表盘固定高度从 245 提高到 300；已将文件列表从固定 420 改为最小 320 + 纵向 Expanding；已让数据目录卡组保持 Fixed 高度；已让骨架条在窄容器中按可用宽度收缩。
- 待完成内容：因当前环境缺少 PyQt6，Qt 运行态冒烟和截图验证未完成。
- 测试状态：[已测试] 已运行 python -m py_compile 覆盖 import_dashboard_panel.py、home_interface.py、home_controller.py。

## 2026-06-16 16:48
- 操作类型：[修改]
- 影响文件：
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\components\import_dashboard_panel.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\docs\operateLog.md
- 变更摘要：准备把仪表盘骨架从卡片外层移回 EdgeTabWidget 的占位标签页内容区。
- 原因：骨架屏必须处于标签页内容区内，初始态也应有一个空标题占位标签页，而不是绕过标签页结构直接放在卡片里。
- 计划：
  - [x] 保留用户已调整的骨架尺寸和颜色。
  - [x] 移除 ImportDashboardPanel 中的外层 QStackedLayout 包裹。
  - [x] 增加空标题占位标签页创建逻辑。
  - [x] 确保 clear_dashboard_pages() 回到占位标签页，set_dashboard_pages() 只在有真实数据时创建真实标签页。
  - [x] 运行语法级校验。
- 已完成内容：已确认 EdgeTabWidget.clearTabs() 会删除页面；已改为每次重新创建 DashboardSkeletonWidget，并通过空标题、固定 routeKey 的占位 tab 加入 EdgeTabWidget。
- 待完成内容：因当前环境缺少 PyQt6，Qt 运行态冒烟和截图验证未完成。
- 测试状态：[已测试] 已运行 python -m py_compile 覆盖 import_dashboard_panel.py、home_interface.py、home_controller.py。

## 2026-06-17 设计阶段
- 操作类型：[重构]
- 影响文件：
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\docs\superpowers\specs\2026-06-17-slice-param-panel-design.md
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\docs\operateLog.md
- 变更摘要：设计将切片参数抽屉内容拆分为独立 `SliceParamPanel`，恢复文字导航按钮，并规划迁移自动识别、模型选择和导出路径卡片。
- 原因：减少 `SliceInterface` 内部 UI 堆叠，为未来每个 Session 独立子配置和模型选择建立清晰组件边界。
- 计划：
  - [x] 核对现有抽屉、导航按钮、控制器槽函数和模型管理接口。
  - [x] 明确模型选择仅保存在当前面板实例，不修改全局配置。
  - [x] 确认 `SliceParamPanel` 使用普通 `QWidget`，不继承 `SlidingDrawer`。
  - [x] 编写并自检设计文档。
  - [x] 编写测试先行的实施计划。
  - [ ] 分阶段完成生产代码和回归测试。
- 已完成内容：已确定 `slice_param_drawer` 与 `slice_param_panel` 的组合结构，以及模型选择卡的 Session 作用域边界；已将实施拆分为模型卡、参数面板、抽屉迁移、导航连接和最终验证五个 TDD 任务。
- 待完成内容：失败测试、最小实现和运行验证。
- 环境准备：已在 `D:\Miniforge3\envs\pyqt6` 安装 `pytest 9.1.0`，用于执行本次 TDD。
- 基线测试：执行 `D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6/tests/unit -q`，在收集阶段发现 3 个既有错误：`cluster_single_slice` 导入失败、`core.data` 模块缺失、`AppSignalBus` 导入失败。
- 测试状态：[待测试] 完整基线被既有测试错误阻塞，尚未修改本次生产代码；等待确认是否以相关 UI 定向测试作为实施基线。

## 2026-06-17 15:42
- 操作类型：[重构]
- 影响文件：
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\components\model_selection_card.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\components\slice_param_panel.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\components\navigation_control_card.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\components\__init__.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\interfaces\slice_interface.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\controllers\slice_controller.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\ui\controllers\identify_controller.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\tests\unit\test_model_selection_card.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\tests\unit\test_slice_param_panel.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\tests\unit\test_slice_interface.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\RadarIdentifySystem_PyQt6\tests\unit\test_navigation_controls.py
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\docs\operateLog.md
- 变更摘要：抽离普通 `QWidget` 类型的 `SliceParamPanel`，迁入自动识别和导出路径卡，新增实例级 PA/DTOA 模型选择卡，并恢复切片与类别文字导航按钮。
- 原因：降低 `SliceInterface` 的抽屉内容布局职责，为未来每个 Session 独立子配置和模型选择建立 UI 基础，同时保留图形与文字两套导航入口。
- 计划：
  - [x] 先写模型选择卡失败测试并确认目标模块缺失。
  - [x] 实现只读取全局默认值、不回写全局配置的实例级模型选择卡。
  - [x] 先写参数面板失败测试，再抽离三类卡片布局。
  - [x] 先写抽屉组合失败测试，再改为 `slice_param_drawer + slice_param_panel` 组合。
  - [x] 先写双入口导航失败测试，再让文字按钮连接现有控制器槽函数。
  - [x] 完成语法编译、Qt 离屏实例化、相关单元测试和差异检查。
- 已完成内容：右栏和抽屉共同使用 `RIGHT_COLUMN_WIDTH = 630`；自动识别卡与导出路径卡已从常驻右栏迁入参数面板；模型选择结果只保存在 `ModelSelectionCard` 实例；四个文字导航按钮与标题区图形按钮共用现有槽函数。
- 待完成内容：本次需求无待实现项。完整测试目录仍有既有收集错误，抽屉视觉测试仍有 3 个既有阴影参数断言失败，均未在本次范围内修改。
- 测试状态：[已测试] 相关测试 17 项通过、3 项既有抽屉视觉测试跳过；`compileall` 通过；Qt 离屏实例化输出 `SliceParamPanel 630 630 False True`；完整单元测试目录因 `cluster_single_slice`、`core.data`、`AppSignalBus` 三个旧接口错误在收集阶段失败。

## 2026-06-17 抽屉布局防抖设计
- 操作类型：[重构]
- 影响文件：
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\docs\superpowers\specs\2026-06-17-slice-param-panel-jitter-layout-design.md
  - E:\myProjects_Trae\RadarIdentifySystem_Codex\docs\operateLog.md
- 变更摘要：设计将 `SliceParamPanel` 改为滚动区、简单卡片容器和 `JitterFreeCardGroup` 的嵌套结构，并增加左右 16px 内容边距。
- 原因：降低可展开卡片引发布局抖动的风险，并避免抽屉内容紧贴左右边缘。
- 计划：
  - [x] 对照右栏滚动区和无抖动卡片组结构。
  - [x] 明确滚动区、卡片容器和边距契约。
  - [ ] 编写失败测试并实施最小布局调整。
  - [ ] 运行相关回归和 Qt 离屏实例化。
- 已完成内容：已确定结构和边距，不修改抽屉动画与业务卡行为。
- 待完成内容：TDD 实现和验证。
- 测试状态：[无需测试] 当前仅新增设计记录。
