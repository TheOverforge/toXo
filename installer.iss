[Setup]
AppId={{A3F2B1C4-7E89-4D2A-B6F3-1C8E9D0A2B5F}
AppName=toXo
AppVersion=1.0
AppPublisher=TheOverforge
DefaultDirName={autopf}\toXo
DefaultGroupName=toXo
OutputDir=installer_output
OutputBaseFilename=toXo_Setup
SetupIconFile=shared\assets\images\app_icon.ico
UninstallDisplayIcon={app}\toXo.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Show language selection dialog at startup
ShowLanguageDialog=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\toXo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\toXo"; Filename: "{app}\toXo.exe"
Name: "{commondesktop}\toXo"; Filename: "{app}\toXo.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional tasks:"

[Run]
Filename: "{app}\toXo.exe"; Description: "Launch toXo"; Flags: nowait postinstall skipifsilent

[Code]
// After installation completes — write the chosen language into the app's QSettings registry key.
// QSettings("todo_app", "todo_mvp") on Windows stores at HKCU\Software\todo_app\todo_mvp
procedure CurStepChanged(CurStep: TSetupStep);
var
  LangValue: String;
begin
  if CurStep = ssPostInstall then
  begin
    if ActiveLanguage = 'ru' then
      LangValue := 'ru'
    else
      LangValue := 'en';

    RegWriteStringValue(
      HKEY_CURRENT_USER,
      'Software\todo_app\todo_mvp',
      'language',
      LangValue
    );
  end;
end;
