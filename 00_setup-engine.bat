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

set AUTO_MODE=0
if "%~1"=="--auto" set AUTO_MODE=1
if "%~2"=="--auto" set AUTO_MODE=1

echo ============================================================
echo IRODORI-VOICE エンジン環境 全自動セットアップ
echo ============================================================
echo.

rem --- Python の探索 ----------------------------------------------------------
set SYS_PYTHON=
for /f "delims=" %%I in ('where python 2^>nul') do (
  if not defined SYS_PYTHON set SYS_PYTHON=%%~fI
)

if not defined SYS_PYTHON (
  for %%P in (%LOCALAPPDATA%\Programs\Python\Python310\python.exe %LOCALAPPDATA%\Programs\Python\Python311\python.exe %LOCALAPPDATA%\Programs\Python\Python312\python.exe C:\Python310\python.exe C:\Python311\python.exe) do (
    if not defined SYS_PYTHON if exist %%~fP set SYS_PYTHON=%%~fP
  )
)

if not defined SYS_PYTHON (
  echo [エラー] Python が見つかりません。
  echo.
  echo IRODORI-VOICE には Python 3.10 以上が必要です。
  echo 下記の公式サイトからインストーラーを取得し、
  echo ★必ず「Add Python to PATH」にチェックを入れてインストールしてください。
  echo.
  echo 公式ダウンロード: https://www.python.org/downloads/
  echo.
  where winget >nul 2>&1
  if not errorlevel 1 (
    echo winget コマンドで自動インストールを試みますか？
    set /p INSTALL_CHOICE=インストールする場合は Y を押してください [Y/N]: 
    if /i "!INSTALL_CHOICE!"=="Y" (
      echo Python 3.10 をインストール中...
      winget install --id Python.Python.3.10 -e --source winget
      echo インストールが完了したら、このウィンドウを閉じて再度バッチを実行してください。
    )
  )
  pause
  exit /b 1
)

for /f "tokens=*" %%I in ('"%SYS_PYTHON%" --version 2^>^&1') do set PY_VER=%%I
echo 検出した Python: !PY_VER! (!SYS_PYTHON!)

rem --- runtime 仮想環境の作成 -------------------------------------------------
if exist "%ROOT%runtime\Scripts\python.exe" goto :skip_create_venv

echo.
echo [1/4] Python 仮想環境（runtime）を作成しています...
"%SYS_PYTHON%" -m venv "%ROOT%runtime"
if errorlevel 1 (
  echo.
  echo [エラー] 仮想環境の作成に失敗しました。
  pause
  exit /b 1
)
echo 仮想環境を作成しました。
goto :after_create_venv

:skip_create_venv
echo 既に runtime フォルダが存在します。環境の確認・更新を行います。

:after_create_venv
set VENV_PY=%ROOT%runtime\Scripts\python.exe

rem --- pip の更新 -------------------------------------------------------------
echo.
echo [2/4] pip を最新化しています...
"%VENV_PY%" -m pip install --upgrade pip >nul 2>&1

rem --- GPU の判定と PyTorch の導入 --------------------------------------------
echo.
echo [3/4] 音声合成ライブラリ（PyTorch）を準備しています...
set USE_CUDA=0
where nvidia-smi >nul 2>&1
if not errorlevel 1 set USE_CUDA=1

if "!USE_CUDA!"=="1" (
  echo NVIDIA GPU を検出しました。CUDA 12.6 対応版 PyTorch を導入します...
  "%VENV_PY%" -m pip install torch==2.10.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu126
  if errorlevel 1 (
    echo.
    echo [警告] CUDA 版 PyTorch の導入に失敗しました。
    echo CPU 版 PyTorch へフォールバックして再試行します...
    set USE_CUDA=0
  )
)

if "!USE_CUDA!"=="0" (
  echo CPU 版 PyTorch を導入します...
  "%VENV_PY%" -m pip install torch==2.10.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cpu
  if errorlevel 1 (
    echo.
    echo [エラー] PyTorch の導入に失敗しました。ネットワーク接続を確認してください。
    pause
    exit /b 1
  )
)

rem --- 依存ライブラリの導入 ---------------------------------------------------
echo.
echo [4/4] 音声合成エンジンの関連ライブラリを導入しています...
"%VENV_PY%" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 (
  echo.
  echo [エラー] requirements.txt の導入でエラーが発生しました。
  pause
  exit /b 1
)

echo 音声コーデック（DACVAE）を導入しています...
"%VENV_PY%" -m pip install --no-deps git+https://github.com/facebookresearch/dacvae
if errorlevel 1 (
  echo.
  echo [エラー] DACVAE の導入に失敗しました。git が利用可能か確認してください。
  pause
  exit /b 1
)

echo 電子透かしモジュール（SilentCipher）を導入しています...
"%VENV_PY%" -m pip install --no-deps git+https://github.com/SesameAILabs/silentcipher.git@d46d7d0893a583d8968ab3a6626e2289faec9152
if errorlevel 1 (
  echo.
  echo [エラー] SilentCipher の導入に失敗しました。
  pause
  exit /b 1
)

rem --- 自己診断テスト ---------------------------------------------------------
echo.
echo エンジンの自己診断を実行しています...
"%VENV_PY%" "%ROOT%engine\run_engine.py" --diagnose
if errorlevel 1 (
  echo.
  echo [警告] 自己診断で問題が検出されましたが、基本環境は準備されました。
)

echo.
echo ============================================================
echo エンジンのセットアップが完了しました！
echo ============================================================
echo.

if "!AUTO_MODE!"=="0" (
  echo 「000-Irodori-Voice-STARTER.bat」を実行すればエディタとエンジンが起動します。
  echo.
  pause
)

endlocal
