; ══════════════════════════════════════════════════════════════════════════════
; Lily - Assistente Vocale — Inno Setup Installer
; ══════════════════════════════════════════════════════════════════════════════

#define MyAppName      "Lily"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "AmMstools"
#define MyAppURL       "https://github.com/AmMstools"
#define MyAppExeName   "Lily.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=Lily_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableWelcomePage=no
LicenseFile=
MinVersion=10.0

; Installa senza admin se possibile (AppData), con override per Program Files
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "italian";  MessagesFile: "compiler:Languages\Italian.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}";  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Avvia Lily all'accensione del PC"; GroupDescription: "Avvio automatico:"; Flags: unchecked

[Files]
; Copia tutto il contenuto della cartella PyInstaller onedir
Source: "dist\Lily\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Modello Whisper large-v3 → AppData dell'utente (skip se già presente)
Source: "models\faster-whisper-large-v3\*"; DestDir: "{userappdata}\AmMstools\Lily\models\faster-whisper-large-v3"; Flags: ignoreversion onlyifdoesntexist recursesubdirs createallsubdirs

[Icons]
; Menu Start
Name: "{group}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Disinstalla {#MyAppName}";   Filename: "{uninstallexe}"
; Desktop (opzionale)
Name: "{userdesktop}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Startup (opzionale)
Name: "{userstartup}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Lancia l'app dopo l'installazione
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Pulisci modello e configurazione alla disinstallazione
Type: filesandordirs; Name: "{userappdata}\AmMstools\Lily\models"
; Impostazioni (commentato di default — decommenta per pulire tutto)
; Type: filesandordirs; Name: "{userappdata}\AmMstools\Lily"
