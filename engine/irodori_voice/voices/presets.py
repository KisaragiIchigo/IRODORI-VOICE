"""同梱の話者プリセット。

参照音声を 1 本も持っていない状態でも起動直後に合成できるよう、キャプション条件だけで
成立する話者を用意している。声の同一性は乱数シードに依存するため、同じ話者でもシードを
変えると別人になる。固定したい場合はスタイル側でシードを指定するか、気に入った声を
参照音声として書き出して「参照あり話者」を作る運用を想定している。

各スタイルには注釈絵文字を添えてある。Irodori-TTS はこれを表現の指示として解釈し、
キャプションより強く効く。ノーマルにだけ付けないのは、素の声を確かめる基準が
どの話者にも要るため。
"""

from __future__ import annotations

from .store import VoicePreset, VoiceStyleDef


def _styles(*rows: tuple[str, str, str, str | None]) -> list[VoiceStyleDef]:
    return [
        VoiceStyleDef(style_id=style_id, name=name, caption=caption, emoji=emoji)
        for style_id, name, caption, emoji in rows
    ]


BUILTIN_PRESETS: list[VoicePreset] = [
    VoicePreset(
        preset_id="design-soft-female",
        name="やわらか",
        description="近い距離感で落ち着いて話す女性の声です。ナレーションや解説に向きます。",
        color_key="kobai",
        mode="caption",
        builtin=True,
        styles=_styles(
            ("normal", "ノーマル", "落ち着いた、近い距離感の女性話者。丁寧で穏やかな語り口。", None),
            ("joy", "よろこび", "落ち着いた女性話者。嬉しそうに、少し弾んだ調子で話している。", "😊"),
            ("sorrow", "かなしみ", "落ち着いた女性話者。沈んだ声で、ゆっくりと話している。", None),
            ("whisper", "ささやき", "落ち着いた女性話者。ごく近い距離でささやくように話している。", "👂"),
        ),
    ),
    VoicePreset(
        preset_id="design-bright-female",
        name="はきはき",
        description="明るくテンポよく話す女性の声です。実況や紹介動画に向きます。",
        color_key="yamabuki",
        mode="caption",
        builtin=True,
        styles=_styles(
            ("normal", "ノーマル", "明るくはきはきと話す若い女性話者。テンポが良く聞き取りやすい。", None),
            ("joy", "よろこび", "明るい女性話者。とても楽しそうに、笑いを含んだ声で話している。", "😆"),
            ("anger", "おこり", "明るい女性話者。少し怒ったように、強い語調で話している。", "😠"),
            ("calm", "おちつき", "明るい女性話者。トーンを落として、丁寧に説明している。", "😌"),
        ),
    ),
    VoicePreset(
        preset_id="design-calm-male",
        name="おだやか",
        description="低めで落ち着いた男性の声です。朗読や真面目な解説に向きます。",
        color_key="asagi",
        mode="caption",
        builtin=True,
        styles=_styles(
            ("normal", "ノーマル", "落ち着いた大人の男性話者。低めの声で、丁寧に話している。", None),
            ("warm", "やさしさ", "落ち着いた大人の男性話者。親しい相手に、やわらかく話しかけている。", "🫶"),
            ("serious", "まじめ", "落ち着いた大人の男性話者。真剣な調子で、はっきりと話している。", None),
            ("whisper", "ささやき", "落ち着いた大人の男性話者。声を潜めて、静かに話している。", "👂"),
        ),
    ),
    VoicePreset(
        preset_id="design-lively-male",
        name="たのしい",
        description="軽快でくだけた男性の声です。掛け合いやコメント読み上げに向きます。",
        color_key="wakatake",
        mode="caption",
        builtin=True,
        styles=_styles(
            ("normal", "ノーマル", "余裕のある大人の男性。くだけた雰囲気で、楽しそうに話している。", None),
            ("joy", "よろこび", "余裕のある大人の男性。笑いながら、ご機嫌に話している。", "😆"),
            ("tired", "あきれ", "余裕のある大人の男性。冷めた調子で話している。", "😒"),
            ("shout", "よびかけ", "余裕のある大人の男性。少し離れた相手に、張った声で呼びかけている。", "📣"),
        ),
    ),
    VoicePreset(
        preset_id="design-narration",
        name="ナレーション",
        description="抑揚を抑えた中性的な声です。字幕読み上げや情報系の動画に向きます。",
        color_key="rurikon",
        mode="caption",
        builtin=True,
        styles=_styles(
            ("normal", "ノーマル", "抑揚を抑えた中性的な声のナレーター。淡々と正確に読み上げている。", None),
            ("documentary", "ドキュメント", "落ち着いたナレーター。間を取りながら、重みのある調子で読み上げている。", "📖"),
            ("news", "ニュース", "明瞭なナレーター。ニュース原稿を読むように、一定のテンポで読み上げている。", "📄"),
        ),
    ),
]
