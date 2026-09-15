@echo off
rem Switch the console to UTF-8, then re-read this file. See the note under :body.
if "%~1"=="--utf8" goto :body
chcp 65001 > nul
cmd /c "%~f0" --utf8
exit /b %errorlevel%

:body
setlocal enabledelayedexpansion

rem 上の 5 行について。ファイルの途中で chcp すると cmd の読み取り位置がずれ、
rem ここから下の日本語の行が途中で切れて、その後半が別のコマンドとして実行される。
rem そのため、先にコンソールを UTF-8 へ切り替えてから読み直させている。

rem IRODORI-VOICE を単体で動く実行ファイルへまとめます。
rem
rem 作るもの（1 種類につき 3 形式）:
rem   IRODORI VOICE Setup.exe     … インストーラ。導入して使う形
rem   IRODORI VOICE Portable.exe  … 単一の実行ファイル。起動のたびに展開されます
rem   IRODORI-VOICE\             … フォルダそのまま。中の exe を実行するだけ
rem
rem CPU 版と GPU 版は PyTorch が別物で、実行ファイルへ固めた時点でどちらかが
rem 焼き込まれます。あとから差し替えられないため、作り分けます。
rem
rem 1 種類あたり 50 分以上、ディスクを 20GB ほど使います。

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

for /f "tokens=*" %%V in ('"%PYTHON%" -c "import torch; print(torch.version.cuda or 'CPU')" 2^>nul') do set "TORCHNOW=%%V"
if not defined TORCHNOW set "TORCHNOW=不明"

echo 使用する Python: %PYTHON%
echo 現在の PyTorch : %TORCHNOW%
echo.

rem --- 何を作るか ---------------------------------------------------------
rem GPU 版に CUDA 12.6 を選ぶ理由は、これが Maxwell〜Hopper（GTX 750Ti 〜 RTX 40xx）を
rem 一度に覆う最後の世代だからです。CUDA 12.8 以降は Maxwell / Pascal / Volta の
rem サポートを削除しており、GTX 10xx 世代が動かなくなります。
echo   1. 両方つくる … CPU 版と GPU 版を続けて作ります（合計 100 分以上）
echo   2. CPU 版だけ … GPU が無い環境でも確実に動きます
echo   3. GPU 版だけ … CUDA 12.6。GTX 750Ti 〜 RTX 40xx で使えます
echo   4. 入れ替えない … いま入っている %TORCHNOW% のまま 1 種類だけ作ります
echo.
set "BUILDCHOICE="
set /p "BUILDCHOICE=番号を選んでください [1/2/3/4]: "
echo.

if "%BUILDCHOICE%"=="1" set "TARGETS=cpu gpu"
if "%BUILDCHOICE%"=="2" set "TARGETS=cpu"
if "%BUILDCHOICE%"=="3" set "TARGETS=gpu"
if "%BUILDCHOICE%"=="4" set "TARGETS=asis"
if not defined TARGETS (
  echo 1 から 4 のいずれかを入力してください。
  pause
  exit /b 1
)

rem --- 管理画面は 1 回だけ作ります ----------------------------------------
rem エンジンの spec が admin\dist を見て、在れば実行ファイルへ同梱します。
rem CPU 版と GPU 版で中身は変わらないため、先に 1 回だけ作ります。
echo [共通] 管理画面をビルドします...
cd /d "%ROOT%admin"
call pnpm build
if errorlevel 1 (
  echo 管理画面のビルドに失敗しました。
  pause
  exit /b 1
)
echo.

rem 前回の成果物を消します。種類ごとのフォルダはこのあと作ります。
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"

for %%K in (%TARGETS%) do (
  call :build_one %%K
  if errorlevel 1 (
    echo.
    echo %%K 版のビルドで中断しました。
    pause
    exit /b 1
  )
)

echo.
echo ============================================================
echo  ビルドが完了しました
echo ============================================================
echo.
for /d %%D in ("%OUT%\*") do (
  echo [%%~nxD]
  dir /b "%%D"
  echo.
)
echo   Setup.exe     導入して使う形です。設定と話者は
echo                 %%APPDATA%%\IRODORI-VOICE に入り、アンインストールしても残ります。
echo   Portable.exe  1 つの実行ファイルにまとめた形です。起動のたびに中身を
echo                 展開するため、最初の起動には時間がかかります。
echo   IRODORI-VOICE フォルダごと移して使う形です。展開の待ち時間がありません。
echo.
echo   cpu\ は GPU が無い環境でも動きます。配布の既定はこちらです。
echo   gpu\ は CUDA 12.6 対応の GPU（GTX 750Ti 〜 RTX 40xx）で速くなります。
echo        VRAM 6GB 以上ならモデル本体も GPU に載ります。足りない場合は
echo        コーデックだけ GPU に残します。
echo.
echo どれもエンジンを同梱しており、起動すると一緒に立ち上がります。
echo 初回の起動時は、音声合成モデルの取得のためにネットへ接続します。
echo 取得後はオフラインでも動きます。
echo.
pause
endlocal
exit /b 0


rem ========================================================================
rem  PyTorch を入れ替えます。%1 期待する版 / %2 torch / %3 torchaudio / %4 index
rem
rem  先に uninstall するのは、CPU 版と CUDA 版でファイル構成が違うためです。
rem  上書きだけで済ませると CUDA の DLL（caffe2_nvrtc.dll など 13 個）が残り、
rem  CPU 版の torch と混ざって「指定されたモジュールが見つかりません」で
rem  import できなくなります。実際にこれで壊れた状態からビルドが進みました。
rem  入れ替えたあとは必ず読み込みを確かめ、駄目ならここで止めます。
rem ========================================================================
:swap_torch
echo PyTorch を入れ替えます（%~1）...
call "%PYTHON%" -m pip uninstall -y torch torchaudio >nul 2>&1
call "%PYTHON%" -m pip install --force-reinstall --no-deps %~2 %~3 --index-url %~4
if errorlevel 1 (
  echo PyTorch の導入に失敗しました。
  exit /b 1
)

echo 入れ替えた PyTorch を確認します...
"%PYTHON%" -c "import torch, sys; sys.exit(0 if '%~1'.replace('cu126','+cu126').replace('cpu','+cpu') in torch.__version__ else 1)"
if errorlevel 1 (
  echo.
  echo 入れ替えた PyTorch を読み込めないか、期待した版ではありません。
  echo 壊れたままビルドを続けると、動かない実行ファイルが出来上がります。
  echo 次を手で実行してから、やり直してください。
  echo   "%PYTHON%" -m pip uninstall -y torch torchaudio
  echo   "%PYTHON%" -m pip install %~2 %~3 --index-url %~4
  exit /b 1
)
for /f "tokens=*" %%V in ('"%PYTHON%" -c "import torch; print(torch.__version__)"') do echo   確認: %%V
echo.
exit /b 0


rem ========================================================================
rem  1 種類ぶんを作ります。%1 に cpu / gpu / asis を受け取ります。
rem ========================================================================
:build_one
setlocal
set "KIND=%~1"

rem 作る形式。GPU 版は CUDA ランタイムを含んで 5GB になり、NSIS の 32bit 実装が
rem 抱えられる上限（2GB 前後）を超えるため、インストーラと単一実行ファイルを作れません。
rem 実測では extractEmbeddedAppPackage で失敗しました。フォルダ版だけを作ります。
set "IRODORI_BUILD_TARGETS=nsis,portable,dir"

if "%KIND%"=="cpu" (
  echo ============================================================
  echo  CPU 版をビルドします
  echo ============================================================
  call :swap_torch cpu "torch==2.10.0" "torchaudio==2.10.0" https://download.pytorch.org/whl/cpu
  if errorlevel 1 (
    endlocal
    exit /b 1
  )
  set "SUBDIR=cpu"
)
if "%KIND%"=="gpu" (
  echo ============================================================
  echo  GPU 版をビルドします
  echo ============================================================
  call :swap_torch cu126 "torch==2.10.0+cu126" "torchaudio==2.10.0+cu126" https://download.pytorch.org/whl/cu126
  if errorlevel 1 (
    endlocal
    exit /b 1
  )
  set "SUBDIR=gpu"
  set "IRODORI_BUILD_TARGETS=dir"
  echo GPU 版はフォルダ形式のみ作ります（サイズが NSIS の上限を超えるため）。
  echo.
)
if "%KIND%"=="asis" (
  echo ============================================================
  echo  いま入っている PyTorch でビルドします
  echo ============================================================
  set "SUBDIR=build"
)

rem --- エンジンを実行ファイルへ固めます ------------------------------------
echo [1/2] エンジンを実行ファイルへ固めます。10 分以上かかります...
cd /d "%ROOT%engine"
"%PYTHON%" -m PyInstaller irodori-voice-engine.spec --noconfirm --clean
if errorlevel 1 (
  echo エンジンのビルドに失敗しました。
  endlocal
  exit /b 1
)
if not exist "%ROOT%engine\dist\irodori-voice-engine\irodori-voice-engine.exe" (
  echo エンジンの実行ファイルが出力されていません。
  endlocal
  exit /b 1
)
echo.

rem --- エディタを実行ファイルへ固めます ------------------------------------
rem 配布用の .env を置きます。ここで executionEnabled を true にすることで、
rem エディタが同梱のエンジンを子プロセスとして起動するようになります。
echo [2/2] エディタをビルドします。15 分以上かかります...
copy /y "%ROOT%voicevox-editor.env.production.template" "%EDITOR%\.env.production" >nul
if errorlevel 1 (
  echo 配布用の .env の配置に失敗しました。
  endlocal
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
  endlocal
  exit /b 1
)

if not exist "%BUILDOUT%\win-unpacked" (
  echo ビルド結果が見つかりません。
  endlocal
  exit /b 1
)

rem --- 成果物を release\<種類>\ へ移します ---------------------------------
mkdir "%OUT%\%SUBDIR%" 2>nul
move "%BUILDOUT%\win-unpacked" "%OUT%\%SUBDIR%\IRODORI-VOICE" >nul
if errorlevel 1 (
  echo フォルダ版の移動に失敗しました。出力は %BUILDOUT% に残っています。
  endlocal
  exit /b 1
)
move "%BUILDOUT%\*Setup.exe" "%OUT%\%SUBDIR%\" >nul 2>&1
move "%BUILDOUT%\*Portable.exe" "%OUT%\%SUBDIR%\" >nul 2>&1

rem 中間物（7z アーカイブなど）ごと作業先を片付けます。
if exist "%BUILDOUT%" rmdir /s /q "%BUILDOUT%"

rem どちらを固めたかを残します。成果物を見ただけでは区別がつかないためです。
rem for /f で受けると、torch の読み込みに失敗したときに空文字のまま進んでしまい、
rem 中身が "ECHO is off." のファイルが出来ます。一時ファイル経由なら中身が残ります。
"%PYTHON%" -c "import torch; print(torch.__version__)" > "%OUT%\%SUBDIR%\同梱している PyTorch.txt" 2>&1
type "%OUT%\%SUBDIR%\同梱している PyTorch.txt" > nul
set /p KINDNOTE=<"%OUT%\%SUBDIR%\同梱している PyTorch.txt"

echo %SUBDIR% 版が出来上がりました（PyTorch: %KINDNOTE%）。
echo.
endlocal
exit /b 0
