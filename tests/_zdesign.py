# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The impedance design of the tests (change c0105): the blink on four copper layers, its two LED nets in
the class ``SE50``, a ``USB2`` pair in ``USB90``, the targets ``SE50`` and ``USB90`` and the bench stack-up.

The numbers are authored round values of a generic 1.6 mm four-layer board (``design.md`` of c0105,
"Context"): 0.2 mm prepreg of permittivity 4.3, a 1.065 mm core, 35 µm copper, 0.35 mm and 0.2 mm tracks.
"""

from __future__ import annotations

from _buildhelp import blink_text

from fenolite.dsl import Design

BOARD = "design.board(mm(50), mm(30))\n"
CLASSES = """
from fenolite.dsl import USB2, ohm, stack, trace

design.rules.netclass("SE50", clearance=mm(0.2), nets=(led_drv, led_a))
usb_p, usb_n = Net("USB_P"), Net("USB_N")
design.rules.netclass("USB90", clearance=mm(0.2), nets=(usb_p, usb_n))
usb = USB2(usb_p, usb_n, name="USB")
"""
SE50 = """
design.rules.impedance(
    "SE50",
    ohms=ohm(50),
    netclass="SE50",
    layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.35)), trace("B.Cu", refs="In2.Cu", width=mm(0.35))),
)
"""
USB90 = """
design.rules.impedance(
    "USB90",
    ohms=90,
    pair=usb,
    tolerance=10,
    layers=(trace("F.Cu", refs="In1.Cu", width=mm(0.2), gap=mm(0.15)),),
)
"""
STACKUP = """
design.stackup(
    stack.copper(mm(0.035)),
    stack.prepreg(mm(0.2), epsilon_r="4.3"),
    stack.copper(mm(0.035)),
    stack.core(mm(1.065), epsilon_r="4.3"),
    stack.copper(mm(0.035)),
    stack.prepreg(mm(0.2), epsilon_r="4.3"),
    stack.copper(mm(0.035)),
    impedance_controlled={flag},
)
"""


def script(
    *, copper: int = 4, se50: bool = True, usb90: bool = True, stackup: bool | None = True, extra: str = ""
) -> str:
    """The script text: ``stackup`` is the ``impedance_controlled`` flag of the bench stack-up, ``None``
    for none; ``extra`` is appended."""
    text = blink_text(marks=False)
    assert BOARD in text
    text = text.replace(BOARD, f"design.board(mm(50), mm(30), copper={copper})\n")
    text += CLASSES + (SE50 if se50 else "") + (USB90 if usb90 else "")
    if stackup is not None:
        text += STACKUP.format(flag=stackup)
    return text + extra


def zdesign(**options: object) -> Design:
    scope: dict[str, object] = {"__name__": "design"}
    exec(compile(script(**options), "zdesign.py", "exec"), scope)  # type: ignore[arg-type]  # noqa: S102
    design = scope["design"]
    assert isinstance(design, Design)
    return design
