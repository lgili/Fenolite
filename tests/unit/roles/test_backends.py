# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The roles and measures of the KiCad and the Altium builds of each reference variant (change c0222;
capability net-roles, "Roles on both backends": "Same roles from both builds", and "Role evidence").

The inference reads the circuit of the ``.fenolite/`` model, the measures only the ``Design`` that each
backend reads from its board: the KiCad board with the fill of ``fill_as_outline``, the Altium PCB document
with the polygons its build poured. ``ALTIUM-VERIFIED`` is not claimed: the Altium reading is the model of the
written document.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
from _roleboards import BOARDS, VARIANTS, Built
from _rolecheck import checked

from fenolite.roles.judge import Judged

CASES = [(board, variant) for board in BOARDS for variant in VARIANTS]
TOLERANCE_NM2 = 10_000_000_000
"""0.01 mm² in square nanometres."""


def _altium(reference: Callable[..., Built], board: str, variant: str) -> Judged:
    def altium(name: str, kind: str, target: str = "kicad") -> Built:
        del target
        return reference(name, kind, "altium")

    return checked(altium, board, variant)


def _rows(judged: Judged) -> list[tuple[object, ...]]:
    roles = judged.resolved.roles
    nets = [(r.net, r.kind, r.source, r.rule, r.confidence, r.milliamps, r.working_mv) for r in roles.nets]
    groups = [
        (type(g).__name__, g.name, g.pads, g.origin) for g in (*roles.loops, *roles.kelvins, *roles.gates)
    ]
    return [*nets, *groups]


def _loops(judged: Judged) -> Mapping[str, int | None]:
    return {m.subject: m.values["area_nm2"] for m in judged.measured.measures if m.kind == "loop"}


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_same_roles_from_both_builds(reference: Callable[..., Built], board: str, variant: str) -> None:
    kicad, altium = checked(reference, board, variant), _altium(reference, board, variant)
    assert _rows(altium) == _rows(kicad)
    kicad_loops, altium_loops = _loops(kicad), _loops(altium)
    assert kicad_loops.keys() == altium_loops.keys()
    for name, area in kicad_loops.items():
        other = altium_loops[name]
        assert area is not None and other is not None and abs(area - other) < TOLERANCE_NM2, (
            name,
            area,
            other,
        )
    findings = {(i.code, i.severity) for i in kicad.issues if i.code.startswith("roles.")}
    assert {(i.code, i.severity) for i in altium.issues if i.code.startswith("roles.")} == findings


def test_evidence_of_a_check(reference: Callable[..., Built]) -> None:
    for judged in (checked(reference, "buck_shunt", "bad"), _altium(reference, "buck_shunt", "bad")):
        assert judged.evidence.level.value == "INFERRED"
        assert {"H-G-ROLE-LOOP-RATIO", "H-G-SHAPE-LOOP"} <= set(judged.evidence.hypotheses)
        (width,) = [i for i in judged.issues if i.code == "roles.width-current"]
        assert "S-0851" in width.message
