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
