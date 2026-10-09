# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The capability resolver of the KiCad downgrade (change c0162; capability kicad-version-gating,
"Downgrade resolver", "Downgrade resolver closure", "Downgrade edits" and "Downgrade consent")."""

from __future__ import annotations

import re
from importlib import resources

import pytest

from fenolite.backends.kicad import resolver
from fenolite.backends.kicad.pro import TEN_ONLY_PATHS
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import FileKind, LossyWriteError, check_emittable, load_inventory
from fenolite.core.errors import FormatError

TEXT = resources.files("fenolite.backends.kicad").joinpath("data/downgrade.toml").read_text(encoding="utf-8")


def _without(row_id: str) -> str:
    """The table text without the row ``row_id``."""
    blocks = TEXT.split("[[row]]\n")
    kept = [b for b in blocks if not b.startswith(f'id = "{row_id}"\n')]
    assert len(kept) == len(blocks) - 1, row_id
    return "[[row]]\n".join(kept)


# --- the table and its closure ------------------------------------------------------------------------


def test_table_is_closed() -> None:
    """Scenario "Table is closed": one row per too-new token and form row and per ten-only project path."""
    table = resolver.load()
    inventory = load_inventory()
    expected = {r.id for r in inventory.tokens if r.since_major == 10}
    expected |= {r.id for r in inventory.forms if r.since_major == 10}
    expected |= {f"project:{path}" for path in TEN_ONLY_PATHS} | {resolver.PROJECT_VERSION_ROW}
    assert set(table.rows) == expected
    assert len(table.rows) == 63 + 1 + 11 + 1
    assert {row.target for row in table.rows.values()} == {9}


@pytest.mark.parametrize("row_id", ["capping", "net-by-name", "project:/tuning_profiles"])
def test_closed_missing_row_fails(row_id: str) -> None:
    with pytest.raises(FormatError, match=re.escape(row_id)):
        resolver.parse_table(_without(row_id))


def test_closed_unknown_and_repeated_ids_fail() -> None:
    extra = '\n[[row]]\nid = "fenolite-invented"\ntarget = 9\naction = "design"\n'
    with pytest.raises(FormatError, match="fenolite-invented"):
        resolver.parse_table(TEXT + extra)
    again = '\n[[row]]\nid = "capping"\ntarget = 9\naction = "design"\n'
    with pytest.raises(FormatError, match="row capping: duplicate id"):
        resolver.parse_table(TEXT + again)


def test_closed_incomplete_rewrite_fails() -> None:
    broken = TEXT.replace('form = "(island)"\n', "")
    with pytest.raises(FormatError, match="row island-yes: a rewrite needs its form and its sources"):
        resolver.parse_table(broken)
    unknown = TEXT.replace('id = "point"\ntarget = 9\naction = "presentation"', 'id = "point"\ntarget = 9\n'
                           'action = "rewrite"\nform = "(x)"')  # fmt: skip
    with pytest.raises(FormatError, match="row point: no rewriter is registered"):
        resolver.parse_table(unknown)


def test_closed_condition_needs_else() -> None:
    broken = TEXT.replace('when = ["no", "none"]\nelse = "design"\n', 'when = ["no", "none"]\n', 1)
    with pytest.raises(FormatError, match="when needs an else action"):
        resolver.parse_table(broken)


def test_closed_rewriters_match_the_rewrite_rows() -> None:
    table = resolver.load()
    rewrites = {
        r.id
        for r in table.rows.values()
        if r.action == "rewrite" and not r.id.startswith("project:") and r.id != "net-by-name"
    }
    assert rewrites == set(resolver.REWRITERS)


def test_decisions_by_value() -> None:
    table = resolver.load()
    assert table.row("capping").decide(["no"]) == "same"
    assert table.row("capping").decide(["none"]) == "same"
    assert table.row("capping").decide(["yes"]) == "design"
    jumpers = table.row("footprint-duplicate-pad-numbers-are-jumpers")
    assert (jumpers.decide(["no"]), jumpers.decide(["yes"])) == ("same", "design")
    pos = table.row("sch-symbol-in-pos-files")
    assert (pos.decide(["yes"]), pos.decide(["no"])) == ("same", "design")
    assert table.row("point").loss == "report"
    assert table.row("capping").loss == "refuse"
    assert table.row("island-no").loss is None


def test_maintainer_decisions() -> None:
    """Open questions 2 and 3 of the design: a dropped via protection value and a dropped position-file flag
    are design losses unless they are the default."""
    table = resolver.load()
    for row_id in ("covering", "plugging", "capping", "filling"):
        row = table.row(row_id)
        assert (row.action, row.when, row.otherwise) == ("same", ("no", "none"), "design"), row_id
    for row_id in ("sch-symbol-in-pos-files", "sch-lib-in-pos-files", "sym-in-pos-files"):
        row = table.row(row_id)
        assert (row.action, row.when, row.otherwise) == ("same", ("yes",), "design"), row_id


# --- edits at the node --------------------------------------------------------------------------------

BOARD = """(kicad_pcb (version 20241229) (generator "fenolite") (generator_version "9.0")
  (setup (pad_to_mask_clearance 0)
    (tenting (front yes) (back yes)) (covering (front no) (back no)) (capping no)
    (pcbplotparams (layerselection 0x00010fc_ffffffff)))
  (footprint "x:y" (layer "F.Cu") (duplicate_pad_numbers_are_jumpers no)
    (units (unit (name "A") (pins "1")))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (tenting (front none) (back none)))
    (pad "2" smd rect (at 2 0) (size 1 1) (layers "F.Cu") (tenting (front yes) (back none))))
  (via (at 1 1) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (capping yes))
)"""


def _resolved(text: str, *, allow_lossy: bool = True) -> resolver.Resolution:
    return resolver.resolve(parse(text), FileKind.BOARD, 9, allow_lossy=allow_lossy)


def test_edits_at_the_node() -> None:
    """Scenario "Setup kept" in small: ``setup`` stays, each construct is edited where it is."""
    found = _resolved(BOARD)
    text = found.root
    setup = text.find("setup")
    assert setup is not None
    assert [c.name for c in setup.nodes()] == ["pad_to_mask_clearance", "tenting", "pcbplotparams"]
    tenting = setup.find("tenting")
    assert tenting is not None and [a.text for a in tenting.atoms()] == ["front", "back"]
    footprint = text.find("footprint")
    assert footprint is not None
    assert footprint.find("duplicate_pad_numbers_are_jumpers") is None and footprint.find("units") is None
    pads = footprint.nodes("pad")
    assert pads[0].find("tenting") is None
    second = pads[1].find("tenting")
    assert second is not None and [a.text for a in second.atoms()] == ["front"]
    assert not [
        i for i in check_emittable(text, FileKind.BOARD, 9) if i.severity == "error" and "token" in i.code
    ]
    assert dict(found.counts) == {
        ("tenting-front", "rewrite"): 2, ("tenting-back", "rewrite"): 2,
        ("tenting-front", "same"): 1, ("tenting-back", "same"): 1,
        ("covering", "same"): 1, ("capping", "same"): 1, ("capping", "design"): 1,
        ("footprint-duplicate-pad-numbers-are-jumpers", "same"): 1, ("footprint-units", "presentation"): 1,
    }  # fmt: skip


def test_design_loss_needs_consent() -> None:
    """Scenario "Design loss needs consent" at the resolver: the capped via is a design loss."""
    with pytest.raises(LossyWriteError) as refused:
        _resolved(BOARD, allow_lossy=False)
    assert refused.value.droppable
    assert [i.code for i in refused.value.issues] == [resolver.DESIGN_CODE]
    assert "row capping" in refused.value.issues[0].message
    via = _resolved(BOARD).root.find("via")
    assert via is not None and via.find("capping") is None


def test_rewrite_the_target_cannot_hold_falls_back() -> None:
    """A pad whose tenting is ``no`` cannot be written for 9 (9.0 names only tented sides of a pad)."""
    text = BOARD.replace("(tenting (front yes) (back none))", "(tenting (front no) (back none))")
    with pytest.raises(LossyWriteError) as refused:
        _resolved(text, allow_lossy=False)
    assert {resolver.row_id(i) for i in refused.value.issues} == {"tenting-front", "tenting-back", "capping"}


def test_value_rewrites() -> None:
    board = parse(
        """(kicad_pcb (version 20241229)
  (zone (filled_polygon (layer "F.Cu") (island yes) (pts (xy 0 0))) (filled_polygon (layer "F.Cu") (island no)
  (pts (xy 0 0))))
  (via buried (at 1 1) (size 0.6) (drill 0.3) (layers "In1.Cu" "In2.Cu")))"""
    )
    found = resolver.resolve(board, FileKind.BOARD, 9)
    zone = found.root.find("zone")
    assert zone is not None
    fills = zone.nodes("filled_polygon")
    first, second = (fill.find("island") for fill in fills)
    assert first is not None and first.children == () and second is None
    via = found.root.find("via")
    assert via is not None and via.atoms()[0].text == "blind"
    assert dict(found.counts) == {
        ("island-yes", "rewrite"): 1,
        ("island-no", "same"): 1,
        ("via-buried", "rewrite"): 1,
    }


def test_schematic_rewrites() -> None:
    sheet = parse(
        """(kicad_sch (version 20250114)
  (lib_symbols (symbol "power:GND" (power global) (in_pos_files yes) (duplicate_pin_numbers_are_jumpers no)))
  (symbol (lib_id "power:GND") (at 0 0 0) (body_style 1) (in_pos_files yes)))"""
    )
    found = resolver.resolve(sheet, FileKind.SCHEMATIC, 9)
    lib = found.root.find("lib_symbols")
    assert lib is not None
    symbol = lib.find("symbol")
    assert symbol is not None
    power = symbol.find("power")
    assert power is not None and power.children == ()
    assert [c.name for c in symbol.nodes()] == ["power"]
    instance = found.root.find("symbol")
    assert instance is not None and [c.name for c in instance.nodes()] == ["lib_id", "at", "convert"]
    assert found.counts[("sch-symbol-body-style", "rewrite")] == 1
    assert found.counts[("sym-jumpers-duplicate", "same")] == 1


def test_edit_issues() -> None:
    found = _resolved(BOARD)
    issues = resolver.edit_issues(found.edits, 9)
    assert {i.code for i in issues} == {resolver.CHANGED_CODE, resolver.LOST_CODE}
    lost = [i for i in issues if i.code == resolver.LOST_CODE]
    assert {i.hint for i in lost} == {"row capping (design)", "row footprint-units (presentation)"}


def test_no_edit_without_too_new_tokens() -> None:
    plain = parse("(kicad_pcb (version 20241229) (setup (tenting front back)))")
    found = resolver.resolve(plain, FileKind.BOARD, 9)
    assert found.root is plain and found.edits == ()
