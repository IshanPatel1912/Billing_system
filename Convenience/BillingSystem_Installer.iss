[Setup]
AppName=BillingSystem
AppVersion=1.0
DefaultDirName={pf}\BillingSystem
DefaultGroupName=BillingSystem
OutputDir=Installer
OutputBaseFilename=BillingSystem_Installer
Compression=lzma
SolidCompression=yes
; --- ADDS ICON TO THE INSTALLER ITSELF ---
SetupIconFile=app_icon.ico 

[Files]
Source: "dist\BillingSystem.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Installer\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
; --- COPIES THE ICON TO THE INSTALL FOLDER ---
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; --- APPLIES THE ICON TO YOUR SHORTCUTS ---
Name: "{group}\BillingSystem"; Filename: "{app}\BillingSystem.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{commondesktop}\BillingSystem"; Filename: "{app}\BillingSystem.exe"; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; StatusMsg: "Installing Visual C++ Redistributables..."; Flags: runhidden
Filename: "{app}\BillingSystem.exe"; Description: "Launch BillingSystem"; Flags: nowait postinstall