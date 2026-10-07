# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The filled fan-out fixtures follow the build and the route (capability kicad-oracle, "Plane routing passes
the oracle", fan-out; hypothesis H-K-FANOUT; change c0107).

``tests/data/kicad/routing/planebench_t9_<before|after>_filled.kicad_pcb`` are the target-9 plane bench as
built and as routed by ``fenolite route --router direct`` on its two plane nets, each filled by KiCad 10.0.6,
which KiCad 9.0.9 judges because it cannot refill zones. Each fixture must equal the board of this tree
except for the fills and the ``filled`` flag of its zones, so a change of the build or of the fan-out cannot
leave a stale fixture. No ``kicad-cli`` runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fenolite.backends.kicad.pcb import read_board

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kicad" / "board"))

import _planebench as pb  # noqa: E402
import _planecases as pc  # noqa: E402

ORACLE = "tests/kicad/routing/test_fanout_oracle.py"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def board_text(tmp_path: Path, label: str) -> str:
    board, _result, findings = pc.fanout_board(tmp_path / label, label, 9)
    assert findings == ()
    return board.read_text(encoding="utf-8")


@pytest.mark.parametrize("label", pc.FANOUT_LABELS)
def test_fixtures_follow_the_build_and_the_route(tmp_path: Path, label: str) -> None:
    path = pc.fanout_fixture(label)
    assert path.is_file(), f"{path.name} is missing: run {ORACLE} on KiCad 10"
    text = path.read_text(encoding="utf-8")
    fixture = read_board(text)
    assert fixture.board is not None
    assert [(zone.filled, len(zone.fills)) for zone in fixture.board.zones] == [(True, 1), (True, 1)]
    assert len(fixture.board.vias) == (len(pb.PLANE_PADS) if label == "after" else 0)
    assert pc.unfilled_text(text) == board_text(tmp_path, label), (
        f"{path.name} differs from the target-9 board of this tree: write it again with "
        f"FENOLITE_PROBES_WRITE=1 on KiCad 10 ({ORACLE})"
    )


def test_another_board_is_noticed(tmp_path: Path) -> None:
    """The comparison fails when the tree gives another board: here the fixture of the routed bench against
    the bench as built, and a fixture against its own text (the fills are left out)."""
    after = pc.fanout_fixture("after").read_text(encoding="utf-8")
    assert pc.unfilled_text(after) != board_text(tmp_path, "before")
    assert pc.unfilled_text(after) != after
