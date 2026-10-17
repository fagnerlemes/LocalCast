import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .diagnostics import configure_logging, environment_report


def main():
    parser = argparse.ArgumentParser(
        description="LocalCast para Windows e Chromecast 2ª geração"
    )
    parser.add_argument("--version", action="version", version=f"LocalCast {__version__}")
    parser.add_argument(
        "--diagnose", action="store_true", help="Verifica dependências, sem buscar TV"
    )
    parser.add_argument("--port", type=int, default=8767, help="Porta HTTP LAN (padrão: 8767)")
    parser.add_argument("--smoke-test", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("porta deve estar entre 1 e 65535")
    from .paths import data_dir
    from .storage import ProfileLease

    lease = ProfileLease(data_dir())
    try:
        return run(args)
    finally:
        lease.close()


def run(args):
    configure_logging()
    if args.diagnose:
        report = environment_report()
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        if sys.stdout is not None:
            print(payload)
        else:
            from .paths import data_dir

            (data_dir() / "logs" / "diagnostico.json").write_text(payload, encoding="utf-8")
        return 0 if all(report[name]["ok"] for name in ("ffmpeg", "ffprobe")) else 1
    try:
        from .gui import launch

        return launch(args.port, args.smoke_test) if args.smoke_test else launch(args.port)
    except Exception:
        logging.getLogger(__name__).exception("Falha ao iniciar LocalCast")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
