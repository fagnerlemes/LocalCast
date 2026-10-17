"""Local diagnostics. Does not claim a successful TV/hardware test."""

import importlib.metadata
import json
import logging
import platform
import subprocess
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __build__, __version__
from .paths import data_dir, process_options, tool_path


def close_logging():
    logger = logging.getLogger()
    for handler in list(logger.handlers):
        if isinstance(handler, RotatingFileHandler) and (
            Path(handler.baseFilename).parent == data_dir() / 'logs'
        ):
            logger.removeHandler(handler)
            handler.close()


def configure_logging() -> Path:
    directory = data_dir() / "logs"
    directory.mkdir(exist_ok=True)
    path = directory / "localcast.log"
    handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
    return path


def environment_report() -> dict:
    report = {
        "localcast": __version__,
        "build": __build__,
        "python": platform.python_version(),
        "system": platform.platform(),
        "data_dir": str(data_dir()),
        "hardware_test": "Não executado por este relatório",
    }
    for package in ("PySide6", "PyChromecast", "psutil"):
        try:
            report[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            if package == "PySide6":
                try:
                    report[package] = importlib.metadata.version("PySide6-Essentials")
                    report["PySide6_package"] = "PySide6-Essentials"
                except importlib.metadata.PackageNotFoundError:
                    report[package] = "ausente"
            else:
                report[package] = "ausente"
    for name in ("ffmpeg", "ffprobe"):
        try:
            path = tool_path(name)
            result = subprocess.run(
                [path, "-version"],
                check=False,
                capture_output=True,
                timeout=10,
                **process_options(),
            )
            report[name] = {
                "path": path,
                "version": result.stdout.decode("utf-8", "replace").splitlines()[0],
                "ok": result.returncode == 0,
            }
        except (OSError, subprocess.SubprocessError, IndexError) as exc:
            report[name] = {"ok": False, "error": str(exc)}
    return report


def hints(snapshot: dict) -> list[str]:
    messages = []
    if snapshot.get('history_warning'):
        messages.append(snapshot['history_warning'])
    if snapshot.get("last_failure"):
        failure = snapshot["last_failure"]
        messages.append("Última falha: " + failure["message"])
        messages.extend(hints(failure["session"]))
    active = snapshot.get("mode")
    http = snapshot.get("http", {})
    if active and not snapshot.get("connected"):
        messages.append("Conexão Cast caiu. Confira Wi-Fi, energia e TCP 8009.")
    if active and not http.get("get_ok"):
        messages.append(
            "Sem GET de mídia confirmado: confira IP LAN, firewall TCP e isolamento de clientes no roteador."
        )
    if http.get("errors"):
        messages.append(
            "HTTP registrou erro: confira playlist/segmentos, Range e se a sessão foi substituída."
        )
    if snapshot.get("load_error") or snapshot.get("idle_reason") == "ERROR":
        messages.append(
            "Receiver rejeitou o arquivo original. Escolha conversão automática e transmita novamente. Não foi feita conversão de fallback."
            if active == "original"
            else "Receiver rejeitou a mídia. Compare MP4 direto e Forçar HLS; HTTP OK não garante codec ou receiver compatível."
        )
    transcode = snapshot.get("transcode")
    if transcode:
        if transcode.get("control_warning"):
            messages.append("Controle da reserva: " + transcode["control_warning"])
        if transcode.get("fallbacks"):
            messages.append("GPU não concluiu o início; alternativa ativa: " + transcode["encoder"])
        if transcode.get("error"):
            messages.append(transcode["error"])
        if transcode.get("returncode") not in (None, 0):
            messages.append(
                "FFmpeg encerrou com erro. Consulte stderr_tail e o log; HDR precisa de zscale/tonemap."
            )
        if (
            transcode.get("encoded_seconds", 0) > 10
            and 0 < transcode.get("speed", 0) < 1
            and transcode.get("returncode") is None
            and not transcode.get("resting")
        ):
            messages.append(
                "Conversão abaixo de 1×: pode faltar reserva. Tente GPU automática ou 720p."
            )
    return messages


def write_report(path: Path, snapshot: dict):
    # Don't export capability URLs. Local filename and IP can remain in an intentional report.
    safe = {key: value for key, value in snapshot.items() if key != "content_id"}
    path.write_text(
        json.dumps(
            {"environment": environment_report(), "session": safe, "hints": hints(snapshot)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
