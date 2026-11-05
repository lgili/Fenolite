# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fixed-seed two/four-layer router acceptance boards (change c0370, task 2).

The generator ``examples/routing/acceptance.py`` is authored for Fenolite; these tests pin its bytes, its
bounds and the boards that ``fenolite build`` makes of it, without any third-party board data.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "examples" / "routing" / "acceptance.py"


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_route_acceptance", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ beside the example
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


acceptance = _generator()

# The script bytes of fixed arguments; a change here changes every acceptance measurement.
GOLDEN = {
    (1, 2, 40): "87b606b8db9392aeee73ae41e63f5ee91a525014d128fb5d1820e9622cda911c",
    (1, 4, 150): "eca389402b96b3adec48e26940efbaa09104f2eef24a90fa6db1aa4beeebd669",
}


def _build(tmp_path: Path, *, seed: int, layers: int, parts: int):
    script = tmp_path / "board.py"
    script.write_text(acceptance.script(seed=seed, layers=layers, parts=parts), encoding="utf-8")
    out = tmp_path / "out"
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main(["build", str(script), "--out", str(out), "--confirm", "--json"])
    envelope = json.loads(stdout.getvalue() or "{}")
    assert code == 0, (code, stderr.getvalue())
    assert envelope["issues"] == []
    (board,) = sorted(out.glob("*.kicad_pcb"))
    return envelope["result"], read_board(board.read_text(encoding="utf-8"), file=board.name)


@pytest.mark.parametrize(("seed", "layers", "parts"), sorted(GOLDEN))
def test_fixed_arguments_give_fixed_bytes(seed: int, layers: int, parts: int) -> None:
    text = acceptance.script(seed=seed, layers=layers, parts=parts)
    assert text == acceptance.script(seed=seed, layers=layers, parts=parts)
    assert hashlib.sha256(text.encode()).hexdigest() == GOLDEN[(seed, layers, parts)]


def test_seeds_change_the_nets_and_turns_but_not_the_grid() -> None:
    one, two = (acceptance.script(seed=s, layers=2, parts=40) for s in (1, 2))
    assert one != two
    places = [re.findall(r"place\((mm\([^)]*\)), (mm\([^)]*\))", text) for text in (one, two)]
    assert places[0] == places[1] and len(places[0]) == 40


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": -1, "layers": 2, "parts": 10},
        {"seed": True, "layers": 2, "parts": 10},
        {"seed": 1, "layers": 3, "parts": 10},
        {"seed": 1, "layers": 6, "parts": 10},
        {"seed": 1, "layers": 2, "parts": 3},
        {"seed": 1, "layers": 2, "parts": 161},
        {"seed": 1, "layers": 2, "parts": 10.0},
    ],
)
def test_arguments_outside_the_bounds_are_refused(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        acceptance.script(**kwargs)


def test_mixer_is_the_published_splitmix64_sequence() -> None:
    # The first outputs of SplitMix64 from seed 0 (the reference constants of the algorithm).
    mixer = acceptance.Mixer(0)
    assert [mixer.next() for _ in range(3)] == [
        0xE220A8397B1DCDAF,
        0x6E789E6AA1B965F4,
        0x06C45D188009454F,
    ]


def test_header_marks_the_board_as_authored() -> None:
    text = acceptance.script(seed=7, layers=4, parts=20)
    assert text.startswith("# SPDX-License-Identifier: CC0-1.0\n# Authored for Fenolite")


@pytest.mark.parametrize(("layers", "parts"), [(2, 13), (4, 13), (4, 150)])
def test_built_board_holds_every_part_on_its_grid(tmp_path: Path, layers: int, parts: int) -> None:
    result, design = _build(tmp_path, seed=3, layers=layers, parts=parts)
    assert design.board is not None
    copper = [layer for layer in design.board.layers if layer.kind == "copper"]
    assert len(copper) == layers
    assert len(result["placed"]) == parts and not result["staged"]
    pads = board_pads(design, issues=[])
    assert len({pad.ref for pad in pads}) == parts and len(pads) == 2 * parts
    # Every net reaches at least two pads, pads 1 carry signals and pads 2 the supply.
    nets = Counter(pad.net for pad in pads)
    assert all(count >= 2 for count in nets.values()), nets
    assert {pad.net for pad in pads if pad.number == "2"} == {"VIN", "GND"}
    assert all(str(pad.net).startswith("SIG") for pad in pads if pad.number == "1")
    # Each part's centre (the midpoint of its two pads) lies in its own grid cell.
    cols, rows = acceptance.grid(parts)
    ends: dict[str, list[tuple[int, int]]] = {}
    for pad in pads:
        ends.setdefault(pad.ref, []).append((pad.position.x, pad.position.y))
    ring = board_outline(design).rings[0]
    left, top = min(point.x for point in ring), min(point.y for point in ring)
    width, height = max(point.x for point in ring) - left, max(point.y for point in ring) - top
    assert (width, height) == (
        (cols * acceptance.PITCH_X_UM + 2 * acceptance.MARGIN_UM) * 1000,
        (rows * acceptance.PITCH_Y_UM + 2 * acceptance.MARGIN_UM) * 1000,
    )
    cells = set()
    for (x0, y0), (x1, y1) in ends.values():
        x = ((x0 + x1) // 2 - left) // 1000 - acceptance.MARGIN_UM
        y = ((y0 + y1) // 2 - top) // 1000 - acceptance.MARGIN_UM
        assert x % acceptance.PITCH_X_UM == acceptance.PITCH_X_UM // 2
        assert y % acceptance.PITCH_Y_UM == acceptance.PITCH_Y_UM // 2
        cells.add((x // acceptance.PITCH_X_UM, y // acceptance.PITCH_Y_UM))
    assert len(cells) == parts and all(0 <= col < cols and 0 <= row < rows for col, row in cells)
    names = {net.id: net.name for net in design.circuit.nets}
    zones = {
        (names[zone.net_id], layer) for zone in design.board.zones if zone.net_id for layer in zone.layers
    }
    expected = {("GND", "B.Cu")} if layers == 2 else {("GND", "In1.Cu"), ("VIN", "In2.Cu")}
    assert zones == expected
