# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Kelvin attachment and the gate-return attachment on ``path_network`` (change c0222; capability
net-roles, "Kelvin attachment" and "Hot and gate loop checks": "Sense lines of the bad buck", "A gate return
from the source pour"; hypothesis ``H-G-ROLE-KELVIN-EDGE``)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from _boards import Built, judge
from _reference import checked

from fenolite.core.coords import Point
from fenolite.roles.kelvin import offset

BUCK = {"VOUT": 2000, "VL": 2000, "SW": 2000, "VIN": 1000}


def _attachments(judged: object) -> dict[str, object]:
    return {a.pad: a for _, found in judged.measured.attachments for a in found}  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        (Point(500_000, 0), 500_000),  # inner half, toward the other pad
        (Point(0, 0), 0),  # the centre
        (Point(-550_000, 0), -550_000),  # outer half
        (Point(-300_000, 400_000), -300_000),  # off the axis: only the part along it counts
    ],
)
def test_offset_along_the_axis(point: Point, expected: int) -> None:
    assert offset(point, Point(0, 0), Point(6_000_000, 0)) == expected


def test_offset_rounds_toward_zero() -> None:
    assert offset(Point(1, 1), Point(0, 0), Point(3, 4)) == 1  # (3 + 4) / 5 = 1.4
    assert offset(Point(-1, -1), Point(0, 0), Point(3, 4)) == -1


def test_reference(reference: Callable[..., Built]) -> None:
    """The bad buck: one sense line leaves the outer end of ``R12-1``, the other leaves the pour."""
    good = _attachments(judge(reference("buck_shunt", "good"), currents=BUCK))
    assert all(t >= 0 for a in good.values() for t in a.offsets)  # type: ignore[attr-defined]
    assert not [a for a in good.values() if a.shared]  # type: ignore[attr-defined]
    judged = judge(reference("buck_shunt", "bad"), currents=BUCK)
    bad = _attachments(judged)
    assert bad["R12-1"].offsets == (-550_000,)  # type: ignore[attr-defined]
    assert bad["R12-2"].shared and not bad["R12-2"].reached  # type: ignore[attr-defined]
    (outer,) = [i for i in judged.issues if i.code == "roles.kelvin-outer"]
    assert outer.where == "kelvin_R12:R12-1" and "t = -0.55 mm" in outer.message
    (shared,) = [i for i in judged.issues if i.code == "roles.kelvin-shared"]
    assert shared.where == "kelvin_R12:R12-2" and "/kicad_pcb/zone[" in shared.message
    assert "S-0850" in shared.message


def test_four_pad_shunt(reference: Callable[..., Built]) -> None:
    """The bad battery board: the monitor's inputs sit on the force pads' nets."""
    judged = checked(reference, "bms", "bad")
    found = {i.where: i.message for i in judged.issues if i.code == "roles.kelvin-shared"}
    assert sorted(found) == ["kelvin_R1:R1-2", "kelvin_R1:R1-3"]
    assert found["kelvin_R1:R1-2"].endswith("R1-1 (S-0850)") and found["kelvin_R1:R1-3"].endswith(
        "R1-4 (S-0850)"
    )
    good = checked(reference, "bms", "good")
    sense = {m.subject: m.values["shared"] for m in good.measured.measures if m.kind == "sense"}
    assert sense == {"SNS_N": [], "SNS_P": []}  # analyze_ties: the separate sense nets touch no other net


def test_gate_return(reference: Callable[..., Built]) -> None:
    """The bad half-bridge: the high side's gate return leaves from the source pour."""
    judged = checked(reference, "half_bridge", "bad")
    (found,) = [i for i in judged.issues if i.code == "roles.gate-return-shared"]
    assert found.where == "gate_Q1" and found.severity == "error"
    assert "before its source pad Q1-2: /kicad_pcb/zone[" in found.message
    returns = {gate.name: a for gate, a in judged.measured.returns}
    assert returns["gate_Q1"].shared and returns["gate_Q2"].reached and not returns["gate_Q2"].shared
    good = checked(reference, "half_bridge", "good")
    assert all(a.reached and not a.shared for _, a in good.measured.returns)


def test_gate_return_without_a_kelvin_pin(reference: Callable[..., Built]) -> None:
    """The buck's switches have no Kelvin pin: the return lands in the source copper, which counts as the
    source pad."""
    judged = judge(reference("buck_shunt", "good"), currents=BUCK)
    assert all(a.reached and not a.shared for _, a in judged.measured.returns)
