@echo off
rem Switch the console to UTF-8, then re-read this file.
if "%~1"=="--utf8" goto :body
chcp 65001 > nul
cmd /c ""%~f0" --utf8 %*"
exit /b %errorlevel%

:body
shift
setlocal enabledelayedexpansion

set ROOT=%~dp0
cd /d "%ROOT%"

set EDITOR_DIR=%ROOT%editor-voicevox
set VENV_PY=%ROOT%runtime\Scripts\python.exe

echo ============================================================
echo IRODORI-VOICE 全自動ランチャー
echo ============================================================
echo.

rem --- 1. エンジン環境のチェック ----------------------------------------------
set NEED_ENGINE_SETUP=0
if not exist "%VENV_PY%" (
  set NEED_ENGINE_SETUP=1
) else (
  "%VENV_PY%" -c "import sys; sys.path.insert(0, 'engine'); import torch, torchaudio, dacvae, silentcipher, fastapi, irodori_voice" >nul 2>&1
  if errorlevel 1 set NEED_ENGINE_SETUP=1
)

if "!NEED_ENGINE_SETUP!"=="1" (
  echo 音声合成エンジンの実行環境（runtime）を準備しています...
  echo ※ 初回セットアップには数分〜10分程度かかります。そのままお待ちください。
  echo.
  call "%ROOT%00_setup-engine.bat" --auto
  if errorlevel 1 (
    echo.
    echo [エラー] エンジンの自動セットアップに失敗しました。
    pause
    exit /b 1
  )
)

rem --- 2. エディタ環境のチェック ----------------------------------------------
set NEED_EDITOR_SETUP=0
if not exist "%EDITOR_DIR%\package.json" set NEED_EDITOR_SETUP=1
if not exist "%EDITOR_DIR%\node_modules" set NEED_EDITOR_SETUP=1

if "!NEED_EDITOR_SETUP!"=="1" (
  echo.
  echo VOICEVOX エディタ環境を準備しています...
  echo ※ 初回のみエディタの取得と依存パッケージの導入を行います（10分程度）。
  echo.
  call "%ROOT%01_setup-voicevox-editor.bat" --auto
  if errorlevel 1 (
    echo.
    echo [エラー] エディタの自動セットアップに失敗しました。
    pause
    exit /b 1
  )
)

rem --- 3. 起動処理 ------------------------------------------------------------
echo.
echo ============================================================
echo IRODORI-VOICE を起動しています...
echo ============================================================
echo.

call "%ROOT%03_start-voicevox-editor.bat"
exit /b %errorlevel%
