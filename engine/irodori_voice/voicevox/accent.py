"""テキストからアクセント句を組み立てる。

VOICEVOX ではこの処理を OpenJTalk が担っており、推論モデルからは独立している。
つまり Irodori-TTS でもまったく同じ手順でアクセント句を返せる。

区切りはフルコンテキストラベルから読む。句読点だけで割ると
「ジカンヲカケテナイヨーヲリカイスルバメント」のように 1 句が長くなりすぎ、
エディタのアクセント欄が使いものにならない。ラベルの ``A:a2``（アクセント句内の
モーラ位置）が 1 に戻るところで切れば、本家と同じ単位になる。

なお Irodori-TTS にはモーラ単位のピッチ制御機構が無いため、ここで返す
アクセントや長さを編集しても音には反映されない。表示と往復のために生成する。
"""

from __future__ import annotations

import logging
import re

from .labels import Label, LabelPhrase, group_into_phrases, parse_labels
from .phonemes import is_unvoiced, mora_text
from .schemas import AccentPhrase, Mora

# モーラ長と音高の既定値。Irodori-TTS は実測値を持たないため、
# 表示が破綻しない程度の一定値を置く。
DEFAULT_VOWEL_LENGTH = 0.10
DEFAULT_CONSONANT_LENGTH = 0.06
DEFAULT_PITCH = 5.5
UNVOICED_PITCH = 0.0
PAUSE_LENGTH = 0.3

_KANA_ONLY = re.compile(r"[ァ-ヶー]+")

# 単独で 1 モーラを成す母音。長音記号へ戻す判定に使う。
_STANDALONE_VOWELS = frozenset("アイウエオ")

# 母音の音素。これ以外（撥音・促音・無音）が挟まったら連続とみなさない。
_VOWEL_PHONEMES = frozenset("aiueo")

logger = logging.getLogger(__name__)

# 代替へ落ちた理由。診断（run_engine.py --diagnose）から参照する。
# ここが空でなければ、アクセント句はカタカナを並べただけの粗いものになっている。
last_fallback_reason: str | None = None


def pyopenjtalk_available() -> bool:
    try:
        import pyopenjtalk  # noqa: F401
    except ImportError:
        return False
    return True


def _build_moras(labels: list[Label]) -> list[Mora]:
    """アクセント句 1 つぶんのラベルからモーラ列を作る。

    子音は直後の母音とひとまとめにする。母音だけの音素は単独でモーラになる。
    """

    moras: list[Mora] = []
    pending_consonant: str | None = None

    for label in labels:
        if not label.is_vowel:
            # 子音。次の母音と組にする。
            pending_consonant = label.phoneme
            continue

        vowel = label.phoneme
        moras.append(
            Mora(
                text=mora_text(pending_consonant, vowel),
                consonant=pending_consonant,
                consonant_length=DEFAULT_CONSONANT_LENGTH if pending_consonant else None,
                vowel=vowel,
                vowel_length=DEFAULT_VOWEL_LENGTH,
                pitch=UNVOICED_PITCH if is_unvoiced(vowel) or vowel == "cl" else DEFAULT_PITCH,
            )
        )
        pending_consonant = None

    return moras


def _pause_mora() -> Mora:
    """句の間に置く無音。VOICEVOX は pauseMora として扱う。"""

    return Mora(
        text="、",
        consonant=None,
        consonant_length=None,
        vowel="pau",
        vowel_length=PAUSE_LENGTH,
        pitch=0.0,
    )


def _to_accent_phrase(phrase: LabelPhrase, *, is_interrogative: bool) -> AccentPhrase | None:
    moras = _build_moras(phrase.labels)
    if not moras:
        return None

    return AccentPhrase(
        moras=moras,
        # アクセント型は 1 始まり。モーラ数を超える値は丸める。
        accent=min(max(phrase.accent_type, 0), len(moras)),
        pause_mora=_pause_mora() if phrase.has_pause else None,
        is_interrogative=is_interrogative,
    )


def _phrases_from_labels(text: str) -> list[AccentPhrase]:
    import pyopenjtalk

    labels = parse_labels(pyopenjtalk.extract_fullcontext(text))
    grouped = group_into_phrases(labels)
    if not grouped:
        return []

    ends_with_question = text.rstrip().endswith(("?", "？"))

    phrases: list[AccentPhrase] = []
    for index, phrase in enumerate(grouped):
        built = _to_accent_phrase(
            phrase,
            # 疑問符は文末の句にだけ効かせる。
            is_interrogative=ends_with_question and index == len(grouped) - 1,
        )
        if built is not None:
            phrases.append(built)
    return phrases


def _phrases_from_kana(text: str) -> list[AccentPhrase]:
    """OpenJTalk が無いときの代替。

    カタカナ部分だけを拾って 1 句にまとめる。読みの精度は落ちるが、
    外部ツールとの往復は成立する。
    """

    moras: list[Mora] = []
    for chunk in _KANA_ONLY.findall(text):
        for char in chunk:
            moras.append(
                Mora(
                    text=char,
                    consonant=None,
                    consonant_length=None,
                    vowel="a",
                    vowel_length=DEFAULT_VOWEL_LENGTH,
                    pitch=DEFAULT_PITCH,
                )
            )
    if not moras:
        return []
    return [AccentPhrase(moras=moras, accent=0)]


def build_accent_phrases(text: str) -> list[AccentPhrase]:
    """テキストからアクセント句の一覧を組み立てる。"""

    global last_fallback_reason

    stripped = text.strip()
    if stripped == "":
        return []

    from .user_dict import shared_user_dict
    from ..backends.irodori.reading_overrides import apply_reading_overrides
    
    # UIのカタカナ表示（OpenJTalk解析）にも反映させるため、解析前に全角半角無視の置換を適用する
    overrides = shared_user_dict().reading_overrides()
    stripped = apply_reading_overrides(stripped, overrides)

    if not pyopenjtalk_available():
        last_fallback_reason = "pyopenjtalk を読み込めません。"
        logger.warning("pyopenjtalk が無いため、アクセント句をカタカナから組み立てます。")
        return _phrases_from_kana(stripped)

    try:
        phrases = _phrases_from_labels(stripped)
    except Exception as exc:
        # 解析に失敗しても合成自体は続けられる。代替へ落とすが、理由は残す。
        # 握りつぶすと「アクセント欄が 1 句しか出ない」現象の原因が追えなくなる。
        last_fallback_reason = f"{type(exc).__name__}: {exc}"
        logger.exception("フルコンテキストラベルの解析に失敗しました")
        return _phrases_from_kana(stripped)

    if phrases:
        last_fallback_reason = None
        return phrases

    last_fallback_reason = "ラベルからアクセント句を組み立てられませんでした。"
    return _phrases_from_kana(stripped)


def _phrase_reading(moras: list[Mora]) -> str:
    """アクセント句のモーラ列を読みへ直す。

    OpenJTalk のモーラ表記は長音を母音字で表すため、並べるだけでは「カード」が
    「カアド」、「情報」が「ジョオホオ」になる。Irodori-TTS はテキスト表記から
    直接音を作るモデルで、この綴りを音にできない（「カアドオ」が別の語に化ける）。
    そのため、直前と同じ母音が続く箇所を「ー」へ戻す。

    句の最後のモーラは畳まない。「楽天カードを」の「を」のように、直前の母音と
    一致する助詞が長音へ吸われるのを避けるため。
    """

    parts: list[str] = []
    previous_vowel: str | None = None

    for index, mora in enumerate(moras):
        # 無声化した母音は大文字で来るため、比較の前に揃える。
        vowel = mora.vowel.lower()

        if (
            mora.consonant is None
            and mora.text in _STANDALONE_VOWELS
            and previous_vowel == vowel
            and index != len(moras) - 1
            and parts
            and parts[-1] != "ー"
        ):
            parts.append("ー")
            continue

        parts.append(mora.text)
        previous_vowel = vowel if vowel in _VOWEL_PHONEMES else None

    return "".join(parts)


_KANA_TO_HIRA = str.maketrans(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポァィゥェォャュョッヴ",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっゔ"
)

def accent_phrases_to_text(phrases: list[AccentPhrase]) -> str:
    """アクセント句から読み上げ用のテキストを復元する。

    元の表記（漢字混じり）は AudioQuery に含まれないため、ここで得られるのは
    カタカナの読み。元テキストが分かる場合は、呼び出し側がそちらを優先する。
    
    Irodori-TTSはカタカナを外来語風に読むため、UIで手動編集された読みを
    モデルへ渡す際はひらがなへ変換する。
    """

    parts: list[str] = []
    for phrase in phrases:
        parts.append(_phrase_reading(phrase.moras))
        if phrase.pause_mora is not None:
            parts.append("、")
        elif phrase.is_interrogative:
            parts.append("?")
    
    katakana_text = "".join(parts)
    return katakana_text.translate(_KANA_TO_HIRA)
