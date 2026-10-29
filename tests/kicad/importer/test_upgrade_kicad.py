# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An old KiCad board imported through ``kicad-cli pcb upgrade`` on a private copy (``H-K-IMPORT-UPGRADE``;
capability board-to-code, scenario "KiCad 7 board"; change c0275)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from _importcode import OLD_VERSION, imported, old

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_kicad_7_board(tmp_path: Path) -> None:
    source = old(tmp_path)
    before = source.read_bytes()
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    (row,) = reply.result["upgrade"]
    assert row["from_version"] == OLD_VERSION and row["to_version"] > OLD_VERSION
    assert row["tool_version"].startswith("10.")
    assert row["sha256_before"] == hashlib.sha256(before).hexdigest()
    assert source.read_bytes() == before
    assert reply.result["equivalence"] == {"levels": [1, 2, 3, 4, 5], "equivalent": True}
    assert sorted(p.name for p in source.parent.iterdir()) == ["old.kicad_pcb"]
