; IRODORI-VOICE のインストーラ用カスタムスクリプト。
;
; 中身は空だが、置いてあることに意味がある。
;
; electron-builder は buildResources（build/）の直下に installer.nsh があると、
; include を指定していない限り自動で読み込む。本家の build/installer.nsh は
; nsis-web 専用で、952 行すべてが「インストーラが本体を分割ダウンロードする」ための
; 処理でできている。これが通常の nsis ビルドへ混入すると、nsis-web でしか定義されない
; APP_PACKAGE_STORE_FILE を参照して makensis が警告を出し、既定では警告がエラー扱いの
; ため「warning treated as error」でビルドが落ちる。
;
; nsis.include にこのファイルを指定することで、その自動読み込みを止めている。
; インストーラへ処理を足したくなったら、ここへ書く。
;
; 本家の installer.nsh 自体は残してある。nsis-web ターゲットへ戻す場合に必要なため!
