import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


backend_directory = Path(SPECPATH)
fastembed_data, fastembed_binaries, fastembed_hidden = collect_all("fastembed")
onnx_data, onnx_binaries, onnx_hidden = collect_all("onnxruntime")
rapidocr_data, rapidocr_binaries, rapidocr_hidden = collect_all("rapidocr")
sherpa_data, sherpa_binaries, sherpa_hidden = collect_all("sherpa_onnx")

a = Analysis(
    [str(backend_directory / "main.py")],
    pathex=[str(backend_directory)],
    binaries=[*fastembed_binaries, *onnx_binaries, *rapidocr_binaries, *sherpa_binaries],
    datas=[*fastembed_data, *onnx_data, *rapidocr_data, *sherpa_data],
    hiddenimports=[
        *fastembed_hidden,
        *onnx_hidden,
        *rapidocr_hidden,
        *sherpa_hidden,
        "docx",
        "pypdf",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ],
    runtime_hooks=[str(backend_directory / "pyi_rth_onnxruntime.py")],
    noarchive=False,
)

vc_runtime_names = {
    "msvcp140.dll",
    "msvcp140_1.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
}
a.binaries = [
    binary for binary in a.binaries
    if Path(binary[0]).name.lower() not in vc_runtime_names
]
system_directory = Path(os.environ["WINDIR"]) / "System32"
a.binaries += [
    (name, str(system_directory / name), "BINARY")
    for name in sorted(vc_runtime_names)
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="kaltsit-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
