@echo off
rem Switch the console to UTF-8, then re-read this file.
if "%~1"=="--utf8" goto :body
chcp 65001 > nul
cmd /c ""%~f0" --utf8 %*"
exit /b %errorlevel%

:body
shift
setlocal enabledelayedexpansion

rem IRODORI-VOICE を起動します。エンジンはエディタが子プロセスとして起動するため、
rem このバッチ 1 つで完結します。エディタを閉じるとエンジンも一緒に終了します。

set ROOT=%~dp0
set DEST=%ROOT%editor-voicevox
set PORT=50121

rem --- エディタ環境の確認 ---------------------------------------------------
if not exist "%DEST%\package.json" (
  echo VOICEVOX エディタが準備されていません。
  echo 自動セットアップを開始します...
  call "%ROOT%01_setup-voicevox-editor.bat" --auto
  if not exist "%DEST%\package.json" (
    echo [エラー] エディタの準備が完了していません。
    pause
    exit /b 1
  )
)

rem --- エンジンの起動方法を決めます ---------------------------------------
for %%I in ("%ROOT%runtime\Scripts\python.exe") do set CAND_RUNTIME=%%~fI
for %%I in ("%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe") do set CAND_VENV=%%~fI
for %%I in ("%ROOT%engine\dist\irodori-voice-engine\irodori-voice-engine.exe") do set CAND_EXE=%%~fI
for %%I in ("%ROOT%engine\run_engine.py") do set ENGINE_SCRIPT=%%~fI

set ENGINE_PYTHON=

rem runtime の健全性チェック
if exist "%CAND_RUNTIME%" (
  "%CAND_RUNTIME%" -c "import sys; sys.path.insert(0, 'engine'); import torch, torchaudio, dacvae, silentcipher, fastapi, irodori_voice" >nul 2>&1
  if not errorlevel 1 (
    set ENGINE_PYTHON=%CAND_RUNTIME%
  ) else (
    echo runtime 仮想環境に不足しているライブラリがあります。自動更新します...
    call "%ROOT%00_setup-engine.bat" --auto
    if exist "%CAND_RUNTIME%" set ENGINE_PYTHON=%CAND_RUNTIME%
  )
)

rem 外部の Irodori-TTS 仮想環境の確認
if not defined ENGINE_PYTHON if exist "%CAND_VENV%" (
  "%CAND_VENV%" -c "import sys; sys.path.insert(0, 'engine'); import torch, torchaudio, dacvae, silentcipher, fastapi, irodori_voice" >nul 2>&1
  if not errorlevel 1 set ENGINE_PYTHON=%CAND_VENV%
)

rem runtime が無い場合は作成
if not defined ENGINE_PYTHON (
  if exist "%ROOT%00_setup-engine.bat" (
    echo.
    echo 音声合成エンジンの実行環境（runtime）がまだ準備されていません。
    echo 自動セットアップを開始します...
    echo.
    call "%ROOT%00_setup-engine.bat" --auto
    if exist "%CAND_RUNTIME%" set ENGINE_PYTHON=%CAND_RUNTIME%
  )
)

set ENGINE_FILE=
set ENGINE_ARGS=[]
if defined ENGINE_PYTHON set ENGINE_FILE=%ENGINE_PYTHON%
if not defined ENGINE_FILE if exist "%CAND_EXE%" set ENGINE_FILE=%CAND_EXE%

if not defined ENGINE_FILE (
  echo [エラー] エンジンを起動する方法が見つかりません。
  echo 00_setup-engine.bat を実行して環境を準備してください。
  pause
  exit /b 1
)

rem JSON へ埋めるため区切りを / にする。\ は JSON のエスケープ記号と衝突する。
set ENGINE_FILE_JSON=%ENGINE_FILE:\=/%
set ENGINE_SCRIPT_JSON=%ENGINE_SCRIPT:\=/%
if defined ENGINE_PYTHON set ENGINE_ARGS=["%ENGINE_SCRIPT_JSON%"]

set VITE_DEFAULT_ENGINE_INFOS=[{"uuid":"0b2a5f31-9c4d-4f6a-8e7b-3d1c5a9f2e40","name":"IRODORI-VOICE Engine","executionEnabled":true,"executionFilePath":"%ENGINE_FILE_JSON%","executionArgs":%ENGINE_ARGS%,"host":"http://127.0.0.1:%PORT%"}]

echo エンジン: %ENGINE_FILE%
if defined ENGINE_PYTHON echo スクリプト: %ENGINE_SCRIPT%

netstat -ano -p tcp | findstr /c:":%PORT% " | findstr /c:LISTENING > nul 2>&1
if not errorlevel 1 (
  echo.
  echo 注意: ポート %PORT% は既に使われています。02_start-engine.bat 等で起動した
  echo エンジンが残っている場合は、そちらを閉じてからやり直してください。
  echo.
)

set ELECTRON_RUN_AS_NODE=
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8

cd /d "%DEST%"
call pnpm run electron:serve

endlocal
exit /b %errorlevel%
