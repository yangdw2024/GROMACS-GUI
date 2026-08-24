; ============================================================================
; GROMACS GUI v4.3.0 Inno Setup 安装脚本
; 生成专业的 exe 安装程序
; ============================================================================

#define MyAppName "GROMACS GUI"
#define MyAppFullName "GROMACS 动力学模拟与分析集成工具"
#define MyAppVersion "4.3.0"
#define MyAppPublisher "Trae"
#define MyAppURL "https://github.com/Trae/GROMACS-GUI"
#define MyAppExeName "GROMACS_GUI_v4.3.0.exe"
#define MyAppIcon "app_icon.ico"

[Setup]
; 基本设置
AppId={{GROMACS-GUI-v4-3-0-Trae}}
AppName={#MyAppName}
AppVerName={#MyAppName} {#MyAppVersion}
AppCopyright=Copyright (c) 2026 Trae. All rights reserved.
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppContact=Trae

; 版本信息
VersionInfoVersion=4.3.0.0
VersionInfoCompany=Trae
VersionInfoDescription=GROMACS 动力学模拟与分析集成工具
VersionInfoTextVersion=4.3.0
VersionInfoProductVersion=4.3.0.0
VersionInfoProductName=GROMACS GUI

; 安装目录
DefaultDirName={autopf}\GROMACS_GUI
DefaultGroupName=GROMACS GUI
DisableProgramGroupPage=yes

; 安装程序外观
SetupIconFile=D:\YDW\Trae_Gromacs\resources\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; 卸载设置
UninstallDisplayIcon={app}\GROMACS_GUI_v4.3.0.exe
UninstallDisplayName=GROMACS GUI v4.3.0

; 输出设置
OutputDir=D:\YDW\Trae_Gromacs\release
OutputBaseFilename=GROMACS_GUI_v4.3.0_Setup

; 磁盘空间要求 (约2GB)
DiskSpanning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "在桌面上创建快捷方式"; GroupDescription: "附加图标: "
Name: "quicklaunchicon"; Description: "在快速启动栏创建快捷方式"; GroupDescription: "附加图标: "

[Files]
; 主程序及依赖
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\GROMACS_GUI_v4.3.0.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; 资源文件
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs

; 配置文件
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

; 版本配置
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\version.config"; DestDir: "{app}"; Flags: ignoreversion

; 说明书
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\说明书.md"; DestDir: "{app}"; Flags: ignoreversion

; GROMACS 程序
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\gromacs\*"; DestDir: "{app}\gromacs"; Flags: ignoreversion recursesubdirs createallsubdirs

; 启动脚本
Source: "D:\YDW\Trae_Gromacs\dist\GROMACS_GUI_v4.3.0\启动GROMACS_GUI_v4.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GROMACS GUI"; Filename: "{app}\GROMACS_GUI_v4.3.0.exe"; IconFilename: "{app}\GROMACS_GUI_v4.3.0.exe"; Comment: "启动 GROMACS GUI v4.3.0"
Name: "{group}\启动GROMACS GUI (推荐)"; Filename: "{app}\启动GROMACS_GUI_v4.bat"; IconFilename: "{app}\GROMACS_GUI_v4.3.0.exe"; Comment: "通过启动脚本启动 (自动配置GROMACS环境变量)"
Name: "{group}\使用说明书"; Filename: "{app}\说明书.md"; Comment: "查看使用说明书"
Name: "{group}\卸载 GROMACS GUI"; Filename: "{uninstallexe}"; Comment: "卸载 GROMACS GUI v4.3.0"
Name: "{commondesktop}\GROMACS GUI"; Filename: "{app}\启动GROMACS_GUI_v4.bat"; IconFilename: "{app}\GROMACS_GUI_v4.3.0.exe"; Tasks: desktopicon; Comment: "启动 GROMACS GUI v4.3.0"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\GROMACS GUI"; Filename: "{app}\启动GROMACS_GUI_v4.bat"; IconFilename: "{app}\GROMACS_GUI_v4.3.0.exe"; Tasks: quicklaunchicon; Comment: "启动 GROMACS GUI v4.3.0"

[Run]
; 移除自动启动，避免安装后自动运行导致多实例问题

[Code]
function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  // 检查是否为 64 位 Windows
  if not IsWin64 then
  begin
    MsgBox('GROMACS GUI 需要 64 位 Windows 系统。', mbError, MB_OK);
    Result := False;
    exit;
  end;
  
  // 检查 Windows 版本 (至少需要 Windows 10)
  if (Version.Major < 10) then
  begin
    MsgBox('GROMACS GUI 需要 Windows 10 或更高版本。', mbError, MB_OK);
    Result := False;
    exit;
  end;
  
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // 安装完成后添加系统环境变量 (GROMACS bin 目录)
    RegWriteStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'GROMACS_GUI_HOME', ExpandConstant('{app}'));
    
    // 添加 GROMACS bin 到 PATH (用户级别)
    // 注意: 不自动添加到系统 PATH，避免影响其他软件
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // 卸载时删除环境变量
    RegDeleteValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'GROMACS_GUI_HOME');
  end;
end;
