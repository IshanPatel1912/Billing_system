[Setup]
AppName=BillingSystem
AppVersion=3.0
DefaultDirName={pf}\BillingSystem
DefaultGroupName=BillingSystem
OutputDir=Installer
OutputBaseFilename=BillingSystem_Installer_3.0
Compression=lzma
SolidCompression=yes
SetupIconFile=app_icon.ico

[Files]
Source: "dist\BillingSystem.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Installer\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\BillingSystem"; Filename: "{app}\BillingSystem.exe"
Name: "{commondesktop}\BillingSystem"; Filename: "{app}\BillingSystem.exe"

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; StatusMsg: "Installing Visual C++ Redistributables..."; Flags: runhidden
Filename: "{app}\BillingSystem.exe"; Description: "Launch BillingSystem"; Flags: nowait postinstall