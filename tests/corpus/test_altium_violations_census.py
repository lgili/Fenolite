# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census of the stored DRC violations of the public PCB documents (change c0498, task 1.1; S-2335,
``H-A-DRC-STORED``). Counts, kinds and key names only: no author, comment or description text is kept."""

from __future__ import annotations

from collections import Counter

import pytest
from _corpus import manifest_items, require

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.cfb import read_compound
from fenolite.backends.altium.read.pcbprops import parse_blocks
from fenolite.backends.altium.read.violations import stored_violations

pytestmark = pytest.mark.needs_corpus
ROWS = {item.id: item for item in manifest_items("altium-pcbdoc")}
STORED = {
    "altium-third-party-pcbdoc-01": ("MinimumSolderMaskSliver", 103, 0),
    "altium-third-party-pcbdoc-03": ("SilkToSilkClearance", 11, 0),
    "altium-third-party-pcbdoc-07": ("BoardOutlineClearance", 10, 10),
}
"""Row → the rule kind of its one violation storage, its record count, and how many are waived."""
WAIVED = {"altium-third-party-pcbdoc-05": 15, "altium-third-party-pcbdoc-07": 10}
KEYS = {"RULEINDEX", "PRIM1ID", "PRIM1INDEX", "PRIM2ID", "PRIM2INDEX", "LOCATION1.X", "LOCATION1.Y"}


@pytest.mark.parametrize("row", sorted(STORED))
def test_stored_violations_read_back(row: str) -> None:
    path = require(ROWS[row])
    read = stored_violations(path, AltiumBackend().read(path).design)
    kind, count, waived = STORED[row]
    assert read.issues == ()
    assert Counter(f.kind for f in read.findings) == {kind: count}
    assert sum(f.waived for f in read.findings) == waived and not any(f.stale for f in read.findings)
    assert all(f.at is not None and len(f.primitives) == 2 for f in read.findings)


@pytest.mark.parametrize("row", sorted(ROWS))
def test_layout_of_every_storage(row: str) -> None:
    """Every violation and waived record is a property block of the recorded keys; the count is the Header."""
    compound = read_compound(require(ROWS[row]))
    for name in {n.split("/", 1)[0] for n in compound.streams()}:
        if not (name.endswith("Violation") or name == "WaivedViolations"):
            continue
        records, trailing, problems = parse_blocks(compound.read(f"{name}/Data"), where=name)
        assert not trailing and not problems
        assert len(records) == int.from_bytes(compound.read(f"{name}/Header")[:4], "little")
        wanted = {"RULEINDEX", "PRIM1INDEX", "PRIM2INDEX"} if name == "WaivedViolations" else KEYS
        assert all(wanted <= set(record.keys()) for record in records), name
    held = {n.split("/", 1)[0] for n in compound.streams()}
    if row in WAIVED:
        assert int.from_bytes(compound.read("WaivedViolations/Header")[:4], "little") == WAIVED[row]
    assert any(n.endswith("Violation") for n in held) == (row in STORED)
