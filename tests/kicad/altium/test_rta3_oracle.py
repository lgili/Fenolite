# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's importer on rewritten PCB documents (capability altium-verification, "Round-trip level RT-A3";
change c0090; ``H-A-VER-RTA3-KICAD``).

A document is read by Fenolite, its model is written as a new PCB document, and ``kicad-cli pcb import``
reads that rewrite. RT-A3 says that Fenolite's two reads agree; this test says that a second reader, which
shares no code with Fenolite, reads the rewrite as Fenolite does, at the levels 1 to 5 of ``equivalent``
under the profile of the running version. The counts are recorded in ``docs/evidence/altium-roundtrip.md``.
"""

from __future__ import annotations

import _probes
import pytest
from _corpus import manifest_items, require
from _rta3oracle import OWN, SAMPLES, judge, rewrite_sides
from _triangle import counts_line, profile_for

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
ROWS = [item for item in manifest_items("rta") if "-pcbdoc-" in item.id and not item.heavy]
IDS = [item.id for item in ROWS]


@pytest.mark.parametrize("name", OWN)
def test_own_rewrite_is_read_by_kicad(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    """The rewrite of an own document: no difference at any level, and level 5 compares its nets."""
    found = judge(SAMPLES / name)
    with capsys.disabled():
        print("\n" + counts_line(f"rewrite of {name}", found))
    assert [len(level.differences) for level in found.levels] == [0, 0, 0, 0, 0] and found.equivalent
    assert found.excluded == () and found.levels[-1].compared > 0
    assert found.frame == "relative"


def test_probe() -> None:
    assert _probes.run("altium-rta3-kicad") == "equal"


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", IDS)
def test_corpus_rewrite_is_read_by_kicad(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """The rewrite of a public document: no difference remains under the profile at levels 1 to 5, and no
    rule of the profile is needed that the original document does not need."""
    item = next(i for i in ROWS if i.id == row)
    source = require(item)
    found = judge(source, row)
    with capsys.disabled():
        print("\n" + counts_line(f"rewrite of {row}", found))
    assert found.levels[-1].level == 5 and all(level.compared > 0 for level in found.levels)
    assert found.differences == (), [(d.level, d.kind, d.where) for d in found.differences][:10]
    known = {rule.id for rule in profile_for(rewrite_sides(source, row).version).rules}
    assert {excluded.rule for excluded in found.excluded} <= known
