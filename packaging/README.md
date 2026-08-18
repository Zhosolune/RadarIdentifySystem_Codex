# Windows 打包说明

## 构建

在仓库根目录执行：

```powershell
.\packaging\build.ps1 -Version 0.1.0
```

脚本依次执行默认模型校验、`uv sync --locked`、多尺寸 ICO 转换、
PyInstaller `onedir/windowed` 构建和 Inno Setup 安装包编译。

冻结程序通过 PyInstaller runtime hook 在 Qt 之前预加载 ONNX Runtime，
避免两者携带的 MSVC Runtime DLL 因加载顺序发生冲突。构建产物保留各依赖
收集到的运行库，不依赖安装器强制校验目标机器上的特定 VC++ 运行库版本。

仅验证 PyInstaller 目录产物时执行：

```powershell
.\packaging\build.ps1 -Version 0.1.0 -SkipInstaller
```

## 输出

- `dist/RadarIdentifySystem/`：PyInstaller onedir 产物。
- `artifacts/RadarIdentifySystem-Setup-<版本>.exe`：按用户安装包。

安装目录为 `%LOCALAPPDATA%\Programs\RadarIdentifySystem`，用户数据位于
`%LOCALAPPDATA%\RadarIdentifySystem`。卸载默认保留用户数据，只有用户在
卸载完成时明确确认才会删除。

## 发布阻断项

正式分发前必须确认 PyQt6、PyQt6-Fluent-Widgets、
PyQt6-Frameless-Window 以及默认 ONNX 模型的再分发授权。当前依赖为 CPU
版 `onnxruntime`，安装包不得宣称内置 GPU 推理支持。
