# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Written boards load and count on both majors (capability kicad-oracle, "Written boards load and
count on both majors"; hypothesis H-K-PCB-WRITE; change c0017).

The triad and the created test board are written with ``write_board`` and checked by the running
``kicad-cli`` on copies, with a ``{}`` project file next to the board and an empty
``KICAD_CONFIG_HOME``. Load outcomes come from the probes of ``tests/kicad/_probes.py``.
"""

from __future__ import annotations

from pathlib import Path

import _triad
import pytest
from _boards import created_board
from _frame import pos_problems, read_pos
from _probes import load, major, run, runner, triad_text

from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import FileKind, check_emittable
from fenolite.core.coords import Point

pytestmark = pytest.mark.needs_kicad


def written(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    target = major()
    board = _triad.write(_triad.triad(target), target, tmp_path)
    return board, _triad.project(board)


def test_emit_check_before_kicad() -> None:
    for target in (9, 10):
        assert check_emittable(parse(triad_text(target)), FileKind.BOARD, target) == ()
        assert (
            check_emittable(parse(write_board(created_board(4), target=target).text), FileKind.BOARD, target)
            == ()
        )


def test_triad_loads() -> None:
    assert run(f"pcb-write-triad-{major()}") == "load"


def test_created_heads_load() -> None:
    """The created test board (every CANONICAL_ORDER head, every FLOOR_HEADS name, 4 copper layers)."""
    assert run(f"pcb-write-heads-{major()}") == "load"


def test_report_parses(tmp_path: Path) -> None:
    board, files = written(tmp_path)
    drc = runner().drc(board, files=files)
    assert drc.report is not None and drc.report.kicad_version.split(".")[0] == str(major())


def test_placements(tmp_path: Path) -> None:
    board, files = written(tmp_path)
    rows = read_pos(runner().export_pos_csv(board, files=files))
    assert pos_problems(_triad.triad(major()), rows) == []
    by_ref = {row.ref: (row.side, row.rotation, row.position) for row in rows}
    assert by_ref == {
        "R1": ("top", 0, Point(10_000_000, 10_000_000)),
        "D1": ("bottom", 90_000_000, Point(24_000_000, 12_000_000)),
        "U1": ("top", 30_000_000, Point(38_000_000, 15_000_000)),
    }


@pytest.mark.kicad_min_major(10)
def test_counts(tmp_path: Path) -> None:
    board, files = written(tmp_path)
    stats = runner().export_stats(board, files=files)
    components = stats["components"]
    pads = stats["pads"]
    assert isinstance(components, dict) and isinstance(pads, dict)
    assert components["total"]["total"] == 3  # type: ignore[index]
    assert sum(int(n) for n in pads.values()) == _triad.pad_count(_triad.triad(10))  # type: ignore[arg-type]


def test_target_10_rejected_on_9(tmp_path: Path) -> None:
    if major() != 9:
        pytest.skip("the negative control runs on KiCad 9")
    board = tmp_path / "ten.kicad_pcb"
    board.write_text(triad_text(10), encoding="utf-8")
    args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", board.name]
    result = runner().run(args, files={board.name: board})
    assert result.returncode == 3
    assert run("pcb-write-triad-10") == "reject" and load(triad_text(10)) == "reject"
