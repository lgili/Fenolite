# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad panel board (capability kicad-file-backend, "Panel boards written"; change c0173)."""

from __future__ import annotations

import runpy
from collections import Counter
from pathlib import Path

import pytest
from _panels import PANELS, committed_board, script_for

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import edge_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.dsl import Panel, to_model
from fenolite.model.panel import Panel as ModelPanel
from fenolite.panel.build import PanelOutput, kicad_panel
from fenolite.panel.kicad import ORIGIN, PanelWriteError

MM = 1_000_000


def model_of(name: str) -> ModelPanel:
    panel = runpy.run_path(str(PANELS / f"{name}.py"))["panel"]
    assert isinstance(panel, Panel)
    return to_model(panel)


def written(name: str, major: int = 10, panel: ModelPanel | None = None) -> PanelOutput:
    return kicad_panel(panel or model_of(name), committed_board(major), target=major)


@pytest.mark.parametrize("major", [9, 10])
def test_panel_board_of_the_fixture(major: int) -> None:
    output = written("tabs", major)
    assert not output.refused, output.issues
    source = read_board(committed_board(major))
    design = read_board(output.files["tabs.kicad_pcb"].decode("utf-8"))
    assert design.board is not None and source.board is not None
    refs = Counter(design.by_id[fp.component_id].ref for fp in design.board.footprints)  # type: ignore[attr-defined]
    for fp in source.board.footprints:
        assert refs[source.by_id[fp.component_id].ref] == 8  # type: ignore[attr-defined]
    laid = output.layout
    rows = sum(len({h.x if t.axis == "y" else h.y for h in t.holes}) for t in laid.tabs)
    assert len(design.board.footprints) == 8 * len(source.board.footprints) + rows + 3 + 4
    names = [net.name for net in design.circuit.nets if net.name]
    assert names and all(name.split("/")[0] in {f"B{k}" for k in range(1, 9)} for name in names)
    assert len(names) == 8 * len([n for n in source.circuit.nets if n.name])
    outline = edge_outline(design)
    assert outline is not None
    assert len(outline.points) == 4 and len(outline.cutouts) == len(laid.gap_rings) > 0
    assert set(output.files) >= {
        "tabs.kicad_pcb", "tabs.kicad_pro", "tabs.panel.json", "fp-lib-table",
        "lib/Fenolite_Panel.pretty/MouseBites_5x0.6mm_P1mm.kicad_mod",
    }  # fmt: skip


def test_panel_fixture_rebuilds_to_the_same_bytes() -> None:
    assert written("tabs").files == written("tabs").files


def test_panel_fixture_uuids_are_distinct() -> None:
    import re

    text = written("tabs").files["tabs.kicad_pcb"].decode("utf-8")
    uuids = re.findall(r'\(uuid "([0-9a-f-]+)"\)', text)
    assert len(uuids) == len(set(uuids))


def test_panel_fixture_score_layer() -> None:
    output = written("mixed")
    text = output.files["mixed.kicad_pcb"].decode("utf-8")
    assert output.score_layer == "User.1" and '(39 "User.1" user "V-Score")' in text
    design = read_board(text)
    assert design.board is not None
    lines = [g for g in design.board.graphics if g.layer == "User.1"]
    assert len(lines) == len(output.layout.score_lines) == 3


def test_vscore_fixture_plans_nothing() -> None:
    output = written("vscore")
    assert output.refused and output.files == {}
    assert [i.code for i in output.issues if i.severity == "error"] == ["panel.vscore-copper"] * 2


def test_turned_copies_keep_their_pads(tmp_path: Path) -> None:
    """A quarter turn moves every pad exactly where ``PanelCopy.place`` puts its board point."""
    panel = Panel("turned", board="board_t10.kicad_pcb")
    panel.grid(1, 2, rot=90)
    model = to_model(panel)
    output = kicad_panel(model, committed_board(10), target=10)
    assert not output.refused, output.issues
    source = read_board(committed_board(10))
    design = read_board(output.files["turned.kicad_pcb"].decode("utf-8"))
    expected = sorted(
        (
            f"B{copy.k}/{p.net}" if p.net else "",
            copy.place(p.position).x + ORIGIN.x,
            copy.place(p.position).y + ORIGIN.y,
        )
        for copy in output.layout.copies
        for p in board_pads(source)
    )
    found = sorted(
        (p.net or "", p.position.x, p.position.y) for p in board_pads(design) if not p.ref.startswith("MB")
    )
    assert found == expected
    for copy in output.layout.copies:
        assert copy.place(Point(100 * MM, 100 * MM)) in {
            Point(x, y) for x, y in ((0, 40 * MM), (32 * MM, 40 * MM))
        }


def test_a_board_of_another_major() -> None:
    with pytest.raises(PanelWriteError, match="KiCad 9"):
        kicad_panel(model_of("tabs"), committed_board(9), target=10)


def test_script_copy_names_another_board(tmp_path: Path) -> None:
    script = script_for("tabs", tmp_path, committed_board(9))
    assert 'board="board_t9.kicad_pcb"' in script.read_text(encoding="utf-8")
    assert (tmp_path / "board_t9.kicad_pcb").is_file()


def test_project_holds_the_renamed_nets() -> None:
    import json

    from fenolite.panel.kicad import project_text

    source = {"net_settings": {"netclass_patterns": [{"netclass": "PWR", "pattern": "GND"}],
                               "netclass_assignments": {"VIN": "PWR"}}}  # fmt: skip
    data = json.loads(project_text(json.dumps(source), "p", 2, lambda: "{}"))
    assert data["meta"]["filename"] == "p.kicad_pro"
    assert data["net_settings"]["netclass_patterns"] == [{"netclass": "PWR", "pattern": "B*/GND"}]
    assert data["net_settings"]["netclass_assignments"] == {"B1/VIN": "PWR", "B2/VIN": "PWR"}
    assert project_text(None, "p", 2, lambda: "made\n") == "made\n"
