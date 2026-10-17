"""Entry point for pythonw: record startup failures and show a useful Windows dialog."""

import os
import sys
import traceback
from pathlib import Path


def startup_error(exc):
    try:
        from localcast.paths import data_dir

        directory = data_dir() / "logs"
    except Exception:
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LocalCast"
        directory = Path(os.environ.get("LOCALCAST_DATA_DIR", root)) / "logs"
    detail = traceback.format_exc()
    log = directory / "startup.log"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as output:
            output.write(detail + "\n")
    except OSError:
        pass
    message = f"Não foi possível iniciar o LocalCast.\n\n{exc}\n\nDiagnóstico: {log}\nVocê também pode executar iniciar-debug.cmd."
    if sys.stderr is not None:
        sys.stderr.write(detail)
    elif os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "LocalCast - falha ao iniciar", 0x10)


def run():
    try:
        from localcast.__main__ import main

        return main()
    except SystemExit as exc:
        if exc.code in (None, 0):
            return 0
        startup_error(
            RuntimeError(
                "Argumentos inválidos. Execute iniciar-debug.cmd para conferir os detalhes."
            )
        )
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        startup_error(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
