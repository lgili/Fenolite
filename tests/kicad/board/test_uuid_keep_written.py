# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Written uuids survive a KiCad re-save (capability kicad-oracle; Fenolite-written half of
H-K-UUID-KEEP-2, the test the refuted H-K-UUID-KEEP names; change c0017)."""

from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

import pytest
from _probes import runner, triad_text

from fenolite.backends.kicad.sexpr import Node, parse, walk

pytestmark = pytest.mark.needs_kicad


def uuids(root: Node) -> Counter[str]:
    return Counter(n.atoms()[0].value for _, n in walk(root) if n.name == "uuid" and n.atoms())


@pytest.mark.kicad_min_major(10)
def test_uuid_keep_written() -> None:
    text = triad_text(10)
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "triad.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        resaved = runner().upgrade_board(board).decode("utf-8")
    assert uuids(parse(resaved)) == uuids(parse(text))
