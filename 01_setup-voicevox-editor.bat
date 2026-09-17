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

rem VOICEVOX エディタを取得して IRODORI-VOICE 用に設定します。
rem 取得するのは VOICEVOX 公式リポジトリ（LGPL-3.0 / 一部 MIT）です。
rem 内容を確認したうえで実行してください。

set "ROOT=%~dp0"
set "DEST=%ROOT%editor-voicevox"

where git >nul 2>&1
if errorlevel 1 (
  echo git が見つかりません。git をインストールしてから実行してください。
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js が見つかりません。Node.js 24 系をインストールしてから実行してください。
  pause
  exit /b 1
)

rem --- pnpm を用意します ---------------------------------------------------
rem VOICEVOX は pnpm を使います。さらに postinstall が pnpm を PATH から呼ぶため、
rem corepack 経由ではなく PATH に通った状態が必要です。
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
rem vite が package.json の name と VITE_APP_NAME の一致を検証するため、
rem name を irodori-voice へ変更します（変更するのはこの 1 行のみ）。
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
  echo フォルダのパスに空白が含まれると、この展開が失敗することがあります。
  echo.
)

echo 管理画面の依存パッケージを導入します...
cd /d "%ROOT%admin"
call pnpm install

rem --- ライセンス情報を作ります -------------------------------------------
rem public/licenses.json は本家リポジトリではダミーが入っており、配布物では CI が
rem 生成しています。生成しないとヘルプのライセンス情報に「dummy name1」が並びます。
echo ライセンス情報を生成します...
cd /d "%DEST%"
call pnpm run license:generate -o public/licenses.json
if errorlevel 1 (
  echo ライセンス情報の生成に失敗しました。ヘルプの表示以外に影響はありません。
)

echo.
echo セットアップが完了しました。
echo.
echo 起動手順:
echo   1. 02_start-engine.bat でエンジンを起動する（ウィンドウは閉じない）
echo   2. 03_start-voicevox-editor.bat を実行する
echo.
pause

endlocal
