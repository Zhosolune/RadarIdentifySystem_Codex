# P07 Infra 适配层迁移

## 目标
完成 infra 适配层迁移（解析/推理/绘图/导出），配置不再由 infra 单独维护。

## 本阶段新增文件
1. `infra/parsers/excel_parser.py`
2. `infra/parsers/bin_parser.py`
3. `infra/parsers/mat_parser.py`
4. `infra/onnx/predictor.py`
5. `infra/plotting/plot_service.py`
6. `infra/storage/result_exporter.py`
7. `infra/storage/pulse_exporter.py`
8. `tests/integration/test_infra_parsers.py`
9. `tests/integration/test_infra_exporters.py`

## 执行步骤
1. 迁移解析器（Excel/Bin/MAT）。
2. 迁移 ONNX 与绘图适配器。
3. 迁移导出适配器并补测试。
4. 所有参数读取统一走 `appConfig`。

## 验收标准
1. infra 模块可被 app 独立调用。
2. core 不直接依赖第三方库细节。
3. 配置读取路径统一，不再出现双配置源。
