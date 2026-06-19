#define MyAppName "Lax Scheduler Export"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Lax Scheduler"
#define MyAppExeName "LaxSchedulerExport.exe"

[Setup]
AppId={{A4B8C2D1-9E3F-4A5B-8C7D-1E2F3A4B5C6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\LaxSchedulerExport
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=LaxSchedulerExport-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\LaxSchedulerExport\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ConnectionPage: TInputQueryWizardPage;
  ConfigureLaterCheck: TNewCheckBox;

function IsValidPostgresUrl(const Url: String): Boolean;
var
  LowerUrl: String;
begin
  LowerUrl := LowerCase(Trim(Url));
  Result := (LowerUrl <> '') and
    ((Pos('postgresql://', LowerUrl) = 1) or (Pos('postgres://', LowerUrl) = 1)) and
    (Pos('@', LowerUrl) > 0) and
    (Pos('/', Copy(LowerUrl, Pos('://', LowerUrl) + 3, MaxInt)) > 0);
end;

function JsonEscape(const Value: String): String;
var
  I: Integer;
  Ch: Char;
begin
  Result := '';
  for I := 1 to Length(Value) do
  begin
    Ch := Value[I];
    case Ch of
      '\': Result := Result + '\\';
      '"': Result := Result + '\"';
      Chr(8): Result := Result + '\b';
      Chr(9): Result := Result + '\t';
      Chr(10): Result := Result + '\n';
      Chr(13): Result := Result + '\r';
      Chr(12): Result := Result + '\f';
    else
      if Ord(Ch) < 32 then
        Result := Result + '\u' + IntToHex(Ord(Ch), 4)
      else
        Result := Result + Ch;
    end;
  end;
end;

procedure InitializeWizard;
begin
  ConnectionPage := CreateInputQueryPage(wpSelectDir,
    'Database Connection',
    'Paste your readonly PostgreSQL connection string',
    'Use the readonly connection string provided by your administrator. ' +
    'This is not your Neon owner password.');

  ConnectionPage.Add('Connection string:', False);
  ConnectionPage.Values[0] := '';
  ConnectionPage.Edits[0].PasswordChar := '#';

  ConfigureLaterCheck := TNewCheckBox.Create(ConnectionPage);
  ConfigureLaterCheck.Parent := ConnectionPage.Surface;
  ConfigureLaterCheck.Caption := 'Configure later (skip writing config.json)';
  ConfigureLaterCheck.Top := ConnectionPage.Edits[0].Top + ConnectionPage.Edits[0].Height + 12;
  ConfigureLaterCheck.Left := ConnectionPage.Edits[0].Left;
  ConfigureLaterCheck.Width := ConnectionPage.Surface.Width;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ConnectionPage.ID then
  begin
    if not ConfigureLaterCheck.Checked then
    begin
      if not IsValidPostgresUrl(ConnectionPage.Values[0]) then
      begin
        MsgBox('Enter a valid PostgreSQL connection string starting with postgresql:// or postgres://',
          mbError, MB_OK);
        Result := False;
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath: String;
  ConfigContent: String;
  Url: String;
begin
  if CurStep = ssPostInstall then
  begin
    if ConfigureLaterCheck.Checked then
      Exit;

    Url := Trim(ConnectionPage.Values[0]);
    if Url = '' then
      Exit;

    ConfigPath := ExpandConstant('{app}\config.json');
    ConfigContent := '{' + Chr(13) + Chr(10) +
      '  "database_url": "' + JsonEscape(Url) + '"' + Chr(13) + Chr(10) +
      '}' + Chr(13) + Chr(10);
    SaveStringToFile(ConfigPath, ConfigContent, False);
  end;
end;
