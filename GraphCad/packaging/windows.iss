; Inno Setup 6. Build from project root: ISCC packaging\windows.iss
#define MyAppName "GraphCad"
#define MyAppVersion "1.1.0"
[Setup]
AppId={{E326523E-7A80-4D75-AD4B-379613380F66}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\GraphCad
DefaultGroupName=GraphCad
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=GraphCad-1.1.0-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\GraphCad.exe
ChangesAssociations=yes
UsePreviousGroup=no
VersionInfoProductName=GraphCad
VersionInfoDescription=GraphCad Setup
VersionInfoProductVersion=1.1.0.0
; Keep the prior AppId and Graphite.Document ProgID for existing installations.
[InstallDelete]
Type: files; Name: "{app}\Graphite.exe"
Type: files; Name: "{userdesktop}\Graphite.lnk"
Type: files; Name: "{userprograms}\Graphite\Graphite.lnk"
[Files]
Source: "..\dist\GraphCad\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\GraphCad"; Filename: "{app}\GraphCad.exe"
Name: "{autodesktop}\GraphCad"; Filename: "{app}\GraphCad.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Registry]
Root: HKCU; Subkey: "Software\Classes\.graphite\OpenWithProgids"; ValueType: string; ValueName: "Graphite.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Graphite.Document"; ValueType: string; ValueData: "GraphCad Diagram"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Graphite.Document\shell\open\command"; ValueType: string; ValueData: """{app}\GraphCad.exe"" ""%1"""
[Run]
Filename: "{app}\GraphCad.exe"; Description: "Launch GraphCad"; Flags: nowait postinstall skipifsilent
