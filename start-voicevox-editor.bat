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

rem IRODORI-VOICE を起動します。エンジンはエディタが子プロセスとして起動するため、
rem このバッチ 1 つで完結します。エディタを閉じるとエンジンも一緒に終了します。

set "ROOT=%~dp0"
set "DEST=%ROOT%editor-voicevox"
set "PORT=50121"

if not exist "%DEST%\package.json" (
  echo VOICEVOX エディタが用意されていません。
  echo setup-voicevox-editor.bat を先に実行してください。
  pause
  exit /b 1
)

rem --- エンジンの起動方法を決めます ---------------------------------------
rem エディタへ渡す値は絶対パスにする。エディタは相対パスをカレントディレクトリ
rem 基準で解決するため、どこから起動されたかに依存させたくない。
for %%I in ("%ROOT%runtime\Scripts\python.exe") do set "CAND_RUNTIME=%%~fI"
for %%I in ("%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe") do set "CAND_VENV=%%~fI"
for %%I in ("%ROOT%engine\dist\irodori-voice-engine\irodori-voice-engine.exe") do set "CAND_EXE=%%~fI"
for %%I in ("%ROOT%engine\run_engine.py") do set "ENGINE_SCRIPT=%%~fI"

set "ENGINE_PYTHON="
if exist "%CAND_RUNTIME%" set "ENGINE_PYTHON=%CAND_RUNTIME%"
if not defined ENGINE_PYTHON if exist "%CAND_VENV%" set "ENGINE_PYTHON=%CAND_VENV%"
if not defined ENGINE_PYTHON call :find_python

rem Python があればソースから起動する（エンジンを直した内容がそのまま反映される）。
rem 無ければ、固めた実行ファイルへ落とす。
set "ENGINE_FILE="
set "ENGINE_ARGS=[]"
if defined ENGINE_PYTHON set "ENGINE_FILE=%ENGINE_PYTHON%"
if not defined ENGINE_FILE if exist "%CAND_EXE%" set "ENGINE_FILE=%CAND_EXE%"

if not defined ENGINE_FILE (
  echo エンジンを起動する方法が見つかりません。
  echo Irodori-TTS/.venv を用意するか、build-engine.bat で実行ファイルを作ってください。
  pause
  exit /b 1
)

rem JSON へ埋めるため区切りを / にする。\ は JSON のエスケープ記号と衝突する。
set "ENGINE_FILE_JSON=%ENGINE_FILE:\=/%"
set "ENGINE_SCRIPT_JSON=%ENGINE_SCRIPT:\=/%"
if defined ENGINE_PYTHON set "ENGINE_ARGS=["%ENGINE_SCRIPT_JSON%"]"

rem エディタは process.env を .env より優先して読む。ここで上書きすることで、
rem .env に環境依存の絶対パスを書き残さずに済む。
set "VITE_DEFAULT_ENGINE_INFOS=[{"uuid": "0b2a5f31-9c4d-4f6a-8e7b-3d1c5a9f2e40", "name": "IRODORI-VOICE Engine", "executionEnabled": true, "executionFilePath": "%ENGINE_FILE_JSON%", "executionArgs": %ENGINE_ARGS%, "host": "http://127.0.0.1:%PORT%"}]"

echo エンジン: %ENGINE_FILE%
if defined ENGINE_PYTHON echo スクリプト: %ENGINE_SCRIPT%

rem 既に誰かが待ち受けていると、エディタは別のポートへ 2 つ目を立ち上げる。
rem そのとき %PORT% を見ている外部ツールは古い方へ繋がるため、先に知らせる。
netstat -ano -p tcp | findstr /c:":%PORT% " | findstr /c:"LISTENING" > nul 2>&1
if not errorlevel 1 (
  echo.
  echo 注意: ポート %PORT% は既に使われています。start-engine.bat で起動したエンジンが
  echo       残っている場合は、そちらを閉じてからやり直してください。このまま進むと
  echo       エディタは別のポートへもう 1 つエンジンを起動します。
  echo.
)

rem VSCode のターミナルなどでは ELECTRON_RUN_AS_NODE が設定されていることがあり、
rem そのままだと Electron が Node として起動して失敗します。
set "ELECTRON_RUN_AS_NODE="

cd /d "%DEST%"
call pnpm run electron:serve

endlocal
exit /b %errorlevel%

rem PATH の python を 1 つ目だけ採る。for の中で goto :eof すると、そこで打ち切れる。
:find_python
for /f "delims=" %%I in ('where python 2^>nul') do (
  set "ENGINE_PYTHON=%%~fI"
  goto :eof
)
goto :eof
