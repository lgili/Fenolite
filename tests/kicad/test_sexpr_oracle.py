# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""S-expression fixtures against kicad-cli (H-K-SEXPR-LEX-10/-9, -STRICT, -NUM-READ, -ESCAPES).

Every run happens in ``tmp_path`` because KiCad writes a ``.kicad_prl`` next to the board.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest
from _kicad import major, run, run_raw

from fenolite.backends.kicad import Atom, Node, dumps, load, parse
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind
from fenolite.core.errors import FormatError

pytestmark = pytest.mark.needs_kicad
FIXTURES = Path(__file__).resolve().parents[1] / "data" / "kicad" / "sexpr"
ROWS: list[dict[str, Any]] = list(
    tomllib.loads((FIXTURES / "EXPECT.toml").read_text(encoding="utf-8"))["fixture"]
)
ENCODER_VALUES = ['quote " here', "back\\slash", "line\nfeed", "carriage\rreturn", "tab\there", "vt\x0bhere",
                  "ctrl\x01here", "non-ASCII éü 日本 Ω"]  # fmt: skip


@pytest.mark.parametrize("row", ROWS, ids=lambda r: str(r["file"]))
def test_fixture_outcomes(row: dict[str, Any], tmp_path: Path) -> None:
    key = f"expect_kicad_{major()}"
    if key not in row:
        pytest.skip(f"{row['file']}: no {key} recorded")
    board = tmp_path / Path(str(row["file"])).name
    # Fixtures are 10.0 files; on another major the header becomes that major's own board constant.
    header = f"(version {FORMAT_VERSIONS[FileKind.BOARD][major()]})".encode()
    board.write_bytes((FIXTURES / str(row["file"])).read_bytes().replace(b"(version 20260206)", header))
    svg = board.with_suffix(".svg")
    result = run_raw("pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", svg, board)
    assert result.returncode == row[key], (
        f"{row['file']}: kicad-cli exited {result.returncode}\n{result.stderr}"
    )
    if result.returncode == 0:
        assert svg.is_file()


def _texts(root: Node) -> list[str]:
    return [node.atoms()[0].value for node in root.nodes("gr_text")]


def _upgrade(board: Path) -> Node:
    """``pcb upgrade --force`` in place (10.x only, see the markers), then parse the re-saved file."""
    load(board)  # never upgrade a file that does not parse: the CLI stops on a raw newline
    run("pcb", "upgrade", "--force", board)
    return load(board)


@pytest.mark.kicad_min_major(10)
def test_escapes_after_upgrade(tmp_path: Path) -> None:
    board = tmp_path / "escapes.kicad_pcb"
    shutil.copy(FIXTURES / "escapes.kicad_pcb", board)
    expected = _texts(load(board))
    assert len(expected) == 10
    assert _texts(_upgrade(board)) == expected


@pytest.mark.kicad_min_major(10)
def test_encoder_after_upgrade(tmp_path: Path) -> None:
    base = load(FIXTURES / "minimal.kicad_pcb")
    texts = [
        parse(
            f'(gr_text {Atom.string(value).text} (at 5 {2 + i} 0) (layer "F.Cu") '
            "(effects (font (size 1 1) (thickness 0.15))))"
        )  # fmt: skip
        for i, value in enumerate(ENCODER_VALUES)
    ]
    board = tmp_path / "encoder.kicad_pcb"
    board.write_text(dumps(base.with_children([*base.children, *texts])), encoding="utf-8")
    assert _texts(_upgrade(board)) == ENCODER_VALUES


def test_upgrade_guard_refuses_unparseable_files(tmp_path: Path) -> None:
    board = tmp_path / "bad.kicad_pcb"
    shutil.copy(FIXTURES / "mirror" / "newline-in-string.kicad_pcb", board)
    with pytest.raises(FormatError):
        _upgrade(board)
