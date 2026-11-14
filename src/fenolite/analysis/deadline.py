# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The deadline of the power analysis and of the split (change c0503; capability board-analyses,
"Deadline of power and split"; ``docs/analyses.md``, "Power paths").

The clock is injectable so that tests cut a run at a chosen point without waiting."""

from __future__ import annotations

import time
from collections.abc import Callable


class Deadline:
    """``seconds`` (whole) from the moment it is made, read in nanoseconds on ``clock`` (default
    ``time.monotonic_ns``): integers only, as everywhere in ``fenolite.analysis``."""

    __slots__ = ("_clock", "_end", "seconds")

    def __init__(self, seconds: int, clock: Callable[[], int] = time.monotonic_ns) -> None:
        if seconds < 0:
            raise ValueError(f"a deadline must be 0 seconds or more, got {seconds}")
        self.seconds = seconds
        self._clock = clock
        self._end = clock() + seconds * 1_000_000_000

    def passed(self) -> bool:
        return self._clock() >= self._end


def passed(deadline: Deadline | None) -> bool:
    """Whether ``deadline`` is set and has passed."""
    return deadline is not None and deadline.passed()


__all__ = ["Deadline", "passed"]
