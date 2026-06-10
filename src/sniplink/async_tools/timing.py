"""Timing utilities for the async tools module."""

from __future__ import annotations

import time


class Timer:
    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.ended = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        end = getattr(self, "ended", time.perf_counter())
        return (end - self.started) * 1000
