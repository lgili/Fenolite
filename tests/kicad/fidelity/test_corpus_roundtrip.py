# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""All-level project round trips on external corpus inputs; count ratchets are reviewed, never invented."""

from __future__ import annotations

import json
import time
import tomllib
from pathlib import Path

import pytest
from _fidelity import ALL_LEVELS, difference_counts, roundtrip
from _fidelity_corpus import load_ratchet, materialize, ratchet_problems, rtf_roots

ROOT = Path(__file__).resolve().parents[3]
ROWS = tomllib.loads((ROOT / "tests/corpus/manifest.toml").read_text(encoding="utf-8"))["file"]
BOARDS = rtf_roots(ROWS)
RATCHET = load_ratchet(Path(__file__).with_name("accepted.toml"))
pytestmark = [pytest.mark.needs_corpus, pytest.mark.slow]


@pytest.mark.parametrize("board", BOARDS, ids=lambda row: row["id"])
def test_demo_project_roundtrip(board: dict[str, object], tmp_path: Path) -> None:
    ident = str(board["id"])
    if ident in RATCHET.get("pending", {}):
        pytest.skip(f"{ident}: unreviewed fidelity baseline: {RATCHET['pending'][ident]}")
    baseline = {row["id"]: row for row in RATCHET.get("row", [])}
    assert ident in baseline, f"{ident}: no reviewed fidelity baseline"
    original = materialize(board, ROWS, tmp_path / "original")
    started = time.monotonic()
    reply = roundtrip(original, tmp_path / "roundtrip")
    counts = difference_counts(reply)
    measurement = {
        "probe": "fidelity-demos", "id": ident, "counts": counts,
        "levels": {str(row["level"]): row["status"] for row in reply.result["levels"]},
        "seconds": round(time.monotonic() - started, 3),
    }  # fmt: skip
    (tmp_path / "fidelity-census.json").write_text(json.dumps(measurement, sort_keys=True) + "\n")
    print("FIDELITY_CENSUS " + json.dumps(measurement, sort_keys=True))
    assert reply.exit_code in (0, 5), reply.error
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["reason"] for row in reply.result["levels"] if row["status"] == "skipped")
    assert reply.result["accepted"] == [], "the corpus tier compares raw counts without acceptance globs"
    assert ratchet_problems(ident, counts, baseline[ident]["counts"]) == []
