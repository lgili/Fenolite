# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original small-field counterexample through strict reviewed import/full proof (c0326)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import _drawn_fonts
import pytest
from _fidelity import ALL_LEVELS, snapshot

from fenolite import api
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.lens.drawn import read_drawn
from fenolite.model.drawn import DrawnFont


def _args(original: Path, output: Path) -> tuple[str, ...]:
    return (
        str(next(original.glob("*.kicad_pro"))),
        "--to",
        "python",
        "--out",
        str(output),
        "--licence",
        "CC0-1.0",
        "--copyright",
        "2026 Fenolite contributors",
        "--source",
        "https://example.invalid/fenolite-authored-font-probe",
        "--revision",
        "authored-font-1",
    )


def test_small_field_font_roundtrips_all_nine_levels(tmp_path: Path) -> None:
    original = _drawn_fonts.original(tmp_path / "original")
    _roundtrip(original, tmp_path)


def _roundtrip(original: Path, tmp_path: Path) -> None:
    before = snapshot(original)
    output = _confirmed(original, tmp_path)
    reply = api.run(
        "verify-source", str(output / "design.py"), "--against", str(original), cwd=tmp_path, seed=0
    )
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["differences"] == reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"]), reply.result["levels"]
    routing = next(row for row in reply.result["levels"] if row["level"] == 5)
    assert routing["summary"]["strict"]["tracks"]["matched"] == 1
    assert snapshot(original) == before


def _confirmed(original: Path, tmp_path: Path) -> Path:
    output = tmp_path / "code"
    args = _args(original, output)
    dry = api.run("import", *args, "--dry-run", cwd=tmp_path, seed=0)
    assert dry.exit_code == 0, dry.error
    assert dry.result["unexpressed"] == []
    confirmed = api.run("import", *args, "--confirm", "--plan", dry.result["plan_id"], cwd=tmp_path, seed=0)
    assert confirmed.exit_code == 0, confirmed.error
    for item in dry.result["plan"]:
        path = Path(item["path"])
        path = path if path.is_absolute() else tmp_path / path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    return output


@pytest.mark.parametrize("target", (9, 10))
def test_every_text_surface_roundtrips_reviewed_import(target: int, tmp_path: Path) -> None:
    original = _drawn_fonts.styled_hierarchy(tmp_path / "original", target=target)
    _roundtrip(original, tmp_path)
    drawing = read_drawn((tmp_path / "code/schematic.toml").read_text(encoding="utf-8"))
    assert {label.kind for sheet in drawing.sheets for label in sheet.labels} == {
        "local",
        "global",
        "hierarchical",
    }
    assert all(label.font and label.justify == "" for sheet in drawing.sheets for label in sheet.labels)
    assert all(power.fields[0].font for sheet in drawing.sheets for power in sheet.powers)
    ref = drawing.sheets[0].sheet_refs[0]
    assert ref.pins and all(pin.font and pin.justify == "" for pin in ref.pins)
    assert {field.name for field in ref.fields} == {"Sheetname", "Sheetfile"}
    assert all(field.font for field in ref.fields)
    assert next(field for field in ref.fields if field.name == "Sheetfile").hide


@pytest.mark.parametrize("font", ("(font (size 0.25 0.25) future_effect)", "(font (size 0.000001 0.25))"))
def test_unsupported_field_effect_refuses_before_plan(font: str, tmp_path: Path) -> None:
    original = _drawn_fonts.original(tmp_path / "original", parse(font))
    before = snapshot(original)
    output = tmp_path / "code"
    reply = api.run("import", *_args(original, output), "--dry-run", cwd=tmp_path, seed=0)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004", reply.error
    assert "font" in reply.error["where"]
    assert not output.exists() and not reply.result.get("plan")
    assert snapshot(original) == before


def _native_text(folder: Path, surface: str, transform: Callable[[Node], Node]) -> None:
    """Change exactly one authored text node, retaining every unrelated source byte value."""
    path = next(folder.glob("*.kicad_pro")).with_suffix(".kicad_sch")
    root = parse(path.read_text(encoding="utf-8"))
    owner = root.nodes("sheet")[0] if surface == "pin" else root
    item = owner.nodes(surface)[0]
    changed = transform(item)
    replacement = owner.with_children(tuple(changed if child is item else child for child in owner.children))
    if owner is not root:
        replacement = root.with_children(
            tuple(replacement if child is owner else child for child in root.children)
        )
    path.write_text(dumps(replacement), encoding="utf-8")


def _bad_effect(item: Node, effect: str) -> Node:
    effects = item.find("effects")
    assert effects is not None
    changed = effects.with_children((*effects.children, parse(effect)))
    return item.with_children(tuple(changed if child is effects else child for child in item.children))


@pytest.mark.parametrize(
    ("surface", "effect"),
    (
        ("label", "(future_effect yes)"),
        ("global_label", "(hide yes)"),
        ("pin", "(hide yes)"),
        ("pin", "(future_effect yes)"),
    ),
)
def test_unrepresented_label_or_pin_effect_has_no_plan(surface: str, effect: str, tmp_path: Path) -> None:
    original = _drawn_fonts.styled_hierarchy(tmp_path / "original")
    _native_text(original, surface, lambda item: _bad_effect(item, effect))
    before = snapshot(original)
    output = tmp_path / "code"
    reply = api.run("import", *_args(original, output), "--dry-run", cwd=tmp_path, seed=0)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004", reply.error
    assert "label" in reply.error["where"] or "pin" in reply.error["where"]
    assert not output.exists() and not reply.result.get("plan")
    assert snapshot(original) == before


@pytest.mark.parametrize("surface", ("label", "pin"))
def test_source_style_edit_invalidates_reviewed_plan(surface: str, tmp_path: Path) -> None:
    original = _drawn_fonts.styled_hierarchy(tmp_path / "original")
    output = tmp_path / "code"
    args = _args(original, output)
    dry = api.run("import", *args, "--dry-run", cwd=tmp_path, seed=0)
    assert dry.exit_code == 0, dry.error
    _native_text(original, surface, lambda item: _bad_effect(item, "(future_effect yes)"))
    changed = snapshot(original)
    reply = api.run("import", *args, "--confirm", "--plan", dry.result["plan_id"], cwd=tmp_path, seed=0)
    assert reply.exit_code == 4 and reply.error and reply.error["code"] == "FEN-4002", reply.error
    assert not output.exists()
    assert snapshot(original) == changed


def test_independent_footprint_text_difference_stays_visible(tmp_path: Path) -> None:
    original = _drawn_fonts.original(tmp_path / "original", parse("(font (size 1.27 1.27))"))
    path = original / "font_probe.kicad_sch"
    root = parse(path.read_text(encoding="utf-8"))
    symbol = root.nodes("symbol")[0]
    prop = next(p for p in symbol.nodes("property") if p.atoms()[0].value == "Footprint")
    changed = prop.with_children((prop.children[0], Atom.string("VisibleAlias:Other"), *prop.children[2:]))
    changed_symbol = symbol.with_children(tuple(changed if c is prop else c for c in symbol.children))
    path.write_text(
        dumps(root.with_children(tuple(changed_symbol if c is symbol else c for c in root.children))),
        encoding="utf-8",
    )
    before = snapshot(original)
    output = tmp_path / "code"
    reply = api.run("import", *_args(original, output), "--dry-run", cwd=tmp_path, seed=0)
    # c0342 rejects contradictory physical identity rather than inventing a text override.
    assert reply.exit_code == 3 and reply.error is not None
    assert reply.error["code"] == "FEN-3004"
    assert reply.error["message"].startswith("R1.Footprint:")
    assert "Other" in reply.error["message"] and "Mini_R_0603" in reply.error["message"]
    assert not output.exists() and reply.envelope is not None
    assert not reply.envelope["result"].get("plan") and reply.envelope["receipt"] is None
    assert snapshot(original) == before


def test_root_filename_spelling_keeps_full_font_proof_equal(tmp_path: Path) -> None:
    original = _drawn_fonts.original(tmp_path / "original", parse("(font (size 1.27 1.27))"))
    for source in tuple(original.glob("font_probe.kicad_*")):
        source.rename(source.with_name(source.name.replace("font_probe", "font probe", 1)))
    _roundtrip(original, tmp_path)


@pytest.mark.parametrize(
    "font",
    (
        DrawnFont(bold=True),
        DrawnFont(italic=True),
        DrawnFont(face="Authored Sans"),
        DrawnFont(thickness=100_000),
    ),
)
def test_native_style_preservation_and_actual_renderer_boundary(font: DrawnFont, tmp_path: Path) -> None:
    original = _drawn_fonts.styled_hierarchy(tmp_path / "original", font=font)
    before = snapshot(original)
    output = _confirmed(original, tmp_path)
    drawing = read_drawn((output / "schematic.toml").read_text(encoding="utf-8"))
    assert all(label.font == font for sheet in drawing.sheets for label in sheet.labels)
    args = (str(output / "design.py"), "--against", str(original))
    native = api.run("verify-source", *args, "--levels", "1-7,S", cwd=tmp_path, seed=0)
    assert native.exit_code == 0, (native.error, native.result.get("differences"))
    assert native.result["differences"] == native.result["accepted"] == []
    assert all(row["status"] == "equal" for row in native.result["levels"])
    assert tuple(row["level"] for row in native.result["levels"]) == (*range(1, 8), "S")
    full = api.run("verify-source", *args, cwd=tmp_path, seed=0)
    if font.face is not None:
        assert full.exit_code == 3 and full.error and full.error["code"] == "FEN-3004", full.error
        assert "unsupported schematic rendering" in full.error["message"]
        assert not full.result.get("equivalent") and not full.result.get("accepted")
    else:
        assert full.exit_code == 0, (full.error, full.result.get("differences"))
        assert full.result["equivalent"] is True
        assert full.result["differences"] == full.result["accepted"] == []
        assert all(row["status"] == "equal" for row in full.result["levels"])
        assert tuple(row["level"] for row in full.result["levels"]) == (*range(1, 8), "S", 8)
    assert snapshot(original) == before
