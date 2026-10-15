"""Validate private Python and native Qt/Cast imports, without LAN discovery."""

import json
import struct
import sys
from importlib import import_module
from pathlib import Path

import PySide6

import localcast


def main():
    if not hasattr(import_module("PySide6.QtWidgets"), "QApplication"):
        raise RuntimeError("Qt Widgets indisponível.")
    if not hasattr(import_module("pychromecast"), "get_chromecasts"):
        raise RuntimeError("PyChromecast indisponível.")
    root = Path(__file__).resolve().parents[1]
    if sys.version_info < (3, 11) or struct.calcsize("P") != 8:
        raise RuntimeError("Python portátil precisa ser 3.11+ de 64 bits.")
    app_file = Path(localcast.__file__).resolve()
    if not app_file.is_relative_to(root / "src"):
        raise RuntimeError("O runtime não carregou o código desta pasta LocalCast.")
    print(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "PySide6": PySide6.__version__,
                "mode": "portable",
                "global_python_required": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
