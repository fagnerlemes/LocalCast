"""Windows installer regression checks; no installation or registry writes."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell installer")
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def powershell(*args, env=None):
    executable = shutil.which("powershell.exe")
    if not executable:
        pytest.skip("Windows PowerShell ausente")
    return subprocess.run(
        [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
        capture_output=True,
        timeout=30,
        env=env,
        check=False,
    )


def test_explicit_runtime_without_launcher():
    result = powershell(
        "-File", str(SCRIPTS / "setup.ps1"), "-CheckOnly", "-Python", sys.executable
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert b"Python encontrado" in result.stdout


def test_invalid_explicit_runtime_reports_actionable_error(tmp_path):
    result = powershell(
        "-File", str(SCRIPTS / "setup.ps1"), "-CheckOnly", "-Python", str(tmp_path / "missing.exe")
    )
    assert result.returncode == 1
    assert b"3.11+" in result.stdout
    assert b"CommandNotFoundException" not in result.stderr


def test_microsoft_store_alias_is_not_started():
    # Explicit WindowsApps is rejected before executing a file or opening Store.
    result = powershell(
        "-File",
        str(SCRIPTS / "setup.ps1"),
        "-CheckOnly",
        "-Python",
        r"C:\Users\Test\AppData\Local\Microsoft\WindowsApps\python.exe",
    )
    assert result.returncode == 1
    assert b"3.11+" in result.stdout


def test_auto_detects_conventional_directory_without_path_or_launcher(tmp_path):
    # Point a conventional installation layout at the real test interpreter.
    installation = tmp_path / "Programs" / "Python" / "Python312"
    installation.mkdir(parents=True)
    # A cmd cannot masquerade as python.exe: mock the probe only, retaining discovery logic.
    (installation / "python.exe").write_bytes(b"candidate-marker")
    environment = dict(os.environ, LOCALAPPDATA=str(tmp_path))
    probe = SCRIPTS / "python-runtime.ps1"
    code = "& { param($Source,$Expected) . $Source; function Test-LocalCastPython { param($Executable,$Prefix) if ($Executable -eq $Expected) { return @{executable=$Executable} } }; $result=Resolve-LocalCastPython; if ($result.executable -ne $Expected) { exit 2 }; Write-Output 'discovery OK' }"
    # Paths are supplied via environment, so spaces/quotes never become shell code.
    environment["LOCALCAST_TEST_SOURCE"] = str(probe)
    environment["LOCALCAST_TEST_EXPECTED"] = str(installation / "python.exe")
    result = powershell(
        "-Command",
        code + " $env:LOCALCAST_TEST_SOURCE $env:LOCALCAST_TEST_EXPECTED",
        env=environment,
    )
    assert result.returncode == 0 and b"discovery OK" in result.stdout, (
        result.stdout,
        result.stderr,
    )
