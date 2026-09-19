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

from .. import audio as audio_utils
from ..backends.base import BackendError, SynthesisParams
from ..backends.irodori.backend import IrodoriBackend, voice_id_for
from ..synthesis.steps.resolve_seed import resolve_voice_seed
from .reference import SEED_REFERENCE_TEXT, save_reference_wavs
from .seed_profile import apply_seed_expression_profile
from .seed_source import build_seed_style, create_seed_preset, resolve_seed_source
from .store import VoicePreset, VoicePresetStore


def _resolve_text(reference_text: str | None) -> str:
    return (reference_text or "").strip() or SEED_REFERENCE_TEXT


def bake_seed_reference(
    *,
    irodori: IrodoriBackend,
    store: VoicePresetStore,
    seed: int,
    caption: str | None,
    reference_text: str | None = None,
    source_voice_id: str | None = None,
) -> list[str]:
    """シードの声を 1 本合成し、参照音声として保存してファイル名を返す。

    合成には話者の定義が要るため、一時の話者を作って使い、終わったら必ず消す。
    試聴（/voices/preview-seed）と同じ形で、保存されるのは参照音声だけになる。
    """

    preset = create_seed_preset(
        store, seed=seed, caption=caption, source_voice_id=source_voice_id,
    )

    try:
        output = irodori.synthesize(
            SynthesisParams(
                text=_resolve_text(reference_text),
                voice_id=voice_id_for(preset),
                style_id="normal",
                # 参照に必要なのは声が鳴っている区間だけ。前後の無音はそのぶん
                # latent を食うので付けない。
                pre_silence=0.0,
                post_silence=0.0,
            )
        )
    finally:
        # 合成が失敗しても一時の話者は残さない。
        store.delete(preset.preset_id)

    if output.samples.size == 0:
        raise BackendError("参照音声を合成できませんでした。読ませる文を変えてお試しください。")

    wav = audio_utils.encode_wav(output.samples, sample_rate=output.sample_rate)
    return save_reference_wavs([wav])


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
) -> VoicePreset:
    """シードの声を焼き付けた話者を作る。

    シードは話者へ残す。声そのものは参照音声が決めるようになるが、同じ文なら同じ音に
    なる再現性はシードが担っており、どの値から生まれた声なのかも辿れる。
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

    return store.create(
        name=name,
        description=description,
        color_key=color_key,
        mode="reference",
        styles=[
            apply_seed_expression_profile(build_seed_style(source, caption))
        ],
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

    styles = [apply_seed_expression_profile(definition).to_json() for definition in preset.styles]

    return store.update(
        preset_id,
        {
            "mode": "reference",
            "reference_files": reference_files,
            "voice_seed": seed,
            "styles": styles,
        },
    )
