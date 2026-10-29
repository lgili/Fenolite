# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The benches of the octilinear router (change c0228), built with ``tests/_ties.py`` from the authored
footprints of ``tests/_reusebench.py`` and a round pad ``DOT``. No file is read, nothing comes from a
library, and every value is a round invented one.

``gate_loop``: a driver ``U1`` (``IC6``) at (20, 20) mm and a switch ``Q1`` (``IC6``) at (30, 25) mm; the
net ``GATE`` joins ``U1-4`` (22, 21) to ``Q1-2`` (28, 25) and ``KSRC`` joins ``U1-5`` (22, 20) to ``Q1-1``
(28, 24). ``sense``: the pair ``SNS_P``/``SNS_N`` from the test pads ``TP1`` (10, 29) and ``TP2`` (10, 31)
to ``U2-1`` (18, 29.5) and ``U2-2`` (18, 30.5), class ``SNS`` with pair width 0.2 mm, gap 0.2 mm and
clearance 0.15 mm. Both have a ``Default`` clearance of 0.3 mm and 0.25 mm tracks.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from _groundties import _p
from _reusebench import IC6, TP
from _ties import MM, TieBoard, tie_footprint

from fenolite.model.circuit import NetClass
from fenolite.model.design import Design

CLEARANCE = 3 * MM // 10
WIDTH = MM // 4
DOT = tie_footprint("DOT", (0,), size=6 * MM // 10, shape="circle")
"""One round pad of 0.6 mm."""


def _classes(design: Design, extra: Mapping[str, NetClass] = {}) -> Design:  # noqa: B006
    """``design`` with the ``Default`` class given its track width, and the nets of ``extra`` (by name) put
    in their class."""
    default = dataclasses.replace(design.circuit.netclasses[0], track_width=WIDTH)
    classes = (default, *{item.id: item for item in extra.values()}.values())
    nets = tuple(
        dataclasses.replace(net, netclass_id=extra[net.name].id) if net.name in extra else net
        for net in design.circuit.nets
    )
    circuit = dataclasses.replace(design.circuit, netclasses=classes, nets=nets)
    return dataclasses.replace(design, circuit=circuit)


def gate_loop() -> Design:
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", IC6, _p(20, 20), nets={"4": "GATE", "5": "KSRC"})
    board.place("Q1", IC6, _p(30, 25), nets={"1": "KSRC", "2": "GATE"})
    return _classes(board.build())


SNS = NetClass(
    id="cls_00000000-0000-4000-8000-000000000002",
    name="SNS",
    clearance=15 * MM // 100,
    track_width=MM // 5,
    diff_pair_width=MM // 5,
    diff_pair_gap=MM // 5,
)


def sense() -> Design:
    board = TieBoard(clearance=CLEARANCE)
    board.place("TP1", TP, _p(10, 29), nets={"1": "SNS_P"})
    board.place("TP2", TP, _p(10, 31), nets={"1": "SNS_N"})
    board.place("U2", IC6, _p(20, 30.5), nets={"1": "SNS_P", "2": "SNS_N"})
    return _classes(board.build(), {"SNS_P": SNS, "SNS_N": SNS})


def dots(nets: Mapping[str, tuple[tuple[float, float], ...]], *, width: int = 60) -> Design:
    """A board of ``DOT`` pads: per net, its pad centres in millimetres (``D1``, ``D2``, … in order)."""
    board = TieBoard(clearance=CLEARANCE)
    n = 0
    for name, points in nets.items():
        for x, y in points:
            n += 1
            board.place(f"D{n}", DOT, _p(x, y), nets={"1": name})
    return _classes(board.build(width=width * MM))


__all__ = ["CLEARANCE", "DOT", "SNS", "WIDTH", "dots", "gate_loop", "sense"]
