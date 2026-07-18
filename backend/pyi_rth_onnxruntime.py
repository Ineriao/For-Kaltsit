import os
import sys
from pathlib import Path


_dll_handles = []
bundle_directory = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
capi_directory = bundle_directory / "onnxruntime" / "capi"
if os.name == "nt" and capi_directory.is_dir():
    os.environ["PATH"] = f"{capi_directory}{os.pathsep}{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        _dll_handles.append(os.add_dll_directory(capi_directory))
