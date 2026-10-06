# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The complete PCB document against ``kicad-cli pcb import`` (capability altium-pcb-writer; change c0085;
hypothesis ``H-A-PCBX-KICAD``).

The six-layer sample's ``board6.PcbDoc`` is imported with ``kicad-cli pcb import --format altium`` and read
back with ``backends.kicad.pcb.read_board``; the probes ``altium-pcbx-<kind>`` (``tests/_pcbxcases.py``)
compare each kind with the model and are pinned in ``docs/evidence/kicad/probes/<version>.json``.
``pcb import`` exists from 10.0 only (S-0166), so the importer of 9.0 is not run.

A pass checks only what KiCad's importer reads; it settles no Altium row. What the import does not carry
is listed in ``_pcbxcases.NOT_COMPARED`` and asserted below where the import shows it.
"""

from __future__ import annotations

import re

import _pcbxcases
import _probes
import pytest
from _altium_board6 import at, bare_spec
from _resources import kicad_cli_major

from fenolite.backends.altium.pcbdoc import write_pcbdoc
from fenolite.model.board import Keepout

pytestmark = pytest.mark.needs_kicad

ALLOWED_WARNING = re.compile(r"Layer 'Internal Plane \d+' could not be mapped and will be skipped\.")
KINDS = ("stack", "vias", "texts", "graphics", "keepouts", "holes", "zones")


def _needs_import() -> None:
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")


def test_the_probes_cover_every_kind_kicad_imports() -> None:
    assert tuple(_pcbxcases.KINDS) == KINDS
    assert sorted(pid for pid in _probes.PROBES if pid.startswith("altium-pcbx-")) == sorted(
        f"altium-pcbx-{kind}" for kind in KINDS
    )
    assert all(_probes.PROBES[f"altium-pcbx-{kind}"].majors == (10,) for kind in KINDS)
    assert len(_pcbxcases.NOT_COMPARED) == 5


@pytest.mark.parametrize("kind", KINDS)
def test_kicad_reads_the_kind_as_the_model_holds_it(kind: str) -> None:
    """``H-A-PCBX-KICAD``: the probe of each kind KiCad imports says ``equal``."""
    _needs_import()
    assert _probes.run(f"altium-pcbx-{kind}") == "equal"


def test_the_import_gives_no_other_warning() -> None:
    """KiCad warns once per internal plane outside the stack (fifteen with one plane) and nothing else."""
    _needs_import()
    found, _model = _pcbxcases.imported()
    assert found.code == 0
    warnings = [line for line in found.output.splitlines() if "Warning" in line or "Error" in line]
    assert len(warnings) == 15 and all(ALLOWED_WARNING.search(line) for line in warnings), warnings


def test_kicad_imports_exactly_the_restrictions_written() -> None:
    """The sample's keep-out forbids tracks and vias, and KiCad imports it with those two alone: it reads
    the key ``KEEPOUTRESTRIC``, which the writer adds beside ``KEEPOUTRESTRICTIONS`` (the maintainer's
    decision of 2026-10-06)."""
    _needs_import()
    found, model = _pcbxcases.imported()
    assert model.board is not None and found.board.board is not None
    (wanted,) = model.board.keepouts
    (read,) = found.board.board.keepouts
    assert (wanted.no_tracks, wanted.no_vias, wanted.no_pads, wanted.no_copper_pour) == (
        True,
        True,
        False,
        False,
    )
    assert (read.no_tracks, read.no_vias, read.no_pads, read.no_copper_pour) == (True, True, False, False)
    assert not read.no_footprints


RESTRICTIONS = ("no_vias", "no_tracks", "no_copper_pour", "no_pads")


def test_kicad_imports_each_restriction_alone() -> None:
    """One keep-out per restriction, each on every copper layer: KiCad imports each with that restriction
    and no other (the bits 1, 2, 4 and 8 + 16 of ``pcb-records.md``)."""
    _needs_import()
    keepouts = tuple(
        Keepout(
            id=f"kpo_{name}",
            outline=(at(2 + 8 * n, 2), at(8 + 8 * n, 2), at(8 + 8 * n, 8), at(2 + 8 * n, 8)),
            layers=("F.Cu", "B.Cu"),
            **{name: True},  # type: ignore[arg-type]
        )
        for n, name in enumerate(RESTRICTIONS)
    )
    found = _pcbxcases.import_document(write_pcbdoc(bare_spec(keepouts=keepouts), filename="k.PcbDoc"))
    assert found.board.board is not None
    read = sorted(found.board.board.keepouts, key=lambda k: min(p.x for p in k.outline))
    assert len(read) == len(RESTRICTIONS)
    for area, name in zip(read, RESTRICTIONS, strict=True):
        assert [other for other in RESTRICTIONS if getattr(area, other)] == [name], name
        assert set(area.layers) == {"F.Cu", "B.Cu"} and not area.no_footprints


def test_what_the_import_does_not_carry() -> None:
    """A text is anchored at its lower-left corner, whatever the model means by its position."""
    _needs_import()
    found, _model = _pcbxcases.imported()
    assert "(justify left bottom)" in found.text and "(justify left bottom mirror)" in found.text
