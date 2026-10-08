# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The order of the rotation and the mirror of a symbol instance, asked of ``kicad-cli`` (capability
kicad-oracle, "Schematic naming facts are probed"; hypothesis ``H-K-SCH-PINFRAME``; change c0137).

The probes ``sch-pin-frame-*`` count open pins of a 32-pin symbol whose pin positions both mirrors map onto
themselves, so they cannot tell the order of the two operations. This test asks the netlist export: on
the authored sheet of ``tests/_pinframe.py`` each pin of the twelve frames must be on the net of the label
``schlayout.pin_point`` puts at its point. The control sets the labels where the other order puts them and
must leave the pins of the four mirrored and turned instances off their nets.
"""

from __future__ import annotations

import _pinframe
import pytest
from _gencases import nets_of
from _probes import major, version

pytestmark = pytest.mark.needs_kicad


def test_every_pin_is_on_the_net_of_its_frame() -> None:
    on = nets_of(_pinframe.frame_sheet(major()), name="frames")
    wanted = _pinframe.expected()
    wrong = {node: (on.get(node), net) for node, net in wanted.items() if on.get(node) != net}
    print(f"{len(wanted) - len(wrong)} of {len(wanted)} pins on the net of their label, {version()}")
    assert not wrong, f"pins off the net of their label (found, wanted): {wrong}"


def test_the_control_tells_the_two_orders_apart() -> None:
    on = nets_of(_pinframe.frame_sheet(major(), _pinframe.mirror_first), name="frames")
    wanted = _pinframe.expected()
    turned = {_pinframe.ref(index) for index in _pinframe.distinguishing()}
    assert turned == {"U6", "U8", "U10", "U12"}
    for (reference, number), net in wanted.items():
        if reference in turned:
            assert on.get((reference, number)) != net, f"{reference}-{number} is on {net} in the other order"
        else:
            assert on.get((reference, number)) == net, (reference, number, on.get((reference, number)))
