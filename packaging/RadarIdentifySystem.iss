#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#define MyAppName "RadarIdentifySystem"
#define MyAppExeName "RadarIdentifySystem.exe"

[Setup]
AppId={{7D2B1229-344B-47D8-A931-53B4CF8FE2EA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=RadarIdentifySystem
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\artifacts
OutputBaseFilename=RadarIdentifySystem-Setup-{#MyAppVersion}
SetupIconFile=..\build\packaging\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "..\dist\RadarIdentifySystem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStep(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    UserDataDir := ExpandConstant('{localappdata}\RadarIdentifySystem');
    if MsgBox(
      '是否同时删除配置、日志、Session、数据池和用户模型？' + #13#10 +
      '默认建议选择“否”，以便重新安装或升级后继续使用。',
      mbConfirmation,
      MB_YESNO
    ) = IDYES then
      DelTree(UserDataDir, True, True, True);
  end;
end;
