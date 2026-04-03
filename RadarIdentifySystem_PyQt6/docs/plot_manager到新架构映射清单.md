# plot_manager 到新架构映射清单

## 1. 文档目的

本文用于整理旧项目 `RadarIdentifySystem/cores/plot_manager.py` 在新项目 `RadarIdentifySystem_PyQt6` 中的落位方式，作为后续抽离绘图模块时的统一依据。

目标不是把旧版 `SignalPlotter` 整类搬入新项目，而是保留其有效的“数据映射成图像”能力，拆除其与流程状态、磁盘路径、业务判断之间的耦合。

---

## 2. 新架构约束

依据 `docs/目录结构与分层约束.md`，本项目采用以下边界：

- `core`：纯业务规则与算法，不依赖 UI、线程、基础设施适配层
- `infra`：第三方或系统适配能力，包含绘图、解析、存储等
- `runtime`：流程编排、任务调度、状态推进、事件分发
- `ui`：界面显示与交互，不直接承载算法与数据加工

因此，旧版 `plot_manager.py` 中所有“生成图像”的能力应迁入 `infra`，所有“何时绘图、绘哪一片、显示哪一类”的能力应迁入 `runtime`，所有“将图像渲染到控件”的能力应保留在 `ui`。

---

## 3. 对旧版 plot_manager 的总体判断

旧版 `SignalPlotter` 同时承担了以下多种职责：

- 波段检测与绘图配置切换
- 切片时间范围缓存
- 切片图绘制
- 聚类图绘制
- 合并多颜色图绘制
- PNG 文件输出
- 颜色信息查询
- 临时目录与结果目录管理

这说明旧版实现是“可用的工程整合体”，但不符合新项目的分层要求。  
新项目中应将它拆为“纯渲染能力 + 流程调度 + UI 展示”三段。

---

## 4. 推荐落位

### 4.1 infra/plotting 子包

负责真正的绘图与图像生成能力，已拆分为以下模块：

- `types.py`: 定义绘图配置结构，如 `PlotSpec`, `PlotProfile`, `MergePalette`
- `utils.py`: 根据频段或外部传入配置生成维度绘图参数、派生维度处理
- `engine.py`: 根据脉冲数组生成单维度二值图、根据 cluster 列表生成多颜色合并图
- `facades.py`: 提供切片、聚类、合并等场景的渲染门面函数
- `exporter.py`: 在需要导出时，提供可选的 PNG 落盘函数

不负责：

- 当前切片索引维护
- session 生命周期状态
- UI 类别勾选状态
- 业务频段判断

### 4.2 runtime/workflow

负责绘图时机与输入组织：

- 从 session 中读取当前切片、聚类结果、合并结果
- 提供统一的时间范围
- 决定调用哪一种绘图入口
- 生成后通过 signal_bus 通知 UI 更新

不负责：

- 像素映射
- PNG 编码细节
- 控件显示逻辑

### 4.3 ui/components 与 ui/interfaces

负责图像展示：

- 接收图像结果并显示
- 清空占位图
- 更新标题
- 提供合并类别勾选面板

不负责：

- DTOA 计算
- 多颜色合并图生成
- 配置切换

### 4.4 core

继续只负责业务数据与算法：

- preprocess
- slicing
- clustering
- recognition
- merge

不新增任何绘图依赖。

---

## 5. 旧函数到新架构映射

### 5.1 配置与状态相关

| 旧函数/能力 | 旧职责 | 新归属 | 处理建议 |
| --- | --- | --- | --- |
| `detect_frequency_band()` | 根据 CF 数据判断波段 | `core` 结果输入 / `runtime` 传参 | 不在 plotting 内重复判断，直接消费预处理阶段产出的 `band` |
| `update_configs()` | 按波段切换 CF/PW/DTOA 图像范围 | `infra/plotting/utils.py` | 改成“根据 band 返回 PlotSpec 集合”，不要直接读取原始数据 |
| `set_slice_time_ranges()` | 在 plotter 中缓存流程时间范围 | `runtime/workflow` / `ProcessingSession` | 时间范围应挂在 session 或 workflow 上，不应挂在 renderer 实例上 |
| `set_temp_dir()` | 设置预测图临时目录 | `infra/storage` 或导出服务 | 主链路展示优先走内存，不在 renderer 中持久化目录状态 |
| `set_save_dir()` | 设置结果图保存目录 | `infra/storage` 或导出服务 | 同上，导出能力单独处理 |

### 5.2 切片与聚类绘图

| 旧函数/能力 | 旧职责 | 新归属 | 处理建议 |
| --- | --- | --- | --- |
| `plot_slice()` | 为切片生成 5 张维度图 | `infra/plotting/facades.py` | 保留，改成输出内存图像结果而非路径 |
| `plot_cluster()` | 为单个聚类生成 2 张或 5 张图 | `infra/plotting/facades.py` | 保留，建议拆成“预测输入图”和“展示图”两个模式 |
| `_plot_dimension()` | 栅格化单维度二值图 | `infra/plotting/engine.py` 私有核心函数 | 必保留，是最核心的可迁移逻辑 |

### 5.3 合并可视化

| 旧函数/能力 | 旧职责 | 新归属 | 处理建议 |
| --- | --- | --- | --- |
| `plot_merged_cluster()` | 生成合并结果全维度图 | `infra/plotting/facades.py` | 保留，作为 merge 渲染入口 |
| `_plot_merged_dimension()` | 生成单维度多颜色图 | `infra/plotting/engine.py` | 保留，输入改为显式 `visible_cluster_indices` |
| `_convert_multicolor_to_rgb()` | 将颜色索引图转 RGB 图 | `infra/plotting/engine.py` | 保留，属于纯渲染辅助函数 |
| `get_color_info()` | 提供颜色名与 RGB | `infra/plotting/types.py` 或 `ui` 公共 palette | 若 UI 需要显示颜色名，可保留公开接口 |

---

## 6. 必须保留的旧设计

### 6.1 固定时间窗绘制

切片图、聚类图、合并图的横轴时间范围不能完全依赖当前数据实际最小值和最大值，而应优先使用流程阶段已经确定的时间窗。

原因：

- 同一切片下五张图的横轴必须一致
- 切换不同类别时视觉尺度不能漂移
- 合并前后对比时需要统一时间参照

结论：

- 时间窗属于 `runtime/session` 数据
- plotting 只消费 `time_range`

### 6.2 DTOA 作为派生维度

DTOA 不是原始输入列，而是由 TOA 差分派生得到。  
该逻辑应保留，但从场景函数中抽成独立辅助函数，避免在切片、聚类、合并三个入口中重复实现。

### 6.3 多颜色合并图

旧版合并可视化最有价值的能力，是将多个 cluster 叠加到统一画布中，并允许按类别显隐重绘。  
这一能力建议完整保留，但应拆成：

- runtime 维护哪些 cluster 可见
- infra 根据可见 cluster 渲染图像
- ui 只展示结果

---

## 7. 应废弃的旧设计

以下设计不建议迁入新项目：

- renderer 内持有 `save_dir/temp_dir/time_ranges`
- renderer 自己判断 band
- 主展示链路依赖“先写 PNG 再读 PNG”
- 一个类同时承担切片图、聚类图、合并图、配置切换、目录管理

这些设计会让新项目再次回到“单大类协调一切”的旧结构。

---

## 8. 新版建议接口

建议在 `infra/plotting` 子包中逐步形成如下接口：

### 8.1 数据结构

- `PlotSpec`
- `PlotProfile`
- `MergePalette`
- `RenderedImageBundle`

### 8.2 辅助函数

- `build_plot_profile(band: str | None) -> PlotProfile`
- `build_dtoa_series(toa: np.ndarray) -> np.ndarray`
- `rasterize_dimension(...) -> np.ndarray`
- `rasterize_merge_dimension(...) -> np.ndarray`
- `convert_color_index_to_rgb(...) -> np.ndarray`

### 8.3 场景函数

- `render_slice_images(...)`
- `render_cluster_images(...)`
- `render_predict_images(...)`
- `render_merge_images(...)`

### 8.4 导出函数

- `save_rendered_images(...)`

说明：

- 场景函数优先返回内存中的图像数组或可显示对象
- 是否落盘应由调用方显式决定

---

## 9. 推荐迁移顺序

### 第一步：单维度栅格化

先迁 `_plot_dimension()` 对应能力，得到新项目第一版纯渲染核心。

### 第二步：切片图

实现 `render_slice_images()`，打通切片页左列展示。

### 第三步：聚类图

实现 `render_cluster_images()`，打通识别结果中列展示。

### 第四步：预测图

将“仅 PA/DTOA 两张图”的模型输入图单独建入口，避免与展示图耦合。

### 第五步：合并图

最后补 `render_merge_images()` 和多颜色图逻辑，因为其输入组织最复杂。

### 第六步：导出

若后续需要保留 PNG 导出，再补存盘接口，不要在第一阶段绑定磁盘。

---

## 10. 本次重构的落地判断标准

后续如果绘图模块抽离完成，应满足以下标准：

- `core` 中没有任何绘图依赖
- `infra/plotting` 子包可以在无 Qt 环境下单独运行
- `ui` 不直接调用 `core` 或 `infra` 具体实现
- 绘图函数不持有 session 内部状态
- 主链路展示可以不依赖磁盘中转
- 合并类别显隐只影响渲染输入，不影响 renderer 内部状态机

---

## 11. 一句话结论

旧版 `plot_manager.py` 最值得继承的不是类结构，而是“固定时间窗下的五维栅格化规则”和“多类别叠色合并图规则”。  
新项目应继承其图像生成算法，放弃其流程状态、目录状态和业务判断混装的实现方式。
