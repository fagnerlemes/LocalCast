# PyInstaller onedir: easier diagnosis and codec-tool distribution on Windows.
from pathlib import Path
import os
import tomllib
from PyInstaller.utils.hooks import collect_submodules, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct,
    VarFileInfo, VarStruct,
)

root = Path(SPECPATH)
version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
version_tuple = tuple(int(part) for part in version.split('.')) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple,
                      mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable('041604B0', [
        StringStruct('CompanyName', 'By Fagner Lemes'),
        StringStruct('FileDescription', 'LocalCast para Windows'),
        StringStruct('FileVersion', version),
        StringStruct('InternalName', 'LocalCast'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026 Fagner Lemes'),
        StringStruct('OriginalFilename', 'LocalCast.exe'),
        StringStruct('ProductName', 'LocalCast'),
        StringStruct('ProductVersion', version),
    ])]), VarFileInfo([VarStruct('Translation', [1046, 1200])])],
)
onefile = os.environ.get('LOCALCAST_BUILD_ONEFILE') == '1'
binaries = []
if os.environ.get('LOCALCAST_BUILD_INCLUDE_FFMPEG') == '1':
    binaries = [(str(root / 'tools' / name), 'tools') for name in ('ffmpeg.exe', 'ffprobe.exe')]

a = Analysis(
    [str(root / 'run_localcast.py')],
    pathex=[str(root / 'src')],
    binaries=binaries,
    datas=[(str(root / 'assets'), 'assets'), (str(root / 'LICENSE'), '.'),
           (str(root / 'THIRD_PARTY_NOTICES.md'), '.'), (str(root / 'licenses'), 'licenses')]
          + copy_metadata('PyChromecast') + copy_metadata('PySide6-Essentials') + copy_metadata('psutil'),
    hiddenimports=collect_submodules('pychromecast.controllers'),
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets'],
)
pyz = PYZ(a.pure)
options = dict(name='LocalCast', debug=False, bootloader_ignore_signals=False,
               strip=False, upx=False, console=False, icon=str(root / 'assets' / 'localcast.ico'),
               version=version_info)
if onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **options)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LocalCast')

