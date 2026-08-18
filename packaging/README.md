# Windows 打包说明

## 构建

在仓库根目录执行：

```powershell
.\packaging\build.ps1
```

脚本依次执行默认模型校验、`uv sync --locked`、多尺寸 ICO 转换、
PyInstaller `onedir/windowed` 构建和 Inno Setup 安装包编译。
应用版本只在根目录 `pyproject.toml` 的 `[project].version` 中维护，构建脚本
会据此生成 EXE 版本资源、安装器版本和安装包文件名，不再接受独立版本参数。

构建脚本依次从显式参数、`PATH`、Inno Setup 卸载注册表和系统默认目录
查找 `ISCC.exe`。自定义安装目录也可以直接指定：

```powershell
.\packaging\build.ps1 `
    -IsccPath "D:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

`-IsccPath` 也接受包含 `ISCC.exe` 的 Inno Setup 安装目录。

冻结程序通过 PyInstaller runtime hook 在 Qt 之前预加载 ONNX Runtime，
避免两者携带的 MSVC Runtime DLL 因加载顺序发生冲突。构建产物保留各依赖
收集到的运行库，不依赖安装器强制校验目标机器上的特定 VC++ 运行库版本。

仅验证 PyInstaller 目录产物时执行：

```powershell
.\packaging\build.ps1 -SkipInstaller
```

## 输出

- `dist/RadarIdentifySystem/`：PyInstaller onedir 产物。
- `artifacts/RadarIdentifySystem-Setup-<版本>.exe`：按用户安装包。

安装目录为 `%LOCALAPPDATA%\Programs\RadarIdentifySystem`，用户数据位于
`%LOCALAPPDATA%\RadarIdentifySystem`。卸载默认保留用户数据，只有用户在
卸载完成时明确确认才会删除。

## 版本升级

发布新版本时，先修改 `pyproject.toml` 中的 `[project].version`，再重新执行
构建脚本。将生成的新版本完整安装包提供给用户，用户关闭应用后直接运行即可，
无需先卸载旧版本。

安装器使用固定 `AppId` 和安装目录进行覆盖升级。写入新文件前只清理
`{app}\_internal`，防止已删除或改名的 DLL、PYD 和 Python 包残留；不会清理
`%LOCALAPPDATA%\RadarIdentifySystem`，因此配置、日志、Session、数据池、用户模型
和缓存会继续保留。当前安装包体积适合完整覆盖升级，不维护 PyInstaller 二进制
差分补丁。

## 发布阻断项

正式分发前必须确认 PyQt6、PyQt6-Fluent-Widgets、
PyQt6-Frameless-Window 以及默认 ONNX 模型的再分发授权。当前依赖为 CPU
版 `onnxruntime`，安装包不得宣称内置 GPU 推理支持。
