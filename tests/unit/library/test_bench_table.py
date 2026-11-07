# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The benchmark table of the library's boards (capability fenolite-library, "Benchmark runs"; change
c0279)."""

from __future__ import annotations

from fenolite.library.proof import bench_table

PASSING = {
    "id": "demo-src/blink",
    "seconds": 12.5,
    "levels": [{"level": 1, "status": "equal"}, {"level": 7, "status": "accepted"}],
    "differences": [],
    "fidelity": {"accepted": [], "proof": {"levels": {"1": "equal", "7": "accepted"}}},
}
FAILING = {
    "id": "demo-src/sensor",
    "seconds": 30.0,
    "levels": [{"level": 1, "status": "equal"}, {"level": 2, "status": "differs"}],
    "differences": [{"level": 2, "kind": "net", "where": "J4-0", "a": "no net", "b": "unconnected"}],
    "fidelity": {"accepted": [], "proof": {"levels": {"1": "equal", "2": "equal"}}},
}


def test_benchmark_table() -> None:
    """Scenario "Benchmark table": both boards listed with their levels, only the failing one marked."""
    rows = bench_table([FAILING, PASSING])
    assert [r["id"] for r in rows] == ["demo-src/blink", "demo-src/sensor"]
    assert rows[0]["levels"] == {"1": "equal", "7": "accepted"} and rows[0]["result"] == "pass-with-accepted"
    assert rows[1]["result"] == "fail" and rows[1]["differences"] == 1
    assert [r["issue"] for r in rows] == [False, True]
    again = bench_table([FAILING, PASSING], previous={"demo-src/sensor": "fail"})
    assert [r["issue"] for r in again] == [False, False]
