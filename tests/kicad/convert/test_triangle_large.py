# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad imports a large document and the pads of a converted board (capability altium-compound-reader,
"Large written documents are read", scenario "KiCad imports a large document"; capability
altium-pcb-writer, "Full-stack pad records" and "Slotted pad holes"; change c0160, ``H-A-CONV-DIFAT`` and
``H-A-CONV-PADSTACK``).

The probes are built from the committed blink sample in memory (``_convcases``): ``convert-difat`` adds
lines on the overlay until the PCB document needs DIFAT sectors, and ``convert-padstack`` gives the LED a
stacked pad and a slotted pad. The demo board ``vme-wren`` (corpus, heavy) is the large document of the
scenario.
"""

from __future__ import annotations

from collections import Counter

import _convcases
import _probes
import pytest
from _corpus import manifest_items, require

from fenolite.checks.equivalence import Tolerances, compare_designs
from fenolite.convert import convert_project

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
PREFIX = "kicad-demo-10-0-6-pcb-"
LARGE = {item.id.removeprefix(PREFIX): item for item in manifest_items("rt0") if item.id.startswith(PREFIX)}


def test_probe_difat() -> None:
    outcome = _probes.run("convert-difat")
    print(f"convert-difat: {outcome} on kicad-cli {_probes.version()}")
    assert outcome == "equal"


def test_probe_padstack() -> None:
    outcome = _probes.run("convert-padstack")
    print(f"convert-padstack: {outcome} on kicad-cli {_probes.version()}")
    assert outcome == "equal"


@pytest.mark.needs_corpus
@pytest.mark.parametrize("key", ["18", "06"])
def test_difat_demo_board(key: str) -> None:
    """Scenario "KiCad imports a large document": the conversion of the demo board needs DIFAT sectors;
    KiCad's import of its PCB document equals the source at level 4 under the profile ``kicad-import``,
    apart from the differences that the report's lost items explain."""
    source = require(LARGE[key])
    conversion = convert_project(source, to="altium", allow_lossy=True)
    data = conversion.files[conversion.read_back]
    assert int.from_bytes(data[0x48:0x4C], "little") >= 1  # DIFAT sectors in the header
    found = _convcases.triangle(source)
    level4 = [d for d in found.unexplained if d.level <= 4]
    explained = dict(Counter((d.kind, kind) for d, kind in found.explained if d.level <= 4))
    print(f"{LARGE[key].path.stem}: {explained}, unexplained at level 4: {len(level4)}")
    assert level4 == []


def test_large_sample_level_4() -> None:
    """The large sample of ``convert-difat`` at level 4 within the importer's 10 nm, every line back."""
    design = _convcases.large_design()
    _written, back = _convcases._imported(design)  # pyright: ignore[reportPrivateUsage]
    assert _convcases.silk_lines(back) == _convcases.silk_lines(design) >= _convcases.LARGE_TRACKS
    report = compare_designs(design, back, level=4, tolerances=Tolerances(10, 0, 0), frame="relative")
    assert report.differences == ()
