# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for AURA Studio.

Set AURA_ONEFILE=1 to build a single EXE instead of the faster onedir layout.
"""
import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ONEFILE = os.environ.get("AURA_ONEFILE") == "1"

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("pptx")
hiddenimports += collect_submodules("pyttsx3")
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "fastapi",
    "starlette",
    "starlette.responses",
    "starlette.staticfiles",
    "pydantic",
    "pydantic_core",
    "anyio",
    "h11",
    "httpx",
    "httpcore",
    "certifi",
    "openai",
    "mutagen",
    "mutagen.mp3",
    "mutagen.id3",
    "mutagen.flac",
    "mutagen.mp4",
    "mutagen.oggvorbis",
    "mutagen.ogg",
    "mutagen.easyid3",
    "mutagen.wave",
    "mutagen.aiff",
    "mutagen.asf",
    "pygame",
    "pygame.mixer",
    "markdown_it",
    "mdurl",
    "cryptography",
    "cryptography.fernet",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFilter",
    "PIL.ImageGrab",
    "lxml",
    "lxml.etree",
    "pyaudio",
    "vosk",
    "comtypes",
    "comtypes.client",
    "comtypes.gen",
    "imageio_ffmpeg",
]

binaries = []
binaries += collect_dynamic_libs("vosk")
binaries += collect_dynamic_libs("pyaudio")

datas = [
    ("assets", "assets"),
    ("mobile_web", "mobile_web"),
    ("agents", "agents"),
    ("skills", "skills"),
    ("plugins", "plugins"),
    ("README_RU.md", "."),
]
datas += collect_data_files("pptx", includes=["templates/*"])
datas += collect_data_files("imageio_ffmpeg", includes=["binaries/*"])

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "turtle",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        # openai lazily imports pandas/numpy; scipy/sklearn/torch come from
        # TYPE_CHECKING blocks that PyInstaller would otherwise follow.
        "torch",
        "torchvision",
        "torchaudio",
        "torchtext",
        "functorch",
        "accelerate",
        "transformers",
        "tokenizers",
        "huggingface_hub",
        "safetensors",
        "tensorflow",
        "tensorboard",
        "keras",
        "onnxruntime",
        "scipy",
        "sklearn",
        "pandas",
        "narwhals",
        "numba",
        "matplotlib",
        "seaborn",
        "plotly",
        "bokeh",
        "cv2",
        "yt_dlp",
        "curl_cffi",
        "IPython",
        "ipykernel",
        "jupyter",
        "notebook",
        "nbformat",
        "jedi",
        "parso",
        "openpyxl",
        "xlsxwriter",
        "sqlalchemy",
        "grpc",
        "h5py",
        "sympy",
        "networkx",
        "Crypto",
        "Cryptodome",
        "bcrypt",
        "sounddevice",
        "fsspec",
        "dask",
        "polars",
        "pyarrow",
        "bs4",
        "soupsieve",
        "html5lib",
        "websockets",
        "uvloop",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

common = dict(
    name="AURA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/aura.ico",
    version="packaging/version_info.txt",
)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        exclude_binaries=False,
        **common,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        **common,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="AURA",
    )
