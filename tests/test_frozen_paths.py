import sys
from pathlib import Path

from localcast.paths import data_dir, tool_path


def test_frozen_uses_existing_portable_settings(monkeypatch, tmp_path):
    executable_root = tmp_path / "LocalCast source"
    portable = executable_root / "localcast-data"
    portable.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_root / "LocalCast.exe"))
    monkeypatch.delenv("LOCALCAST_DATA_DIR", raising=False)
    assert data_dir() == portable


def test_frozen_keeps_data_outside_temporary_bundle(monkeypatch, tmp_path):
    executable_root = tmp_path / "Program"
    extracted = tmp_path / "temporary extraction"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_root / "LocalCast.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(extracted), raising=False)
    monkeypatch.delenv("LOCALCAST_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    assert data_dir() == tmp_path / "appdata/LocalCastMVP"
    assert not extracted.exists()


def test_frozen_finds_extracted_ffmpeg(monkeypatch, tmp_path):
    extracted = tmp_path / "bundle"
    tools = extracted / "tools"
    tools.mkdir(parents=True)
    ffmpeg = tools / "ffmpeg.exe"
    ffmpeg.write_bytes(b"test binary")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "different/LocalCast.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(extracted), raising=False)
    monkeypatch.delenv("LOCALCAST_FFMPEG", raising=False)
    assert Path(tool_path("ffmpeg")) == ffmpeg
