# Slice 参数面板防抖滚动布局设计

## 目标

将 `SliceParamPanel` 的直接纵向布局改为与 `SliceInterface.right_panel_scroll_area` 一致的滚动卡片组织结构，使用 `JitterFreeCardGroup` 承载可展开设置卡，减少展开和折叠时的布局抖动，并为抽屉内容增加适当的水平留白。

## 结构

`SliceParamPanel` 保持普通 `QWidget`，内部结构调整为：

```text
SliceParamPanel
└─ ScrollArea
   └─ scroll_content_widget
      └─ SimpleCardWidget
         └─ JitterFreeCardGroup
            ├─ auto_recognize_card
            ├─ model_selection_card
            └─ export_path_card
```

三张业务卡的职责、顺序和配置行为不变。`SliceInterface` 仍只负责把 `SliceParamPanel` 安装到 `SlidingDrawer`，不接管面板内部布局。

## 边距

- 滚动内容区左右边距为 16px。
- 滚动内容区上边距为 8px，下边距为 16px。
- `SimpleCardWidget` 内部四周边距为 12px，与右栏控制卡容器一致。
- 卡片组不增加额外标题，卡片间距继续由 `JitterFreeCardGroup` 管理。

## 测试

- 先修改 `test_slice_param_panel.py`，断言面板包含可缩放滚动区、`SimpleCardWidget` 和 `JitterFreeCardGroup`。
- 断言滚动内容布局边距为左 16、上 8、右 16、下 16。
- 断言三张业务卡的父级均为 `JitterFreeCardGroup`，且原有模型局部状态测试和抽屉组合测试继续通过。
- 运行相关 UI 定向测试、`compileall` 和 Qt 离屏实例化。

## 范围限制

不修改 `SlidingDrawer` 动画、阴影、宽度或遮罩，不调整业务卡行为，不引入新的样式表文件。
