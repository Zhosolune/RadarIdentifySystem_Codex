# 操作日志

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
