# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fiducials, their keep-out and test pads under ``kicad-cli`` (capability kicad-oracle, "Assembly and test
features pass the oracle"; hypotheses ``H-K-FIDUCIAL-FORM`` and ``H-K-FIDUCIAL-KEEPOUT``; change c0118).

The bench is written through the model API (``_featurebench.feature_design``): the footprints that
``design.fiducial()`` and ``design.test_point()`` generate, less the courtyard. Building the same bench
from a script with the three calls (``_asmfeatures.CALLS``), and the probes ``asm-tooling-drill`` and
``asm-features-pos``, are task 3.6, owed to a run with ``kicad-cli``."""

from __future__ import annotations

import _featurebench as fb
import _probes
import pytest

from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad


def _recorded() -> None:
    if _probes.major() not in fb.MAJORS:
        pytest.skip(f"the probes of change c0118 are recorded for the majors {fb.MAJORS} only")


def test_the_bench_holds_the_features() -> None:
    """Not vacuous: two fiducials of two unnumbered pads, four marked test pads and one keep-out."""
    for target in (9, 10):
        design = read_board(fb.feature_text(target))
        assert design.board is not None
        fiducials = [fp for fp in design.board.footprints if "Fiducial" in fp.lib_ref]
        assert [[(p.number, p.fab_property) for p in fp.pads] for fp in fiducials] == [
            [("", "fiducial_global"), ("", None)],
        ] * 2
        assert [fp.side for fp in fiducials] == ["top", "bottom"]
        assert [p.layers for p in fiducials[1].pads] == [("B.Cu", "B.Mask"), ("B.Mask",)]
        marked = [p for fp in design.board.footprints for p in fp.pads if p.fab_property == "test_point"]
        assert len(marked) == len(fb.TEST_PADS)
        (keepout,) = design.board.keepouts
        assert (keepout.no_tracks, keepout.no_vias, keepout.no_copper_pour, keepout.no_pads) == (
            True, True, True, False,
        )  # fmt: skip
        assert keepout.layers == ("F.Cu",) and len(keepout.outline) == 8


def test_fiducial_drc() -> None:
    """``asm-fiducial-drc``: no violation names a fiducial or a test pad."""
    _recorded()
    assert _probes.run("asm-fiducial-drc") == "absent"


def test_fiducial_mask() -> None:
    """``asm-fiducial-mask``: a flash of the mask diameter at the centre, on the fiducial's side."""
    _recorded()
    assert _probes.run("asm-fiducial-mask") == "equal"


def test_fiducial_d356() -> None:
    """``asm-fiducial-d356``: one ``327`` record on no net, covered on the other side only."""
    _recorded()
    assert _probes.run("asm-fiducial-d356") == "equal"


def test_keepout_track() -> None:
    """``asm-keepout-track``: ``items_not_allowed`` for the track, nothing for the fiducial's pads."""
    _recorded()
    assert _probes.run("asm-keepout-track") == "present"


def test_keepout_fill() -> None:
    """``asm-keepout-fill``: the refilled pour stays at the apothem of the keep-out, to 1 µm."""
    if _probes.major() < 10:
        pytest.skip("KiCad 9 cannot refill from the command line")
    assert _probes.run("asm-keepout-fill") == "equal"
    gap = fb.fill_gap(_probes.runner())
    assert gap is not None and fb.APOTHEM - 1000 <= gap <= fb.APOTHEM + 1000
