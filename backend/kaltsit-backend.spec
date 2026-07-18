import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


backend_directory = Path(SPECPATH)
fastembed_data, fastembed_binaries, fastembed_hidden = collect_all("fastembed")
onnx_data, onnx_binaries, onnx_hidden = collect_all("onnxruntime")

a = Analysis(
    [str(backend_directory / "main.py")],
    pathex=[str(backend_directory)],
    binaries=[*fastembed_binaries, *onnx_binaries],
    datas=[*fastembed_data, *onnx_data],
    hiddenimports=[
        *fastembed_hidden,
        *onnx_hidden,
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
