# RadarIdentifySystem

RadarIdentifySystem 是一套基于 PyQt6 的雷达脉冲数据识别桌面应用。项目提供数据导入、预处理、切片、聚类、ONNX 模型识别、参数提取、结果合并与 Excel 导出能力，并同时支持交互式分析和全速批处理。

当前项目版本：`0.2.1`

## 主要功能

- 导入 Excel 和大端 PDW BIN 脉冲文件。
- 按载频将一次导入拆分为独立的 L、S、C 波段数据包。
- 通过数据池创建多个相互独立的交互式或全速处理 Session。
- 执行脉冲清洗、TOA 翻折修正、切片、CF/PW 聚类和 PA/DTOA 模型识别。
- 提取识别结果参数，并按策略合并雷达结果。
- 管理 PA、DTOA ONNX 模型和每个 Session 的模型选择。
- 展示切片、聚类、识别和合并结果图像。
- 将全速处理结果导出为雷达结果、综合结果和脉冲明细三个 Excel 工作簿。
- 持久化配置、Session、数据池、用户模型和运行日志。

## 技术栈

- Python 3.12
- PyQt6 6.7.1
- qfluentwidgets
- NumPy、pandas、scikit-learn、Matplotlib
- ONNX Runtime（CPU）
- openpyxl
- pytest
- PyInstaller + Inno Setup

## 快速开始

### 环境要求

- Windows 10/11
- Python `>=3.12,<3.13`
- 推荐安装 [uv](https://docs.astral.sh/uv/)

### 使用 uv

在仓库根目录执行：

```powershell
uv sync --locked --group test --cache-dir .uv-cache
uv run python main.py
```

### 使用 venv 和 pip

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

> `pyproject.toml` 与 `uv.lock` 是推荐的依赖基线；`requirements.txt` 主要用于最小运行环境安装。

## 基本使用流程

```text
选择导入目录
→ 解析 Excel/BIN 文件
→ 生成 L/S/C 数据包
→ 创建交互式或全速 Session
→ 切片、识别、参数提取与合并
→ 查看或导出结果
```

### 交互式处理

交互式 Session 适合逐片检查数据。用户可以调整切片和识别参数、切换切片与类别、查看特征图像，并独立执行识别和合并操作。

### 全速处理

全速 Session 会按当前参数和模型连续处理全部切片。每个 Session 独立保存输入数据、参数快照、模型选择和输出目录；完成后生成三个带时间戳且不会覆盖历史结果的 Excel 文件：

- `*_雷达结果.xlsx`
- `*_综合结果.xlsx`
- `*_脉冲明细.xlsx`

## 输入数据

当前 UI 支持以下文件类型：

| 类型 | 扩展名 | 说明 |
| --- | --- | --- |
| Excel | `.xls`、`.xlsx`、`.xlsm` | 支持旧格式和新格式，文件至少包含 8 列 |
| BIN | `.bin` | 每条记录 32 字节，由 16 个大端 `uint16` 组成的 `pdw_v1` 格式 |
| MAT | `.mat` | 界面保留入口，当前尚未实现解析 |

导入后统一转换为六列 `PulseBatch`：

| 索引 | 字段 | 单位或约定 |
| ---: | --- | --- |
| 0 | CF | MHz |
| 1 | PW | μs |
| 2 | PA | 保留导入值；BIN 数据不额外缩放 |
| 3 | DOA | 度 |
| 4 | PDOA | 度 |
| 5 | TOA | 原始 `0.1 μs` 计数 |

波段划分规则为：L `[1000, 2000)` MHz、S `[2000, 4000)` MHz、C `[4000, 8000)` MHz。范围外的数据不会生成波段数据包。

## 项目结构

```text
RadarIdentifySystem_Codex/
├── app/          # 应用生命周期、配置、日志、资源和全局服务装配
├── core/         # 纯业务数据模型、算法和规则
├── infra/        # 文件解析、ONNX 推理、绘图、导出和持久化适配
├── runtime/      # Workflow 编排、Session 管理和后台线程
├── ui/           # 界面、组件和 Controller
├── resources/    # 图标、样式和内置 ONNX 模型
├── tests/        # 单元测试与集成测试
├── docs/         # 架构、迁移、风险和操作记录
├── packaging/    # PyInstaller 与 Inno Setup 构建配置
├── main.py       # 程序入口
└── pyproject.toml
```

项目遵循以下依赖方向：

```text
ui → runtime → core
ui → app
runtime → infra → core
```

`core` 不依赖 Qt、UI、线程或基础设施实现；UI 不直接调用 `core` 或 `infra`。详细约束见 [目录结构与分层约束](docs/目录结构与分层约束.md)。

## 用户数据目录

源码开发版和安装版使用不同的数据根目录，避免开发配置污染正式数据：

- 源码开发版：`%LOCALAPPDATA%\RadarIdentifySystem-Dev`
- 安装版：`%LOCALAPPDATA%\RadarIdentifySystem`

其中包含配置、日志、交互式与全速 Session、数据池、用户模型和缓存。测试或嵌入场景可通过以下环境变量覆盖默认位置：

- `RADAR_IDENTIFY_DATA_ROOT`
- `RADAR_IDENTIFY_TEMP_ROOT`

## 测试

安装测试依赖后，在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp
```

如需运行单个测试文件：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_packaging_config.py -q --basetemp .pytest-tmp-packaging
```

## Windows 打包

正式安装包采用 PyInstaller `onedir/windowed` 与 Inno Setup 构建：

```powershell
.\packaging\build.ps1
```

主要产物：

- `dist\RadarIdentifySystem\`：PyInstaller 目录产物。
- `artifacts\RadarIdentifySystem-Setup-<版本>.exe`：Windows 完整安装包。

仅验证 PyInstaller 目录产物时可执行：

```powershell
.\packaging\build.ps1 -SkipInstaller
```

版本只在 `pyproject.toml` 的 `[project].version` 中维护。完整构建、覆盖升级和发布检查要求见 [Windows 打包说明](packaging/README.md) 与 [版本发布 SOP](packaging/RELEASE_SOP.md)。

## 开发约定

- 保持 `ui → runtime → core` 和 `runtime → infra` 的分层边界。
- 配置统一由 `app/app_config.py` 管理，不新增第二套配置系统。
- 新功能和跨模块改动应补充针对真实故障或业务规则的回归测试。
- 重大功能、架构或 UI/UX 变更需按时间倒序记录到 [操作日志](docs/operateLog.md)。
- `pyproject.toml` 是项目版本和依赖声明的主入口；依赖变化后应同步更新 `uv.lock`。

## 相关文档

- [目录结构与分层约束](docs/目录结构与分层约束.md)
- [算法参数对象规则](docs/算法参数对象规则.md)
- [配置系统设计](docs/配置系统设计.md)
- [风险清单](docs/风险清单.md)
- [Windows 打包说明](packaging/README.md)
- [版本发布 SOP](packaging/RELEASE_SOP.md)
- [操作日志](docs/operateLog.md)

## 许可证与发布提醒

仓库当前未提供独立许可证文件。对外分发前必须确认源码、PyQt6、PyQt6-Fluent-Widgets、PyQt6-Frameless-Window 以及内置 ONNX 模型的使用和再分发授权。当前安装包使用 CPU 版 `onnxruntime`，不得宣称内置 GPU 推理支持。
