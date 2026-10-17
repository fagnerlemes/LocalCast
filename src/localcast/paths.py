"""Paths for source and PyInstaller; writable state is outside the application."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("LOCALCAST_DATA_DIR")
    if override:
        base = Path(override).expanduser().absolute()
    elif not getattr(sys, "frozen", False):
        base = Path(__file__).resolve().parents[2] / "localcast-dev-data"
    else:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LocalCast"
    base.mkdir(parents=True, exist_ok=True)
    return base


def tool_path(name: str) -> str:
    override = os.environ.get(f"LOCALCAST_{name.upper()}")
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(
                f"LOCALCAST_{name.upper()} não aponta para um arquivo: {candidate}"
            )
        return str(candidate.resolve())
    root = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[2]
    )
    bundled_root = Path(getattr(sys, "_MEIPASS", root))
    for directory in (root / "tools", bundled_root / "tools"):
        candidate = directory / (f"{name}.exe" if os.name == "nt" else name)
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"{name} ausente. Coloque {name}.exe em tools ou configure LOCALCAST_{name.upper()}."
    )


def process_options() -> dict:
    # No console windows for ffprobe/ffmpeg, including PyInstaller --windowed.
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
