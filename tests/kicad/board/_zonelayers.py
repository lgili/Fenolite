# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two heads of a zone's layers against ``kicad-cli`` (change c0145; ``H-K-ZONE-LAYER-HEAD``).

The authored board ``two_layer.kicad_pcb`` holds one copper zone on ``B.Cu`` and one rule area on
``F.Cu``, both written ``(layer "X")``. ``variant(child)`` is that text with the layer child of both
replaced by ``child``: a token edit, nothing is committed besides this module. The probes run on major
10 only: the re-saves need ``pcb upgrade``, which 9.0 lacks, and the loads were not run on 9.0.9.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable
from functools import cache
from pathlib import Path

from _boards import FIXTURE

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import dumps, parse

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
ZONE_UUID = "44edb74d-faf2-4793-bbd2-aef0794c6dcc"
AREA_UUID = "178d1501-3f49-496b-b907-7d6a94fc0f4a"
BOTH = ("F.Cu", "B.Cu")
SINGULAR_WILDCARD = '(layer "*.Cu")'
SINGULAR_MASK = '(layer "F&B.Cu")'
SINGULAR_LIST = '(layer "F.Cu" "B.Cu")'
PLURAL_WILDCARD = '(layers "*.Cu")'
PLURAL_MASK = '(layers "F&B.Cu")'
PLURAL_LIST = '(layers "F.Cu" "B.Cu")'
PLURAL_ONE = '(layers "B.Cu")'
SINGULAR_ONE = '(layer "B.Cu")'
LOADS = {
    "singular-wildcard": SINGULAR_WILDCARD,
    "singular-mask": SINGULAR_MASK,
    "singular-list": SINGULAR_LIST,
    "plural-wildcard": PLURAL_WILDCARD,
    "plural-mask": PLURAL_MASK,
    "plural-one": PLURAL_ONE,
}
"""Per load probe, the layer child given to the zone and to the rule area."""
SAVES = {"plural-wildcard": (PLURAL_WILDCARD, PLURAL_LIST), "plural-mask": (PLURAL_MASK, PLURAL_LIST),
         "plural-one": (PLURAL_ONE, SINGULAR_ONE)}  # fmt: skip
"""Per re-save probe, the layer child given to both and the child Fenolite's emitter writes for the same
layers (several names under ``layers``, one name under ``layer``)."""


def variant(child: str, text: str | None = None) -> str:
    """The authored board with ``child`` as the layer child of its zone and of its rule area."""
    out = FIXTURE.read_text(encoding="utf-8") if text is None else text
    for old, uuid in (('(layer "B.Cu")', ZONE_UUID), ('(layer "F.Cu")', AREA_UUID)):
        before = f'\t\t{old}\n\t\t(uuid "{uuid}")'
        assert out.count(before) == 1, uuid
        out = out.replace(before, f'\t\t{child}\n\t\t(uuid "{uuid}")')
    return out


def layer_children(text: str) -> dict[str, list[str]]:
    """Per zone uuid of ``text``, its ``layer`` and ``layers`` children in compact form."""
    found: dict[str, list[str]] = {}
    for zone in parse(text).nodes("zone"):
        uuid = zone.find("uuid")
        assert uuid is not None
        found[uuid.atoms()[0].value] = [
            dumps(c, style="compact") for c in zone.nodes() if c.name in ("layer", "layers")
        ]
    return found


def _runner() -> KicadCli:
    from _probes import runner  # _probes imports this module

    return runner()


@cache
def resaved(text: str) -> str:
    """``text`` saved again by ``pcb upgrade --force``."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "zones.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        return _runner().upgrade_board(board).decode("utf-8")


@cache
def changed(start: str, layers: tuple[str, ...]) -> str:
    """Fenolite's text for target 10 of the board read with ``start`` as both layer children, after the
    model's layers of the zone and of the rule area became ``layers``."""
    design = read_board(variant(start))
    assert design.board is not None
    for entity in (*design.board.zones, *design.board.keepouts):
        design = design.replace_entity(dataclasses.replace(entity, layers=layers))
    return write_board(design, target=10).text


def load_outcome(name: str) -> str:
    from _probes import load

    return load(variant(LOADS[name]))


def save_outcome(name: str) -> str:
    """``equal`` when KiCad's re-save holds, for both, the child Fenolite's emitter writes."""
    child, expected = SAVES[name]
    saved = layer_children(resaved(variant(child)))
    return "equal" if saved[ZONE_UUID] == [expected] and saved[AREA_UUID] == [expected] else "different"


def write_outcome(start: str, layers: tuple[str, ...]) -> str:
    """``equal`` when KiCad's re-save of a board Fenolite wrote after a change of the layers keeps the
    layer child Fenolite wrote, for the zone and for the rule area."""
    written = changed(start, layers)
    ours, theirs = layer_children(written), layer_children(resaved(written))
    return "equal" if all(ours[u] == theirs.get(u) for u in (ZONE_UUID, AREA_UUID)) else "different"


def zone_layer_probes() -> Probes:
    probes: Probes = {
        f"pcb-zone-layers-load-{name}": (lambda name=name: load_outcome(name), (10,)) for name in LOADS
    }
    for name in SAVES:
        probes[f"pcb-zone-layers-save-{name}"] = (lambda name=name: save_outcome(name), (10,))
    probes["pcb-zone-layers-write-widened"] = (lambda: write_outcome(SINGULAR_ONE, BOTH), (10,))
    probes["pcb-zone-layers-write-narrowed"] = (lambda: write_outcome(PLURAL_LIST, ("F.Cu",)), (10,))
    return probes


__all__ = [
    "AREA_UUID",
    "BOTH",
    "LOADS",
    "PLURAL_LIST",
    "PLURAL_MASK",
    "PLURAL_ONE",
    "PLURAL_WILDCARD",
    "SAVES",
    "SINGULAR_LIST",
    "SINGULAR_MASK",
    "SINGULAR_ONE",
    "SINGULAR_WILDCARD",
    "ZONE_UUID",
    "changed",
    "layer_children",
    "load_outcome",
    "resaved",
    "save_outcome",
    "variant",
    "write_outcome",
    "zone_layer_probes",
]
