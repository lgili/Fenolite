# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0342: source-instance footprint aliases bind exact board geometry, never arbitrary text."""

from __future__ import annotations

from pathlib import Path

import pytest
from _footprint_alias import alias_project
from _importcode import build, copy_project, imported
from _projects import tree_snapshot

from fenolite.api import read_board, run
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse


@pytest.mark.parametrize("target", [9, 10])
def test_visible_source_alias_is_preserved_with_local_exact_geometry(tmp_path: Path, target: int) -> None:
    source = alias_project(tmp_path, native_target=target)
    reply = imported(tmp_path, source, "--confirm", "--kicad-version", str(target))
    assert reply.exit_code == 0, reply.error
    out = tmp_path / "out"
    assert 'footprint="Original:Mini_LED_THT_3mm"' in (out / "design.py").read_text()
    assert (out / "lib/Original.pretty/Mini_LED_THT_3mm.kicad_mod").is_file()
    uri = (
        '(uri "${KIPRJMOD}/lib/Original.pretty")' if target == 10 else "(uri ${KIPRJMOD}/lib/Original.pretty)"
    )
    assert uri in (out / "fp-lib-table").read_text()
    made = build(out, "--kicad-version", str(target))
    assert made.exit_code == 0, made.error
    original = read_board(source.with_suffix(".kicad_pcb")).design
    rebuilt = read_board(out / "built/two_sheet.kicad_pcb").design
    assert original.board is not None and rebuilt.board is not None
    originals = {c.id: c.ref for c in original.circuit.components}
    rebuilt_refs = {c.id: c.ref for c in rebuilt.circuit.components}
    first = next(fp for fp in original.board.footprints if originals[fp.component_id] == "J1")
    second = next(fp for fp in rebuilt.board.footprints if rebuilt_refs[fp.component_id] == "J1")
    assert first.native_ids == second.native_ids
    assert (first.position, first.rotation, first.side) == (second.position, second.rotation, second.side)
    assert [(p.number, p.position, p.size, p.layers, p.native_ids) for p in first.pads] == [
        (p.number, p.position, p.size, p.layers, p.native_ids) for p in second.pads
    ]
    proof = run(
        "verify-source", str(out / "design.py"), "--against", str(source), "--levels", "3,S,8", cwd=tmp_path
    )
    assert proof.exit_code == 0, proof.error
    assert proof.envelope is not None
    assert proof.envelope["result"]["differences"] == [] and proof.envelope["result"]["accepted"] == []
    assert {str(row["level"]): row["status"] for row in proof.envelope["result"]["levels"]} == {
        "3": "equal",
        "S": "equal",
        "8": "equal",
    }


@pytest.mark.parametrize(
    "alias", ["Original:DifferentName", "../bad:Mini_LED_THT_3mm", "CON:Mini_LED_THT_3mm"]
)
def test_incompatible_or_unsafe_alias_refuses_before_staging(tmp_path: Path, alias: str) -> None:
    source = alias_project(tmp_path, alias)
    snapshot = tree_snapshot(source.parent)
    reply = imported(tmp_path, source, "--dry-run")
    assert reply.exit_code == 3, reply.error
    assert not (tmp_path / "out").exists()
    assert tree_snapshot(source.parent) == snapshot
    assert reply.envelope is not None and not reply.envelope["result"].get("plan")


@pytest.mark.parametrize("same_lookup", [False, True])
def test_source_alias_keeps_exact_variants_but_refuses_lookup_collision(
    tmp_path: Path, same_lookup: bool
) -> None:
    source = copy_project(tmp_path)
    for path in (source.parent / "sheets").glob("*.kicad_sch"):
        path.write_text(path.read_text().replace('"Mini:Mini_R_0603"', '"Original:Mini_R_0603"'))
    board = source.with_suffix(".kicad_pcb")
    text = board.read_text()
    start = text.index('"R201"')
    pad = text.index('(pad "1"', start)
    position = text.index("(at -0.8 0 180)", pad)
    board.write_text(text[:position] + "(at -0.9 0 180)" + text[position + len("(at -0.8 0 180)") :])
    if same_lookup:
        parsed = parse(board.read_text())
        nodes = []
        for child in parsed.children:
            if isinstance(child, Node) and child.name == "footprint":
                props = {p.atoms()[0].value: p.atoms()[1].value for p in child.nodes("property")}
                if props.get("Reference") == "R201":
                    child = child.with_children((Atom.string("OtherBoard:Mini_R_0603"), *child.children[1:]))
            nodes.append(child)
        board.write_text(dumps(parsed.with_children(nodes)))
    snapshot = tree_snapshot(source.parent)
    reply = imported(tmp_path, source, "--dry-run")
    assert tree_snapshot(source.parent) == snapshot
    if same_lookup:
        assert reply.exit_code == 3, reply.error
        assert reply.error is not None and "incompatible board geometry" in reply.error["message"]
        assert not (tmp_path / "out").exists()
        return
    assert reply.exit_code == 0, reply.error
    confirmed = imported(tmp_path, source, "--confirm")
    assert confirmed.exit_code == 0, confirmed.error
    script = tmp_path / "out/design.py"
    code = "\n".join(path.read_text() for path in (tmp_path / "out").rglob("*.py"))
    assert 'footprint="Original:Mini_R_0603"' in code
    assert 'footprint_definition="Original:Mini_R_0603_2"' in code
    proof = run("verify-source", str(script), "--against", str(source), "--levels", "3,S,8", cwd=tmp_path)
    assert proof.exit_code == 0, proof.error
    assert proof.envelope is not None and proof.envelope["result"]["differences"] == []


def test_no_source_alias_does_not_invent_one(tmp_path: Path) -> None:
    source = alias_project(tmp_path, "")
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert 'footprint="Mini:Mini_LED_THT_3mm"' in (tmp_path / "out/design.py").read_text()
    assert not (tmp_path / "out/lib/Original.pretty").exists()


def test_conflicting_native_use_bindings_are_not_resolved_by_approximate_names(tmp_path: Path) -> None:
    from dataclasses import replace

    from fenolite.core.errors import FormatError
    from fenolite.core.ids import derived_id
    from fenolite.importer.source import read_kicad
    from fenolite.importer.vendor import source_footprints

    source = read_kicad(alias_project(tmp_path))
    root_file = next(iter(source.hierarchy))
    sheet = source.hierarchy[root_file]
    native = next(s for s in sheet.symbols if s.ref == "J1")
    conflict = replace(
        native,
        id=derived_id("sci", "authored", "conflicting-unit"),
        unit=2,
        footprint="Other:Mini_LED_THT_3mm",
    )
    ambiguous = replace(
        source, hierarchy={**source.hierarchy, root_file: replace(sheet, symbols=(*sheet.symbols, conflict))}
    )
    with pytest.raises(FormatError, match="conflicting footprint aliases"):
        source_footprints(ambiguous)


def test_default_import_still_only_prepares_a_reviewable_plan(tmp_path: Path) -> None:
    source = alias_project(tmp_path)
    before = tree_snapshot(source.parent)
    reply = run("import", str(source), "--to", "python", "--out", "out", cwd=tmp_path)
    assert reply.exit_code == 4 and reply.envelope is not None
    assert reply.envelope["receipt"] is None and not (tmp_path / "out").exists()
    assert tree_snapshot(source.parent) == before
    assert any(
        "lib/Original.pretty/Mini_LED_THT_3mm.kicad_mod" in row["path"]
        for row in reply.envelope["result"]["plan"]
    )
