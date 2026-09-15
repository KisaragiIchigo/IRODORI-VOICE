@echo off
rem Switch the console to UTF-8, then re-read this file. See the note under :body.
if "%~1"=="--utf8" goto :body
chcp 65001 > nul
cmd /c "%~f0" --utf8
exit /b %errorlevel%

:body
setlocal

rem 上の 5 行について。ファイルの途中で chcp すると cmd の読み取り位置がずれ、
rem ここから下の日本語の行が途中で切れて、その後半が別のコマンドとして実行される。
rem そのため、先にコンソールを UTF-8 へ切り替えてから読み直させている。

rem IRODORI-VOICE エンジンを実行ファイルへまとめます。
rem これにより VOICEVOX エディタの executionEnabled を true にでき、
rem エディタを起動するだけでエンジンも自動的に立ち上がります。
rem
rem torch と DACVAE を含むため、出力は数 GB になります。
rem ビルドには 10 分以上かかります。

set "ROOT=%~dp0"

set "PYTHON="
if exist "%ROOT%runtime\Scripts\python.exe" set "PYTHON=%ROOT%runtime\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe" set "PYTHON=%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe"
if not defined PYTHON set "PYTHON=python"

"%PYTHON%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
  echo PyInstaller が導入されていません。
  echo 次を実行してください:  pip install pyinstaller
  pause
  exit /b 1
)

cd /d "%ROOT%engine"

echo エンジンをビルドします。10 分以上かかることがあります...
"%PYTHON%" -m PyInstaller irodori-voice-engine.spec --noconfirm --clean
if errorlevel 1 (
  echo ビルドに失敗しました。
  pause
  exit /b 1
)

echo.
echo ビルドが完了しました。
echo   出力: engine\dist\irodori-voice-engine\irodori-voice-engine.exe
echo.
echo エディタから自動起動させる場合は、voicevox-editor.env.template の
echo executionEnabled を true にし、executionFilePath に上記の exe への
echo パスを指定してから setup-voicevox-editor.bat を再実行してください。
echo.
pause

endlocal
