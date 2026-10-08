# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The same board gives the same copper findings whichever backend read it (capability
altium-verification, "Copper check on Altium boards", scenario "Same board, two backends"; change c0088;
hypothesis ``H-A-DRC-SAME``).

One design script is built for KiCad and for Altium by ``fenolite build``; each written board is read by
its own backend, with that backend's rules source and board frame, and judged by ``checks.copper``. The
findings must be equal by code, by the two nets and by place within 2 nm. The two files put the board at
different places (the PCB document keeps its outline 1000 mil from its origin), so a place is taken
relative to pad 1 of ``U1``, which both readings hold. The samples are the routed blink as it is, and
with the short and the clearance fault of ``tests/_altium_drc.py``.

No tool runs here: ``kicad-cli`` reads neither board. What KiCad's own importer makes of the document is
the subject of ``test_script_copper_oracle.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium_drc import CROSSING, DOCUMENT, NEAR, build_altium, plant
from _routed import Routed

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.base import BoardFrame, DesignRulesSource, ProjectSet
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks.copper import CopperReport, check_copper
from fenolite.core.coords import Point
from fenolite.model.design import Design

TOLERANCE_NM = 2
SAMPLES = {
    "as built": ((), (0, 0)),
    "two tracks cross": ((CROSSING,), (1, 0)),
    "a track too close": ((NEAR,), (0, 1)),
    "both faults": ((CROSSING, NEAR), (1, 1)),
}
Finding = tuple[str, tuple[str, str], str, Point]


def judged(backend: object, design: Design, project: ProjectSet) -> tuple[CopperReport, Point]:
    """The copper report of ``design`` with the rules and pads of ``backend``, and where pad 1 of ``U1``
    lies in that reading."""
    assert isinstance(backend, DesignRulesSource) and isinstance(backend, BoardFrame)
    rules = backend.design_rules(design, project)
    pads = backend.board_pads(rules.design)
    report = check_copper(
        rules.design,
        pads=pads,
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
    )
    (anchor,) = [pad.position for pad in pads if pad.ref == "U1" and pad.number == "1"]
    return report, anchor


def findings(report: CopperReport, anchor: Point) -> list[Finding]:
    found = [
        (
            f.code,
            (min(i.net for i in f.items), max(i.net for i in f.items)),
            f.layer,
            Point(f.at.x - anchor.x, f.at.y - anchor.y),
        )
        for f in report.findings
    ]
    return sorted(found, key=lambda entry: (entry[0], entry[1], entry[2], entry[3].x, entry[3].y))


@pytest.mark.parametrize("name", list(SAMPLES))
def test_same_board_two_backends(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lines, (shorts, clearance) = SAMPLES[name]
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, *lines)
    code, env, err = routed.build("--copper-check", "warn", "--confirm")
    assert code == 0, (env.get("issues"), err)
    altium_out = tmp_path / "A"
    code, env, err = build_altium(routed, "--copper-check", "warn", "--confirm", out=altium_out)
    assert code == 0, (env.get("issues"), err)

    kicad = KicadBackend()
    as_kicad, kicad_anchor = judged(kicad, routed.read(), project_set(routed.board))
    altium = AltiumBackend()
    document = altium_out / DOCUMENT
    read = altium.read(document).design
    assert isinstance(read, Design)
    as_altium, altium_anchor = judged(altium, read, ProjectSet(altium_out, DOCUMENT, {DOCUMENT: document}))

    ours, theirs = findings(as_altium, altium_anchor), findings(as_kicad, kicad_anchor)
    assert [entry[:3] for entry in ours] == [entry[:3] for entry in theirs], name
    for mine, other in zip(ours, theirs, strict=True):
        assert abs(mine[3].x - other[3].x) <= TOLERANCE_NM and abs(mine[3].y - other[3].y) <= TOLERANCE_NM, (
            name
        )
    for report in (as_altium, as_kicad):
        assert (report.summary["shorts"], report.summary["clearance"]) == (shorts, clearance), name
    # both readings judged the same copper: the same items per kind
    assert as_altium.summary["items"] == as_kicad.summary["items"], name
    assert as_altium.summary["unsupported"] == as_kicad.summary["unsupported"] == {}
