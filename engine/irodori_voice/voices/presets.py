"""同梱の話者プリセット。

どの声も、年齢と性別を書いたキャプションとシードから生まれた声を、利用者が聴き比べて
選んだもの。その声を参照音声として焼き付けてあり（builtin_assets/<話者 ID>/）、「シードから」
作った話者と同じ作りになっている。参照を持たせないと、読み上げる文の長さで声が動き、行ごとに
年齢や性別まで変わって聞こえる（seed_bake.py の冒頭）。

参照を持たない生成では、声だけでなく録音環境の質も文ごとに変わる。試聴（/voices/preview-seed）の
既定文はどの声でもこもった環境を引いており、それを 1 本目に焼くと、参照を真似る合成が
その環境を写して全行がこもった（若い女で 6kHz 以上が 0.14%）。参照の帯域を後から広げても
戻らなかった（ClearerVoice の超解像はサーッというノイズを足し、AP-BWE は合成で効きが消えた）。

そこで 1 本目は、同じシードとキャプションで短い文を試聴と同じ条件（80 回・本文 CFG 2）で
読ませ、高域が声と連動して静かに鳴っている候補を選んだ。2 本目以降はその 1 本目を参照に据え、
生成回数 40 回で reference.py の SEED_FOLLOWUP_TEXTS を読ませている。焼き直した若い女は
3 文とも 6kHz 以上が 4.9〜5.4%、8〜16kHz の発話と合間の差が 55〜57dB で鳴る。

スタイルもシードの話者と同じ顔ぶれ・同じ生成条件にしてある。同じ名前のスタイルが、
同梱話者と利用者の作った話者で違う鳴り方をしないようにするため。
"""

from __future__ import annotations

from ..paths import builtin_voice_assets_dir
from .expression_styles import build_expression_styles
from .seed_profile import apply_seed_expression_profile
from .store import VoicePreset, VoiceStyleDef

CHILD_GIRL = "5歳くらいの幼い女の子。舌足らずで、無邪気にかわいらしく話している。"
TEEN_GIRL = "中学生くらいの少女。明るく澄んだ声で、素直に話している。"
YOUNG_MAN = "20代の若い男性。爽やかで自然な話し方。"
YOUNG_WOMAN = "20代の若い女性。明るく自然な話し方。"
THIRTIES_MAN = "30代の落ち着いた男性。はっきりとした自然な話し方。"
THIRTIES_WOMAN = "30代の落ち着いた女性。丁寧で自然な話し方。"
SIXTIES_MAN = "60代の男性。落ち着いた低い声で、ゆったりと話している。"
SIXTIES_WOMAN = "60代の女性。穏やかで少し枯れた声で、ゆったりと話している。"
ELDER_MAN = "80歳を超えた高齢の男性。しわがれた声で、ゆっくりと話している。"
ELDER_WOMAN = "80歳を超えた高齢のおばあさん。しわがれた細い声で、ゆっくりと話している。"

# 上の文面は声を生んだキャプションで、ノーマルにはこのうち冒頭の一文（年齢と性別）だけを残し、
# 話し方の部分をこれへ差し替える。「自然な話し方」のままだと、利用者の耳には指名されて教科書を
# 読む中高生のような棒読みに聞こえた。聴き比べでは、この文面と本文 CFG 2 の組み合わせがもっとも
# 朗読らしく、そこから注釈絵文字で調整するのが理想とされた。声そのものは参照音声が決めるため、
# 話し方の部分を差し替えても声は変わらない。
RECITE_MANNER = "登場人物の気持ちを込めて、物語を感情豊かに朗読している。"
RECITE_TEXT_CFG = 2.0


def _recite_caption(caption: str) -> str:
    return caption.split("。", 1)[0] + "。" + RECITE_MANNER


def _baked(
    preset_id: str, name: str, description: str, color_key: str, seed: int, caption: str
) -> VoicePreset:
    root = builtin_voice_assets_dir()
    # 焼き付けの本数は上限 30 秒で打ち切るため、声によっては変わりうる。置いてあるファイルを
    # そのまま使う。フォルダが欠けていれば参照は空になり、合成時に「参照音声が設定されていません」と
    # 報告される。
    references = sorted(
        path.relative_to(root).as_posix() for path in (root / preset_id).glob("*.flac")
    )
    # 本文 CFG はノーマルを土台に全スタイルへ行き渡る。1 人の中で読みの自然さを揃えるため。
    normal = apply_seed_expression_profile(
        VoiceStyleDef(
            style_id="normal", name="ノーマル", caption=_recite_caption(caption),
            cfg_scale_text=RECITE_TEXT_CFG,
        )
    )
    return VoicePreset(
        preset_id=preset_id,
        name=name,
        description=description,
        color_key=color_key,
        mode="reference",
        styles=build_expression_styles(normal),
        reference_files=references,
        voice_seed=seed,
        builtin=True,
    )


BUILTIN_PRESETS: list[VoicePreset] = [
    _baked("child-girl", "幼い", "5歳くらいの幼い女の子の声です。", "yamabuki", 3333, CHILD_GIRL),
    _baked(
        "child-girl-slow", "幼い（のんびり）",
        "5歳くらいの幼い女の子の声です。のんびりとした話し方です。", "yamabuki", 11, CHILD_GIRL,
    ),
    # 少女のキャプションから生まれた声を、聴いて少年として選んだもの。キャプションへ「男の子」と
    # 書くと、幼い子でも声の高さが成人男性の範囲（145〜170Hz）へ落ちた。文面を少年向けに
    # 書き換えると同じ理由で声が大人の男性へ寄るおそれがあるため、ノーマルに残る冒頭の一文も
    # 「少女」のままにしている。
    _baked("teen-boy", "少年", "声変わり前の少年の声です。", "wakatake", 222, TEEN_GIRL),
    _baked("teen-girl-a", "少女 A", "中学生くらいの少女の声です。", "kobai", 11, TEEN_GIRL),
    _baked("teen-girl-b", "少女 B", "中学生くらいの少女の声です。", "kobai", 3333, TEEN_GIRL),
    _baked("young-man", "若い男", "20代の男性の声です。", "asagi", 222, YOUNG_MAN),
    _baked(
        "young-man-fresh", "若い男（さわやか）",
        "20代の男性の声です。さわやかな話し方です。", "asagi", 3333, YOUNG_MAN,
    ),
    _baked("young-woman", "若い女", "20代の女性の声です。", "shu", 11, YOUNG_WOMAN),
    _baked(
        "young-woman-fresh", "若い女（さわやか）",
        "20代の女性の声です。さわやかな話し方です。", "shu", 3333, YOUNG_WOMAN,
    ),
    _baked("thirties-man-a", "30代男 A", "30代の落ち着いた男性の声です。", "rurikon", 11, THIRTIES_MAN),
    _baked("thirties-man-b", "30代男 B", "30代の落ち着いた男性の声です。", "rurikon", 222, THIRTIES_MAN),
    _baked("thirties-man-c", "30代男 C", "30代の落ち着いた男性の声です。", "rurikon", 3333, THIRTIES_MAN),
    _baked("thirties-woman-a", "30代女 A", "30代の落ち着いた女性の声です。", "fuji", 11, THIRTIES_WOMAN),
    _baked("thirties-woman-b", "30代女 B", "30代の落ち着いた女性の声です。", "fuji", 222, THIRTIES_WOMAN),
    _baked("thirties-woman-c", "30代女 C", "30代の落ち着いた女性の声です。", "fuji", 3333, THIRTIES_WOMAN),
    _baked("sixties-man-a", "60代男 A", "60代の男性の声です。低めの声で、ゆったりと話します。", "rurikon", 11, SIXTIES_MAN),
    _baked("sixties-man-b", "60代男 B", "60代の男性の声です。低めの声で、ゆったりと話します。", "rurikon", 222, SIXTIES_MAN),
    _baked("sixties-man-c", "60代男 C", "60代の男性の声です。低めの声で、ゆったりと話します。", "rurikon", 3333, SIXTIES_MAN),
    _baked("sixties-woman-a", "60代女 A", "60代の女性の声です。穏やかな声で、ゆったりと話します。", "fuji", 11, SIXTIES_WOMAN),
    _baked("sixties-woman-b", "60代女 B", "60代の女性の声です。穏やかな声で、ゆったりと話します。", "fuji", 222, SIXTIES_WOMAN),
    _baked("sixties-woman-c", "60代女 C", "60代の女性の声です。穏やかな声で、ゆったりと話します。", "fuji", 3333, SIXTIES_WOMAN),
    _baked("elder-man-a", "老人男 A", "80歳を超えた男性の声です。しわがれた声で、ゆっくりと話します。", "sumire", 11, ELDER_MAN),
    _baked("elder-man-b", "老人男 B", "80歳を超えた男性の声です。しわがれた声で、ゆっくりと話します。", "sumire", 222, ELDER_MAN),
    _baked("elder-man-c", "老人男 C", "80歳を超えた男性の声です。しわがれた声で、ゆっくりと話します。", "sumire", 3333, ELDER_MAN),
    _baked("elder-woman-a", "老人女 A", "80歳を超えた女性の声です。細くしわがれた声で、ゆっくりと話します。", "sumire", 11, ELDER_WOMAN),
    _baked("elder-woman-b", "老人女 B", "80歳を超えた女性の声です。細くしわがれた声で、ゆっくりと話します。", "sumire", 222, ELDER_WOMAN),
    _baked("elder-woman-c", "老人女 C", "80歳を超えた女性の声です。細くしわがれた声で、ゆっくりと話します。", "sumire", 3333, ELDER_WOMAN),
]
