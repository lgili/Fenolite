# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored RED: TAB value support requires explicit native ownership (c0363)."""

from pathlib import Path

import pytest
from _native_custom import tab_project

from fenolite import api
from fenolite.backends.kicad.sexpr import Atom, dumps, parse
from fenolite.dsl import DslError, Part
from fenolite.importer.vendor import library_footprint


@pytest.mark.parametrize("value", ["First\tauthored", "First\tauthored\nSecond\tline"])
def test_native_tab_value_is_retained_exactly(value: str):
    node = parse(
        '(footprint "Authored" (property "Author" '
        + dumps(Atom.string(value))
        + ' (at 1 2 0) (layer "F.Fab") (hide yes) '
        + "(effects (font (size 1 1) (thickness 0.15)))))"
    )
    assert library_footprint(node) == node


@pytest.mark.parametrize("value", ["A\tB", "A\nB", "A\tB\nC"])
def test_public_properties_still_refuse_tabs_and_lines(value: str):
    with pytest.raises(DslError):
        Part("R1", "Mini:Mini_R", properties={"Author": value})


@pytest.mark.parametrize("control", ["\r", "\x01", "\x0b", "\x0c", "\x7f"])
def test_native_tab_does_not_admit_other_controls(control: str):
    from fenolite.core.errors import FormatError

    native = parse(
        '(footprint "Authored" (property "Author" ' + dumps(Atom.string("A\tB" + control + "C")) + "))"
    )
    with pytest.raises(FormatError, match="unsupported native custom property text"):
        library_footprint(native)


@pytest.mark.parametrize("name", ["A\tB", "fenolite.custom", "ki_custom"])
def test_native_tab_does_not_admit_unsupported_names(name: str):
    from fenolite.core.errors import FormatError

    native = parse('(footprint "Authored" (property ' + dumps(Atom.string(name)) + ' "A\\tB"))')
    with pytest.raises(FormatError, match="unsupported native custom property text"):
        library_footprint(native)


@pytest.mark.parametrize("defect", ["size", "thickness", "layer", "font", "justify", "duplicate-name"])
def test_tab_profile_validates_pose_and_font_before_plan(tmp_path: Path, defect: str):
    source = tab_project(tmp_path / "source", 10, "top", 180, True, True)
    board = source.with_suffix(".kicad_pcb")
    tree = parse(board.read_text())
    (fp,) = tree.nodes("footprint")
    prop = next(p for p in fp.nodes("property") if p.atoms()[0].value == "Author")
    if defect == "duplicate-name":
        changed = fp.with_children((*fp.children, prop))
    else:
        a, b = {
            "size": ("(size 1 1)", "(size 1 2)"),
            "thickness": ("(thickness 0.15)", ""),
            "layer": ('(layer "F.Fab")', '(layer "User.Drawings")'),
            "font": ("(thickness 0.15)", "(thickness 0.15) (future_style yes)"),
            "justify": ("right bottom mirror", "right bottom mirror unknown"),
        }[defect]
        assert a in dumps(prop)
        replacement = parse(dumps(prop).replace(a, b))
        changed = fp.with_children(tuple(replacement if c is prop else c for c in fp.children))
    board.write_text(dumps(tree.with_children(tuple(changed if c is fp else c for c in tree.children))))
    before = board.read_bytes()
    reply = api.run("import", str(source), "--to", "python", "--out", "refused", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004"
    assert not reply.result.get("plan") and not (tmp_path / "refused").exists()
    assert board.read_bytes() == before


def test_native_tab_variants_and_printable_value_conflict(tmp_path: Path):
    import ast

    from _importcode import copy_project

    source = copy_project(tmp_path)
    board = source.with_suffix(".kicad_pcb")
    tree = parse(board.read_text())
    changed = {}
    expected = {ref: ref + "\tauthored\nCC0" for ref in ("R101", "R201")}
    for fp in tree.nodes("footprint"):
        ref = next(p.atoms()[1].value for p in fp.nodes("property") if p.atoms()[0].value == "Reference")
        if ref in expected:
            prop = parse(
                '(property "Author" '
                + dumps(Atom.string(expected[ref]))
                + ' (at 1 2 0) (layer "F.Fab") (hide yes) '
                + "(effects (font (size 1 1) (thickness 0.15))))"
            )
            changed[id(fp)] = fp.with_children((*fp.children, prop))
    assert len(changed) == 2
    board.write_text(dumps(tree.with_children(tuple(changed.get(id(c), c) for c in tree.children))))
    args = ("import", str(source), "--to", "python", "--out", "code", "--licence", "CC0-1.0")
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    write = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert write.exit_code == 0, write.error
    native_values = []
    for path in (tmp_path / "code/lib").rglob("*.kicad_mod"):
        native_values.extend(
            p.atoms()[1].value
            for p in parse(path.read_text()).nodes("property")
            if p.atoms()[0].value == "Author"
        )
    for value in expected.values():
        assert native_values.count(value) == 1
    assert len(native_values) == 2
    proof = api.run(
        "verify-source", "code/design.py", "--against", str(source), "--levels", "1,2,3,4,5,6,7", cwd=tmp_path
    )
    assert proof.exit_code == 0 and proof.result["differences"] == [] and proof.result["accepted"] == []
    edited = 0
    for path in (tmp_path / "code").rglob("*.py"):
        script = ast.parse(path.read_text())
        hit = False
        for node in ast.walk(script):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Part"
                and node.args
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Attribute)
                and node.args[0].func.attr == "get"
                and isinstance(node.args[0].args[-1], ast.Constant)
                and node.args[0].args[-1].value == "R101"
            ):
                assert not any(k.arg == "properties" for k in node.keywords)
                node.keywords.append(
                    ast.keyword(
                        arg="properties",
                        value=ast.Dict(
                            keys=[ast.Constant("Author")], values=[ast.Constant("Altered printable value")]
                        ),
                    )
                )
                hit = True
                edited += 1
        if hit:
            path.write_text(ast.unparse(ast.fix_missing_locations(script)) + "\n")
    assert edited == 1
    conflict = api.run("build", "code/design.py", "--out", "conflict", "--dry-run", cwd=tmp_path)
    assert conflict.exit_code == 5, conflict.error
    assert any(row["code"] == "build.property-conflict" for row in conflict.envelope["issues"])
    assert not conflict.result.get("plan")


@pytest.mark.parametrize(
    "extra",
    [
        "future_atom",
        "(future_property yes)",
        "(unlocked unknown)",
        "(hide unknown)",
        '(uuid "one") (uuid "two")',
    ],
)
def test_tab_native_malformed_or_unknown_shape_refuses(extra: str):
    from fenolite.core.errors import FormatError

    native = parse('(footprint "Authored" (property "Author" "A\\tB" ' + extra + "))")
    with pytest.raises(FormatError, match="unsupported native TAB property"):
        library_footprint(native)


@pytest.mark.parametrize("defect", ["missing-pose"])
def test_tab_requires_measured_source_and_single_pose(tmp_path: Path, defect: str):
    from dataclasses import replace

    from fenolite.core.errors import FormatError
    from fenolite.importer.emit import Options, emit
    from fenolite.importer.provenance import Provenance
    from fenolite.importer.source import read_kicad

    path = tab_project(tmp_path / "source", 10, "top", 180, True, True)
    source = read_kicad(path)
    if defect == "source-backend":
        source = replace(source, backend="altium")
    else:
        assert source.design.board is not None
        (fp,) = source.design.board.footprints
        fp = replace(fp, fields=tuple(field for field in fp.fields if field.name != "Author"))
        source = replace(
            source, design=replace(source.design, board=replace(source.design.board, footprints=(fp,)))
        )
    with pytest.raises(FormatError, match="native TAB"):
        emit(source, Options(source.name, Provenance(licence="CC0-1.0"), target=10))


def test_tab_of_another_backend_is_a_declared_loss(tmp_path: Path):
    """change c0379: a TAB value read from a non-KiCad source no longer refuses the whole import."""
    from dataclasses import replace

    from fenolite.importer.emit import Options, emit
    from fenolite.importer.provenance import Provenance
    from fenolite.importer.source import read_kicad

    source = replace(
        read_kicad(tab_project(tmp_path / "source", 10, "top", 180, True, True)), backend="altium"
    )
    emission = emit(source, Options(source.name, Provenance(licence="CC0-1.0"), target=10))
    lost = {row.kind: row for row in emission.unexpressed}
    assert lost["property-tab"].count == 1 and lost["property-tab"].examples[0].endswith(":Author")
    code = "".join(data.decode("utf-8") for name, data in emission.files.items() if name.endswith(".py"))
    assert "\t" not in code and "Author" not in code
