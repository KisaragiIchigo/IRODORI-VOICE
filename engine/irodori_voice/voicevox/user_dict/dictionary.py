"""登録語の保管と、OpenJTalk の解析への反映。

JSON へ残し、naist-jdic 互換の CSV へ書き出し、.dic へビルドして読み込ませる。
保存するだけで読みが変わらない実装にしないための経路がここにある。"""

from __future__ import annotations

import json
import threading
import uuid as uuid_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...paths import user_data_root
from .word import DEFAULT_PRIORITY, UserDictWord, WordType, word_type_of


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
