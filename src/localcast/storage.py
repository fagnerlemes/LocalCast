"""Profile ownership and narrowly scoped local-data maintenance."""

import json
import os
import re
import stat
import threading
from pathlib import Path

import psutil


def safe_path(root, path):
    root, path = Path(root).absolute(), Path(path).absolute()
    if not path.is_relative_to(root) or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Caminho fora dos dados do LocalCast.')
    # Refuse symlinks/junctions both in the profile and every existing ancestor.
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Link ou junção não permitido na limpeza.')
    return path


def atomic_json(path, value):
    path = Path(path)
    safe_path(path.parent, path)
    temporary = path.with_name(path.name + '.tmp')
    safe_path(path.parent, temporary)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class ProfileLease:
    """One running application per profile, without interfering with other versions."""
    def __init__(self, root):
        from PySide6.QtCore import QLockFile
        self.root = Path(root)
        safe_path(self.root, self.root)
        self.lock = QLockFile(str(self.root / '.localcast.lock'))
        if not self.lock.tryLock(0):
            raise RuntimeError('Este perfil do LocalCast já está aberto. Feche a outra janela.')
        self.mutex = None
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.api = ctypes.WinDLL('kernel32', use_last_error=True)
            self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            self.api.CreateMutexW.restype = wintypes.HANDLE
            self.api.CloseHandle.argtypes = [wintypes.HANDLE]
            self.mutex = self.api.CreateMutexW(None, False, 'LocalCast.FagnerLemes.Desktop')

    def close(self):
        if self.mutex:
            self.api.CloseHandle(self.mutex)
            self.mutex = None
        self.lock.unlock()


def process_alive(pid, created):
    try:
        return abs(psutil.Process(pid).create_time() - created) < .1
    except psutil.NoSuchProcess:
        return False
    except (psutil.Error, TypeError, ValueError):
        return True  # Unknown ownership is never permission to delete.


def mark_session(directory, process=None, closed=False):
    owner = psutil.Process()
    child = psutil.Process(process.pid) if process else None
    atomic_json(Path(directory) / '.owner.json', {
        'application': 'LocalCast', 'schema': 1, 'pid': owner.pid,
        'created': owner.create_time(), 'closed': closed,
        'child_pid': child.pid if child else None,
        'child_created': child.create_time() if child else None,
    })


class StorageManager:
    def __init__(self, root, history, movies, session):
        self.root, self.history, self.movies, self.session = Path(root), history, movies, session
        self.lock = threading.RLock()

    def sizes(self):
        result = {'history': 0, 'logs': 0, 'cache': 0, 'movie-cache': 0,
                  'records': self.history.count(), 'path': str(self.root)}
        for key, location in [('history', self.history.path), *[
            (name, self.root / name) for name in ('logs', 'cache', 'movie-cache')
        ]]:
            pending = [location]
            while pending:
                path = pending.pop()
                try:
                    safe_path(self.root, path)
                    if path.is_dir():
                        pending.extend(path.iterdir())
                    elif path.is_file():
                        result[key] += path.stat().st_size
                except (OSError, ValueError):
                    continue
        return result

    def _remove(self, path, result):
        try:
            path = safe_path(self.root, path)
            if path.is_file():
                size = path.stat().st_size
                path.unlink()
                result['bytes'] += size
                result['files'] += 1
        except (OSError, ValueError):
            result['skipped'] += 1

    def _logs(self, result, all_logs=False):
        directory = safe_path(self.root, self.root / 'logs')
        if not directory.is_dir():
            return
        for path in directory.iterdir():
            if re.fullmatch(r'localcast\.log\.[1-3]', path.name) or path.name in {
                'startup.log', 'startup-error.log', 'startup-launcher.log', 'diagnostico.json',
            } or (all_logs and path.name == 'localcast.log'):
                self._remove(path, result)

    def _cache(self, result):
        # Invalidates even a lookup currently waiting on the network, before it writes.
        with self.movies.lock:
            self.movies.epoch += 1
            directory = safe_path(self.root, self.movies.cache)
            if directory.is_dir():
                for path in directory.iterdir():
                    if re.fullmatch(r'[a-f0-9]{64}\.(json|image|json\.tmp)', path.name):
                        self._remove(path, result)
        cache = safe_path(self.root, self.root / 'cache')
        if not cache.is_dir():
            return
        for directory in cache.iterdir():
            try:
                safe_path(self.root, directory)
                if not directory.is_dir() or not directory.name.startswith('session-'):
                    continue
                marker = safe_path(self.root, directory / '.owner.json')
                owner = json.loads(marker.read_text(encoding='utf-8'))
                if owner.get('application') != 'LocalCast' or owner.get('schema') != 1:
                    continue
                if not owner.get('closed') and process_alive(owner['pid'], owner['created']):
                    result['skipped'] += 1
                    continue
                if owner.get('child_pid') and process_alive(owner['child_pid'], owner['child_created']):
                    result['skipped'] += 1
                    continue
                for path in directory.iterdir():
                    if re.fullmatch(r'(master|stream)\.m3u8(\.tmp)?|segment_\d+\.ts(\.tmp)?', path.name):
                        self._remove(path, result)
                # Keep proof of ownership if any unknown/locked content remains.
                if list(directory.iterdir()) == [marker]:
                    self._remove(marker, result)
                    directory.rmdir()
            except (OSError, ValueError, KeyError, TypeError):
                result['skipped'] += 1

    def clean(self, operation):
        if operation not in {'history', 'logs', 'cache', 'reset'}:
            raise ValueError('Operação de limpeza desconhecida.')
        result = {'files': 0, 'bytes': 0, 'skipped': 0}
        with self.lock, self.session._lock:
            active = self.session.mode or self.session.standby_active
            if operation in {'history', 'reset'} and active:
                raise RuntimeError('Desconecte do Chromecast antes de apagar estes dados.')
            safe_path(self.root, self.root)
            if operation == 'history':
                self.history.clear()
            elif operation == 'reset':
                self.history.reset()
            if operation in {'cache', 'reset'}:
                self._cache(result)
            if operation == 'logs':
                self._logs(result)
            if operation == 'reset':
                from .diagnostics import close_logging, configure_logging
                with self.movies.lock:
                    self.movies.epoch += 1
                    self._remove(self.movies.config_path, result)
                    self._remove(self.movies.config_path.with_suffix('.json.tmp'), result)
                # Close only this app's file handlers; never unlink an open log.
                close_logging()
                try:
                    self._logs(result, all_logs=True)
                finally:
                    configure_logging()
        return result
