# Session 独立化设计

## 目标

实现完备的 session 独立化：文件解析完成后不再自动注入全局切片页，而是由用户点击“新建Session并导入”创建独立 session。每个 session 拥有独立的切片页面、控制器、参数子配置和模型选择，并支持 session 元数据与子配置持久化恢复。

本设计采用分阶段兼容迁移，避免一次性替换导入、配置、模型和 UI 生命周期导致主链路不可验证。

## 非目标

- 不持久化 `raw_batch`、`preprocess_result`、`slice_result`、`cluster_result`、`recognition_result` 等计算产物。
- 不实现识别结果保存、导出结果保存或数据库式结果存储系统。
- 不在本轮重做完整模型管理 UI，但为“软件级激活模型集合”预留接口。

## 阶段拆分

### 阶段一：Session 管理骨架

- 拆分解析完成与创建 session 页面两个事件语义。
- 新增 `runtime/session_registry.py`，维护运行态 session 索引、active session、注册、关闭和查询。
- 新增 `infra/session_store.py`，负责 session 元数据和配置文件的持久化适配。
- `MainWindow` 支持动态 `addSubInterface`，每个 session 对应一个独立 `SliceInterface`。
- 启动时从 session store 恢复历史 session 导航项，但计算产物为空。

### 阶段二：Session 子配置与模型快照

- 新增 `SessionConfigSnapshot` 作为 session 子配置真相源。
- 新增 `SessionConfigItem` 作为设置卡适配层，避免直接使用全局 `qconfig`。
- 抽屉参数卡只修改当前 session 的配置快照。
- workflow 读取当前 session 的配置快照，不再直接读取全局算法配置。
- 新增 `SessionModelSelection`，保存当前 session 选用的 PA/DTOA 模型路径。

### 阶段三：Session 管理器 UI 与生命周期治理

- 主页右侧增加 session 管理器。
- 支持 session 列表展示、切换、关闭、重命名。
- 处理源文件丢失、模型路径失效、配置恢复失败等异常状态。

## 模块边界

### `core/models`

`ProcessingSession` 仍是纯数据容器，不持有 Qt、controller、workflow 或文件存储对象。它可以包含可序列化字段：

- `display_name`
- `config_snapshot`
- `model_selection`
- `last_opened_at`
- `restored_from_store`

新增 `core/models/session_config.py`：

- `SessionConfigSnapshot`
- `ClusteringConfigSnapshot`
- `RecognitionConfigSnapshot`
- `ExtractConfigSnapshot`
- `MergeConfigSnapshot`
- `BusinessConfigSnapshot`
- `SessionConfigItem`

新增 `core/models/session_model.py`：

- `SessionModelSelection`
- `ActiveModelCandidate`

### `runtime`

新增 `runtime/session_registry.py`，负责：

- 注册 session。
- 查询 session。
- 设置 active session。
- 关闭 session。
- 从 store 恢复 session 后重建运行态索引。
- 发出或转发 session 生命周期事件。

`SessionRegistry` 不负责 JSON 读写细节，只调用 `infra.session_store`。

### `infra`

新增 `infra/session_store.py`，负责：

- `load_index()`
- `load_session(session_id)`
- `upsert_session(session)`
- `save_session_config(session_id, config_snapshot)`
- `delete_session(session_id)`

这是 session 持久化适配层。后续如果改为数据库，只替换该模块，不影响 runtime 和 UI。

### `app/signal_bus.py`

新增事件语义：

- `parse_completed(ProcessingSession)`：文件解析完成，只给主页仪表盘使用。
- `session_registered(str)`：session 已注册。
- `session_activated(str)`：active session 切换。
- `session_closed(str)`：session 关闭。
- `session_metadata_changed(str)`：标题、配置、模型选择等变化。

现有 `import_completed` 不再作为新设计主事件，后续可以保留一段兼容期，但新代码不再依赖它。

### `ui`

`MainWindow` 增加动态 session 页面管理方法：

- `create_session_interface(session)`
- `activate_session_interface(session_id)`
- `close_session_interface(session_id)`
- `restore_session_interfaces()`

`HomeController` 只负责解析文件并展示仪表盘。点击“新建Session并导入”时，调用 session 注册与页面创建入口。

`SliceInterface` 构造或初始化时绑定一个 session，不再默认监听全局导入事件。

`SliceController` 和 `IdentifyController` 只服务自己绑定的 session 页面。

## 事件与数据流

### 解析文件

1. `HomeController.parse_selected_file()` 创建临时 `ProcessingSession`。
2. `ImportWorkflow.start_import(session, file_path)` 启动导入线程。
3. `ImportWorker` 写入 `raw_batch`、`preprocess_result` 和 `dashboard_info`。
4. workflow 发出 `signal_bus.parse_completed.emit(session)`。
5. `HomeController.render_import_dashboard(session)` 刷新主页仪表盘。
6. `_last_parsed_session = session`。

此时不创建 `SliceInterface`，也不影响任何已有 session 页面。

### 新建 Session 并导入

1. `HomeController.import_current_session()` 接管 `_last_parsed_session`。
2. 初始化 `display_name`、`config_snapshot`、`model_selection` 和 `last_opened_at`。
3. `SessionRegistry.register(session)`。
4. `SessionStore.upsert_session(session)` 写入持久化文件。
5. `MainWindow.create_session_interface(session)` 动态新增导航页面。
6. 自动切换到新建 session 页面。
7. 发出 `session_registered` 和 `session_activated`。

当前进程内可以复用解析阶段已有的 raw/preprocess/dashboard 产物；重启恢复后不恢复这些产物。

### 切片

某个 session 页面的 `SliceController` 校验 `session.is_imported` 后调用 `slice_workflow.start_slice(session)`。切片完成事件只由相同 `session_id` 的页面响应。

### 识别

`IdentifyController` 从当前 session 读取：

- `session.config_snapshot.clustering`
- `session.config_snapshot.recognition`
- `session.model_selection.pa_model_path`
- `session.model_selection.dtoa_model_path`

识别 workflow 不再读取全局启用模型。

## 子配置设计

本地 qfluentwidgets 验证结论：不能原样使用“每个 session 一个同类 `QConfig` 实例 + 现有设置卡直接绑定”。

原因：

- `ConfigItem` 是类属性模型，同一个 `QConfig` 类的多个实例会共享同一批 `ConfigItem.value`。
- 设置卡内部大量直接调用全局 `qconfig.get/set`。
- `qconfig.set()` 保存的是当前全局 `_cfg.file`，不会根据传入 `ConfigItem` 自动定位所属配置文件。

最终方案：

- 全局配置继续使用 `AppConfig/QConfig`。
- session 子配置使用 `SessionConfigSnapshot` 作为可序列化真相源。
- `SessionConfigItem` 模仿 `ConfigItem` 的核心接口，提供 `value`、`defaultValue`、`validator`、`valueChanged`、`group`、`name`。
- session-aware 设置卡写入 `SessionConfigItem`，由它更新当前 session 的 `SessionConfigSnapshot` 并触发持久化。

## 模型系统设计

软件整体层级只维护“激活模型集合”，决定各 session 抽屉模型下拉框候选。真正启用模型由 session 自己决定。

`SessionModelSelection` 保存：

- `pa_model_path`
- `dtoa_model_path`

恢复 session 时，如果模型路径不存在或不在激活集合中，页面显示模型失效状态，要求用户在当前 session 抽屉中重新选择。

## 持久化结构

采用索引加单 session 目录：

```text
config/
  sessions/
    index.json
    <session_id>/
      session.json
      config.json
```

`index.json` 保存：

- `schema_version`
- `active_session_id`
- session 列表摘要

`session.json` 保存：

- `session_id`
- `display_name`
- `source_path`
- `source_type`
- `created_at`
- `last_opened_at`
- `model_selection`

`config.json` 保存 `SessionConfigSnapshot`。

保存时机：

- 新建 session 时写入三类文件。
- 重命名 session 时更新 `index.json` 和 `session.json`。
- 切换 active session 时更新 `index.json.active_session_id` 和 `last_opened_at`。
- 修改抽屉参数时更新内存快照，并防抖保存 `config.json`。
- 修改模型选择时更新 `session.json`。
- 关闭 session 时删除对应目录并更新 `index.json`。

## 启动恢复

启动时：

1. `SessionStore.load_index()`。
2. 遍历 session id。
3. 读取 `session.json` 和 `config.json`。
4. 创建空产物 `ProcessingSession`。
5. 注入元数据、`SessionConfigSnapshot` 和 `SessionModelSelection`。
6. `SessionRegistry.register_restored(session)`。
7. `MainWindow.restore_session_interfaces()` 动态恢复导航项。

恢复后的页面不显示旧计算结果，并提示需要重新解析或重新导入源文件。

## UI 生命周期

`MainWindow` 维护：

- `_session_interfaces: dict[str, SliceInterface]`
- `_session_route_keys: dict[str, str]`

动态页面 objectName 使用：

```text
sessionSliceInterface_<session_id>
```

关闭 session 时，如果该 session 有运行中的导入、切片或识别任务，第一版禁止关闭并提示用户等待任务完成。不做强制取消，避免线程和 session 状态半写入。

session 重命名时更新 `session.display_name`、持久化文件、导航标题和页面内显示。若 qfluentwidgets 没有直接更新导航标题的 API，则移除并重加对应 subinterface。

## 测试策略

新增或扩展测试：

- `test_session_config_snapshot.py`
- `test_session_store.py`
- `test_session_registry.py`
- `test_main_window_sessions.py`
- `test_session_event_isolation.py`
- `test_session_config_item.py`
- `test_model_selection_card.py`

重点覆盖：

- 多 session 注册、激活、关闭。
- session 持久化文件创建、更新、删除。
- 子配置缺字段补默认值、类型错误回退默认值。
- A session 修改参数不影响 B session。
- 解析完成只刷新主页仪表盘，不创建切片页。
- `stage_finished(session_a, "slicing")` 只刷新 A 页面。
- session 抽屉不再直接绑定全局 `appConfig`。
- `IdentifyController` 不再调用 `get_enabled_model_path()` 决定真正启用模型。

优先验证命令：

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_registry.py -q
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_store.py -q
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_session_config_item.py -q
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_main_window_sessions.py -q
```

相关既有测试：

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_navigation_controls.py -q
D:\Miniforge3\envs\pyqt6\python.exe -m pytest RadarIdentifySystem_PyQt6\tests\unit\test_slice_param_panel.py -q
```

语法级兜底：

```powershell
D:\Miniforge3\envs\pyqt6\python.exe -m compileall RadarIdentifySystem_PyQt6\core RadarIdentifySystem_PyQt6\runtime RadarIdentifySystem_PyQt6\infra RadarIdentifySystem_PyQt6\ui
```

## 验收标准

- 解析文件后只刷新主页仪表盘，不新增切片页。
- 点击“新建Session并导入”后新增一个 session 导航项。
- 连续导入两个文件后有两个独立切片页。
- 两个 session 的参数和模型选择互不影响。
- 重启应用后恢复 session 导航项和配置，但不恢复旧计算结果。
- 源文件丢失或模型失效时有明确提示。
- workflow 读取当前 session 配置与模型选择，不再读取全局启用模型。

