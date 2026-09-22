"""参照音声を持つ話者へ添える、喋り方のスタイル一覧。

声の同一性は参照音声が決めるため、スタイルが担うのは「どう話しているか」だけになる。
借りた声（clone.py）とシードの声（seed_bake.py）は声の作り方が違うだけで、できあがる
話者はどちらも mode="reference" なので、同じ一覧を共有する。片方にしか無いスタイルが
あると、同じ名前で呼んでいるのに使えたり使えなかったりする話者ができてしまう。
"""

from __future__ import annotations

from dataclasses import replace

from .store import VoiceStyleDef

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
EXPRESSION_STYLES: tuple[tuple[str, str, str | None, str | None], ...] = (
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

NORMAL_STYLE_ID = EXPRESSION_STYLES[0][0]


def build_expression_styles(
    template: VoiceStyleDef,
    *,
    normal_caption: str | None = None,
    with_emotion: bool = True,
) -> list[VoiceStyleDef]:
    """一覧をスタイル定義へ起こす。

    ``template`` は生成条件の土台。話者の作り方ごとに採用済みの値（生成回数や CFG）が
    違うため、値はここで決めずに呼び出し側から受け取る。スタイルが差し替えるのは
    識別子・表示名・キャプション・注釈絵文字だけで、生成条件には手を付けない。

    ``normal_caption`` はノーマルにだけ入る。喜怒哀楽のスタイルはそれぞれ固有の指示を
    持っているため、利用者の指定を混ぜると意図が濁る。省略したときは土台のキャプションを
    そのまま引き継ぐ。
    """

    rows = EXPRESSION_STYLES if with_emotion else EXPRESSION_STYLES[:1]
    wanted = (normal_caption or template.caption or "").strip() or None
    return [
        replace(
            template,
            style_id=style_id,
            name=name,
            caption=wanted if style_id == NORMAL_STYLE_ID else caption,
            emoji=emoji,
        )
        for style_id, name, caption, emoji in rows
    ]


def extend_with_expression_styles(styles: list[VoiceStyleDef]) -> list[VoiceStyleDef]:
    """既にある話者のスタイルを、一覧の顔ぶれで埋める。

    既存のスタイルは定義ごとそのまま残す（利用者が生成条件を書き換えている場合がある）。
    足りないぶんだけを、先頭のスタイルを土台にして作る。先頭を土台にするのは、生成回数や
    CFG がその話者の作り方に合わせて調整されているため。
    """

    existing = {style.style_id: style for style in styles}
    template = replace(styles[0], style_id=NORMAL_STYLE_ID, name="ノーマル")
    return [
        existing.get(style.style_id, style)
        for style in build_expression_styles(template)
    ]
