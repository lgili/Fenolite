# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The compact board scene (capability viewer-performance, scenario "Same drawing"; change c0182)."""

from __future__ import annotations

import base64
import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fenolite.cli.cmd_view import scene_of
from fenolite.view.compact import SCHEMA_V1, compact, expand, pack, unpack
from fenolite.view.export import template

ROOT = Path(__file__).resolve().parents[3]
BOARDS = (
    ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc",
    ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb",
)


def _size(value: object) -> int:
    return len(json.dumps(value, separators=(",", ":")))


@pytest.mark.parametrize("board", BOARDS, ids=lambda p: p.name)
def test_round_trip(board: Path) -> None:
    if not board.exists():
        pytest.skip(f"{board.name} is not in this checkout")
    scene = scene_of(board)
    small = compact(scene)
    assert small["schema"] == SCHEMA_V1 and "prims" not in small
    assert expand(small)["prims"] == scene["prims"]
    assert unpack(pack(scene))["prims"] == scene["prims"]
    assert _size(small["p1"]) < _size(scene["prims"])


def test_packed_bytes_do_not_depend_on_the_interpreter() -> None:
    """A review sheet embeds packed scenes and its review accepts the sheet's SHA-256 (c0266 6.1): the gzip
    header is fixed (Python 3.11 and 3.12 wrote the host's operating-system byte, 3.13 writes 255)."""
    scene = {"prims": [["F.Cu", "s", [1, 2, 3, 4, 5], -1, -1, "track 1"]], "meta": {}}
    raw = base64.b64decode(pack(scene)[3:])
    assert raw[:10] == bytes.fromhex("1f8b08000000000002ff")
    assert raw[9] == 0xFF
    text = json.dumps(compact(scene), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert gzip.decompress(raw) == text
    assert unpack(pack(scene))["prims"] == scene["prims"]
    assert pack(scene) == pack(json.loads(json.dumps(scene)))


def test_unfit_scene_stays_v0() -> None:
    scene = {"prims": [["F.Cu", "s", [1, 2, 3, 4, 0.5], -1, -1, "x"]], "meta": {}}
    assert compact(scene) is scene


def test_page_decoder_matches() -> None:
    """The page's ``decodeV1`` gives the same primitives as ``expand``, run in Node when it is installed."""
    html = template()
    start, end = html.index("// <decodeV1>"), html.index("// </decodeV1>")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    scene = scene_of(BOARDS[0])
    small = compact(scene)
    script = (
        html[start:end]
        + "const sc = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        + ("console.log(JSON.stringify(decodeV1(sc).prims));")
    )
    done = subprocess.run(
        [node, "-e", script],
        input=json.dumps(small),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    assert json.loads(done.stdout) == scene["prims"]
