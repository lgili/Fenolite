# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated copper judged by the running ``kicad-cli`` (change c0224; capability kicad-oracle, "Generated
copper passes the oracle"; hypothesis ``H-K-GEN-DRC``).

The bench is the blink of ``examples/blink_2layer`` with a ``GND`` pour over the bottom and one over a
square of the top, a mounting hole and the class ``HV`` of ``LED_A``, authored here for Fenolite. The
generated board adds every call: a band of ``LED_A`` on the bottom from the pad of ``D1``, a ring around
the hole, a barrier around ``HV`` on the top, a keep-out under ``R1`` on the bottom, the fan-out of the
``GND`` pad of ``U1`` and the stitching of the two pours. Both boards are built for the running major and
checked with the project the build writes; KiCad 10 refills their zones first.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _buildhelp import blink, build
from _probes import major, runner

from fenolite.dsl import Design, copper, generated, mm
from fenolite.lens.build import BuildOutput

pytestmark = pytest.mark.needs_kicad

LEFT_ASIDE = frozenset({"unconnected_items"})
"""What the comparison leaves aside: the fan-out and the stitches join items."""


def bench(*, calls: bool) -> Design:
    design = blink()
    gnd, led_a = design.nets["GND"], design.nets["LED_A"]
    design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))
    top = ((mm(20), mm(18)), (mm(30), mm(18)), (mm(30), mm(28)), (mm(20), mm(28)))
    design.zone(gnd, name="GND_TOP", layers=("F.Cu",), clearance=mm(0.3), outline=top)
    hole = design.hole("H1", mm(4), mm(4), drill=mm(3))
    design.rules.netclass("HV", clearance=mm(0.5), nets=(led_a,))
    if calls:
        spine = ((mm(40.54), mm(16)), (mm(40.54), mm(26)), (mm(46), mm(26)))
        design.band(
            led_a, spine, width=mm(1), max_width=mm(3), step=mm(0.5), layers=("B.Cu",), clearance=mm(0.5),
            priority=1,
        )  # fmt: skip
        design.keepout_ring(hole, setback=mm(1))
        design.barrier("HV", setback=mm(1), layers=("F.Cu",), forbid=("tracks", "vias"), pieces=True)
        design.body_keepout(design.parts["R1"], setback=mm(0.5), layers=("B.Cu",))
        design.fanout_zone(gnd, width=mm(0.3), diameter=mm(0.6), drill=mm(0.3))
        design.stitch_pieces(gnd, pitch=mm(2), diameter=mm(0.6), drill=mm(0.3))
    return design


def _built(design: Design) -> BuildOutput:
    output = build(
        design,
        target=major(),
        generated_copper=generated(design),
        copper_intents=copper(design),
        authored_footprints={key: fp.definition for key, fp in design.footprints.items()},
        authored_symbols={key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
    )
    errors = [found.message for found in output.issues if found.severity == "error"]
    assert output.files and errors == [], errors
    return output


def _drc(folder: Path, output: BuildOutput) -> Counter[str]:
    folder.mkdir(parents=True)
    for name, data in output.files.items():
        if name.startswith(".fenolite/"):
            continue
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    board = folder / "blink.kicad_pcb"
    files = {
        name: folder / name for name in ("blink.kicad_pro", "blink.kicad_dru") if (folder / name).is_file()
    }
    report = runner().drc(board, files=files, refill_zones=major() >= 10).report
    assert report is not None
    found = (*report.violations, *report.unconnected_items)
    return Counter(item.type for item in found if not item.excluded)


def test_generated_copper_adds_no_drc_finding(tmp_path: Path) -> None:
    """Scenario "Fill and DRC of the bench"."""
    plain = _drc(tmp_path / "plain", _built(bench(calls=False)))
    output = _built(bench(calls=True))
    assert output.summary["generated"] == {
        "records": 6,
        "zones": 1,
        "rule_areas": 6,
        "tracks": 1,
        "vias": output.summary["generated"]["vias"],  # type: ignore[index]
    }
    assert output.summary["generated"]["vias"] >= 3  # type: ignore[index]
    made = _drc(tmp_path / "generated", output)
    aside = LEFT_ASIDE if major() >= 10 else LEFT_ASIDE | {"via_dangling"}
    grown = {
        kind: (plain[kind], made[kind]) for kind in made if kind not in aside and made[kind] > plain[kind]
    }
    assert grown == {}, (plain, made)
    if major() >= 10:
        assert made["via_dangling"] == 0, made
