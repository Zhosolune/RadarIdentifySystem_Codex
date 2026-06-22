# P10 UI 高级功能迁移（Fluent 组件与设置页）

## 目标
迁移配置窗口、模型管理和高级组件，优先采用 Fluent 原生组件替换自定义实现。

## 本阶段重点
1. 设置页使用 Fluent `SettingCard`。
2. 所有配置项绑定到 `app/app_config.py` 中的 `ConfigItem`。
3. 通知/提示统一到 `InfoBar` / Fluent 对话框。
4. 主题与界面偏好使用同一 `QConfig`。
5. 新增绘图配置分组页面，覆盖 `plot.dimension.*`、`plot.bandProfile.*`、`plot.mergePalette`。

## 本阶段新增/迁移文件
1. `ui/dialogs/config_dialog.py`
2. `ui/dialogs/model_import_dialog.py`
3. `ui/dialogs/model_manager_dialog.py`
4. `ui/dialogs/export_dialog.py`
5. `tests/ui/test_config_dialog.py`
6. `tests/ui/test_model_dialogs.py`

## 验收标准
1. 主题切换与主题色切换可用。
2. 算法参数在设置页可编辑并持久化。
3. 绘图参数在设置页可编辑、保存、重启恢复。
4. 不再存在第二套配置系统。
