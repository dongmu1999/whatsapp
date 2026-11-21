; SalesPilot AI Inno Setup 6.5+ 安装脚本（按用户安装，无需管理员权限）
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\SalesPilotAI"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist\installer"
#endif
#define MyAppName "SalesPilot AI"
#define MyAppNameZh "WhatsApp 外贸销售智能助手"
#define MyAppPublisher "SalesPilot"
#define MyAppExeName "SalesPilotAI.exe"
#define MyAppVersionFull "1.0.0.0"

[Setup]
AppId={{6D3A9E1B-7C42-4F6B-9B8D-5A3E2C1F0A77}
AppName={#MyAppName}
AppVerName={#MyAppName} {#MyAppVersion}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments={#MyAppNameZh}
DefaultDirName={autopf}\SalesPilotAI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=SalesPilotAI-Setup-{#MyAppVersion}
SetupIconFile=..\assets\salespilot.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
VersionInfoVersion={#MyAppVersionFull}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoDescription={#MyAppNameZh}安装程序
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; 升级时清理旧版 PyInstaller 运行时；用户数据保存在独立数据目录，不在此安装目录。
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
