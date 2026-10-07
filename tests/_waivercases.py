# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script lines for the waiver, net-tie and severity tests of the CLI (change c0114): the routed blink of
``tests/_routed.py`` with one more authored footprint in its script, built by ``fenolite build`` itself.

No written file is edited: the footprint, its nets and the waiver are in the script, as a user writes
them. Every name and value is authored for Fenolite."""

from __future__ import annotations

from _routed import Routed

ANCHOR = "# Stitching vias every 5 mm"
IMPORT_OLD = "from fenolite.dsl import Design, Net, Part, Power, connect, mm, no_connect, via_step"
IMPORT_NEW = "from fenolite.dsl import Design, Footprint, Net, Part, Power, connect, mm, no_connect, via_step"
WAIVER_NAME = "copper.short:KS1-1,KS1-2"
WAIVER = 'design.waive("copper.short", "KS1-1", "KS1-2", reason="Kelvin pad")\n'
SEVERITY = 'design.rules.severity("kicad.drc.silk-overlap", "ignore")\n'


def two_pad_part(ref: str, name: str, half: str, *, nets: tuple[str, str], tie: bool = False) -> str:
    """The script lines of an authored footprint ``Local:<name>`` with two 1 mm square pads at
    ``-half`` and ``half`` mm, placed as ``ref`` on a free spot of the routed blink, its pads on ``nets``.
    ``tie`` declares the two pads as one net-tie group."""
    var = ref.lower()
    lines = [
        f'{var}_fp = Footprint("Local", "{name}", kind="smd")',
        f'{var}_fp.pad("1", at=(mm(-{half}), mm(0)), size=(mm(1), mm(1)))',
        f'{var}_fp.pad("2", at=(mm({half}), mm(0)), size=(mm(1), mm(1)))',
        *([f'{var}_fp.net_tie("1", "2")'] if tie else []),
        f"design.add_footprint({var}_fp)",
        f'{var} = Part("{ref}", "Mini:Mini_R", footprint="Local:{name}", value="{name}")',
        f"design.add({var})",
        f'{var}_a, {var}_b = Net("{nets[0]}"), Net("{nets[1]}")',
        f"connect({var}_a, {var}[1])",
        f"connect({var}_b, {var}[2])",
        f"{var}.place(mm(27), mm(18))",
    ]
    return "\n".join(lines) + "\n"


KELVIN = two_pad_part("KS1", "Kelvin", "0.4", nets=("ISENSE", "PWR"))
"""``KS1``: two pads that overlap by 0.2 mm, on two nets, without a net-tie group: one ``copper.short``."""
KELVIN_APART = two_pad_part("KS1", "Kelvin", "0.75", nets=("ISENSE", "PWR"))
"""The same part with its pads 0.5 mm apart: no finding."""
KELVIN_CLOSE = two_pad_part("KS1", "Kelvin", "0.55", nets=("ISENSE", "PWR"))
"""The same part with its pads 0.1 mm apart: one ``copper.clearance`` under the 0.2 mm default class."""
NET_TIE = two_pad_part("NT1", "Tie", "0.75", nets=("A", "B"), tie=True)
"""``NT1``: two pads 0.5 mm apart with ``net_tie("1", "2")``."""
NET_TIE_TOUCHING = two_pad_part("NT1", "Tie", "0.4", nets=("A", "B"), tie=True)
"""``NT1`` with its tied pads overlapping: no finding on KiCad."""


CLASS_OLD = "clearance=mm(0.2), track_width=mm(0.5)"
CLASS_TIGHT = "clearance=mm(0.3), track_width=mm(0.5)"
"""The class ``PWR`` of the routed blink (``VIN`` and ``GND``) with a clearance of 0.3 mm: the pads 9, 10
and 11 of ``U1`` are 0.25 mm apart, and the ``GND`` track leaves pad 10 at 0.275 mm from pads 9 and 11.
Four ``copper.clearance`` findings: ``U1-9``/``U1-10``, ``U1-10``/``U1-11`` and each of ``U1-9`` and
``U1-11`` against the track."""
PITCH = (
    'design.waive("copper.clearance", "U1-9", "U1-10", reason="fixed by the package pitch", name="pitch")\n'
)
PITCH_11 = 'design.waive("copper.clearance", "U1-11", "U1-10", reason="fixed by the package pitch")\n'
PITCH_11_NAME = "copper.clearance:U1-11,U1-10"
ESCAPE = (
    'design.waive("copper.clearance", "U1-*", "*", min_gap=mm(0.26), reason="GND escape", name="escape")\n'
)
"""Accepts the two pad-to-track findings (0.275 mm) and not the two pad-to-pad ones (0.25 mm)."""
ESCAPE_STRICT = ESCAPE.replace("mm(0.26)", "mm(0.28)")
"""A bound above 0.275 mm: the pad-to-track findings stay errors."""
TEST_POINT = 'design.waive("kicad.drc.via-dangling", "*", reason="test point", name="tp")\n'


def tight(routed: Routed, *lines: str) -> None:
    """Give the class ``PWR`` of ``routed`` a clearance of 0.3 mm and add ``lines`` to its script."""
    routed.edit_script(CLASS_OLD, CLASS_TIGHT)
    if lines:
        routed.edit_script(ANCHOR, "".join(lines) + ANCHOR)


def plant(routed: Routed, *lines: str) -> None:
    """Add ``lines`` to the script of ``routed``, before its stitching vias, and import ``Footprint``."""
    text = routed.script.read_text(encoding="utf-8")
    if IMPORT_OLD in text:
        routed.edit_script(IMPORT_OLD, IMPORT_NEW)
    routed.edit_script(ANCHOR, "".join(lines) + ANCHOR)


__all__ = [
    "ANCHOR",
    "CLASS_OLD",
    "CLASS_TIGHT",
    "ESCAPE",
    "ESCAPE_STRICT",
    "PITCH",
    "PITCH_11",
    "PITCH_11_NAME",
    "TEST_POINT",
    "tight",
    "KELVIN",
    "KELVIN_APART",
    "KELVIN_CLOSE",
    "NET_TIE",
    "NET_TIE_TOUCHING",
    "SEVERITY",
    "WAIVER",
    "WAIVER_NAME",
    "plant",
    "two_pad_part",
]
