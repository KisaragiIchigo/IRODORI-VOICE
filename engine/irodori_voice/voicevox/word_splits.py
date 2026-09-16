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

from pathlib import Path

# アクセント句の境界を表す内部マーカー。合成テキストには残さない。
PHRASE_MARKER = "|"

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


def dictionary_path() -> Path:
    """辞書ファイルの場所。"""

    return Path("word_splits.txt")


def load_splits() -> dict[str, str]:
    """辞書を読み出す。書式の壊れた行は読み飛ばす。

    利用者が手で書き換えるファイルなので、1 行の書き損じで合成そのものを
    止めない。``=`` の前後の空白は書き手の癖として落とす。
    """

    path = dictionary_path()
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


def apply_word_splits(text: str) -> str:
    """登録された単語を、区切りを入れた表記へ置き換える。"""

    for target, replacement in load_splits().items():
        if target in text:
            text = text.replace(target, _fold_markers(replacement))
    return text


def split_by_marker(text: str) -> list[str]:
    """マーカーで区切る。連続したマーカーが作る空の断片は捨てる。"""

    return [part for part in text.split(PHRASE_MARKER) if part]


def strip_phrase_markers(text: str) -> str:
    """合成へ渡すテキストからマーカーを落とす。"""

    return text.replace(PHRASE_MARKER, "")
