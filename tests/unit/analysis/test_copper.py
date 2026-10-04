# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of a net as thick shapes, equal to the copper check's (capability board-analyses, "Copper of
a net as thick shapes"; change c0047). The test imports both builders; the package imports only one."""

from __future__ import annotations

import ast
import random
from collections import Counter
from pathlib import Path

from _analysis import MM, at
from _coppercheck import Copper

from fenolite.analysis.copper import ARC_TOL_NM, net_copper
from fenolite.backends.base import PadCopper
from fenolite.checks import copper as check_copper
from fenolite.core.coords import Point

ROOT = Path(__file__).resolve().parents[3]
Key = tuple[str, str, tuple[Point, ...], int, bool]


def generated(seed: int) -> Copper:
    rng = random.Random(seed)
    made = Copper(layers=rng.choice((2, 4)))  # type: ignore[arg-type]
    layers = ("F.Cu", "B.Cu") if made.layers == 2 else ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    nets = ("A", "B", "C", None)

    def point() -> Point:
        return Point(rng.randint(0, 40 * MM), rng.randint(0, 30 * MM))

    for _ in range(rng.randint(3, 8)):
        made.track(
            rng.choice(nets), point(), point(), width=rng.randint(100_000, MM), layer=rng.choice(layers)
        )
    for _ in range(rng.randint(1, 4)):
        start = point()
        made.arc(
            rng.choice(nets),
            start,
            Point(start.x + 2 * MM, start.y + rng.choice((-1, 1)) * MM),
            Point(start.x + 4 * MM, start.y),
            width=rng.randint(100_000, MM),
            layer=rng.choice(layers),
        )
    for _ in range(rng.randint(1, 4)):
        made.via(rng.choice(nets), point(), diameter=rng.randint(400_000, MM))
    if made.layers == 4:
        made.via("A", point(), layers=("F.Cu", "In1.Cu"), via_type="blind")
    corner = point()
    ring = (corner, Point(corner.x + 5 * MM, corner.y), Point(corner.x + 5 * MM, corner.y + 3 * MM))
    made.zone("B", ring, layer="F.Cu", fills=(ring, (corner, corner, corner)))
    made.pad("R1", "1", "A", PadCopper("F.Cu", (point(),), 800_000))
    made.pad("R1", "2", "C", PadCopper("F.Cu", (point(), point()), 500_000), PadCopper("B.Cu", ring, 0, True))
    made.pad("H1", "", None, kind="np_thru_hole")
    made.pad("R2", "1", "B")
    return made


def from_analysis(made: Copper) -> tuple[Counter[Key], dict[str, int]]:
    found = net_copper(made.build(), pads=made.pads)
    keys: Counter[Key] = Counter()
    for net, shapes in found.by_net.items():
        for shape in shapes:
            keys[(shape.layer, net, shape.shape.core, shape.shape.width, shape.shape.filled)] += 1
    return keys, dict(found.unsupported)


def from_check(made: Copper) -> tuple[Counter[Key], dict[str, int]]:
    items = check_copper._Items(made.build(), made.pads, ARC_TOL_NM)  # pyright: ignore[reportPrivateUsage]
    band = ARC_TOL_NM + 1
    keys: Counter[Key] = Counter()
    for item in items.items:
        if item.net_id is None:
            continue
        for layer, shapes in item.shapes.items():
            for shape in shapes:
                width = shape.wide.width - (2 * band if item.ref.kind == "arc" else 0)
                keys[(layer, item.ref.net, shape.wide.core, width, shape.wide.filled)] += 1
    return keys, dict(items.unsupported)


def test_same_shapes_as_the_copper_check() -> None:
    total = 0
    for seed in range(60):
        made = generated(seed)
        ours, unsupported = from_analysis(made)
        theirs, theirs_unsupported = from_check(made)
        assert ours == theirs, seed
        assert unsupported == theirs_unsupported, seed
        total += sum(ours.values())
    assert total > 600


def test_bands_wheres_and_netless_copper() -> None:
    made = Copper()
    made.track("A", at(0, 0), at(5, 0), locator="/track")
    made.track(None, at(0, 2), at(5, 2))
    made.arc("A", at(0, 5), at(2, 6), at(4, 5))
    made.pad("R1", "2", "A", PadCopper("F.Cu", (at(8, 8),), 800_000))
    found = net_copper(made.build(), pads=made.pads)
    assert list(found.by_net) == ["A"] and found.outer == ("F.Cu", "B.Cu")
    by_kind = {shape.kind: shape for shape in found.by_net["A"]}
    assert by_kind["track"].where == "/track" and by_kind["track"].band == 0
    assert by_kind["arc"].band == ARC_TOL_NM + 1
    assert by_kind["pad"].where == "R1-2" and by_kind["pad"].layer == "F.Cu"


def test_pads_without_a_frame_are_counted() -> None:
    made = Copper()
    made.pad("R1", "1", "A", PadCopper("F.Cu", (at(8, 8),), 800_000))
    made.pad("R1", "2", "B", PadCopper("F.Cu", (at(9, 8),), 800_000))
    made.pad("H1", "", None, kind="np_thru_hole")
    found = net_copper(made.build(), pads=None)
    assert dict(found.unsupported) == {"pad": 2} and found.by_net == {}


def test_layering_holds() -> None:
    for path in sorted((ROOT / "src" / "fenolite" / "analysis").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                assert not name.startswith("fenolite.checks"), f"{path.name} imports {name}"
                assert not name.startswith("fenolite.backends.") or name == "fenolite.backends.base", name
