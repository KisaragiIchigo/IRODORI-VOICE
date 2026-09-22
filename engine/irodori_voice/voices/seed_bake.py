"""シードの声を参照音声として焼き付ける。

参照音声を持たない話者（mode=caption）は、声を固定する条件を 1 つも持たない。
シードが保証するのは「同じ文なら同じ音」という再現性だけで、文が変われば読み上げの
長さが変わり、初期ノイズの長さも変わる。声を決めているのがそのノイズしかないため、
行ごとに別人になる。

実測（シード 990526849 の話者。全行へ同じシードが渡っていることを確認したうえで）:

    10 文字  F0 中央値 205.6Hz
    23 文字            133.7Hz
    37 文字            119.1Hz
    42 文字            104.2Hz

文が長いほど低くなり、中央値の幅は 101.3Hz に開いた。性別が変わって聞こえるのはこのため。
参照音声を持つ話者では起きない。

そこで作成時に一度だけ合成し、その波形を参照音声として保存する。以降はどの行でも同じ
参照 latent が条件に入るため、声が動かなくなる。

参照は 1 本だけ作る。複数本へ分けて合成すると、その 1 本 1 本が既に別人になってしまい、
混ざった声を手本として渡すことになる（clone.py が 4 本使えるのは、写す元の話者の声が
既に固定されているから）。
"""

from __future__ import annotations

import uuid

from .. import audio as audio_utils
from ..backends.base import BackendError, SynthesisParams
from ..backends.irodori.backend import IrodoriBackend, voice_id_for
from ..synthesis.steps.resolve_seed import resolve_voice_seed
from .expression_styles import build_expression_styles, extend_with_expression_styles
from .reference import (
    REFERENCE_SPEAKER_CFG,
    SEED_FOLLOWUP_TEXTS,
    SEED_REFERENCE_LEAD_SECONDS,
    SEED_REFERENCE_MAX_SECONDS,
    SEED_REFERENCE_TEXT,
    remove_reference_wavs,
    save_reference_wavs,
)
from .seed_profile import apply_seed_expression_profile
from .seed_source import build_seed_style, create_seed_preset, resolve_seed_source
from .store import VoicePreset, VoicePresetStore, VoiceStyleDef


def _resolve_text(reference_text: str | None) -> str:
    return (reference_text or "").strip() or SEED_REFERENCE_TEXT


def _synthesize_reference(
    irodori: IrodoriBackend, preset: VoicePreset, text: str
) -> tuple[bytes, float]:
    """一時の話者へ 1 文読ませ、wav のバイト列とその長さを返す。"""

    output = irodori.synthesize(
        SynthesisParams(
            # 無音の付け外しはサービス層の仕事で、ここはバックエンドを直接呼ぶため効かない。
            # 助走はこのあと自分で足す。
            text=text,
            voice_id=voice_id_for(preset),
            style_id="normal",
            pre_silence=0.0,
            post_silence=0.0,
        )
    )
    if output.samples.size == 0:
        raise BackendError("参照音声を合成できませんでした。読ませる文を変えてお試しください。")

    # 助走の無い参照を手本にすると、生成音声が 0 サンプル目から鳴り出して破裂音になる。
    # 末尾は手本として使わないので足さない。
    samples = audio_utils.pad_silence(
        output.samples,
        sample_rate=output.sample_rate,
        pre_seconds=SEED_REFERENCE_LEAD_SECONDS,
        post_seconds=0.0,
    )
    return (
        audio_utils.encode_wav(samples, sample_rate=output.sample_rate),
        samples.size / float(output.sample_rate),
    )


def _bake_followup_references(
    *,
    irodori: IrodoriBackend,
    store: VoicePresetStore,
    seed: int,
    first_reference: str,
    used_seconds: float,
) -> list[bytes]:
    """固定済みの声で参照音声を足し、wav のバイト列を返す。

    1 本目を参照に持つ一時の話者を作って読ませる。この時点で声は決まっているため、
    何本合成しても同じ人物になる。上限に達したらそこで打ち切る。
    """

    preset = store.create(
        name=f"__seed_ref_{uuid.uuid4().hex[:8]}",
        description="参照音声を足すための一時的な話者",
        color_key="shu",
        mode="reference",
        styles=[
            VoiceStyleDef(
                style_id="normal",
                name="ノーマル",
                cfg_scale_speaker=REFERENCE_SPEAKER_CFG,
            )
        ],
        reference_files=[first_reference],
        voice_seed=seed,
    )

    wavs: list[bytes] = []
    remaining = SEED_REFERENCE_MAX_SECONDS - used_seconds
    try:
        for text in SEED_FOLLOWUP_TEXTS:
            if remaining <= 0.0:
                break
            wav, seconds = _synthesize_reference(irodori, preset, text)
            wavs.append(wav)
            remaining -= seconds
    finally:
        # 合成が失敗しても一時の話者は残さない。
        store.delete(preset.preset_id)

    return wavs


def bake_seed_reference(
    *,
    irodori: IrodoriBackend,
    store: VoicePresetStore,
    seed: int,
    caption: str | None,
    reference_text: str | None = None,
    source_voice_id: str | None = None,
) -> list[str]:
    """シードの声を参照音声として焼き付け、保存したファイル名を返す。

    1 本目は参照を持たない一時の話者で合成する。これでシードの声が決まるので、
    2 本目からはその 1 本目を参照に据え、同じ声のまま読ませて本数を揃える。
    合成には話者の定義が要るため、どちらも一時の話者を作って使い、終わったら必ず消す。
    試聴（/voices/preview-seed）が聴かせるのは 1 本目と同じ音になる。
    """

    preset = create_seed_preset(
        store, seed=seed, caption=caption, source_voice_id=source_voice_id,
    )

    try:
        first_wav, first_seconds = _synthesize_reference(
            irodori, preset, _resolve_text(reference_text)
        )
    finally:
        # 合成が失敗しても一時の話者は残さない。
        store.delete(preset.preset_id)

    names = save_reference_wavs([first_wav])
    try:
        followups = _bake_followup_references(
            irodori=irodori,
            store=store,
            seed=seed,
            first_reference=names[0],
            used_seconds=first_seconds,
        )
    except Exception:
        # 2 本目以降で失敗したら、1 本目を置き去りにしない。
        remove_reference_wavs(names)
        raise

    return names + save_reference_wavs(followups)


def create_voice_from_seed(
    *,
    irodori: IrodoriBackend,
    store: VoicePresetStore,
    name: str,
    seed: int,
    description: str = "",
    color_key: str = "shu",
    caption: str | None = None,
    reference_text: str | None = None,
    source_voice_id: str | None = None,
    with_emotion_styles: bool = True,
) -> VoicePreset:
    """シードの声を焼き付けた話者を作る。

    シードは話者へ残す。声そのものは参照音声が決めるようになるが、同じ文なら同じ音に
    なる再現性はシードが担っており、どの値から生まれた声なのかも辿れる。

    焼き付けたあとは借りた声と同じ mode="reference" の話者になるため、喋り方のスタイルも
    同じ一覧を持たせる。``with_emotion_styles`` を落とすとノーマルだけになる。
    """

    source = resolve_seed_source(store, source_voice_id)
    reference_files = bake_seed_reference(
        irodori=irodori,
        store=store,
        seed=seed,
        caption=caption,
        reference_text=reference_text,
        source_voice_id=source_voice_id,
    )

    normal = apply_seed_expression_profile(build_seed_style(source, caption))
    return store.create(
        name=name,
        description=description,
        color_key=color_key,
        mode="reference",
        styles=build_expression_styles(normal, with_emotion=with_emotion_styles),
        reference_files=reference_files,
        voice_seed=seed,
    )


def bake_existing_voice(
    *,
    irodori: IrodoriBackend,
    store: VoicePresetStore,
    preset_id: str,
    reference_text: str | None = None,
) -> VoicePreset:
    """既にある参照音声なしの話者へ、あとから声を焼き付ける。

    作り直させずに済むよう、話者 ID も名前もアイコンもそのままにして mode だけ移す。
    エディタが覚えている話者の対応付けも変わらない。
    """

    preset = store.get(preset_id)
    if preset.builtin:
        raise BackendError(
            f"同梱話者 {preset.name} には焼き付けられません。複製してからお試しください。"
        )
    if preset.mode != "caption":
        raise BackendError(f"話者 {preset.name} は既に声が固定されています。")

    style = preset.styles[0]
    # シードを持たない話者（表現の指示だけで作ったもの）は、合成時と同じ導出規則で
    # 値を決める。どの行でも声が違う以上どれを焼いても「一つの声を選ぶ」ことに変わりは
    # ないが、合成に使われている値と揃えておけば、焼く前に聴いた声と離れにくい。
    seed = preset.voice_seed
    if seed is None:
        seed = resolve_voice_seed(voice_id_for(preset), style_id=style.style_id)

    reference_files = bake_seed_reference(
        irodori=irodori,
        store=store,
        seed=seed,
        caption=style.caption,
        reference_text=reference_text,
    )

    # 声が固定された以上、借りた声と同じ喋り分けができる。既にあるスタイルは
    # そのまま残し、足りない顔ぶれだけを補う。
    styles = [
        apply_seed_expression_profile(definition).to_json()
        for definition in extend_with_expression_styles(preset.styles)
    ]

    return store.update(
        preset_id,
        {
            "mode": "reference",
            "reference_files": reference_files,
            "voice_seed": seed,
            "styles": styles,
        },
    )
