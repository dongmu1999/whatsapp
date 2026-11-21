; SalesPilot AI NSIS 安装脚本（按当前用户安装，无需管理员权限）
; 在 Linux 上使用 makensis 3.x 交叉生成 Windows 安装包。
Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

!ifndef MyAppVersion
  !define MyAppVersion "1.0.0"
!endif
!ifndef MyAppVersionFull
  !define MyAppVersionFull "1.0.0.0"
!endif
!ifndef SourceDir
  !define SourceDir "../dist/SalesPilotAI"
!endif
!ifndef OutputFile
  !define OutputFile "../dist/installer/SalesPilotAI-Setup-1.0.0.exe"
!endif
!ifndef IconFile
  !define IconFile "../assets/salespilot.ico"
!endif

!define MyAppName "SalesPilot AI"
!define MyAppNameZh "WhatsApp 外贸销售智能助手"
!define MyAppPublisher "SalesPilot"
!define MyAppExeName "SalesPilotAI.exe"
!define AppRegistryKey "Software\Microsoft\Windows\CurrentVersion\Uninstall\SalesPilotAI"

Name "${MyAppName} ${MyAppVersion}"
OutFile "${OutputFile}"
InstallDir "$LOCALAPPDATA\Programs\SalesPilotAI"
InstallDirRegKey HKCU "Software\SalesPilotAI" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32

VIProductVersion "${MyAppVersionFull}"
VIAddVersionKey /LANG=2052 "ProductName" "${MyAppName}"
VIAddVersionKey /LANG=2052 "FileDescription" "${MyAppNameZh} 安装程序"
VIAddVersionKey /LANG=2052 "CompanyName" "${MyAppPublisher}"
VIAddVersionKey /LANG=2052 "LegalCopyright" "Copyright (C) 2026 ${MyAppPublisher}"
VIAddVersionKey /LANG=2052 "FileVersion" "${MyAppVersionFull}"
VIAddVersionKey /LANG=2052 "ProductVersion" "${MyAppVersion}"

!define MUI_ABORTWARNING
!define MUI_ICON "${IconFile}"
!define MUI_UNICON "${IconFile}"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${MyAppExeName}"
!define MUI_FINISHPAGE_RUN_TEXT "启动 ${MyAppName}"
!define MUI_FINISHPAGE_NOREBOOTSUPPORT

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "SalesPilot AI 主程序（必需）" SEC_MAIN
  SectionIn RO
  SetShellVarContext current
  SetOutPath "$INSTDIR"

  ; 升级时清理旧版 PyInstaller 运行时，避免残留旧 DLL；用户数据在独立目录中。
  RMDir /r "$INSTDIR\_internal"
  File /r "${SourceDir}\*.*"

  WriteRegStr HKCU "Software\SalesPilotAI" "InstallLocation" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\${MyAppName}"
  CreateShortCut "$SMPROGRAMS\${MyAppName}\${MyAppName}.lnk" "$INSTDIR\${MyAppExeName}" "" "$INSTDIR\${MyAppExeName}" 0
  CreateShortCut "$SMPROGRAMS\${MyAppName}\卸载 ${MyAppName}.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegStr HKCU "${AppRegistryKey}" "DisplayName" "${MyAppName} ${MyAppVersion}"
  WriteRegStr HKCU "${AppRegistryKey}" "DisplayVersion" "${MyAppVersion}"
  WriteRegStr HKCU "${AppRegistryKey}" "DisplayIcon" "$INSTDIR\${MyAppExeName}"
  WriteRegStr HKCU "${AppRegistryKey}" "Publisher" "${MyAppPublisher}"
  WriteRegStr HKCU "${AppRegistryKey}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${AppRegistryKey}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${AppRegistryKey}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${AppRegistryKey}" "EstimatedSize" $0
  WriteRegDWORD HKCU "${AppRegistryKey}" "NoModify" 1
  WriteRegDWORD HKCU "${AppRegistryKey}" "NoRepair" 1
SectionEnd

Section "创建桌面快捷方式" SEC_DESKTOP
  SetShellVarContext current
  CreateShortCut "$DESKTOP\${MyAppName}.lnk" "$INSTDIR\${MyAppExeName}" "" "$INSTDIR\${MyAppExeName}" 0
SectionEnd

LangString DESC_SEC_MAIN ${LANG_SIMPCHINESE} "安装 SalesPilot AI 主程序、开始菜单快捷方式和卸载程序。"
LangString DESC_SEC_DESKTOP ${LANG_SIMPCHINESE} "在桌面创建 SalesPilot AI 快捷方式。"

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_MAIN} $(DESC_SEC_MAIN)
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} $(DESC_SEC_DESKTOP)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function CheckAppRunning
  check:
  nsExec::ExecToStack '"$SYSDIR\tasklist.exe" /FI "IMAGENAME eq SalesPilotAI.exe" /NH /FO CSV'
  Pop $0
  Pop $1
  StrCpy $2 $1 17
  StrCmp $2 '"SalesPilotAI.exe' 0 done
  MessageBox MB_ICONEXCLAMATION|MB_RETRYCANCEL|MB_DEFBUTTON2 \
    "SalesPilot AI 正在运行，无法覆盖安装文件。$\r$\n$\r$\n请先在任务管理器中结束所有 SalesPilotAI.exe，然后点击“重试”。" \
    IDRETRY check
  Abort
  done:
FunctionEnd

Function CheckInstallDirWritable
  IfFileExists "$INSTDIR\_internal\VCRUNTIME140.dll" 0 done
  ClearErrors
  FileOpen $0 "$INSTDIR\_internal\VCRUNTIME140.dll" a
  IfErrors locked
  FileClose $0
  Goto done

  locked:
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\SalesPilotAI-1.0.0"
  IfSilent +2
  MessageBox MB_ICONINFORMATION "检测到旧安装目录中的文件被占用，本次将安装到：$\r$\n$INSTDIR$\r$\n$\r$\n原有客户数据和备份不会受到影响。"

  done:
FunctionEnd

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "本安装包仅支持 64 位 Windows 10/11。"
    Abort
  ${EndIf}
  SetShellVarContext current
  Call CheckAppRunning
  Call CheckInstallDirWritable
FunctionEnd

Section "Uninstall"
  SetShellVarContext current

  Delete "$SMPROGRAMS\${MyAppName}\${MyAppName}.lnk"
  Delete "$SMPROGRAMS\${MyAppName}\卸载 ${MyAppName}.lnk"
  RMDir "$SMPROGRAMS\${MyAppName}"
  Delete "$DESKTOP\${MyAppName}.lnk"

  ; 只删除程序安装目录。客户数据库、日志、备份、知识库副本和凭据
  ; 位于 %LOCALAPPDATA%\SalesPilotAI，卸载时有意保留。
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${MyAppExeName}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "${AppRegistryKey}"
  DeleteRegKey HKCU "Software\SalesPilotAI"

  MessageBox MB_ICONINFORMATION "SalesPilot AI 已卸载。$\r$\n本地数据仍保留在：$\r$\n%LOCALAPPDATA%\SalesPilotAI"
SectionEnd
