# P04 Core 聚类流程（CF/PW 两轮串行）

## 目标
完整迁移并固化当前真实聚类逻辑：两轮串行聚类 + 未处理点回收，不改变算法行为。

## 本阶段新增文件
1. `core/clustering/dbscan_1d.py`
2. `core/clustering/cluster_filters.py`
3. `core/clustering/pipeline.py`
4. `core/models/cluster_result.py`
5. `tests/unit/test_core_clustering_pipeline.py`
6. `tests/unit/test_core_cluster_filters.py`

## 本阶段迁移来源
- `cores/roughly_clustering.py`
- `cores/cluster_processor.py`
- `cores/params_extractor.py`（DTOA 分组判据部分）

## 关键规则（必须对齐）
1. 维度顺序：`CF -> PW`
2. 每轮为单维 DBSCAN
3. 簇有效性：`len(cluster)<=MIN_CLUSTER_SIZE 且 DTOA 分组无效 -> 丢弃`
4. `processed_points` 推导 `unprocessed_points`
5. 第二轮输入来自第一轮输出重组数据

## 执行步骤
1. 实现 `DBSCAN1DClusterer`（接收维度索引+参数）。
2. 将 DTOA 分组判据抽到 `cluster_filters.py`。
3. 构建 `ClusteringPipeline.run(current_data)` 返回：
   - `clusters_cf`
   - `clusters_pw`
   - `unprocessed_points`
4. 增加“对齐测试”：对固定输入比对簇数量和点索引。
5. 补异常用例：空数组、非法 shape、全噪声。
6. 明确 `cluster_idx` 规则，防止 UI 表格序号变化。

## 验收标准
1. 聚类数量、未处理点集合与旧版一致。
2. 输入同样参数时输出稳定。
3. 核心 pipeline 不依赖 Qt。

## 风险与应对
- 风险：索引重排导致导出序号变化。
- 应对：在测试中加“索引稳定性”断言。

## 回退点
- 回退到旧聚类实现只需替换 pipeline 入口。
