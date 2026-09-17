"""注釈絵文字の表現を、読み上げ本文とは別の補助条件へ変換する。"""

from __future__ import annotations

import re


EXPRESSION_CAPTIONS: dict[str, str] = {
    "😊": "明るくにこやかな声で、嬉しそうに話している。",
    "😆": "楽しくてたまらない様子で、弾んだ声で笑いながら話している。",
    "😭": "悲しみに耐えられず、涙を流して嗚咽しながら話している。",
    "😠": "強い怒りを込めて、苛立った厳しい声で話している。",
    "🙄": "呆れ果てた様子で、うんざりした投げやりな声で話している。",
    "😌": "緊張が解けてほっと安心し、穏やかで柔らかな声で話している。",
    "😟": "相手を心配し、気がかりで落ち着かない声で話している。",
    "😲": "予想外の出来事に驚き、思わず声を上げて話している。",
    "😖": "強い痛みに耐えながら、苦しげに声を絞り出して話している。",
    "🥺": "不安で心細く、声を震わせながら恐る恐る話している。",
    "👂": "耳元でそっと囁くように、息を含んだ小さな声で話している。",
    "📣": "遠くにいる相手へ届くように、よく通る大きな声で呼びかけている。",
    "😱": "切羽詰まった様子で、声を張り上げて激しく叫んでいる。",
    "🐢": "一語ずつ間を取りながら、ゆっくりとした口調で話している。",
    "⏩": "言葉を次々につなげて、間を詰めた早口で話している。",
    "🤐": "口を十分に開けず、くぐもった聞き取りにくい声で話している。",
    "🫣": "恥ずかしがってためらいながら、控えめな小声で話している。",
    "😏": "いたずらっぽく笑みを浮かべ、相手をからかう口調で話している。",
    "😪": "眠気で力が抜け、まどろむような気だるい声で話している。",
    "😴": "眠ったまま寝言を漏らすように、かすかな声で呟いている。",
    "🥱": "眠くて大きなあくびをしながら、途切れがちな声で話している。",
    "🥴": "酒に酔って呂律が回らず、語尾を伸ばした不安定な口調で話している。",
    "😰": "ひどく慌てて焦り、息を乱しながらせわしなく話している。",
    "🤔": "疑問を感じて考え込み、確かめるように問いかけている。",
    "🤭": "笑いをこらえながら、くすくすと小さな笑い声を漏らしている。",
    "😮‍💨": "疲れた様子で、息を長く吐いてため息をついている。",
    "⏸️": "言葉を止めて黙り込み、無言の間を置いている。",
    "📞": "電話の受話器越しに聞こえる、帯域の狭いこもった声で話している。",
    "📢": "声が周囲に反響し、エコーが重なって聞こえている。",
    "🎵": "口を閉じて、言葉にせず旋律を鼻歌で口ずさんでいる。",
    "🥤": "飲み物を口に含み、ごくりと喉を鳴らして飲み込んでいる。",
    "🤧": "鼻がむずむずして、咳やくしゃみを漏らしている。",
    "💋": "唇を軽く開閉し、唇の触れ合う小さなリップノイズを出している。",
}

_EXPRESSION_PATTERN = re.compile(
    "|".join(sorted(map(re.escape, EXPRESSION_CAPTIONS), key=len, reverse=True))
)


def build_expression_caption(
    text: str, *, style_caption: str | None, explicit_caption: str | None,
) -> str | None:
    """明示指定を優先し、それ以外はスタイルの条件に注釈の補助指示を足す。"""
    if explicit_caption is not None:
        return explicit_caption if explicit_caption.strip() else None

    caption = style_caption if style_caption and style_caption.strip() else ""
    annotations = dict.fromkeys(_EXPRESSION_PATTERN.findall(text))
    for annotation in annotations:
        expression = EXPRESSION_CAPTIONS[annotation]
        if expression not in caption:
            caption = f"{caption}\n{expression}" if caption else expression
    return caption or None
