# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored boards for the board reader tests: the CC0 fixture and small inline boards per scenario."""

from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.pcb import opaque_count, opaque_digests, read_board, rebuild_board
from fenolite.backends.kicad.sexpr import dumps, first_difference, parse, tree_equal
from fenolite.model.canonical import to_data
from fenolite.model.design import Design

FIXTURE = Path(__file__).resolve().parent / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
LAYERS = (
    '(layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (2 "B.Cu" signal) (1 "F.Mask" user) (3 "B.Mask" user)'
    ' (25 "Edge.Cuts" user))'
)


def uid(n: int) -> str:
    """An authored uuid, distinct per ``n``."""
    return f"00000000-0000-4000-8000-{n:012d}"


def board(*items: str, version: int = 20241229, nets: Sequence[str] | None = ("", "A", "B")) -> str:
    """A board with the given root items; ``nets`` is the numbered table (``None`` for the name form)."""
    major = "10.0" if version > 20241229 else "9.0"
    table = "" if nets is None else " ".join(f'(net {i} "{name}")' for i, name in enumerate(nets))
    return (
        f'(kicad_pcb (version {version}) (generator "fenolite-tests") (generator_version "{major}")'
        f' (general (thickness 1.6)) (paper "A4") {LAYERS} (setup (pad_to_mask_clearance 0))'
        f" {table} {' '.join(items)})"
    )


def segment(
    n: int, *, start: str = "0 0", end: str = "1 0", net: str = "(net 1)", uuid: str | None = None
) -> str:
    return (
        f'(segment (start {start}) (end {end}) (width 0.25) (layer "F.Cu") {net} (uuid "{uuid or uid(n)}"))'
    )


def pad(
    n: int, number: str = "1", *, extra: str = "", drill: str = "", layers: str = '"F.Cu" "F.Mask"'
) -> str:
    return (
        f'(pad "{number}" smd rect (at 0 0) (size 1 1){drill} (layers {layers}) (net 1 "A"){extra}'
        f' (uuid "{uid(n)}"))'
    )


def footprint(n: int, *, at: str = "10 10", attr: str = "(attr smd)", pads: str = "", ref: str = "U1") -> str:
    return (
        f'(footprint "Lib:FP" (layer "F.Cu") (uuid "{uid(n)}") (at {at})'
        f' (property "Reference" "{ref}" (at 0 0) (layer "F.SilkS") (uuid "{uid(n + 1)}")'
        f" (effects (font (size 1 1) (thickness 0.15)))) {attr} {pads})"
    )


def zone(n: int, *, inner: str, net: str = "(net 1)", layer: str = '(layer "F.Cu")') -> str:
    return (
        f'(zone {net} (net_name "A") {layer} (uuid "{uid(n)}") (hatch edge 0.5)'
        f" (connect_pads (clearance 0.5)) (min_thickness 0.25) {inner})"
    )


SQUARE = "(polygon (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10)))"

SCENARIOS: dict[str, str] = {
    "blind-via": board(
        f'(via blind (at 1 1) (size 0.6) (drill 0.3) (layers "F.Cu" "In1.Cu") (net 1) (uuid "{uid(1)}"))'
    ),
    "unknown-net": board(segment(1, net="(net 7)"), nets=("", "A")),
    "name-form": board(segment(1, net='(net "GND")'), version=20260206, nets=None),
    "spelling": board(segment(1, start="12.000000 0")),
    "sub-nm": board(segment(1, start="0.0000001 0")),
    "fp-angle": board(footprint(1, at="10 10 30.0000001")),
    "repeat-uuid": board(segment(1, uuid=uid(9)), segment(2, uuid=uid(9), start="2 0")),
    "attr": board(footprint(1, attr="(attr smd frobnicate)")),
    "oval-drill": board(footprint(1, pads=pad(5, drill=" (drill oval 1.2 2.0)"))),
    "pintype": board(footprint(1, pads=pad(5, extra=' (pintype "passive+no_connect")'))),
    "padstack": board(
        footprint(
            1,
            pads=pad(
                5, extra=' (padstack (mode front_inner_back) (layer "In1.Cu" (shape circle) (size 1 1)))'
            ),
        )
    ),
    "teardrop": board(zone(1, inner=f"(attr (teardrop (type padvia))) {SQUARE}")),
    "zone-arc": board(
        zone(1, inner="(polygon (pts (xy 0 0) (arc (start 0 0) (mid 1 1) (end 2 0)) (xy 2 5)))")
    ),
    "zone-two-polygons": board(zone(1, inner=f"{SQUARE} {SQUARE}")),
    "island-10": board(
        zone(
            1,
            net='(net "A")',
            inner=(
                f'{SQUARE} (filled_polygon (layer "F.Cu") (island yes) (pts (xy 0 0) (xy 1 0) (xy 1 1)))'
                ' (filled_polygon (layer "F.Cu") (island no) (pts (xy 2 2) (xy 3 2) (xy 3 3)))'
            ),
        ),
        version=20260206,
        nets=None,
    ),
}


def _without_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_provenance(v) for k, v in value.items() if k != "provenance"}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [_without_provenance(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def canonical(design: Design) -> Any:
    """The canonical data of a design read from a board, every provenance removed."""
    return _without_provenance([to_data(design.header), to_data(design.circuit), to_data(design.board)])


def rt1_problems(text: str, design: Design | None = None) -> list[str]:
    """The RT1 conditions that fail for one board text (empty when all three hold)."""
    design = design if design is not None else read_board(text)
    problems: list[str] = []
    rebuilt = rebuild_board(design)
    original = parse(text)
    if not tree_equal(rebuilt, original):
        problems.append(f"(a) rebuild differs at {first_difference(rebuilt, original)}")
    again = read_board(dumps(rebuilt))
    # The header name comes from the file name, not from the content: a text has none.
    again = dataclasses.replace(again, header=dataclasses.replace(again.header, name=design.header.name))
    if canonical(again) != canonical(design):
        problems.append("(b) the re-read model differs")
    if opaque_count(again) != opaque_count(design) or opaque_digests(again) != opaque_digests(design):
        problems.append("(c) opaque counts or digests differ")
    return problems


def census(section: str, key: str, data: Any) -> None:
    """Merge ``data`` under ``section/key`` into the JSON file named by ``FENOLITE_CENSUS_OUT``."""
    target = os.environ.get("FENOLITE_CENSUS_OUT")
    if not target:
        return
    path = Path(target)
    current: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    current.setdefault(section, {})[key] = data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
