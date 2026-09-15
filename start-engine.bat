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

rem IRODORI-VOICE エンジンだけを起動します。
rem VOICEVOX エディタから使う場合は、先にこれを起動しておいてください。

set "ROOT=%~dp0"
set "PORT=50121"

set "PYTHON="
if exist "%ROOT%runtime\Scripts\python.exe" set "PYTHON=%ROOT%runtime\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe" set "PYTHON=%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe"
if not defined PYTHON set "PYTHON=python"

echo IRODORI-VOICE エンジンを起動します（ポート %PORT%）。
echo VOICEVOX ENGINE 互換 API として動作します。

set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
"%PYTHON%" "%ROOT%engine\run_engine.py" --host 127.0.0.1 --port %PORT%

endlocal
