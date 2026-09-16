#define MyAppName "FMES Scheduler"
#define MyAppPublisher "Monett Metals"

#ifndef SourceReleaseDir
  #error SourceReleaseDir define is required. Example: /DSourceReleaseDir="C:\\Path\\to\\release_YYYYMMDD_HHMMSS"
#endif

#ifndef RepoRoot
  #error RepoRoot define is required. Example: /DRepoRoot="C:\\Path\\to\\SchedulerProgram"
#endif

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#ifndef MyBuildLabel
  #define MyBuildLabel "manual"
#endif

[Setup]
AppId={{EE9DF1CB-D13C-4A7D-9D93-9FC2D1488D65}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FMES Scheduler
DefaultGroupName=FMES Scheduler
DisableProgramGroupPage=yes
OutputDir={#SourceReleaseDir}
OutputBaseFilename=FMES_Scheduler_Setup_{#MyBuildLabel}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Scheduler.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicons"; Description: "Create desktop shortcuts"; GroupDescription: "Additional tasks:"; Flags: unchecked

[Files]
Source: "{#SourceReleaseDir}\Scheduler_*.exe"; DestDir: "{app}"; DestName: "Scheduler.exe"; Flags: ignoreversion
Source: "{#SourceReleaseDir}\SchedulerUpdateOnly_*.exe"; DestDir: "{app}"; DestName: "SchedulerUpdateOnly.exe"; Flags: ignoreversion
Source: "{#RepoRoot}\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
Source: "{#RepoRoot}\readme.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\installer\FirstRun-Checklist.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\FMES Scheduler\FMES Scheduler (Full)"; Filename: "{app}\Scheduler.exe"
Name: "{autoprograms}\FMES Scheduler\FMES Scheduler (Update Only)"; Filename: "{app}\SchedulerUpdateOnly.exe"
Name: "{autodesktop}\FMES Scheduler (Full)"; Filename: "{app}\Scheduler.exe"; Tasks: desktopicons
Name: "{autodesktop}\FMES Scheduler (Update Only)"; Filename: "{app}\SchedulerUpdateOnly.exe"; Tasks: desktopicons

[Run]
Filename: "{app}\FirstRun-Checklist.txt"; Description: "Open first-run checklist"; Flags: postinstall shellexec skipifsilent

[Code]
function IsOdbc17Installed(): Boolean;
var
  Value: string;
begin
  Result :=
    (RegQueryStringValue(HKLM64, 'SOFTWARE\\ODBC\\ODBCINST.INI\\ODBC Drivers', 'ODBC Driver 17 for SQL Server', Value) and (CompareText(Value, 'Installed') = 0))
    or
    (RegQueryStringValue(HKLM32, 'SOFTWARE\\ODBC\\ODBCINST.INI\\ODBC Drivers', 'ODBC Driver 17 for SQL Server', Value) and (CompareText(Value, 'Installed') = 0));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Missing: string;
  Prompt: string;
begin
  Result := True;

  if CurPageID = wpReady then begin
    Missing := '';

    if not IsOdbc17Installed() then
      Missing := Missing + '- Microsoft ODBC Driver 17 for SQL Server is not installed.' + #13#10;

    if Missing <> '' then begin
      Prompt :=
        'Setup detected missing prerequisites:' + #13#10 + #13#10 +
        Missing + #13#10 +
        'Click Yes to continue anyway, or No to cancel and install prerequisites first.';

      Result := MsgBox(Prompt, mbConfirmation, MB_YESNO) = IDYES;
    end;
  end;
end;
