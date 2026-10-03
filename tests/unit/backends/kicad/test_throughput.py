# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read and write throughput on a board of at least 5 MiB (capability kicad-file-backend, "Read and write
throughput is measured"; change c0020). A measurement, never a gate: it asserts no time limit, runs only
when ``FENOLITE_CENSUS_OUT`` names a file, and records its numbers for ``docs/evidence/kicad-board-read.md``.

The clock is ``time.perf_counter_ns`` (S-0090) and the memory figure the peak that ``tracemalloc`` traces
(S-0091), measured in a separate pass because tracing slows the code down.
"""

from __future__ import annotations

import os
import platform
import sys
import time
import tracemalloc
from collections.abc import Callable

import pytest
from _boards import census, large_board

from fenolite.backends.kicad.pcb import read_board, write_board

MIN_BYTES = 5 * 2**20
RUNS = 3


def _best_ns(action: Callable[[], object]) -> int:
    best = -1
    for _ in range(RUNS):
        started = time.perf_counter_ns()
        action()
        elapsed = time.perf_counter_ns() - started
        best = elapsed if best < 0 else min(best, elapsed)
    return best


def _peak_bytes(action: Callable[[], object]) -> int:
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        action()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_read_write_5mib() -> None:
    if not os.environ.get("FENOLITE_CENSUS_OUT"):
        pytest.skip("a measurement: set FENOLITE_CENSUS_OUT to a file to run it")
    design = large_board(min_bytes=MIN_BYTES)
    text = write_board(design, target=10).text
    size = len(text.encode("utf-8"))
    assert size >= MIN_BYTES
    read_ns = _best_ns(lambda: read_board(text))
    write_ns = _best_ns(lambda: write_board(design, target=10))
    mib = size / 2**20
    census(
        "throughput",
        "read_write_5mib",
        {
            "bytes": size,
            "read_seconds": round(read_ns / 1e9, 3),
            "write_seconds": round(write_ns / 1e9, 3),
            "read_mib_per_second": round(mib / (read_ns / 1e9), 2),
            "write_mib_per_second": round(mib / (write_ns / 1e9), 2),
            "read_peak_bytes": _peak_bytes(lambda: read_board(text)),
            "write_peak_bytes": _peak_bytes(lambda: write_board(design, target=10)),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    )
