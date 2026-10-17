"""Playback-relative high/low watermarks; no fixed CPU percentage or wall-clock limit."""

import math
from dataclasses import dataclass


@dataclass
class BufferBudget:
    target: float = 90
    suspended: bool = False
    ahead: float = 0

    def __post_init__(self):
        if not math.isfinite(self.target) or not 30 <= self.target <= 300:
            raise ValueError("Antecipação deve estar entre 30 e 300 segundos.")

    @property
    def resume_at(self):
        return max(12, self.target / 2)

    def decide(self, published_seconds, position, state, *, finishing=False):
        # A missing/untrusted receiver clock must never leave FFmpeg suspended.
        if position is None or state not in {"PREPARING", "PLAYING", "PAUSED", "BUFFERING"}:
            self.suspended = False
            return False
        if not math.isfinite(position) or position < 0:
            self.suspended = False
            return False
        self.ahead = max(0, published_seconds - position)
        if finishing:
            self.suspended = False
        elif self.suspended:
            self.suspended = self.ahead > self.resume_at
        else:
            self.suspended = self.ahead >= self.target
        return self.suspended
