# RadarIdentifySystem Windows 版本发布 SOP

## 1. 目的与适用范围

本文档规定 RadarIdentifySystem Windows 桌面版从版本准备、依赖锁定、测试、
安装包构建、覆盖升级验收到发布归档的标准流程。

适用于通过以下技术链路发布的正式版本：

```text
pyproject.toml + uv.lock
→ PyInstaller onedir/windowed
→ Inno Setup 完整安装包
→ 用户直接覆盖安装
```

本项目不维护 PyInstaller 二进制差分补丁。新版本统一发布完整安装包。

## 2. 发布原则

1. `pyproject.toml` 的 `[project].version` 是唯一版本源。
2. 修改版本后必须执行 `uv lock`，因为 `uv.lock` 也记录项目自身版本。
3. 正式构建必须使用锁定依赖，不得在构建阶段隐式升级依赖。
4. 正式安装包必须从明确、可追溯的 Git 提交构建。
5. 覆盖升级只替换程序文件，不得删除用户数据目录。
6. 只有完成安装验收、哈希记录和发布阻断项确认后才能对外发布。

## 3. 路径与产物约定

- 程序安装目录：`%LOCALAPPDATA%\Programs\RadarIdentifySystem`
- 用户数据目录：`%LOCALAPPDATA%\RadarIdentifySystem`
- PyInstaller 目录产物：`dist\RadarIdentifySystem\`
- 安装包目录：`artifacts\`
- 安装包命名：`RadarIdentifySystem-Setup-<版本>.exe`

用户数据目录包含配置、日志、Session、数据池、用户模型和缓存。覆盖升级不得清理
该目录。安装器只在写入新版本前清理 `{app}\_internal`，以避免旧 DLL、PYD 和
Python 包残留。

## 4. 版本规则

推荐使用三段数字版本：

```text
主版本.次版本.修订版本
```

示例：

- `0.2.1`：缺陷修复或小范围调整。
- `0.3.0`：新增向后兼容功能。
- `1.0.0`：首个稳定正式版本。
- `2.0.0`：存在不兼容变化。

当前版本生成器只接受三段或四段纯数字版本，例如 `0.2.1` 或 `0.2.1.0`；不接受
`0.2.1-beta`、`0.2.1-rc1` 等预发布字符串。

## 5. 标准发布流程

以下命令均在仓库根目录执行。

### 5.1 确认发布范围

检查当前分支和工作区：

```powershell
git branch --show-current
git status --short
git diff
```

确认所有待发布功能、测试和文档都属于本次版本。不得将实验代码、调试输出或无关
修改混入正式安装包。

### 5.2 修改唯一版本源

只修改根目录 `pyproject.toml`：

```toml
[project]
name = "radar-identify-system"
version = "0.2.1"
```

不得手工维护以下版本：

- `build\packaging\RadarIdentifySystem.version.txt`
- EXE 文件版本和产品版本
- Inno Setup `AppVersion`
- 安装包文件名

这些内容由 `packaging\build.ps1` 从 `pyproject.toml` 自动生成。

### 5.3 更新并检查 uv.lock

修改项目版本或依赖声明后执行：

```powershell
uv lock --cache-dir .uv-cache
uv lock --check --cache-dir .uv-cache
git diff -- pyproject.toml uv.lock
```

要求：

- `uv lock --check` 必须通过。
- `pyproject.toml` 与 `uv.lock` 必须在同一个发布提交中提交。
- 如果只修改项目版本，`uv.lock` 通常只改变根项目的版本。
- 不得手工编辑 `uv.lock`。
- 版本发布不得使用 `uv lock --upgrade`；该选项可能同时升级第三方依赖。
- 只有明确计划升级依赖并完成相应回归时，才允许使用 `--upgrade` 或
  `--upgrade-package`。

### 5.4 同步测试与构建环境

```powershell
uv sync --locked --group test --group build --cache-dir .uv-cache
```

构建脚本固定使用仓库内 `.venv`。PowerShell 当前显示的 Conda 或其他虚拟环境名称
不决定最终打包环境。

### 5.5 执行发布前测试

至少执行打包配置回归：

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_packaging_config.py `
    -q `
    --basetemp build\pytest-packaging-release
```

正式发布还应执行项目完整回归：

```powershell
.\.venv\Scripts\python.exe -m pytest `
    --basetemp build\pytest-release
```

测试要求：

- 本次修改的专项测试必须全部通过。
- 完整回归失败时必须定位并记录原因。
- 不得仅以“与打包无关”为由静默忽略失败。
- 因环境原因无法执行的测试必须在发布记录中列明，并在独立环境补测。

### 5.6 创建发布候选提交

检查所有发布内容后提交代码、版本、锁文件、测试和操作日志：

```powershell
git status --short
git diff
git add pyproject.toml uv.lock docs\operateLog.md
git add -p
git commit -m "release: prepare v0.2.1"
git status --short
```

使用 `git add -p` 逐项确认已有文件的改动；新增文件应根据 `git status --short` 输出
使用明确路径单独添加。不得使用未检查范围的批量暂存替代发布差异审核。

正式构建前，工作区应无未确认修改。如果构建或验收发现问题，应修复、重新测试并
创建新提交，然后重新构建；不得继续发布旧产物。

### 5.7 构建完整安装包

标准构建命令：

```powershell
.\packaging\build.ps1
```

如果无法自动发现 Inno Setup，可显式指定编译器：

```powershell
.\packaging\build.ps1 `
    -IsccPath "D:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

构建脚本依次执行：

1. 校验默认 ONNX 模型大小和 SHA-256。
2. 使用 `uv sync --locked` 同步锁定依赖。
3. 从 `pyproject.toml` 读取项目版本。
4. 生成 Windows EXE 版本资源。
5. 使用 PyInstaller 构建 `onedir/windowed` 程序。
6. 使用 Inno Setup 生成完整安装包。

正式发布不得使用 `-SkipSync`。`-SkipSync` 只适用于已确认环境一致的本地调试。
`-SkipInstaller` 只生成 PyInstaller 目录产物，也不得作为正式发布结果。

### 5.8 校验构建产物

以 `0.2.1` 为例，确认以下文件存在：

```text
dist\RadarIdentifySystem\RadarIdentifySystem.exe
artifacts\RadarIdentifySystem-Setup-0.2.1.exe
```

检查应用版本：

```powershell
(Get-Item `
    ".\dist\RadarIdentifySystem\RadarIdentifySystem.exe"
).VersionInfo | Select-Object FileVersion, ProductVersion
```

`FileVersion` 和 `ProductVersion` 都应等于 `pyproject.toml` 中的版本。

检查安装器产品版本：

```powershell
(Get-Item `
    ".\artifacts\RadarIdentifySystem-Setup-0.2.1.exe"
).VersionInfo | Select-Object ProductVersion
```

检查安装包哈希：

```powershell
Get-FileHash `
    ".\artifacts\RadarIdentifySystem-Setup-0.2.1.exe" `
    -Algorithm SHA256
```

将最终文件大小、SHA-256、构建提交和测试结果记录到 `docs\operateLog.md` 及发布说明。
如果增加代码签名，必须在完成签名后重新计算最终 SHA-256。

### 5.9 执行安装与覆盖升级验收

验收应在独立测试机或虚拟机执行，不应直接使用开发机的正式用户数据。

最低验收矩阵：

1. 无旧版本时全新安装。
2. 从上一正式版本覆盖升级到新版本。
3. 对新版本执行同版本重新安装。
4. 卸载时选择保留用户数据，然后重新安装。
5. 在一次性环境中验证卸载时选择删除用户数据。

跨版本覆盖升级步骤：

1. 安装并启动上一正式版本，创建测试配置、Session、数据池和用户模型。
2. 关闭应用。
3. 在安装前备份 `%LOCALAPPDATA%\RadarIdentifySystem`，并记录关键文件哈希。
4. 可在旧版 `{app}\_internal` 中放置一个仅用于验收的标记文件。
5. 不卸载旧版，直接运行新版本完整安装包。
6. 安装完成后、首次启动新版本前，确认用户数据仍存在且关键文件未被安装器修改。
7. 确认旧 `_internal` 标记文件已被删除，证明旧依赖目录得到清理。
8. 启动新版本，验证配置、Session、数据池和用户模型可以正常读取。
9. 验证 PA、DTOA 默认模型可以正常加载和预热。
10. 验证快捷方式、应用版本、日志写入和核心业务流程。

覆盖升级时用户的标准操作是：关闭旧版应用，直接运行新版本完整安装包，无需先
卸载。不得向用户分发 `dist\RadarIdentifySystem\` 作为正式升级方式。

### 5.10 确认发布阻断项

对外发布前必须确认：

- PyQt6、PyQt6-Fluent-Widgets、PyQt6-Frameless-Window 的分发授权。
- 默认 ONNX 模型的再分发权。
- 当前安装包为 CPU 版 `onnxruntime`，不得宣称内置 GPU 推理支持。
- 正式发布是否需要为应用 EXE 和安装包添加代码签名。
- 发布说明是否包含已知问题、系统要求和升级说明。

任何未解决的授权问题都应视为发布阻断，而不是普通警告。

### 5.11 创建标签并发布

全部验收通过后，在实际用于构建的提交上创建标签：

```powershell
git tag -a v0.2.1 -m "RadarIdentifySystem v0.2.1"
git push origin newUI
git push origin v0.2.1
```

发布内容至少包括：

- `RadarIdentifySystem-Setup-0.2.1.exe`
- 安装包 SHA-256
- 发布对应的 Git 提交和标签
- 版本更新说明
- 已知问题
- 覆盖升级说明
- 系统和硬件要求

标签必须在安装验收通过后创建。标签、安装包、SHA-256 和发布说明中的版本必须
完全一致。

## 6. 回滚准备

1. 保留上一正式版本安装包、SHA-256、标签和发布说明。
2. 发布前备份有代表性的用户数据，用于验证新旧版本兼容性。
3. 如果新版本包含配置或数据结构迁移，必须明确迁移是否可逆。
4. 未确认数据向后兼容时，不得承诺用户直接覆盖安装旧版本即可回滚。
5. 严重故障时，先备份 `%LOCALAPPDATA%\RadarIdentifySystem`，再按经验证的回滚方案
   处理，避免旧程序读取新格式数据造成二次损坏。

## 7. 常见异常处理

### 7.1 uv.lock 需要更新

错误：

```text
The lockfile at uv.lock needs to be updated, but --locked was provided.
```

处理：

```powershell
uv lock --cache-dir .uv-cache
uv lock --check --cache-dir .uv-cache
git diff -- pyproject.toml uv.lock
```

确认锁文件变化符合预期后再重新构建。

### 7.2 找不到 Inno Setup

```powershell
.\packaging\build.ps1 `
    -IsccPath "D:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

`-IsccPath` 既可传入 `ISCC.exe`，也可传入包含该文件的安装目录。

### 7.3 默认模型校验失败

不得绕过模型大小或 SHA-256 校验。先确认模型是否缺失、损坏或被误替换；如确实
需要发布新模型，应审核模型来源与授权，并有意更新 `packaging\model-manifest.json`。

### 7.4 完整测试存在失败

停止发布，定位失败是否由本版本引入。修复后重新执行测试、创建新提交并重新构建。
环境性阻断必须记录证据，并在满足相同依赖和系统条件的独立环境补测。

## 8. 发布检查清单

### 版本与依赖

- [ ] `pyproject.toml` 版本正确。
- [ ] 已执行 `uv lock --cache-dir .uv-cache`。
- [ ] `uv lock --check --cache-dir .uv-cache` 通过。
- [ ] 已检查 `pyproject.toml` 与 `uv.lock` 差异。
- [ ] 未发生非预期依赖升级。

### 测试与源码

- [ ] 本版本专项测试通过。
- [ ] 完整回归通过，或阻断项已有明确记录和补测结果。
- [ ] 发布提交已包含源码、测试、版本、锁文件和操作日志。
- [ ] 正式构建前工作区无未确认修改。

### 构建与产物

- [ ] 使用标准 `packaging\build.ps1` 完整构建。
- [ ] EXE 文件版本和产品版本正确。
- [ ] 安装器产品版本和文件名正确。
- [ ] 已记录安装包大小和最终 SHA-256。
- [ ] 默认模型校验通过。

### 安装与升级

- [ ] 全新安装通过。
- [ ] 上一正式版本覆盖升级通过。
- [ ] 同版本重新安装通过。
- [ ] 用户数据保留验证通过。
- [ ] 旧 `_internal` 无残留。
- [ ] PA、DTOA 模型加载和预热通过。
- [ ] 卸载保留及删除用户数据行为符合预期。

### 正式发布

- [ ] 依赖和模型分发授权已确认。
- [ ] 代码签名要求已满足或已明确接受未签名风险。
- [ ] 发布说明、安装包、标签和哈希版本一致。
- [ ] 已保留上一正式版本和经验证的回滚资料。
- [ ] Git 分支和版本标签已推送。
