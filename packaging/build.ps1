param(
    [string]$IsccPath = "",
    [switch]$SkipSync,
    [switch]$SkipInstaller
)

function Resolve-InnoSetupCompiler {
    param(
        [string]$RequestedPath
    )

    # 显式路径优先，既允许传入 ISCC.exe，也允许传入 Inno Setup 安装目录。
    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        $ExplicitPath = $RequestedPath
        if (Test-Path -LiteralPath $ExplicitPath -PathType Container) {
            $ExplicitPath = Join-Path $ExplicitPath "ISCC.exe"
        }
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "指定的 Inno Setup 编译器不存在：$ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    # 优先复用 PATH 中可直接调用的编译器。
    $IsccCommand = Get-Command iscc.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($null -ne $IsccCommand) {
        return $IsccCommand.Source
    }

    # Inno Setup 会记录真实安装目录，可覆盖非系统盘和按用户安装场景。
    $RegistryKeys = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
    )
    foreach ($RegistryKey in $RegistryKeys) {
        if (-not (Test-Path -LiteralPath $RegistryKey)) {
            continue
        }
        $InstallLocation = (Get-ItemProperty -LiteralPath $RegistryKey).InstallLocation
        if ([string]::IsNullOrWhiteSpace($InstallLocation)) {
            continue
        }
        $RegistryIsccPath = Join-Path $InstallLocation "ISCC.exe"
        if (Test-Path -LiteralPath $RegistryIsccPath -PathType Leaf) {
            return (Resolve-Path -LiteralPath $RegistryIsccPath).Path
        }
    }

    # 最后兼容未写入注册表的标准安装目录。
    $ProgramRoots = @(${env:ProgramFiles(x86)}, $env:ProgramFiles) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($ProgramRoot in $ProgramRoots) {
        $DefaultIsccPath = Join-Path $ProgramRoot "Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $DefaultIsccPath -PathType Leaf) {
            return (Resolve-Path -LiteralPath $DefaultIsccPath).Path
        }
    }

    throw "未找到 Inno Setup 6。请使用 -IsccPath 指定 ISCC.exe，或使用 -SkipInstaller 仅构建 onedir。"
}

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $ProjectRoot "build\packaging"
$ArtifactRoot = Join-Path $ProjectRoot "artifacts"
$ManifestPath = Join-Path $PSScriptRoot "model-manifest.json"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PyInstallerPath = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"
$IconSource = Join-Path $ProjectRoot "resources\images\icon.png"
$IconTarget = Join-Path $BuildRoot "icon.ico"
$VersionResourcePath = Join-Path $BuildRoot "RadarIdentifySystem.version.txt"
$VersionScriptPath = Join-Path $PSScriptRoot "version_info.py"

Set-Location $ProjectRoot

# 构建前验证默认模型，禁止产出缺模型或模型内容漂移的安装包。
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
foreach ($Model in $Manifest.models) {
    $ModelPath = Join-Path $ProjectRoot ($Model.path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) {
        throw "缺少默认模型：$($Model.path)"
    }
    $ModelFile = Get-Item -LiteralPath $ModelPath
    if ($ModelFile.Length -ne [int64]$Model.size) {
        throw "默认模型大小不匹配：$($Model.path)"
    }
    $ActualHash = (Get-FileHash -LiteralPath $ModelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualHash -ne $Model.sha256.ToLowerInvariant()) {
        throw "默认模型 SHA-256 不匹配：$($Model.path)"
    }
}

if (-not $SkipSync) {
    uv sync --locked --group test --group build --cache-dir .uv-cache
    if ($LASTEXITCODE -ne 0) {
        throw "uv 依赖同步失败"
    }
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "未找到构建环境 Python，请先执行 uv sync --locked --group build"
}
if (-not (Test-Path -LiteralPath $PyInstallerPath -PathType Leaf)) {
    throw "未找到 PyInstaller，请先同步 build 依赖组"
}

New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null

# 以 pyproject.toml 为唯一版本源，构建时生成 Windows EXE 版本资源。
$VersionOutput = & $PythonPath $VersionScriptPath `
    --project-file (Join-Path $ProjectRoot "pyproject.toml") `
    --output-file $VersionResourcePath
if ($LASTEXITCODE -ne 0) {
    throw "应用版本资源生成失败"
}
$Version = [string]($VersionOutput | Select-Object -Last 1)
$Version = $Version.Trim()
if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "未能从 pyproject.toml 读取应用版本"
}
Write-Host "构建应用版本：$Version"

# 从现有 PNG 机械转换多尺寸 ICO，不改变图标视觉内容。
$IconScript = "from PIL import Image; image=Image.open(r'$IconSource').convert('RGBA'); image.save(r'$IconTarget', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
& $PythonPath -c $IconScript
if ($LASTEXITCODE -ne 0) {
    throw "应用图标转换失败"
}

& $PyInstallerPath --noconfirm --clean (Join-Path $PSScriptRoot "RadarIdentifySystem.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败"
}

if ($SkipInstaller) {
    Write-Host "onedir 构建完成：$ProjectRoot\dist\RadarIdentifySystem"
    exit 0
}

$ResolvedIsccPath = Resolve-InnoSetupCompiler -RequestedPath $IsccPath
Write-Host "使用 Inno Setup 编译器：$ResolvedIsccPath"
& $ResolvedIsccPath "/DMyAppVersion=$Version" (Join-Path $PSScriptRoot "RadarIdentifySystem.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup 安装包构建失败"
}

Write-Host "安装包构建完成：$ArtifactRoot"
