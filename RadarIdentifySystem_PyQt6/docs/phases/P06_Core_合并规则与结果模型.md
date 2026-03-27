# P06 Core 合并规则与结果模型

## 目标
将分散在 `DataController/ThreadWorker` 的合并逻辑集中到 `core/merge`，消除双实现漂移。

## 本阶段新增文件
1. `core/merge/rules.py`
2. `core/merge/engine.py`
3. `core/merge/time_overlap.py`
4. `core/models/merge_result.py`
5. `tests/unit/test_core_merge_rules.py`
6. `tests/unit/test_core_merge_engine.py`

## 本阶段迁移来源
- `ui/data_controller.py` 合并相关函数
- `cores/ThreadWorker.py` 合并相关函数

## 关键规则（必须完整保留）
1. PRI 相同合并条件
2. PRI 不同合并条件
3. PRI 不可提取合并条件
4. TOA 时间交叠检查
5. 贪婪扩展合并组

## 执行步骤
1. 从两处实现抽取规则，整理冲突差异表。
2. 统一规则函数签名，输入 `ClusterFeature`，输出 bool。
3. 实现 `MergeEngine.merge(clusters, params)`。
4. 保留合并来源索引，支持 UI 追踪“由哪些簇合并而来”。
5. 建立对齐测试：旧逻辑 vs 新逻辑同输入同输出。
6. 在文档记录所有阈值参数与默认值。

## 验收标准
1. 合并数量与成员关系与旧版一致。
2. 不再有双份合并实现。
3. merge 模块可被 UI 与全速流程复用。

## 风险与应对
- 风险：历史逻辑存在隐式分支，抽取时遗漏。
- 应对：用旧代码回放样本生成黄金输出做对照。

## 回退点
- 保留旧实现适配器，必要时临时切回。
