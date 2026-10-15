"""Real Windows launcher with an offscreen GUI and graceful close; no Chromecast."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows launchers")


@pytest.mark.parametrize("console", [False, True])
def test_launcher_starts_and_closes_gui_with_or_without_console(tmp_path, console):
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pytest.skip("pythonw absent from test runtime")
    bundle = tmp_path / "pasta com espaços [teste]'2"
    scripts = bundle / "scripts"
    scripts.mkdir(parents=True)
    # Suppress native error dialogs only in this temporary test copy.
    launch_script = (ROOT / "scripts/run.ps1").read_text(encoding="utf-8-sig")
    launch_script = launch_script.replace(
        "[System.Windows.Forms.MessageBox]::Show($message, 'LocalCast - falha ao iniciar', 'OK', 'Error') | Out-Null",
        "Write-Output $message",
    )
    (scripts / "run.ps1").write_text(launch_script, encoding="utf-8-sig")
    (scripts / "app-runtime.ps1").write_text(
        "function Get-LocalCastAppRuntime { param($Root) return @{ Executable=$env:LOCALCAST_TEST_PYTHON; Portable=$true } }\n"
        "function Initialize-LocalCastAppRuntime { param($Runtime,$Root) $env:LOCALCAST_DATA_DIR=Join-Path $Root 'data' }\n",
        encoding="utf-8-sig",
    )
    (bundle / "run_localcast.py").write_text(
        """import ctypes, json, os, sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import localcast.gui as gui
gui.environment_report = lambda: {'test': 'no TV'}
app = QApplication([])
window = gui.MainWindow(port=0)
window.show()
QTimer.singleShot(300, window.close)
code = app.exec()
window.worker.thread.join(1)
Path(os.environ['LOCALCAST_TEST_RESULT']).write_text(json.dumps({
    'argv':sys.argv[1:], 'windowed':sys.stdout is None,
    'console_window':ctypes.windll.kernel32.GetConsoleWindow(),
    'exit':code, 'closed':window._can_close,
    'worker_alive':window.worker.thread.is_alive()
}))
""",
        encoding="utf-8",
    )
    result_file = bundle / "result.json"
    environment = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        LOCALCAST_TEST_PYTHON=sys.executable,
        LOCALCAST_TEST_RESULT=str(result_file),
    )
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), environment.get("PYTHONPATH", "")]
    )
    executable = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    args = [
        str(executable),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(scripts / "run.ps1"),
        "-Port",
        "8877",
    ]
    if console:
        args.append("-Console")
    process = subprocess.run(
        args,
        capture_output=True,
        timeout=15,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    launch_log = bundle / "data/logs/startup-launcher.log"
    assert process.returncode == 0, (
        process.stdout,
        process.stderr,
        launch_log.read_text(encoding="utf-8-sig") if launch_log.exists() else "",
    )
    deadline = time.monotonic() + 10
    while not result_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert result_file.exists(), (process.stdout, process.stderr)
    result = json.loads(result_file.read_text())
    assert result["argv"] == ["--port", "8877"]
    assert result["windowed"] is not console
    assert result["console_window"] == 0
    assert result["exit"] == 0 and result["closed"] and not result["worker_alive"]


def test_windowed_startup_failure_has_log_and_visible_alert(monkeypatch, tmp_path):
    import ctypes
    from unittest.mock import Mock

    import localcast.__main__

    spec = importlib.util.spec_from_file_location("localcast_startup", ROOT / "run_localcast.py")
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    monkeypatch.setenv("LOCALCAST_DATA_DIR", str(tmp_path))

    def fail():
        raise RuntimeError("Qt startup test failure")

    monkeypatch.setattr(localcast.__main__, "main", fail)
    monkeypatch.setattr(sys, "stderr", None)
    alert = Mock()
    monkeypatch.setattr(ctypes.windll.user32, "MessageBoxW", alert)
    assert entry.run() == 1
    assert "Qt startup test failure" in (tmp_path / "logs/startup.log").read_text(encoding="utf-8")
    assert "iniciar-debug.cmd" in alert.call_args.args[1]
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setattr(localcast.__main__, "main", lambda: (_ for _ in ()).throw(SystemExit(2)))
    assert entry.run() == 2
