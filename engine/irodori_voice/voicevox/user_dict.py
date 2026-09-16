"""ユーザー辞書。

VOICEVOX エディタの辞書画面から追加された語を、実際に OpenJTalk の解析へ反映させる。
保存するだけで読みが変わらない実装にすると、利用者は「登録したのに直らない」という
一番わかりにくい形で裏切られるため、pyopenjtalk のユーザー辞書機構まで通す。

辞書は naist-jdic 互換の CSV へ書き出してから ``.dic`` にビルドする。
この形式と優先度の対応は VOICEVOX ENGINE に合わせている。
"""

from __future__ import annotations

import json
import re
import threading
import uuid as uuid_module
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..paths import user_data_root

WordType = Literal[
    "PROPER_NOUN",
    "ORGANIZATION_NAME",
    "PERSON_NAME",
    "COMMON_NOUN",
    "VERB",
    "ADJECTIVE",
    "SUFFIX",
]

MIN_PRIORITY = 0
MAX_PRIORITY = 10
DEFAULT_PRIORITY = 5

# priority 0（最低）から 10（最高）に対応するコスト。値が小さいほど優先して採用される。
_COST_CANDIDATES = [15008, 13728, 12448, 11168, 9888, 8608, 7328, 6048, 4768, 3488, -988]

# 品詞ごとの文脈 ID と品詞細分類。naist-jdic の定義に対応する。
#
# 文脈 ID は naist-jdic の left-id で、辞書が持たない値を渡すと mecab_dict_index が
# その行だけを捨てる。捨てても他の語のビルドは通るため、エラーにはならず「その語
# だけ読みが変わらない」という形で出る。同梱の pyopenjtalk 0.4.1-post9 が抱える
# naist-jdic では 1376 が上限で、VOICEVOX ENGINE が SUFFIX へ使う 1417 は範囲外。
# 接尾は AivisSpeech と同じ 1358 を使う。辞書ファイルを相互に持ち運ぶ相手でもある。
_WORD_TYPE_TABLE: dict[str, tuple[int, str, str, str, str]] = {
    "PROPER_NOUN": (1348, "名詞", "固有名詞", "一般", "*"),
    "ORGANIZATION_NAME": (1352, "名詞", "固有名詞", "組織", "*"),
    "PERSON_NAME": (1349, "名詞", "固有名詞", "人名", "一般"),
    "COMMON_NOUN": (1345, "名詞", "一般", "*", "*"),
    "VERB": (642, "動詞", "自立", "*", "*"),
    "ADJECTIVE": (20, "形容詞", "自立", "*", "*"),
    "SUFFIX": (1358, "名詞", "接尾", "一般", "*"),
}

# naist-jdic が持つ left-id の上限。これを超える文脈 ID の語は辞書へ入らない。
MAX_CONTEXT_ID = 1376

# モーラの区切り。長い並びから順に当てる。小書きのカナを一律で直前へ吸収すると、
# 「ビィ」のように 2 モーラで数える並びまで 1 モーラになり、アクセント位置が
# 1 つずれる。どの並びを 1 モーラとするかは VOICEVOX ENGINE に合わせてある。
_MORA_PATTERN = re.compile(
    "|".join(
        [
            "[イ][ェ]",
            "[ヴ][ャュョ]",
            "[トド][ゥ]",
            "[テデ][ィャュョ]",
            "[デ][ェ]",
            "[クグ][ヮ]",
            "[キシチニヒミリギジビピ][ェャュョ]",
            "[ツフヴ][ァィェォ]",
            "[ァ-ヴー]",
        ]
    )
)


def count_moras(pronunciation: str) -> int:
    """カタカナの発音からモーラ数を数える。"""

    return max(1, len(_MORA_PATTERN.findall(pronunciation)))


@dataclass
class UserDictWord:
    surface: str
    priority: int
    context_id: int
    part_of_speech: str
    part_of_speech_detail_1: str
    part_of_speech_detail_2: str
    part_of_speech_detail_3: str
    inflectional_type: str
    inflectional_form: str
    stem: str
    yomi: str
    pronunciation: str
    accent_type: int
    mora_count: int
    accent_associative_rule: str = "*"

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> UserDictWord:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in raw.items() if k in known})

    @classmethod
    def build(
        cls,
        *,
        surface: str,
        pronunciation: str,
        accent_type: int,
        word_type: WordType = "PROPER_NOUN",
        priority: int = DEFAULT_PRIORITY,
    ) -> UserDictWord:
        context_id, pos, detail_1, detail_2, detail_3 = _WORD_TYPE_TABLE.get(
            word_type, _WORD_TYPE_TABLE["PROPER_NOUN"]
        )
        return cls(
            surface=surface,
            priority=max(MIN_PRIORITY, min(MAX_PRIORITY, int(priority))),
            context_id=context_id,
            part_of_speech=pos,
            part_of_speech_detail_1=detail_1,
            part_of_speech_detail_2=detail_2,
            part_of_speech_detail_3=detail_3,
            inflectional_type="*",
            inflectional_form="*",
            stem="*",
            yomi=pronunciation,
            pronunciation=pronunciation,
            accent_type=int(accent_type),
            mora_count=count_moras(pronunciation),
        )

    def to_csv_row(self) -> str:
        cost = _COST_CANDIDATES[max(MIN_PRIORITY, min(MAX_PRIORITY, self.priority))]
        return ",".join(
            [
                self.surface,
                str(self.context_id),
                str(self.context_id),
                str(cost),
                self.part_of_speech,
                self.part_of_speech_detail_1,
                self.part_of_speech_detail_2,
                self.part_of_speech_detail_3,
                self.inflectional_type,
                self.inflectional_form,
                self.stem,
                self.yomi,
                self.pronunciation,
                f"{self.accent_type}/{self.mora_count}",
                self.accent_associative_rule,
            ]
        )


def word_type_of(word: UserDictWord) -> WordType:
    """登録済みの語がどの品詞として作られたかを言い当てる。

    語そのものには品詞の種別を持たせていない。文脈 ID と品詞細分類の組が
    種別ごとに固有なので、そこから引き直す。どれにも当てはまらない語
    （他のソフトが書いた辞書を取り込んだ場合など）は固有名詞として扱う。
    """

    signature = (
        word.part_of_speech,
        word.part_of_speech_detail_1,
        word.part_of_speech_detail_2,
        word.part_of_speech_detail_3,
    )
    for word_type, (context_id, *details) in _WORD_TYPE_TABLE.items():
        if word.context_id == context_id and tuple(details) == signature:
            return word_type  # type: ignore[return-value]
    for word_type, (_, *details) in _WORD_TYPE_TABLE.items():
        if tuple(details) == signature:
            return word_type  # type: ignore[return-value]
    return "PROPER_NOUN"


def is_valid_context_id(context_id: int) -> bool:
    """その文脈 ID で辞書をビルドできるかを返す。"""

    return 0 <= context_id <= MAX_CONTEXT_ID


@dataclass
class UserDictionary:
    """語の追加・削除と、OpenJTalk への反映をまとめて受け持つ。"""

    words: dict[str, UserDictWord] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self._root = user_data_root() / "dict"
        self._root.mkdir(parents=True, exist_ok=True)
        self.last_error: str | None = None
        self._active_dic: Path | None = None
        self._load()
        self.apply()

    @property
    def _json_path(self) -> Path:
        return self._root / "user_dict.json"

    @property
    def _csv_path(self) -> Path:
        return self._root / "user_dict.csv"

    def _load(self) -> None:
        if not self._json_path.is_file():
            return
        try:
            raw = json.loads(self._json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return
        self.words = {
            word_uuid: UserDictWord.from_json(entry)
            for word_uuid, entry in raw.items()
            if isinstance(entry, dict)
        }

    def _save(self) -> None:
        self._json_path.write_text(
            json.dumps(
                {word_uuid: word.to_json() for word_uuid, word in self.words.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def apply(self) -> bool:
        """登録内容を OpenJTalk へ反映する。反映できたかを返す。

        辞書ファイルは適用した時点で OpenJTalk が開いたままになる。Windows では
        使用中のファイルを上書きできないため、先に解除し、さらに世代ごとに別名で
        書き出す。同じ名前に上書きしようとすると、ビルドが静かに失敗して
        「登録したのに読みが変わらない」という症状になる。
        """

        try:
            import pyopenjtalk
        except ImportError:
            self.last_error = (
                "pyopenjtalk が導入されていないため、登録した語は読みへ反映されません。"
            )
            return False

        with self._lock:
            try:
                pyopenjtalk.unset_user_dict()
            except Exception as exc:
                self.last_error = f"辞書の解除に失敗しました: {exc}"
                return False

            if not self.words:
                self._remove_dic_files(keep=None)
                self._active_dic = None
                self.last_error = None
                return True

            rows = [word.to_csv_row() for word in self.words.values()]
            self._csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

            dic_path = self._root / f"user_dict.{uuid_module.uuid4().hex[:8]}.dic"
            try:
                pyopenjtalk.mecab_dict_index(str(self._csv_path), str(dic_path))
                pyopenjtalk.update_global_jtalk_with_user_dict(str(dic_path))
            except Exception as exc:
                self.last_error = f"辞書のビルドに失敗しました: {exc}"
                return False

            self._active_dic = dic_path
            self._remove_dic_files(keep=dic_path)
            self.last_error = None
            return True

    def _remove_dic_files(self, *, keep: Path | None) -> None:
        """古い世代の辞書ファイルを片付ける。

        解放されていないファイルは削除に失敗するが、次の適用では別名を使うので
        実害はない。残骸が増えないよう、消せるものだけ消す。
        """

        for path in self._root.glob("user_dict*.dic"):
            if keep is not None and path == keep:
                continue
            try:
                path.unlink()
            except OSError:
                continue

    def list(self) -> dict[str, UserDictWord]:
        with self._lock:
            return dict(self.words)

    def reading_overrides(self) -> list[tuple[str, str]]:
        """表記とその読みの対応を、長い表記から順に返す。

        Irodori-TTS はモデルへテキスト表記しか渡せず、読み仮名を受け取る口が
        ない。そのため登録語は合成へ渡すテキストの上で置き換えるしかなく、
        この一覧がその材料になる。OpenJTalk を経由する話者には ``.dic`` 側で
        効くため、こちらは使わない。

        長い表記を先に返すのは、「楽天」と「楽天ペイ」の両方が登録されたときに
        短い方が先に当たって残りが崩れるのを避けるため。
        """

        with self._lock:
            pairs = [
                (word.surface, word.pronunciation)
                for word in self.words.values()
                if word.surface and word.pronunciation
            ]
        pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
        return pairs

    def add(
        self,
        *,
        surface: str,
        pronunciation: str,
        accent_type: int,
        word_type: WordType = "PROPER_NOUN",
        priority: int = DEFAULT_PRIORITY,
    ) -> str:
        word = UserDictWord.build(
            surface=surface,
            pronunciation=pronunciation,
            accent_type=accent_type,
            word_type=word_type,
            priority=priority,
        )
        word_uuid = str(uuid_module.uuid4())
        with self._lock:
            self.words[word_uuid] = word
            self._save()
        self.apply()
        return word_uuid

    def rewrite(
        self,
        word_uuid: str,
        *,
        surface: str,
        pronunciation: str,
        accent_type: int,
        word_type: WordType | None = None,
        priority: int | None = None,
    ) -> None:
        with self._lock:
            current = self.words.get(word_uuid)
            if current is None:
                raise KeyError(f"辞書に単語 {word_uuid} がありません。")
            # 品詞を指定されなかったときに固有名詞へ倒すと、取り込んだ辞書の
            # 組織名や人名がエディタで直すたびに固有名詞へ化ける。元の語から
            # 引き直して保つ。
            self.words[word_uuid] = UserDictWord.build(
                surface=surface,
                pronunciation=pronunciation,
                accent_type=accent_type,
                word_type=word_type or word_type_of(current),
                priority=priority if priority is not None else current.priority,
            )
            self._save()
        self.apply()

    def delete(self, word_uuid: str) -> None:
        with self._lock:
            if word_uuid not in self.words:
                raise KeyError(f"辞書に単語 {word_uuid} がありません。")
            del self.words[word_uuid]
            self._save()
        self.apply()

    def import_words(self, words: dict[str, dict[str, Any]], *, override: bool) -> None:
        with self._lock:
            for word_uuid, raw in words.items():
                if not override and word_uuid in self.words:
                    continue
                self.words[word_uuid] = UserDictWord.from_json(raw)
            self._save()
        self.apply()


_shared_dictionary: UserDictionary | None = None


def shared_user_dict() -> UserDictionary:
    """エンジン内で共有するユーザー辞書。

    互換 API（登録・削除）と Irodori バックエンド（読みの置換）が同じ内容を
    見る必要がある。別々に読み込むと、登録した語が合成へ反映されるまでに
    エンジンの再起動を挟むことになる。
    """

    global _shared_dictionary
    if _shared_dictionary is None:
        _shared_dictionary = UserDictionary()
    return _shared_dictionary
