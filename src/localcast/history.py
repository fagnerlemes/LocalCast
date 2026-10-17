"""Small transactional playback store and receiver-confirmed checkpoint policy.

By Fagner Lemes. No movie names or playback positions leave this computer.
"""

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .storage import safe_path


@dataclass(frozen=True)
class VideoIdentity:
    key: str
    path: str
    name: str
    size: int
    modified_ns: int

    @classmethod
    def from_path(cls, path):
        path = Path(path).resolve(strict=True)
        stat = path.stat()
        normalized = os.path.normcase(str(path))
        identity = json.dumps([normalized, stat.st_size, stat.st_mtime_ns], ensure_ascii=False)
        return cls(hashlib.sha256(identity.encode()).hexdigest(), normalized,
                   path.name, stat.st_size, stat.st_mtime_ns)


def completed(position, duration):
    return duration > 0 and (
        position >= duration * .95 or (duration >= 1200 and duration - position < 180)
    )


def resume_position(row):
    if not row or row['completed'] or row['duration'] <= 0:
        return 0.0
    return row['position'] if 30 <= row['position'] < row['duration'] else 0.0


class HistoryStore:
    def __init__(self, root):
        self.path = Path(root) / 'playback.db'
        self.lock = threading.RLock()
        self.epoch = 0
        self.error = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            safe_path(self.path.parent, self.path)
            db = self.connect()
            try:
                version = db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1):
                    raise ValueError('Banco de uma versão mais recente; histórico preservado.')
                db.execute('''CREATE TABLE IF NOT EXISTS playback (
                    id TEXT PRIMARY KEY, path TEXT NOT NULL, name TEXT NOT NULL,
                    size INTEGER NOT NULL, modified_ns INTEGER NOT NULL,
                    duration REAL NOT NULL, position REAL NOT NULL,
                    updated_at REAL NOT NULL, completed INTEGER NOT NULL)''')
                db.execute('PRAGMA user_version=1')
                db.commit()
            finally:
                db.close()
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.error = f'Histórico indisponível; reprodução continua disponível. {exc}'

    def connect(self):
        safe_path(self.path.parent, self.path)
        connection = sqlite3.connect(self.path, timeout=2)
        connection.row_factory = sqlite3.Row
        return connection

    def get(self, identity):
        if self.error:
            return None
        with self.lock:
            db = self.connect()
            try:
                row = db.execute('SELECT * FROM playback WHERE id=?', (identity.key,)).fetchone()
                return dict(row) if row else None
            finally:
                db.close()

    def save(self, identity, position, duration, epoch, finished=False):
        if self.error or not all(math.isfinite(v) and v >= 0 for v in (position, duration)):
            return False
        with self.lock:
            if epoch != self.epoch:
                return False
            if duration:
                position = min(position, duration)
            db = self.connect()
            try:
                with db:
                    db.execute('''INSERT INTO playback VALUES (?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET duration=excluded.duration,
                        position=excluded.position, updated_at=excluded.updated_at,
                        completed=excluded.completed''', (
                        identity.key, identity.path, identity.name, identity.size,
                        identity.modified_ns, duration, position, time.time(),
                        int(finished or completed(position, duration)),
                    ))
                return True
            finally:
                db.close()

    def clear(self):
        with self.lock:
            self.epoch += 1
            if self.error:
                raise RuntimeError(self.error)
            db = self.connect()
            try:
                with db:
                    db.execute('PRAGMA secure_delete=ON')
                    db.execute('DELETE FROM playback')
                db.execute('VACUUM')
            finally:
                db.close()

    def count(self):
        if self.error:
            return 0
        with self.lock:
            db = self.connect()
            try:
                return db.execute('SELECT COUNT(*) FROM playback').fetchone()[0]
            finally:
                db.close()

    def reset(self):
        """Explicit factory reset can also recover a corrupt/unreadable schema."""
        with self.lock:
            epoch, lock = self.epoch + 1, self.lock
            for suffix in ('', '-journal', '-wal', '-shm'):
                path = safe_path(self.path.parent, Path(str(self.path) + suffix))
                path.unlink(missing_ok=True)
            self.__init__(self.path.parent)
            self.epoch, self.lock = epoch, lock
            if self.error:
                raise RuntimeError(self.error)


class PlaybackTracker:
    """Caller serializes this policy with the owning playback session's lock."""
    def __init__(self, store, identity, duration, expected=0, serial_floor=0):
        self.store, self.identity, self.duration = store, identity, duration
        self.epoch = store.epoch
        self.expected, self.serial = expected, serial_floor
        self.confirmed = False
        self.last = None
        self.last_saved = float('-inf')
        self.last_state = None
        self.finished = False

    def observe(self, sample, now=None, force=False):
        now = time.monotonic() if now is None else now
        serial = sample.get('status_serial', 0)
        valid = (sample.get('connected') and sample.get('matches_media')
                 and sample.get('status_age_seconds', 999) <= 15 and serial > self.serial)
        changed = False
        accepted = False
        if valid:
            self.serial = serial
            state = sample.get('player_state')
            raw = sample.get('reported_position')
            if state in ('PLAYING', 'PAUSED') and isinstance(raw, (float, int)):
                if math.isfinite(raw) and raw >= 0:
                    if not self.confirmed and not self.expected - 5 <= raw <= self.expected + 30:
                        return False
                    # A STOP/LOAD transient must not erase a confirmed point. Explicit
                    # seek/restart creates a fresh tracker with its own expected point.
                    if self.confirmed and raw == 0 and self.last and self.last > 5:
                        return False
                    self.confirmed = True
                    accepted = True
                    self.last = min(raw, self.duration) if self.duration else raw
                    changed = state == 'PAUSED' and self.last_state != 'PAUSED'
                    self.last_state = state
            elif state == 'IDLE' and sample.get('idle_reason') == 'FINISHED' and self.confirmed:
                self.finished = True
                self.last = self.duration or self.last
                changed = True
        if self.last is not None and (force or changed or (
            accepted and self.last_state == 'PLAYING' and now - self.last_saved >= 10
        )):
            saved = self.store.save(self.identity, self.last, self.duration,
                                    self.epoch, self.finished)
            if saved:
                self.last_saved = now
            return saved
        return False
