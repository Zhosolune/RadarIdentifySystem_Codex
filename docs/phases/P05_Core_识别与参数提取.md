# P05 Core 识别与参数提取

## 目标
迁移识别判定与参数提取规则，保持“预测结果 -> 有效性判定 -> 参数抽取”链路稳定。

## 本阶段新增文件
1. `core/recognition/evaluator.py`
2. `core/recognition/label_policy.py`
3. `core/params/extractor.py`
4. `core/params/related_filter.py`
5. `core/models/prediction_result.py`
6. `tests/unit/test_core_recognition_evaluator.py`
7. `tests/unit/test_core_params_extractor.py`

## 本阶段迁移来源
- `cores/model_predictor.py`（业务判定部分）
- `cores/params_extractor.py`

## 关键迁移点
1. `is_valid` 判定逻辑（PA/DTOA 标签）
2. 联合概率计算
3. CF/PW/PRI/DOA 提取
4. 倍频/和频相关数过滤

## 执行步骤
1. 抽象 `PredictionDecision` 数据模型。
2. 实现 `evaluate_prediction(pa, dtoa, weights, threshold)`。
3. 迁移并测试 `extract_grouped_values`。
4. 迁移并测试 `filter_related_numbers`。
5. 补充边界：极少点、全异常值、空集合。
6. 与 P04 对接：接收簇对象输出识别摘要。

## 验收标准
1. 识别有效簇判定与旧版一致。
2. 参数提取结果统计一致（允许浮点微小误差）。
3. 与聚类模块接口清晰，无 UI 依赖。

## 风险与应对
- 风险：阈值处理细节差异造成标签漂移。
- 应对：固定样本逐条断言 pa_label/dtoa_label/joint_prob。

## 回退点
- 回退到旧判定逻辑仅需替换 evaluator。
