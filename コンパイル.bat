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

rem IRODORI-VOICE を単体で動く実行ファイルへまとめます。
rem
rem 作るもの:
rem   1. 管理画面（admin）    … エンジンが /admin で配信する画面
rem   2. エンジンの実行ファイル … Python 環境なしで動く形へ固める
rem   3. エディタの実行ファイル … 上のエンジンを同梱し、起動時に自動で立ち上げる
rem
rem 出来上がりは release\ の下に 3 つ出ます。どれも単体で動きます。
rem
rem   IRODORI VOICE Setup.exe     … インストーラ。導入して使う形
rem   IRODORI VOICE Portable.exe  … 単一の実行ファイル。起動のたびに展開されます
rem   IRODORI-VOICE\             … フォルダそのまま。中の exe を実行するだけ
rem
rem 合計で 50 分以上、ディスクを 20GB ほど使います。

set "ROOT=%~dp0"
set "EDITOR=%ROOT%editor-voicevox"
set "OUT=%ROOT%release"

rem ビルドの作業先。インストーラを作る NSIS のコンパイラ（makensis）は、渡された
rem パスを ANSI として扱うため、日本語を含むパスのファイルを開けません。このソフトの
rem 置き場所に日本語が含まれていても通るよう、出力だけをドライブ直下の ASCII な
rem フォルダへ逃がします。同じドライブなので、あとで release へ移すのは一瞬です。
set "BUILDOUT=%~d0\irodori-build"
set "IRODORI_BUILD_OUTPUT=%BUILDOUT%"

echo ============================================================
echo  IRODORI-VOICE をビルドします
echo ============================================================
echo.

rem --- 前提を確認します ---------------------------------------------------
if not exist "%EDITOR%\package.json" (
  echo エディタが見つかりません。先に setup-voicevox-editor.bat を実行してください。
  pause
  exit /b 1
)

if not exist "%EDITOR%\node_modules" (
  echo エディタの依存が導入されていません。先に setup-voicevox-editor.bat を実行してください。
  pause
  exit /b 1
)

where pnpm >nul 2>&1
if errorlevel 1 (
  echo pnpm が見つかりません。先に setup-voicevox-editor.bat を実行してください。
  pause
  exit /b 1
)

set "PYTHON="
if exist "%ROOT%runtime\Scripts\python.exe" set "PYTHON=%ROOT%runtime\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe" set "PYTHON=%ROOT%..\Irodori-TTS\.venv\Scripts\python.exe"
if not defined PYTHON set "PYTHON=python"

"%PYTHON%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
  echo PyInstaller が導入されていません。
  echo 次を実行してください:  "%PYTHON%" -m pip install pyinstaller
  pause
  exit /b 1
)

echo 使用する Python: %PYTHON%
echo.

rem --- 1. 管理画面をビルドします ------------------------------------------
rem 先に作っておく必要があります。エンジンの spec が admin\dist を見て、
rem 在れば実行ファイルへ同梱するためです。
echo [1/3] 管理画面をビルドします...
cd /d "%ROOT%admin"
call pnpm build
if errorlevel 1 (
  echo 管理画面のビルドに失敗しました。
  pause
  exit /b 1
)
echo.

rem --- 2. エンジンを実行ファイルへ固めます --------------------------------
echo [2/3] エンジンを実行ファイルへ固めます。10 分以上かかります...
cd /d "%ROOT%engine"
"%PYTHON%" -m PyInstaller irodori-voice-engine.spec --noconfirm --clean
if errorlevel 1 (
  echo エンジンのビルドに失敗しました。
  pause
  exit /b 1
)

if not exist "%ROOT%engine\dist\irodori-voice-engine\irodori-voice-engine.exe" (
  echo エンジンの実行ファイルが出力されていません。
  pause
  exit /b 1
)
echo.

rem --- 3. エディタを実行ファイルへ固めます --------------------------------
rem 配布用の .env を置きます。ここで executionEnabled を true にすることで、
rem エディタが同梱のエンジンを子プロセスとして起動するようになります。
echo [3/3] エディタをビルドします。15 分以上かかります...
copy /y "%ROOT%voicevox-editor.env.production.template" "%EDITOR%\.env.production" >nul
if errorlevel 1 (
  echo 配布用の .env の配置に失敗しました。
  pause
  exit /b 1
)

if exist "%BUILDOUT%" rmdir /s /q "%BUILDOUT%"

cd /d "%EDITOR%"
call pnpm run electron:build
if errorlevel 1 (
  echo.
  echo エディタのビルドに失敗しました。
  echo 型チェックで止まった場合は、node "%ROOT%tools\patch-editor.mjs" を
  echo 当て直してから再実行してください。
  pause
  exit /b 1
)

if not exist "%BUILDOUT%\win-unpacked" (
  echo ビルド結果が見つかりません。
  pause
  exit /b 1
)

rem --- 成果物を release へ移します ----------------------------------------
if exist "%OUT%" (
  echo 前回の成果物を削除します...
  rmdir /s /q "%OUT%"
)
mkdir "%OUT%"

move "%BUILDOUT%\win-unpacked" "%OUT%\IRODORI-VOICE" >nul
if errorlevel 1 (
  echo フォルダ版の移動に失敗しました。
  echo 出力はそのまま %BUILDOUT% に残っています。
  pause
  exit /b 1
)

rem インストーラと単一実行ファイルは作業先の直下に出ます。
move "%BUILDOUT%\*Setup.exe" "%OUT%\" >nul 2>&1
move "%BUILDOUT%\*Portable.exe" "%OUT%\" >nul 2>&1

rem 中間物（7z アーカイブなど）ごと作業先を片付けます。
if exist "%BUILDOUT%" rmdir /s /q "%BUILDOUT%"

echo.
echo ============================================================
echo  ビルドが完了しました
echo ============================================================
echo.
dir /b "%OUT%"
echo.
echo   Setup.exe     導入して使う形です。設定と話者は
echo                 %%APPDATA%%\IRODORI-VOICE に入り、アンインストールしても残ります。
echo   Portable.exe  1 つの実行ファイルにまとめた形です。起動のたびに中身を
echo                 展開するため、最初の起動には時間がかかります。
echo   IRODORI-VOICE フォルダごと移して使う形です。展開の待ち時間がありません。
echo.
echo どれもエンジンを同梱しており、起動すると一緒に立ち上がります。
echo 初回の起動時は、音声合成モデルの取得のためにネットへ接続します。
echo 取得後はオフラインでも動きます。
echo.
pause

endlocal
