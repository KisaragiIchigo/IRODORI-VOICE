"""フレーズ分割辞書。

外部ツール（YMM4 や AviUtl プラグイン）から届いたテキストへ、登録済みの分割を
当てる層。長い複合語は 1 つの塊のまま渡すとモデルが読みを外すため、利用者が
「ここで区切る」と決めた位置を表記の側で伝える。

区切りには 2 種類ある。

    台湾証券取引所=台湾証券、取引所     読点を書く         -> 間が空く
    台湾証券取引所=台湾証券_取引所      空白や _ を書く    -> 間は空かない

後者は ``PHRASE_MARKER`` へ畳んでおき、アクセント句を組み立てるときだけ区切りと
して使う。合成へ渡すテキストからは ``strip_phrase_markers`` で落とす。Irodori-TTS
は表記から直接音を作るモデルで、``|`` がそのまま届くと区切り記号として読まれ、
間を空けないはずの分割にポーズが入るため。
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ..paths import user_data_root

# アクセント句の境界を表す内部マーカー。合成テキストには残さない。
PHRASE_MARKER = "|"

# 半角を全角へ寄せる対応表。読み方＆アクセント辞書は表記を全角で保存する（エディタが
# 入力を全角へ畳む）ため、そこから同時登録した語は全角で分割辞書へ入る。本文は半角で
# 書かれるのが普通で、字の幅が違うだけで当たらないのを避ける。
_FULLWIDTH_TABLE = {code: code + 0xFEE0 for code in range(0x21, 0x7F)}
_FULLWIDTH_TABLE[0x20] = 0x3000

# 利用者が「間を空けずに区切る」意図で書く文字。すべてマーカーへ畳む。
_MARKER_SOURCES = (" ", "\u3000", "_", "\uff3f")

_HEADER = """\
# ここに「自動で分割させたい単語」を登録します。
# 外部ツール（YMM4等）から送られたテキストに対し、エンジンが処理する直前に置換します。
# 書き方: 置換前の単語=置換後の単語
# 読点（、）で区切ると、そこで間が空きます。
# 空白またはアンダースコア（_）で区切ると、間を空けずにアクセント句だけを分けます。
# 例:
# 台湾証券取引所=台湾証券_取引所
"""


# 配布版より前は実行ディレクトリへ直接置いていた。中身が残っていれば一度だけ引き継ぐ。
_LEGACY_PATH = Path("word_splits.txt")


def dictionary_path() -> Path:
    """辞書ファイルの場所。

    実行ディレクトリからの相対で持つと、インストール先が作業ディレクトリになる
    配布版では読めない。Program Files 配下は書き込みも権限で弾かれるため、登録が
    そのまま失敗する。設定と同じユーザー領域へ置く。
    """

    return user_data_root() / "word_splits.txt"


def _prepare() -> Path:
    """辞書ファイルを、読める状態にして返す。

    実行ディレクトリに残った古い辞書があれば引き継ぎ、どこにも無ければ書き方を
    記した見出しだけのファイルを作る。利用者が手で開いて書き足せるファイルなので、
    置き場所が分かる形で存在していること自体に意味がある。
    """

    path = dictionary_path()
    if path.exists():
        return path

    try:
        if _LEGACY_PATH.is_file():
            path.write_text(
                _LEGACY_PATH.read_text(encoding="utf-8-sig"), encoding="utf-8"
            )
        else:
            path.write_text(_HEADER, encoding="utf-8")
    except OSError:
        # 作れなくても読み書きの本筋は止めない。load_splits が空を返して続く。
        pass
    return path


def load_splits() -> dict[str, str]:
    """辞書を読み出す。書式の壊れた行は読み飛ばす。

    利用者が手で書き換えるファイルなので、1 行の書き損じで合成そのものを
    止めない。``=`` の前後の空白は書き手の癖として落とす。
    """

    path = _prepare()
    if not path.is_file():
        return {}

    try:
        # 手編集や他のツールが付けた BOM を取り除いて読む。
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}

    splits: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        target, replacement = (part.strip() for part in stripped.split("=", 1))
        if target:
            splits[target] = replacement
    return splits


def save_splits(splits: dict[str, str]) -> None:
    """辞書を書き出す。手で読み書きできる形を保つ。"""

    body = "".join(f"{target}={replacement}\n" for target, replacement in splits.items())
    dictionary_path().write_text(_HEADER + body, encoding="utf-8")


def _fold_markers(replacement: str) -> str:
    for source in _MARKER_SOURCES:
        replacement = replacement.replace(source, PHRASE_MARKER)
    return replacement


def _target_pattern(target: str) -> re.Pattern[str]:
    """本文の上で対象語を探す形。全角と半角の書き分けを吸収する。

    照合する形は 3 つ。辞書に書かれたそのまま、NFKC で半角へ畳んだ形、英数記号を全角へ
    寄せた形。読み方＆アクセント辞書からの同時登録は表記が全角で入るため、半角で書かれた
    本文へ当てるには畳んだ形が要る。手で ``GUI=_GUI_`` と書いた辞書を全角の本文へ当てる
    場合はその逆になる。大小文字は ``reading_overrides`` と同じく区別しない。

    3 つをまとめて 1 度だけ走らせる。形ごとに ``replace`` を重ねると、差し込んだ置換後の
    文字列を次の形が拾い直し、マーカーが増える。
    """

    forms = [target]
    for form in (
        unicodedata.normalize("NFKC", target),
        target.translate(_FULLWIDTH_TABLE),
    ):
        if form and form not in forms:
            forms.append(form)
    return re.compile("|".join(re.escape(form) for form in forms), flags=re.IGNORECASE)


def apply_word_splits(text: str) -> str:
    """登録された単語を、区切りを入れた表記へ置き換える。"""

    for target, replacement in load_splits().items():
        folded = _fold_markers(replacement)
        # 置換後の文字列は関数で渡す。\1 のような字を後方参照として解釈させない。
        text = _target_pattern(target).sub(lambda _: folded, text)
    return text


def split_by_marker(text: str) -> list[str]:
    """マーカーで区切る。連続したマーカーが作る空の断片は捨てる。"""

    return [part for part in text.split(PHRASE_MARKER) if part]


def strip_phrase_markers(text: str) -> str:
    """合成へ渡すテキストからマーカーを落とす。"""

    return text.replace(PHRASE_MARKER, "")
