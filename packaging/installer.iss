; Inno Setup script for the Windows installer. Built by packaging\build.ps1.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7C1E4B52-9A3D-4F7E-B6A1-2D8F5C3E9B47}
AppName=FFHelper
AppVersion={#AppVersion}
AppPublisher=FFHelper
DefaultDirName={autopf}\FFHelper
DefaultGroupName=FFHelper
DisableProgramGroupPage=yes
; Per-user install: no admin prompt, and {userappdata} is the same user the app runs as.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=FFHelper-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ffhelper.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "ollama"; Description: "Download and install Ollama (runs the AI coach)"; Check: not OllamaInstalled

[Files]
Source: "..\dist\FFHelper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Starter settings and callouts: never overwritten by upgrades or removed by uninstall.
Source: "..\config.example.toml"; DestDir: "{userappdata}\FFHelper"; DestName: "config.toml"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\mechanics\*"; DestDir: "{userappdata}\FFHelper\mechanics"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\FFHelper"; Filename: "{app}\ffhelper.exe"; Parameters: "run"
Name: "{group}\Calibrate screen regions"; Filename: "{app}\ffhelper.exe"; Parameters: "calibrate"
Name: "{group}\Edit settings"; Filename: "{win}\notepad.exe"; Parameters: """{userappdata}\FFHelper\config.toml"""
Name: "{group}\Callouts folder"; Filename: "{userappdata}\FFHelper\mechanics"
Name: "{group}\Uninstall FFHelper"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FFHelper"; Filename: "{app}\ffhelper.exe"; Parameters: "run"; Tasks: desktopicon

[Run]
Filename: "{tmp}\OllamaSetup.exe"; StatusMsg: "Installing Ollama..."; Check: OllamaDownloaded; Flags: waituntilterminated
Filename: "{app}\ffhelper.exe"; Parameters: "calibrate"; Description: "Calibrate screen regions now (open FFXIV first)"; Flags: postinstall nowait skipifsilent unchecked

[Code]
var
  DownloadPage: TDownloadWizardPage;

function OllamaInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
    or (FileSearch('ollama.exe', GetEnv('PATH')) <> '');
end;

function OllamaDownloaded: Boolean;
begin
  Result := FileExists(ExpandConstant('{tmp}\OllamaSetup.exe'));
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsTaskSelected('ollama') then
  begin
    DownloadPage.Clear;
    DownloadPage.Add('https://ollama.com/download/OllamaSetup.exe', 'OllamaSetup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        if not DownloadPage.AbortedByUser then
          SuppressibleMsgBox('Could not download Ollama: ' + GetExceptionMessage + #13#10 +
            'FFHelper will still be installed. You can get Ollama later from ollama.com.',
            mbError, MB_OK, IDOK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;
