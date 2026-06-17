# Slice 参数面板 UI 重构设计

## 目标

将切片页面参数抽屉的内容布局从 `SliceInterface` 中拆出为独立的 `SliceParamPanel`，恢复文字导航按钮，并把自动识别、模型选择、导出路径三类卡片集中到参数面板中。

本次只为未来“一份文件对应一个 Session、一个 SliceInterface、一个 SliceController 和一份子配置”建立 UI 边界，不实现 Session 子配置复制和识别工作流的模型注入。

## 组件边界

### SliceParamPanel

`SliceParamPanel` 是普通 `QWidget`，只负责抽屉内容区的卡片创建与纵向布局，不继承也不包装 `SlidingDrawer`。

公开属性包括：

- `auto_recognize_card`：从 `NavigationControlCard` 迁入的自动识别卡。
- `model_selection_card`：PA、DTOA 模型选择卡。
- `export_path_card`：从 `SliceInterface` 右侧常驻卡片组迁入的导出路径卡。

`SliceInterface` 继续创建 `SlidingDrawer`，实例名为 `slice_param_drawer`；抽屉内容实例名为 `slice_param_panel`，通过 `setContentWidget()` 组合。

### ModelSelectionCard

模型选择卡使用与 `PlotOptionCard` 相同的 `ExpandGroupSettingCard` 结构，包含 PA 和 DTOA 两个下拉框。

- 可选项来自现有内置模型目录和用户模型目录。
- 展示名复用现有模型注册表规则。
- 初始选择复制全局配置中当前启用的 PA、DTOA 模型。
- 用户切换后只更新当前卡片实例内保存的路径，并发出变更信号。
- 不调用 `set_enabled_model_path()`，不写入全局配置，也不接入识别工作流。
- 没有可用模型时显示空状态且不产生虚假路径。

未来 Session 子配置结构落地后，由 `SliceController` 读取面板状态或连接变更信号，将选择写入对应 Session。

## 导航按钮与信号

`NavigationControlCard` 恢复“上一片、下一片、上一类、下一类”四个文字按钮，同时保留标题旁现有图形按钮。

- 两个“上一片”入口共同连接 `SliceController._on_prev_slice()`。
- 两个“下一片”入口共同连接 `SliceController._on_next_slice()`。
- 两个“上一类”入口共同连接 `IdentifyController` 现有上一类槽函数。
- 两个“下一类”入口共同连接 `IdentifyController` 现有下一类槽函数。

不增加中转信号或重复槽函数。

## 配置兼容边界

本次只迁移自动识别卡和导出路径卡的位置，暂时保留它们现有的全局配置读写行为。模型选择卡必须保持实例局部状态，避免提前污染全局模型选择。

后续建立 Session 子配置时，再把自动识别、导出设置和未来参数卡统一切换到子配置，避免本次同时改动配置体系和识别流程。

## 文件变更

- 新建 `RadarIdentifySystem_PyQt6/ui/components/slice_param_panel.py`。
- 新建 `RadarIdentifySystem_PyQt6/ui/components/model_selection_card.py`。
- 修改 `RadarIdentifySystem_PyQt6/ui/components/__init__.py` 导出新组件。
- 修改 `RadarIdentifySystem_PyQt6/ui/components/navigation_control_card.py`。
- 修改 `RadarIdentifySystem_PyQt6/ui/interfaces/slice_interface.py`。
- 修改 `RadarIdentifySystem_PyQt6/ui/controllers/slice_controller.py`。
- 修改 `RadarIdentifySystem_PyQt6/ui/controllers/identify_controller.py`。
- 增补 `RadarIdentifySystem_PyQt6/tests/unit/` 下的定向回归测试。
- 更新 `docs/operateLog.md`。

## 测试策略

采用测试先行：

1. 锁定 `SliceParamPanel` 的卡片归属和抽屉组合关系。
2. 锁定模型选择只改变组件实例状态，不修改全局启用路径。
3. 锁定抽屉与右栏宽度一致，并移除旧名称 `slice_param_config`。
4. 锁定文字按钮存在，并与图形按钮连接相同槽函数。
5. 运行定向单元测试、相关既有测试和 Python 语法编译检查。

若 Qt 运行态受环境限制，必须明确区分已完成的语法级验证与未完成的运行态验证。
