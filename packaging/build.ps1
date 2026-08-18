param(
    [string]$Version = "0.1.0",
    [switch]$SkipSync,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $ProjectRoot "build\packaging"
$ArtifactRoot = Join-Path $ProjectRoot "artifacts"
$ManifestPath = Join-Path $PSScriptRoot "model-manifest.json"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PyInstallerPath = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"
$IconSource = Join-Path $ProjectRoot "resources\images\icon.png"
$IconTarget = Join-Path $BuildRoot "icon.ico"

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

$IsccCommand = Get-Command iscc.exe -ErrorAction SilentlyContinue
if ($null -eq $IsccCommand) {
    $DefaultIscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $DefaultIscc -PathType Leaf) {
        $IsccPath = $DefaultIscc
    } else {
        throw "未找到 Inno Setup 6。安装后重试，或使用 -SkipInstaller 仅构建 onedir。"
    }
} else {
    $IsccPath = $IsccCommand.Source
}

& $IsccPath "/DMyAppVersion=$Version" (Join-Path $PSScriptRoot "RadarIdentifySystem.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup 安装包构建失败"
}

Write-Host "安装包构建完成：$ArtifactRoot"
