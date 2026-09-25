# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller のビルド定義。

エンジンを単一ディレクトリへ固める。これにより VOICEVOX エディタの
``executionEnabled`` を true にでき、エディタを起動するだけでエンジンも
自動的に立ち上がるようになる。

onefile ではなく onedir にしている。torch と DACVAE を含むため展開サイズが
数 GB になり、onefile だと起動ごとに全体をテンポラリへ展開して待たされる。

collect_submodules を torch や transformers に対して使ってはならない。
これらは実際にモジュールを import して列挙するため、torch では数千モジュールの
読み込みが走り、メモリを数 GB 消費したまま解析が終わらなくなる。
PyInstaller は pyinstaller-hooks-contrib に torch / transformers 用のフックを
持っているので、そちらに任せる。
"""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

ENGINE_ROOT = Path(SPECPATH)

# 自前のパッケージだけを明示的に収集する。動的 import があるため必要。
hidden = collect_submodules("irodori_voice")

# フックが拾わない任意依存を名指しで足す。列挙はしない（上記の理由）。
hidden += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "dacvae",
    "aivmlib",
    "pyopenjtalk",
]

datas = []
binaries = []

# 管理画面のビルド成果物を実行ファイルの隣へ置く。エンジンはここを /admin で配信する。
# admin/ で `pnpm build` を済ませていない場合は同梱しない（画面が無いだけで動く）。
_admin_dist = ENGINE_ROOT.parent / "admin" / "dist"
if (_admin_dist / "index.html").is_file():
    for _item in _admin_dist.rglob("*"):
        if _item.is_file():
            datas.append((str(_item), str(Path("admin") / _item.parent.relative_to(_admin_dist))))

# 同梱話者の参照音声。paths.builtin_voice_assets_dir() はパッケージからの相対位置で探すため、
# _internal/ の下へ同じ相対パスのまま置く。欠けると同梱話者が「参照音声が設定されていません」で鳴らない。
_builtin_voices = ENGINE_ROOT / "irodori_voice" / "voices" / "builtin_assets"
for _item in _builtin_voices.rglob("*.flac"):
    datas.append((str(_item), str(_item.parent.relative_to(ENGINE_ROOT))))

# パッケージのメタデータ（dist-info）は既定ではコピーされない。
# transformers は importlib.metadata.version() で版を読む箇所があり、
# torchcodec については取得の失敗を吸収していないため、
# 「No package metadata was found for torchcodec」で音声系のモジュールが
# まるごと読めなくなる（→ ModernBertModel / DebertaV2Model の解決も巻き添え）。
for distribution in ("torchcodec", "transformers", "style-bert-vits2", "aivmlib"):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

# 小さい任意依存は collect_all で一式を取り込む。動的 import と同梱データを
# 一度に拾えるため、個別に列挙するより漏れにくい。
# audiotools は playback.py が import 時点で templates/headers.html を読むため、
# コードだけ入れても起動しない。
# transformers と torch へ使ってはならない（上記の理由で解析が終わらなくなる）。
for package in ("pyopenjtalk", "style_bert_vits2", "aivmlib", "dacvae", "audiotools", "soundfile"):
    try:
        package_datas, package_binaries, package_hidden = collect_all(package)
    except Exception:
        continue
    datas += package_datas
    binaries += package_binaries
    hidden += package_hidden

# transformers は起動時にパッケージ内の .py を走査し、そこに書かれた __all__ から
# クラス名とモジュールの対応表を組み立てる（transformers/utils/import_utils.py の
# create_import_structure_from_path）。ソースがファイルとして存在しないと、
# アーカイブへ入れてあってもクラスへたどり着けない。
# pyinstaller-hooks-contrib のフックが同じことをしているため現状は重複するが、
# 取りこぼされたときに静かに壊れる箇所なので保険として残す。
try:
    datas += collect_data_files("transformers", include_py_files=True)
except Exception:
    pass

# 実際に使うモデルのアーキテクチャは名指しで含める。
# 対象を絞っているので列挙は一瞬で終わる。
for package in (
    "transformers.models.modernbert",
    "transformers.models.deberta_v2",
    "transformers.models.auto",
):
    try:
        hidden += collect_submodules(package)
    except Exception:
        pass

# 上で拾えなかった場合の保険。
for package in ("pyopenjtalk", "soundfile"):
    try:
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass

analysis = Analysis(
    ["run_engine.py"],
    pathex=[str(ENGINE_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    # 学習系と GUI 系は推論に不要。除外して容量を削る。
    #
    # torch のサブパッケージ（torch.distributed など）は除外してはならない。
    # 推論では使わなくても torch 本体が起動時に import するため、
    # 除外すると ModuleNotFoundError で起動しなくなる。
    excludes=[
        "matplotlib",
        "gradio",
        "wandb",
        "datasets",
        "IPython",
        "tkinter",
        "PyQt5",
        "PySide2",
        "notebook",
        "jupyter",
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="irodori-voice-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="irodori-voice-engine",
)
