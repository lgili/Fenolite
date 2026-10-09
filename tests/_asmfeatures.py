# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The blink with assembly and test features, for the tests of change c0118: an authored test pad on
``LED_A`` and two authored fiducial marks, one per side. Every name, size and position is made up.

``CALLS`` holds the script calls ``design.fiducial()``, ``design.test_point()`` and
``design.tooling_hole()`` of "Features in a build". The parts authored in ``FEATURES`` carry the same pad
marks, which is all that ``pnp``, ``testpoints`` and KiCad's outputs read.
"""

from __future__ import annotations

from _buildhelp import BLINK, blink_text

from fenolite.dsl import Design

LAST_LINE = 'd1.place(mm(38), mm(20), side="bottom")\n'
"""The last line of the blink script: an edit that keeps it and appends to it extends the script."""
FEATURES = (
    LAST_LINE
    + """
from fenolite.dsl import Footprint, Symbol

tp_fp = Footprint("Local", "TestPad", kind="smd")
tp_fp.pad("1", at=(mm(0), mm(0)), size=(mm(1.5), mm(1.5)), shape="circle", layers=("F.Cu", "F.Mask"),
          fab_property="test_point")
tp_sym = Symbol("Local", "TestPad", reference="TP", value="TestPad", footprint="Local:TestPad")
tp_sym.pin("1", "1", at=(mm(0), mm(0)), length=mm(2.54))
fid_fp = Footprint("Local", "Mark", kind="smd")
fid_fp.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)), shape="circle", layers=("F.Cu", "F.Mask"),
           fab_property="fiducial_global")
fid_sym = Symbol("Local", "Mark", reference="FID", value="Mark", footprint="Local:Mark")
fid_sym.pin("1", "1", at=(mm(0), mm(0)), length=mm(2.54))
design.add_footprint(tp_fp)
design.add_footprint(fid_fp)
design.add(tp_sym, fid_sym)
tp1 = Part("TP1", "Local:TestPad", footprint="Local:TestPad")
fid1 = Part("FID1", "Local:Mark", footprint="Local:Mark")
fid2 = Part("FID2", "Local:Mark", footprint="Local:Mark")
design.add(tp1, fid1, fid2)
connect(led_a, tp1[1])
no_connect(fid1[1], fid2[1])
tp1.place(mm(30), mm(12))
fid1.place(mm(3), mm(3))
fid2.place(mm(47), mm(27), side="bottom")
"""
)
"""The replacement of ``LAST_LINE`` that adds the features to the blink script."""
CALLS = (
    'design.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))\n'
    'design.fiducial("FID2", mm(47), mm(27), copper=mm(1), mask=mm(2), side="bottom")\n'
    'design.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))\n'
    'design.tooling_hole("TH1", mm(46), mm(4), drill=mm(3), clear=mm(5))\n'
)
"""The lines that "Features in a build" appends to the blink: the three script calls of change c0118."""


def features_text() -> str:
    """The blink script with the features appended."""
    text = blink_text()
    assert LAST_LINE in text
    return text.replace(LAST_LINE, FEATURES)


def features_design() -> Design:
    """The DSL design of ``features_text``."""
    scope: dict[str, object] = {"__name__": "design"}
    exec(compile(features_text(), str(BLINK), "exec"), scope)  # noqa: S102 - our own example
    design = scope["design"]
    assert isinstance(design, Design)
    return design


def calls_design(append: str = CALLS) -> Design:
    """The blink with ``append`` (by default the three calls of ``CALLS``) at its end."""
    from _outlinehelp import variant

    return variant(append=append)


__all__ = ["CALLS", "FEATURES", "LAST_LINE", "calls_design", "features_design", "features_text"]
