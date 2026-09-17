@echo off
rem Switch the console to UTF-8, then re-read this file.
if "%~1"=="--utf8" goto :body
chcp 65001 > nul
cmd /c ""%~f0" --utf8 %*"
exit /b %errorlevel%

:body
shift
setlocal enabledelayedexpansion

set AUTO_MODE=0
if "%~1"=="--auto" set AUTO_MODE=1
if "%~2"=="--auto" set AUTO_MODE=1

rem VOICEVOX エディタを取得して IRODORI-VOICE 用に設定します。
rem 取得するのは VOICEVOX 公式リポジトリ（LGPL-3.0 / 一部 MIT）です。

set ROOT=%~dp0
set DEST=%ROOT%editor-voicevox

where git >nul 2>&1
if errorlevel 1 (
  echo [エラー] git が見つかりません。
  echo VOICEVOX エディタの取得に git が必要です。
  echo 下記から git をインストールしてください。
  echo.
  echo Git 公式ダウンロード: https://git-scm.com/download/win
  echo.
  where winget >nul 2>&1
  if not errorlevel 1 (
    echo winget コマンドで自動インストールを試みますか？
    set /p INSTALL_GIT=インストールする場合は Y を押してください [Y/N]: 
    if /i "!INSTALL_GIT!"=="Y" (
      echo Git をインストール中...
      winget install --id Git.Git -e --source winget
      echo インストールが完了したら、このウィンドウを閉じて再度バッチを実行してください。
    )
  )
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo [エラー] Node.js が見つかりません。
  echo VOICEVOX エディタの実行に Node.js 24 系が必要です。
  echo 下記から Node.js をインストールしてください。
  echo.
  echo Node.js 公式ダウンロード: https://nodejs.org/
  echo.
  where winget >nul 2>&1
  if not errorlevel 1 (
    echo winget コマンドで自動インストールを試みますか？
    set /p INSTALL_NODE=インストールする場合は Y を押してください [Y/N]: 
    if /i "!INSTALL_NODE!"=="Y" (
      echo Node.js をインストール中...
      winget install --id OpenJS.NodeJS.LTS -e --source winget
      echo インストールが完了したら、このウィンドウを閉じて再度バッチを実行してください。
    )
  )
  pause
  exit /b 1
)

rem --- pnpm を用意します ---------------------------------------------------
where pnpm >nul 2>&1
if errorlevel 1 (
  echo pnpm を用意します...
  call corepack enable pnpm >nul 2>&1
  where pnpm >nul 2>&1
  if errorlevel 1 (
    echo corepack では有効化できませんでした。npm から導入します...
    call npm i -g pnpm@10.28.2
    if errorlevel 1 (
      echo pnpm の導入に失敗しました。
      pause
      exit /b 1
    )
  )
)

rem --- エディタを取得します -----------------------------------------------
if exist "%DEST%\package.json" goto :skip_clone

echo VOICEVOX エディタを取得します...
git clone --depth 1 https://github.com/VOICEVOX/voicevox.git "%DEST%"
if errorlevel 1 (
  echo 取得に失敗しました。
  pause
  exit /b 1
)
goto :after_clone

:skip_clone
echo 既に %DEST% があります。取得は省略します。
echo 更新する場合は、そのフォルダで git pull を実行してください。

:after_clone

rem --- IRODORI-VOICE 用の設定を適用します ---------------------------------
echo 接続設定（.env）を配置します...
copy /y "%ROOT%voicevox-editor.env.template" "%DEST%\.env" >nul
if errorlevel 1 (
  echo .env の配置に失敗しました。
  pause
  exit /b 1
)

echo アプリ名を設定します...
call node "%ROOT%tools\brand-editor.mjs" "%DEST%"
call node "%ROOT%tools\patch-editor.mjs"
if errorlevel 1 (
  echo アプリ名の設定に失敗しました。
  pause
  exit /b 1
)

rem --- 依存を導入します ---------------------------------------------------
cd /d "%DEST%"
echo 依存パッケージを導入します。10 分以上かかることがあります...
call pnpm install
if errorlevel 1 (
  echo.
  echo 依存の導入でエラーが出ました。
  echo 開発用のスペルチェッカー（typos）の展開だけが失敗している場合は、
  echo エディタの起動に影響しないためそのまま進めて構いません。
  echo.
)

echo 管理画面の依存パッケージを導入します...
cd /d "%ROOT%admin"
call pnpm install

rem --- ライセンス情報を作ります -------------------------------------------
echo ライセンス情報を生成します...
cd /d "%DEST%"
call pnpm run license:generate -o public/licenses.json
if errorlevel 1 (
  echo ライセンス情報の生成に失敗しました。ヘルプの表示以外に影響はありません。
)

echo.
echo ============================================================
echo エディタのセットアップが完了しました！
echo ============================================================
echo.

if "!AUTO_MODE!"=="0" (
  echo 「000-Irodori-Voice-STARTER.bat」を実行すればエディタとエンジンが起動します。
  echo.
  pause
)

endlocal
