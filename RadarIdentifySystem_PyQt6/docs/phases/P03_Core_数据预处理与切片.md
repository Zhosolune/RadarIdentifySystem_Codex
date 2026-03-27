# P03 Core 数据预处理与切片

## 目标
将 `cores/data_processor.py` 的业务能力迁入 `core`，并做到不依赖 UI。

## 本阶段新增文件
1. `core/models/pulse_batch.py`
2. `core/models/slice_result.py`
3. `core/data/preprocess.py`
4. `core/data/slicing.py`
5. `tests/unit/test_core_preprocess.py`
6. `tests/unit/test_core_slicing.py`

## 本阶段迁移来源
- `cores/data_processor.py`

## 关键迁移点
1. PA=255 清洗规则
2. TOA 翻折修复规则
3. 时间范围计算
4. 250ms 切片（配置化）
5. `time_ranges` 与切片数据保持索引一致

## 执行步骤
1. 在 `pulse_batch.py` 定义输入数据结构（`np.ndarray + 元数据`）。
2. `preprocess.py` 提供纯函数：`clean_pa`、`fix_toa_flip`、`detect_band`。
3. `slicing.py` 提供 `slice_by_toa(data, slice_length_ms)`。
4. 从旧代码抽离日志与状态依赖，改为参数输入/返回值输出。
5. 为每个规则写边界测试：空数据、单点、翻折点、多翻折点。
6. 输出 `SliceResult`，包含 `slices`、`time_ranges`、统计信息。
7. 在文档记录与旧逻辑的对齐差异（如单位换算细节）。

## 验收标准
1. 同一输入数据下，切片数量与旧版一致。
2. 时间范围、过滤数量统计一致。
3. 核心函数可在无 Qt 环境下运行。

## 风险与应对
- 风险：单位（us/ms）转换偏差导致下游漂移。
- 应对：建立固定样本断言，对比关键字段。

## 回退点
- 保留 `core/data` 独立模块，不影响 UI 与线程模块。
