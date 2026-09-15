# 組み合わせて使うソフトウェアについて

`LICENSE` が定めているのは、IRODORI-VOICE 自身のコード（`engine/` `admin/` `tools/` と
各種バッチ）の扱いです。これらは MIT ライセンスで、改造も再配布も自由に行えます。

一方、IRODORI-VOICE は次のソフトウェアと組み合わせて動きます。それぞれに配布元が定めた
ライセンスが適用されるため、扱いを分けて記載します。

| ソフトウェア | ライセンス | このリポジトリに含まれるか |
| --- | --- | --- |
| [Irodori-TTS](https://github.com/Aratako/Irodori-TTS) | MIT | **含まれます**（`engine/irodori_voice/vendor/`） |
| [VOICEVOX エディタ](https://github.com/VOICEVOX/voicevox) | LGPL-3.0（一部 MIT） | 含まれません |
| [Style-Bert-VITS2](https://github.com/litagin02/Style-Bert-VITS2) | AGPL-3.0 | 含まれません |
| [aivmlib](https://github.com/Aivis-Project/aivmlib) | MIT | 含まれません（任意） |
| [pyopenjtalk-plus](https://github.com/tsukumijima/pyopenjtalk-plus) | MIT（OpenJTalk 本体は Modified BSD） | 含まれません |
| 音声合成モデルの重み | 各配布元の規約 | 含まれません |

## Irodori-TTS

推論コードを `engine/irodori_voice/vendor/irodori_tts/` へ取り込んでいます。ライセンス全文は
`engine/irodori_voice/vendor/LICENSE.irodori-tts` にあります。サンプリング処理そのものは
書き換えていません。上流の改善をそのまま取り込めるようにするためです。

## VOICEVOX エディタ

このリポジトリには含まれていません。`setup-voicevox-editor.bat` が公式リポジトリから取得し、
`tools/patch-editor.mjs` と `tools/brand-editor.mjs` が改変を当てます。改変の内容は、置換前と
置換後の文字列としてこの 2 ファイルにすべて記載されています。

`node tools/patch-editor.mjs --revert` を実行すれば、取得したままの状態へ戻せます。

## Style-Bert-VITS2

任意の追加依存として導入した場合にのみ読み込まれます。`requirements.txt` の末尾にあるもので、この
リポジトリには含まれていません。AGPL-3.0 であるため、**実行ファイルへまとめて配布する場合は
条件が変わります。** `requirements.txt` から外してビルドすれば同梱されません。

## 実行ファイルを配布する場合

`コンパイル.bat` で作った実行ファイルには、VOICEVOX エディタと、導入済みの Python パッケージ
一式が含まれます。ソースを公開するだけであれば追加の義務は生じませんが、実行ファイルを配布
する場合は、同梱されるソフトウェアそれぞれの条件を満たす必要があります。詳しくは
`README.md` の「配布する場合の注意」をご覧ください。
