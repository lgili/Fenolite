# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 custom sheet properties through actual strict import/build/proof (c0329)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _drawn_fonts
import pytest
from _fidelity import ALL_LEVELS, roundtrip, snapshot

from fenolite.backends.kicad import drawn as writer
from fenolite.backends.kicad.sexpr import dumps, parse


def authored(folder: Path, target: int = 10) -> Path:
    original = _drawn_fonts.styled_hierarchy(folder, target=target)
    path = original / "drawn_full.kicad_sch"
    root = parse(path.read_text(encoding="utf-8"))
    ref = root.nodes("sheet")[0]
    visible = parse("""(property "Field2" "AuthoredPropertyProbe"
        (at 5 5 0) (effects (font (size 2.54 1.8)) (justify left)))""")
    empty = parse('(property "EmptyMetadata" "" (at 5 10 0) (effects (font (size 1.27 1.27))))')
    hidden = parse("""(property "HiddenMetadata" "Authored hidden metadata" (at 5 15 0)
        (effects (font (size 1.27 1.27)) (hide yes)))""")
    if target == 10:
        effects = hidden.find("effects")
        assert effects is not None
        flag = effects.find("hide")
        assert flag is not None
        hidden = hidden.with_children(
            (
                hidden.children[0],
                hidden.children[1],
                hidden.find("at"),
                flag,
                effects.with_children(c for c in effects.children if c is not flag),
            )
        )
    changed = ref.with_children((*ref.children, visible, empty, hidden))
    path.write_text(
        dumps(root.with_children(changed if child is ref else child for child in root.children)),
        encoding="utf-8",
    )
    return original


def complete(reply) -> None:
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["differences"] == reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])
    assert reply.result["tolerances"]["length_nm"] == reply.result["tolerances"]["angle_udeg"] == 0
    assert reply.result["tolerances"]["pixel_ppm"] == 1000
    copper = next(row for row in reply.result["levels"] if row["level"] == 5)
    assert copper["summary"]["strict"]["tracks"]["matched"] == 1


@pytest.mark.parametrize("target", (9, 10))
def test_custom_properties_prove_all_nine_levels(target: int, tmp_path: Path) -> None:
    original = authored(tmp_path / "original", target)
    before = snapshot(original)
    complete(roundtrip(original, tmp_path / "proof"))
    assert snapshot(original) == before


@pytest.mark.parametrize("kind", ("drop", "text"))
def test_property_losses_fail_after_a_passing_all_level_control(
    kind: str, tmp_path: Path, monkeypatch
) -> None:
    original = authored(tmp_path / "original")
    before = snapshot(original)
    complete(roundtrip(original, tmp_path / "control"))
    lower = writer.lower_drawn

    def broken(value, *args, **kwargs):
        sheets = []
        for sheet in value.sheets:
            refs = []
            for ref in sheet.sheet_refs:
                properties = tuple(
                    dataclasses.replace(prop, text="DeliberatelyDifferentAuthoredProperty")
                    if prop.name == "Field2" and kind == "text"
                    else prop
                    for prop in ref.properties
                    if prop.name != "Field2" or kind != "drop"
                )
                refs.append(dataclasses.replace(ref, properties=properties))
            sheets.append(dataclasses.replace(sheet, sheet_refs=tuple(refs)))
        return lower(dataclasses.replace(value, sheets=tuple(sheets)), *args, **kwargs)

    monkeypatch.setattr(writer, "lower_drawn", broken)
    reply = roundtrip(original, tmp_path / "fault")
    assert reply.exit_code == 5 and reply.result["equivalent"] is False, (reply.error, reply.result)
    assert reply.result["accepted"] == []
    assert {row["level"]: row["status"] for row in reply.result["levels"]} == {
        **{level: "equal" for level in range(1, 8)},
        "S": "differs",
        8: "differs",
    }
    assert snapshot(original) == before
