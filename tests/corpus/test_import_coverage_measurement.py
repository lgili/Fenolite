# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The emission-only measurement agrees with a complete import of a declared small public board."""

from pathlib import Path

import pytest
from _corpus import manifest_items, require
from _importcoverage import counts, measure, observation

from fenolite.api import run

pytestmark = pytest.mark.needs_corpus
ITEMS = [
    next(item for item in manifest_items("rt0") if item.id == ident)
    for ident in ("kicad-demo-10-0-6-pcb-03", "kicad-demo-10-0-6-pcb-07")
]


@pytest.mark.parametrize("item", ITEMS, ids=[item.id for item in ITEMS])
def test_public_measurement_agrees_with_complete_cli(
    item, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    source = require(item)
    measured = measure(source, ident=item.id, date="2026-11-02")
    reply = run(
        "import",
        str(source),
        "--to",
        "python",
        "--out",
        "out",
        "--allow-lossy",
        "--dry-run",
        cwd=tmp_path,
        timestamp="2026-11-01T00:00:00Z",
    )
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert reply.result["equivalence"]["equivalent"] is True
    assert measured["unexpressed"] == counts(reply.result["unexpressed"])
    assert measured["counts"] == reply.result["counts"]
    recorded = next(row for row in observation()["rows"] if row["id"] == item.id)
    assert recorded["input_sha256"] == measured["input_sha256"]
    assert recorded["unexpressed"] == measured["unexpressed"] and recorded["counts"] == measured["counts"]
    assert not (tmp_path / "out").exists()
