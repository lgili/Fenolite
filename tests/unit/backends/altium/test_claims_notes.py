# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The round-trip notes of the Altium kinds (capability altium-verification, "Round-trip claims of the
Altium kinds"; change c0090)."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.backends.altium import claims, lower
from fenolite.backends.altium.backend import READ_KINDS
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[4]
HYPOTHESIS = re.compile(r"\((H-A-VER-[A-Z0-9-]+)\)")


def test_every_read_kind_has_a_note_with_a_registered_hypothesis() -> None:
    register = {row.id: row for row in load_register(ROOT / "docs" / "hypotheses.md")}
    assert set(claims.ROUND_TRIP_NOTES) == set(READ_KINDS)
    for kind, note in claims.ROUND_TRIP_NOTES.items():
        (found,) = HYPOTHESIS.findall(note)
        assert found in register and not register[found].result.startswith("refuted"), kind
        assert note.startswith(("RT-A1 ", "RT-A3 inside the written scope ")), kind


def test_no_round_trip_cell_is_set_and_the_document_names_the_lowering() -> None:
    """No Altium kind claims that a file keeps its whole content through a read and a write: RT-A3 counts
    what a rewrite leaves out. The docstring no longer says that no Altium file is read and written back."""
    for row in claims.MATRIX:
        assert row.roundtrip_exact is None and row.roundtrip_modified is None, row.kind
    assert "no Altium file is read and written back" not in (claims.__doc__ or "")
    (document,) = [row for row in claims.MATRIX if row.kind == "altium_pcbdoc"]
    assert document.write is not None and set(lower.EVIDENCE.hypotheses) <= set(document.write.hypotheses)
