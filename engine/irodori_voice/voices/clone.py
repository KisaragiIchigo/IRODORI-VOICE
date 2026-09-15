"""取り込んだ話者の声を Irodori-TTS の参照音声として取り込む。

Style-Bert-VITS2 は声の同一性を強く保つ代わりに、喋り方は学習データの
範囲に収まる。Irodori-TTS は参照音声から声の同一性だけを受け取り、抑揚と間は
自前の条件付けで決める。両者を繋ぐと「モデルの声で、Irodori-TTS の喋り方」になる。

参照音声はこの層で合成して保存する。エディタを経由させると同じ波形が 2 度
ネットワークを通るため、バックエンドを直接呼んで numpy のまま扱う。
"""

from __future__ import annotations

import uuid

from .. import audio as audio_utils
from ..backends.sbv2.backend import Sbv2Backend
from ..backends.base import BackendError, SynthesisParams
from ..paths import voice_assets_dir
from .store import VoicePreset, VoicePresetStore, VoiceStyleDef

# 参照音声の既定文。母音・撥音・促音・拗音が偏らないように選んである。
# 声の同一性を掴ませるのが目的なので、内容そのものに意味は無い。
REFERENCE_LINES: tuple[str, ...] = (
    "こんにちは。今日はいい天気ですね。お散歩にちょうどいい陽気だと思います。",
    "新しい機能の説明をします。設定の画面から、音量や話す速さを変えられます。",
    "ありがとうございました。またのご利用を、心よりお待ちしております。",
    "東京特許許可局の許可を受けて、朝の新聞をゆっくり読み上げました。",
)

# Irodori-TTS 側が参照として受け取れる長さの上限。これを超えた分は捨てられるため、
# 無駄なファイルを残さないよう合成の段階で打ち切る。
MAX_REFERENCE_SECONDS = 30.0

# (style_id, 表示名, キャプション, 注釈絵文字)
#
# 表現の主役は絵文字。キャプションだけでスタイルを分けたときは F0 中央値の割れ幅が
# 12.6Hz にとどまったが、🐢（ゆっくり）と ⏩（早口）では同じ文の長さが 1.76 秒開く。
# キャプションは補助として併記する。声そのものは参照音声が決めるので、キャプションに
# 声質は書かず「どう話しているか」だけを書く。
#
# 顔ぶれは実際に聴いて選んである。表現の難しい注釈（こらえ笑い、ひそひそ声、あくび、
# 泣き声）はモデルが破綻して音が濁るため外した。「かなしみ」と「まじめ」に絵文字が
# 無いのはそのため。ノーマルは素の声を確かめる基準として、どちらも付けない。
#
# 使える記号は duration.py の ALLOWED_ANNOTATION_EMOJIS にあるものだけ。
# 😳（動揺）や 😨（恐れ）のように、一般的な感情でも一覧に無いものがある。
CLONE_STYLES: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("normal", "ノーマル", None, None),
    ("bright", "あかるい", "自然に嬉しそうな声で話している。", "😊"),
    ("joy", "よろこび", "弾むように、嬉しそうに話している。", "😆"),
    ("warm", "やさしさ", "やわらかく、丁寧に話しかけている。", "🫶"),
    ("relief", "あんど", "落ち着いて、満足げに話している。", "😌"),
    ("confident", "じしん", "余裕のある口調で話している。", "😎"),
    ("tease", "からかい", "少し得意げに、からかうように話している。", "😏"),
    ("thinking", "かんがえ", "迷いながら、考えるように話している。", "🤔"),
    ("impressed", "かんたん", "はっと驚いた声で話している。", "😮"),
    ("surprise", "おどろき", "大きく驚いた声を上げている。", "😲"),
    ("shy", "てれ", "恥ずかしそうに話している。", "🫣"),
    ("anxious", "ふあん", "弱々しく、頼りなげに話している。", "🥺"),
    ("panic", "あせり", "慌てて、緊張気味に話している。", "😰"),
    ("pain", "くるしげ", "つらそうに話している。", "😖"),
    ("anger", "おこり", "強く、不満げに話している。", "😠"),
    ("dismay", "あきれ", "冷めた調子で話している。", "😒"),
    ("sleepy", "ねむそう", "気だるく、眠そうに話している。", "😪"),
    ("drunk", "よい", "ふらついた雰囲気で話している。", "🥴"),
    ("strong", "ちからづよく", "力を込めて話している。", "💪"),
    ("plead", "おねがい", "懇願するように話している。", "🙏"),
    ("narration", "ろうどく", "落ち着いたナレーション調で読み上げている。", "📖"),
    ("sorrow", "かなしみ", "沈んだ声で、ゆっくりと話している。", None),
    ("serious", "まじめ", "真剣な調子で、はっきりと話している。", None),
    # 話速の指示。効きは実測済み（🐢 が +0.84 秒、⏩ が -0.92 秒）だが、
    # 音質の善し悪しはまだ聴いて確かめていない。
    ("slow", "ゆっくり", "一語ずつ、ゆっくりと話している。", "🐢"),
    ("fast", "はやくち", "急いで、矢継ぎ早に話している。", "⏩"),
)

# 参照音声への忠実さ。上げるほど声が寄る、というものではない。
#
# 実測（ある話者を写したもの・同一文・同一シード。元の声の F0 中央値は 252Hz）:
#
#     cfg  高域(6kHz以上)の比率  F0 中央値   元の声との差
#     3.0        6.73%            246.2Hz        -5.8Hz
#     5.0        2.00%            324.3Hz       +72.3Hz
#     9.0        0.04%            310.7Hz       +58.7Hz
#
# 上げると高域が失われ、こもった音になる。9.0 では高域がほぼ消える（AM ラジオのような音）。
# F0 が下がるのも声が寄ったからではなく、単にこもった結果だった。
# 音質と声の近さがどちらも最良になる 3.0 を既定にする。
#
# なお MeanFlow 蒸留版のチェックポイントでは、この値を含む CFG スケールが
# すべて 0 に潰される。効かせるには標準版を選んでおく必要がある。
CLONE_SPEAKER_CFG = 3.0


def _synthesize_clips(
    aivm: Sbv2Backend,
    *,
    source_voice_id: str,
    source_style_id: str | None,
    lines: tuple[str, ...],
) -> list[tuple[bytes, float]]:
    """参照用のクリップを合成する。wav のバイト列と長さの組を返す。

    上限に達した時点で打ち切る。残りの行を合成しても Irodori-TTS 側で捨てられる。
    """

    clips: list[tuple[bytes, float]] = []
    total_seconds = 0.0

    for line in lines:
        text = line.strip()
        if not text:
            continue

        output = aivm.synthesize(
            SynthesisParams(
                text=text,
                voice_id=source_voice_id,
                style_id=source_style_id,
                # 参照に必要なのは声が鳴っている区間だけ。前後の無音は
                # そのぶん latent を食うので付けない。
                pre_silence=0.0,
                post_silence=0.0,
            )
        )
        seconds = output.samples.size / float(output.sample_rate)
        if seconds <= 0.0:
            continue

        clips.append(
            (
                audio_utils.encode_wav(output.samples, sample_rate=output.sample_rate),
                seconds,
            )
        )
        total_seconds += seconds
        if total_seconds >= MAX_REFERENCE_SECONDS:
            break

    if not clips:
        raise BackendError("参照音声を 1 本も合成できませんでした。参照文を確認してください。")
    return clips


def _save_clips(clips: list[tuple[bytes, float]]) -> list[str]:
    """合成したクリップをアセット領域へ書き出し、ファイル名を返す。"""

    root = voice_assets_dir()
    names: list[str] = []
    for wav, _ in clips:
        name = f"ref-{uuid.uuid4().hex[:12]}.wav"
        (root / name).write_bytes(wav)
        names.append(name)
    return names


def clone_from_aivm(
    *,
    aivm: Sbv2Backend,
    store: VoicePresetStore,
    source_voice_id: str,
    source_style_id: str | None = None,
    name: str,
    description: str = "",
    color_key: str = "shu",
    reference_lines: tuple[str, ...] | None = None,
    with_emotion_styles: bool = True,
    normal_caption: str | None = None,
) -> VoicePreset:
    """取り込んだ話者の声を写した Irodori-TTS 話者を作る。

    ``with_emotion_styles`` を落とすとノーマルだけの話者になる。喜怒哀楽が
    要らない用途では、スタイルの選択肢が減るぶん扱いやすい。

    ``normal_caption`` はノーマルのスタイルにだけ入る。喜怒哀楽のスタイルは
    それぞれ固有の指示を持っているため、混ぜると意図が濁る。
    """

    lines = tuple(reference_lines) if reference_lines else REFERENCE_LINES
    clips = _synthesize_clips(
        aivm,
        source_voice_id=source_voice_id,
        source_style_id=source_style_id,
        lines=lines,
    )
    reference_files = _save_clips(clips)

    definitions = CLONE_STYLES if with_emotion_styles else CLONE_STYLES[:1]
    wanted = (normal_caption or "").strip() or None
    styles = [
        VoiceStyleDef(
            style_id=style_id,
            name=style_name,
            caption=wanted if style_id == "normal" and wanted else caption,
            emoji=emoji,
            cfg_scale_speaker=CLONE_SPEAKER_CFG,
        )
        for style_id, style_name, caption, emoji in definitions
    ]

    return store.create(
        name=name,
        description=description,
        color_key=color_key,
        mode="reference",
        styles=styles,
        reference_files=reference_files,
    )
