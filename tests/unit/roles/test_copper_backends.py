# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad and the Altium builds of the six role-copper scripts (change c0243, decision 13; capability
altium-build, "Script copper in an Altium build"; hypothesis ``H-G-ROLE-COPPER-ALTIUM``).

Each script is built for both targets. The Altium build resolves the role copper in its in-memory KiCad
build, so the PCB document holds the same zones (outline points within the readers' rounding), rule areas,
vias and tracks as the KiCad board, and its build reports no ``kicad.generate.altium``. ``ALTIUM-VERIFIED``
is not claimed: the Altium reading is the model of the written document.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from _roleboards import BOARDS, EXAMPLES, VARIANTS, Built, read
from _rolecopper import cli, outcome

from fenolite.backends.altium.rulemap import selector_text
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.model.design import Design

CASES = [(name, variant) for name in BOARDS for variant in VARIANTS]
ROUNDING_NM = 1_000
"""The two readers round a coordinate to their units (1 nm, and 1/10 000 mil = 2.54 nm); 1 µm covers both and
the board origins of the two documents."""


def _names(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


def _shift(kicad: Sequence[BoardPad], altium: Sequence[BoardPad]) -> tuple[int, int]:
    """The offset from the KiCad frame to the Altium one, from the first pad of both."""
    a = min(kicad, key=lambda pad: (pad.ref, pad.number))
    (b,) = [pad for pad in altium if (pad.ref, pad.number) == (a.ref, a.number)]
    return b.position.x - a.position.x, b.position.y - a.position.y


def _near(a: Point, b: Point, shift: tuple[int, int]) -> bool:
    return abs(a.x + shift[0] - b.x) <= ROUNDING_NM and abs(a.y + shift[1] - b.y) <= ROUNDING_NM


def _zones(design: Design) -> list[tuple[str, tuple[str, ...], tuple[Point, ...]]]:
    assert design.board is not None
    names = _names(design)
    return sorted(
        (names.get(z.net_id or "", ""), tuple(z.layers), tuple(z.outline))
        for z in design.board.zones
        if len(z.outline) >= 3
    )


@pytest.mark.parametrize(("name", "variant"), CASES)
def test_same_copper_from_both_builds(
    role_copper: Callable[..., Built], tmp_path: Path, name: str, variant: str
) -> None:
    kicad, kicad_pads = read(role_copper(name, variant))
    altium, altium_pads = read(role_copper(name, variant, "altium"))
    shift = _shift(kicad_pads, altium_pads)
    assert kicad.board is not None and altium.board is not None
    kicad_zones, altium_zones = _zones(kicad), _zones(altium)
    assert [(n, layers, len(ring)) for n, layers, ring in kicad_zones] == [
        (n, layers, len(ring)) for n, layers, ring in altium_zones
    ]
    for (_, _, ring), (_, _, other) in zip(kicad_zones, altium_zones, strict=True):
        assert any(_near(ring[0], point, shift) for point in other)
        assert all(any(_near(p, q, shift) for q in other) for p in ring)
    kicad_names, altium_names = _names(kicad), _names(altium)
    assert len(altium.board.vias) == len(kicad.board.vias)
    for via in kicad.board.vias:
        net = kicad_names.get(via.net_id or "", "")
        assert any(
            _near(via.position, other.position, shift)
            and altium_names.get(other.net_id or "", "") == net
            and abs(other.diameter - via.diameter) <= ROUNDING_NM
            for other in altium.board.vias
        ), (net, via.position)
    assert len(altium.board.tracks) == len(kicad.board.tracks)
    # the Altium reader keeps no keep-out: the build's own account counts what it wrote
    code, envelope = cli(
        "build", str(EXAMPLES / name / f"{variant}_roles.py"), "--out", str(tmp_path), "--target", "altium",
        "--dry-run",
    )  # fmt: skip
    assert code == 0, envelope
    codes = {i["code"] for i in envelope["issues"]}
    assert "kicad.generate.altium" not in codes and "altium.zone-unpoured" not in codes
    written = envelope["result"]["pcb"]["written"]
    copper = {layer.name for layer in kicad.board.layers if layer.kind == "copper"}
    # an area over every copper layer is one keep-out on the Keep-Out layer, any other one per layer
    assert written["keep-out"] == sum(
        1 if set(area.layers) >= copper else len(area.layers) for area in kicad.board.keepouts
    )
    assert written["zone"] == len(kicad_zones)
    # the role rules of the KiCad build's plan are all written as Altium rules
    planned = outcome(role_copper(name, variant)).plan.rules
    written_rules = envelope["result"]["rules"]
    assert not written_rules["not_lowered"], written_rules
    assert len(written_rules["written"]) >= len(planned)
    assert {selector_text(r.selector_a) for r in planned} <= {
        row["selector"].split(" | ")[0] for row in written_rules["written"]
    }
