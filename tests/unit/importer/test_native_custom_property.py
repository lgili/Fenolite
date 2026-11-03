# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native-owned fields outside the printable Part.properties contract (c0358)."""

from pathlib import Path

import pytest
from _custom_fields import original

from fenolite import api
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.dsl import DslError, Part


@pytest.mark.parametrize("target", [9, 10])
def test_native_multiline_property_survives_import(tmp_path: Path, target: int):
    source = original(tmp_path / "original", 180, target)
    board = source.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    (footprint,) = root.nodes("footprint")
    prop = next(p for p in footprint.nodes("property") if p.atoms()[0].value == "Author")
    value = "First authored line\nSecond authored line"
    atoms = prop.atoms()
    changed = prop.with_children((atoms[0], Atom.string(value), *prop.children[2:]))
    changed_fp = footprint.with_children(tuple(changed if c is prop else c for c in footprint.children))
    board.write_text(
        dumps(root.with_children(tuple(changed_fp if c is footprint else c for c in root.children)))
    )
    before = board.read_bytes()
    args = (
        "import",
        str(source),
        "--to",
        "python",
        "--out",
        "code",
        "--licence",
        "CC0-1.0",
        "--kicad-version",
        str(target),
    )
    planned = api.run(*args, "--dry-run", cwd=tmp_path)
    assert planned.exit_code == 0, planned.error
    confirmed = api.run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path)
    assert confirmed.exit_code == 0, confirmed.error
    proof = api.run(
        "verify-source",
        "code/design.py",
        "--against",
        str(source),
        "--levels",
        "1,2,3,4,5,6,7",
        "--kicad-version",
        str(target),
        cwd=tmp_path,
    )
    assert proof.exit_code == 0, proof.result.get("differences")
    assert proof.result["differences"] == [] and proof.result["accepted"] == []
    assert all(row["status"] == "equal" for row in proof.result["levels"])
    assert board.read_bytes() == before
    assert any('property "Author"' in p.read_text() for p in (tmp_path / "code/lib").rglob("*.kicad_mod"))


@pytest.mark.parametrize("value", ["A\nB", "A\tB", "A\x00B", "A\rB"])
def test_public_properties_still_refuse_control_characters(value: str):
    with pytest.raises(DslError, match="non-printable"):
        Part("R1", "Mini:Mini_R", properties={"Author": value})


def test_native_owned_property_variants_and_unsupported_controls():
    from fenolite.core.errors import FormatError
    from fenolite.importer.vendor import library_footprint

    def footprint(value: str):
        return parse(
            '(footprint "Authored" '
            + dumps(parse('(property "Reference" "R1")'))
            + " "
            + dumps(parse('(property "Value" "R")'))
            + ' (property "Author" '
            + dumps(Atom.string(value))
            + ' (at 1 2 0) (layer "F.Fab") (effects (font (size 1 1)))))'
        )

    first = footprint("A\nB")
    other = footprint("A\nC")
    assert library_footprint(first) == first
    assert library_footprint(other) == other
    assert library_footprint(first) != library_footprint(other)
    printable = footprint("A B")
    assert all(p.atoms()[0].value != "Author" for p in library_footprint(printable).nodes("property"))
    for text in ("A\tB", "A\rB"):
        with pytest.raises(FormatError, match="unsupported native custom property"):
            library_footprint(footprint(text))
    with pytest.raises(ValueError, match="NUL"):
        footprint("A\x00B")
    duplicate = first.with_children((*first.children, first.nodes("property")[-1]))
    with pytest.raises(FormatError, match="unsupported native custom property"):
        library_footprint(duplicate)


def test_distinct_native_owned_properties_get_separate_variants(tmp_path: Path):
    from _importcode import copy_project

    source = copy_project(tmp_path)
    board = source.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    changed = {}
    for fp in root.nodes("footprint"):
        ref = next(p.atoms()[1].value for p in fp.nodes("property") if p.atoms()[0].value == "Reference")
        if ref in {"R101", "R201"}:
            prop = parse(
                '(property "Author" '
                + dumps(Atom.string(ref + "\nDistinct authored value"))
                + ' (at 1 2 0) (layer "F.Fab") (hide yes)'
                + " (effects (font (size 1 1) (thickness 0.15))))"
            )
            changed[id(fp)] = fp.with_children((*fp.children, prop))
    assert len(changed) == 2
    board.write_text(dumps(root.with_children(tuple(changed.get(id(c), c) for c in root.children))))
    args = ("import", str(source), "--to", "python", "--out", "code", "--licence", "CC0-1.0")
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    reply = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert reply.exit_code == 0, reply.error
    definitions = [p.read_text() for p in (tmp_path / "code/lib").rglob("*.kicad_mod")]
    for ref in ("R101", "R201"):
        assert sum(ref + "\\nDistinct authored value" in text for text in definitions) == 1
    proof = api.run(
        "verify-source",
        "code/design.py",
        "--against",
        str(source),
        "--levels",
        "1,2,3,4,5,6,7",
        cwd=tmp_path,
    )
    assert proof.exit_code == 0, proof.result.get("differences")
    assert proof.result["accepted"] == [] and proof.result["differences"] == []


@pytest.mark.parametrize("value", ["A\tB", "A\rB"])
def test_native_unmeasured_control_refuses_before_plan(tmp_path: Path, value: str):
    source = original(tmp_path / "original", 180, 10)
    board = source.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    (fp,) = root.nodes("footprint")
    prop = next(p for p in fp.nodes("property") if p.atoms()[0].value == "Author")
    changed = prop.with_children((prop.atoms()[0], Atom.string(value), *prop.children[2:]))
    replacement = fp.with_children(tuple(changed if c is prop else c for c in fp.children))
    board.write_text(dumps(root.with_children(tuple(replacement if c is fp else c for c in root.children))))
    before = board.read_bytes()
    reply = api.run("import", str(source), "--to", "python", "--out", "refused", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004"
    assert "Author" in reply.error.get("where", "")
    assert not reply.result.get("plan") and not (tmp_path / "refused").exists()
    assert board.read_bytes() == before
