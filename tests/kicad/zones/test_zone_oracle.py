# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone settings pass the oracle (capability kicad-oracle, "Zone settings pass the oracle"; hypotheses
H-K-ZONE-CONNECT, H-K-ZONE-GEOM and H-K-ZONE-LOAD9; change c0031).

Each bench case is written by ``write_board`` from the model. On KiCad 10 it is refilled on a copy by
``pcb drc --refill-zones --save-board``, read back with ``read_board`` and judged with the exact helpers
of ``_zonebench``, never by counting DRC messages. KiCad 9 has no refill, so there every form is only
loaded (``-k load``).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import _buildcases as bc
import _zonebench as zb
import pytest
from _buildhelp import build, pour_variant
from _probes import major, runner

from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad
MM = zb.MM
UM = 1_000
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]
BLINK_BOARD = "blink.kicad_pcb"

# case → how the fill meets the GND SMD pad and the GND through-hole pad
CONNECTIONS: dict[str, tuple[str, str]] = {
    "thermal": ("axes", "diagonals"),
    "solid": ("solid", "solid"),
    "none": ("none", "none"),
    "thru-hole-only": ("solid", "diagonals"),
    "pad-0": ("none", "none"),  # zone solid, pads 0
    "pad-1": ("axes", "diagonals"),  # zone solid, pads 1
    "pad-2": ("solid", "solid"),  # zone thermal, pads 2
    "pad-3": ("solid", "diagonals"),  # zone none, pads 3
    "fp-2": ("solid", "solid"),  # zone thermal, footprint 2
    "fp-2-pad-1": ("axes", "solid"),  # footprint 2, SMD pad 1
}
# case → the clearance in force around the SIG pads
CLEARANCES: dict[str, int] = {
    "clearance-0.3": 300_000,  # the zone's
    "clearance-0.1": zb.CLASS_CLEARANCE,  # the Default class's 0.2 mm, above the zone's 0.1 mm
    "clearance-rule": 600_000,  # the .kicad_dru rule on SIG, above the zone's 0.3 mm
}
ISLANDS: dict[str, tuple[bool, bool]] = {
    # case → (the island is filled, it is flagged as an island)
    "thermal": (False, False),  # always removed
    "island-never": (True, True),
    "island-below-10": (True, True),  # about 22 mm², above the limit
    "island-below-50": (False, False),
}


def rings(name: str) -> list[tuple[object, ...]]:
    return zb.fill_rings(zb.refilled(name))  # type: ignore[return-value]


def gap(name: str) -> int:
    return zb.CASES[name].zone_settings.thermal_gap


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", sorted(CONNECTIONS))
def test_connection(name: str) -> None:
    """Thermal reliefs give four spokes (on the axes of the SMD pad, at 45° on the round through-hole pad),
    solid covers the relief ring, none isolates the pad, and a pad's or footprint's ``zone_connect``
    overrides the zone."""
    found = rings(name)
    smd, tht = CONNECTIONS[name]
    assert zb.pattern(zb.GND_SMD, gap(name), found) == smd  # type: ignore[arg-type]
    assert zb.pattern(zb.GND_THT, gap(name), found) == tht  # type: ignore[arg-type]


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", sorted(CLEARANCES))
def test_clearance(name: str) -> None:
    """The gap between the fill and each SIG pad lies in [c, c + 5 µm], c being the larger of the zone
    clearance and the class or rule clearance."""
    found = rings(name)
    c = CLEARANCES[name]
    for spot in (zb.SIG_SMD, zb.SIG_THT):
        measured = zb.gap_to_pad(spot, found)  # type: ignore[arg-type]
        assert c <= measured <= c + 5 * UM, f"{name} {spot.label}: {measured} nm"


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", ["thermal", "spoke-0.35", "spoke-0.25"])
def test_geometry_of_a_thermal_relief(name: str) -> None:
    settings = zb.CASES[name].zone_settings
    found = rings(name)
    width = zb.spoke_width(zb.GND_SMD, settings.thermal_gap, found)  # type: ignore[arg-type]
    relief = zb.relief_gap(zb.GND_SMD, found)  # type: ignore[arg-type]
    assert abs(width - settings.thermal_spoke_width) <= UM, f"spoke {float(width)} nm"
    assert abs(relief - settings.thermal_gap) <= UM, f"relief {float(relief)} nm"


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", sorted(ISLANDS))
def test_geometry_of_islands(name: str) -> None:
    design = zb.refilled(name)
    found = zb.fill_rings(design)
    filled, flagged = ISLANDS[name]
    assert zb.in_fill(zb.ISLAND, found) is filled
    assert design.board is not None
    zone = next(z for z in design.board.zones if z.name == zb.ZONE_NAME)
    islands = [f for f in zone.fills if f.island]
    assert bool(islands) is flagged
    if flagged:
        assert zb.in_fill(zb.ISLAND, [f.polygon for f in islands])


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize(("name", "filled"), [("channel-0.15", True), ("thermal", False)])
def test_geometry_of_the_minimum_thickness(name: str, filled: bool) -> None:
    """The 0.2 mm channel is filled with a minimum thickness of 0.15 mm, and empty with 0.25 mm."""
    assert zb.in_fill(zb.CHANNEL, rings(name)) is filled  # type: ignore[arg-type]


@pytest.mark.kicad_min_major(10)
def test_geometry_of_a_hatched_fill() -> None:
    """1 mm bars and 1.5 mm holes at 0°, each within 5 µm."""
    rows = zb.hatch_spans(rings("hatch"))  # type: ignore[arg-type]
    assert rows, "no scan line crosses a hole"
    for row in rows:
        assert len(row) >= 5
        for inside, length in row:
            wanted = 1 * MM if inside else 1_500_000
            assert abs(length - wanted) <= 5 * UM, f"{'bar' if inside else 'hole'} of {float(length)} nm"


@pytest.mark.parametrize("name", sorted(zb.CASES))
def test_load_target_9(name: str) -> None:
    """Every case board written for target 9 loads: ``pcb drc`` exits 0 and writes a report (on 9.0.9
    this is all that can be observed, ``H-K-ZONE-LOAD9``)."""
    assert zb.loads(name, 9)


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", sorted(zb.CASES))
def test_load_target_10(name: str) -> None:
    assert zb.loads(name, 10)


@pytest.mark.parametrize("target", TARGETS)
def test_build_loads(target: int) -> None:
    """The blink pour variant of ``design-dsl`` "Zones in a build" loads on the running major."""
    output = build(pour_variant(), target)
    found = bc.drc(bc._files(output), BLINK_BOARD)  # noqa: SLF001
    assert found.run.ok and found.report is not None
    print(f"KiCad {major()}: blink pour variant, target {target}: loaded")


@pytest.mark.kicad_min_major(10)
def test_build_refill() -> None:
    """On 10.0.6 the refilled blink pour holds a ``GND`` fill on ``B.Cu``."""
    output = build(pour_variant(), 10)
    with tempfile.TemporaryDirectory() as tmp:
        tops = bc._folder(bc._files(output), Path(tmp))  # noqa: SLF001
        args = [
            "pcb",
            "drc",
            "--refill-zones",
            "--save-board",
            "--format",
            "json",
            "-o",
            "drc.json",
            BLINK_BOARD,
        ]
        run = runner().run(args, files=tops)
    assert run.ok and BLINK_BOARD in run.outputs
    design = read_board(run.outputs[BLINK_BOARD].decode("utf-8"), issues=[])
    assert design.board is not None
    (zone,) = design.board.zones
    assert zone.name == "GND" and zone.filled is True
    assert zone.fills and {f.layer for f in zone.fills} == {"B.Cu"}
    assert zone.settings.clearance == 300_000 and zone.settings.connection == "solid"


# --- fresh fills under the zone's own clearance (change c0068, ``H-K-COPPER-ZONECLR``) --------------


@pytest.mark.kicad_min_major(10)
def test_fresh_fill_is_clean() -> None:
    """Scenario "A refilled pour is clean": ``check_copper`` reports nothing of what KiCad's filler made."""
    import _freshfill as ff
    from _probes import run

    text = ff.refilled_text()
    found, fills = ff.findings(text, major())
    assert fills >= 1
    assert ff.zone_findings(text, major()) == []
    assert [f for f in found if f.code in ("copper.clearance", "copper.short")] == []
    assert run("copper-zoneclr-fresh") == "absent"


@pytest.mark.kicad_min_major(10)
def test_fresh_fill_bench_holds_every_kind() -> None:
    import _freshfill as ff

    design = ff.fresh_bench(major()).bench.design
    assert design.board is not None
    board = design.board
    assert board.tracks and board.arcs and board.vias and len(board.footprints) == 3
    assert not any(zone.fills for zone in board.zones)
    assert "(offset" in ff.fresh_bench(major()).files[ff.BOARD]


@pytest.mark.kicad_min_major(10)
def test_stale_fill_is_still_reported() -> None:
    """Scenario "A stale fill is still reported": the track moved 0.3 mm towards the kept fill."""
    import _freshfill as ff

    (found,) = ff.zone_findings(ff.stale_text(), major())
    assert sorted(item.kind for item in found.items) == ["fill", "track"]
    assert (found.clearance, found.source) == (ff.ZONE_CLEARANCE, "zone")
    assert ff.CLASS_CLEARANCE <= found.gap < ff.ZONE_CLEARANCE
    assert ff.kicad_reports_stale()
