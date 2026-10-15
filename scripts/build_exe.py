"""Prepare verified local build tools and build without installing global Python packages."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tomllib
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def prepare_tools(root):
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    manifest = json.loads((root / "build-manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != 1 or manifest["platform"] != "windows-x64":
        raise ValueError("Manifesto das ferramentas de compilação inválido.")
    destination = root / ".build-tools"
    marker = destination / "localcast-build-manifest.json"
    if marker.is_file() and json.loads(marker.read_text(encoding="utf-8")) == manifest:
        return destination
    stage = root / (".build-tools-stage-" + uuid.uuid4().hex[:8])
    stage.mkdir()
    try:
        for item in manifest["packages"]:
            parsed = urlsplit(item["url"])
            if parsed.scheme != "https" or parsed.hostname != "files.pythonhosted.org":
                raise ValueError("Origem de download não permitida.")
            filename = item["filename"]
            if Path(filename).name != filename:
                raise ValueError("Nome de download inválido.")
            print("Baixando ferramenta: " + filename, flush=True)
            request = Request(item["url"], headers={"User-Agent": f"LocalCast-build/{version}"})
            with urlopen(request, timeout=60) as response:
                body = response.read(25_000_001)
            if len(body) > 25_000_000 or hashlib.sha256(body).hexdigest() != item["sha256"]:
                raise ValueError("Checksum não confere: " + filename)
            archive = stage / filename
            archive.write_bytes(body)
            with zipfile.ZipFile(archive) as bundle:
                for entry in bundle.infolist():
                    target = (stage / entry.filename).resolve()
                    if not target.is_relative_to(stage.resolve()):
                        raise ValueError("Wheel contém caminho fora do destino.")
                bundle.extractall(stage)
            archive.unlink()
        (stage / marker.name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if destination.exists():
            backup = root / (".build-tools-backup-" + uuid.uuid4().hex[:8])
            if not destination.resolve().is_relative_to(
                root.resolve()
            ) or not backup.resolve().is_relative_to(root.resolve()):
                raise ValueError("Pasta fora do projeto.")
            destination.rename(backup)
        stage.rename(destination)
    finally:
        if stage.exists() and stage.resolve().is_relative_to(root.resolve()):
            shutil.rmtree(stage)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--onefile", action="store_true")
    parser.add_argument("--include-ffmpeg", action="store_true")
    parser.add_argument("--install-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    tools = prepare_tools(root)
    sys.path.insert(0, str(tools))
    # Avoid collecting similarly named DLLs from unrelated applications in PATH.
    native_directories = [Path(sys.executable).parent, Path(sys.base_prefix)]
    for package in ("PySide6", "shiboken6"):
        spec = importlib.util.find_spec(package)
        if spec and spec.submodule_search_locations:
            native_directories.extend(Path(path) for path in spec.submodule_search_locations)
    windows = Path(os.environ["SystemRoot"])
    native_directories.extend([windows / "System32", windows])
    os.environ["PATH"] = os.pathsep.join(str(path) for path in native_directories)
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(root / "build" / "pyinstaller-config")
    import PyInstaller.__main__

    if args.install_only:
        print("Ferramentas de compilação prontas nesta pasta.", flush=True)
        return 0
    if args.include_ffmpeg:
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            if not (root / "tools" / name).is_file():
                raise FileNotFoundError("Coloque " + name + " na pasta tools antes de gerar o EXE.")
    os.environ["LOCALCAST_BUILD_INCLUDE_FFMPEG"] = "1" if args.include_ffmpeg else "0"
    os.environ["LOCALCAST_BUILD_ONEFILE"] = "1" if args.onefile else "0"
    mode = "onefile" if args.onefile else "onedir"
    PyInstaller.__main__.run(
        [
            str(root / "localcast.spec"),
            "--noconfirm",
            "--clean",
            "--log-level",
            "WARN",
            "--distpath",
            str(root / "dist"),
            "--workpath",
            str(root / "build" / mode),
        ]
    )
    result = root / "dist" / ("LocalCast.exe" if args.onefile else "LocalCast/LocalCast.exe")
    if not result.is_file():
        raise RuntimeError("O executável não foi gerado.")
    if args.onefile:
        shutil.copy2(result, root / "LocalCast.exe")
        print(
            "Pronto: LocalCast.exe na pasta principal. O código-fonte foi preservado.", flush=True
        )
    else:
        print(
            "Pronto: dist/LocalCast/LocalCast.exe. Preserve toda a pasta dist/LocalCast.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("Não foi possível gerar o executável: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
