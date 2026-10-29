# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite import`` (capability board-to-code, "Import to code" and "Import inputs"; capability
cli-contract, "Import command"; change c0275)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from _importcode import STAMP, board_only, build, built_board, copy_project, imported

from fenolite.api import run

PLANNED = ("design.py", "copper.py", "design.lock", "fp-lib-table", "sym-lib-table", "PROVENANCE.json")


def test_plan_of_an_authored_board(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    reply = imported(tmp_path, project, "--json")
    assert reply.exit_code == 0, reply.error
    planned = [row["path"] for row in reply.result["plan"]]
    for name in PLANNED:
        assert f"out/{name}" in planned
    assert any(path.startswith("out/lib/") for path in planned)
    assert not (tmp_path / "out").exists()
    assert reply.envelope is not None and reply.envelope["schema"] == "fenolite.import.v0"


def test_confirmed_import(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    dry = imported(tmp_path, project)
    assert dry.exit_code == 0, dry.error
    reply = imported(tmp_path, project, "--confirm", "--plan", dry.result["plan_id"])
    assert reply.exit_code == 0, reply.error
    receipt = (reply.envelope or {})["receipt"]
    written = {row["path"]: row["sha256"] for row in receipt["written"]}
    on_disk = {
        f"out/{p.relative_to(tmp_path / 'out').as_posix()}": hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (tmp_path / "out").rglob("*")
        if p.is_file()
    }
    assert written == on_disk


def test_plan_id_binds_the_inputs(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    dry = imported(tmp_path, project)
    assert dry.exit_code == 0, dry.error
    sheet = project.parent / "sheets" / "ch1.kicad_sch"
    sheet.write_text(sheet.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    reply = imported(tmp_path, project, "--confirm", "--plan", dry.result["plan_id"])
    assert reply.exit_code == 4
    assert reply.error is not None and reply.error["code"] == "FEN-4002"
    assert not (tmp_path / "out").exists()


def test_eagle_board_refused(tmp_path: Path) -> None:
    (tmp_path / "board.brd").write_text("<eagle/>\n", encoding="utf-8")
    reply = imported(tmp_path, "board.brd")
    assert reply.exit_code == 2
    assert reply.error is not None and reply.error["code"] == "FEN-2001"
    assert "Eagle" in reply.error["message"]


def test_output_over_the_source_refused(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    for out in ("src", "."):
        reply = imported(tmp_path, project, out=out)
        assert reply.exit_code == 2, out
        assert reply.error is not None and reply.error["code"] == "FEN-2001"


def test_board_without_a_schematic(tmp_path: Path) -> None:
    source = board_only(tmp_path)
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert build(tmp_path / "out").exit_code == 0
    built = built_board(tmp_path / "out", "board_only").design
    original = built_board(tmp_path / "out", "board_only")  # the built board, read with its pads
    assert original.design is not None

    def pads(design: object) -> set[tuple[str, str, str, str]]:
        from fenolite.model.design import Design

        assert isinstance(design, Design) and design.board is not None
        refs = {c.id: c.ref for c in design.circuit.components}
        names = {n.id: n.name for n in design.circuit.nets}
        return {
            (refs[fp.component_id], fp.lib_ref.split(":")[-1], pad.number, names.get(pad.net_id or "", ""))
            for fp in design.board.footprints
            for pad in fp.pads
            if not names.get(pad.net_id or "", "").startswith("unconnected-(")
        }

    from fenolite.api import read_board

    assert pads(built) == pads(read_board(source).design)


def test_import_needs_a_target(tmp_path: Path) -> None:
    reply = run("import", "x.kicad_pcb", "--out", "out", cwd=tmp_path, timestamp=STAMP)
    assert reply.exit_code == 2
