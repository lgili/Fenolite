# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The token inventory: schema, scope, source discipline and matching (capability kicad-token-inventory)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fenolite.backends.kicad.versions import FileKind, Inventory, load_inventory, major_for
from fenolite.core.errors import FormatError

ROOT = Path(__file__).resolve().parents[4]
INV = load_inventory()
# Dated board-format versions after the 8.0 constant up to the 10.0 constant (S-0030; numbers only).
DATED = [
    20240201,
    20240202,
    20240225,
    20240609,
    20240617,
    20240703,
    20240706,
    20240819,
    20240928,
    20240929,
    20241006,
    20241007,
    20241009,
    20241010,
    20241030,
    20241129,
    20241228,
    20241229,
    20250210,
    20250222,
    20250228,
    20250302,
    20250309,
    20250324,
    20250401,
    20250513,
    20250801,
    20250811,
    20250818,
    20250829,
    20250901,
    20250907,
    20250909,
    20250914,
    20250926,
    20251027,
    20251028,
    20251101,
    20260101,
    20260206,
]
KEYWORD_SOURCES = {"S-0033", "S-0034", "S-0036"}
HEAD = 'format = 1\ncollected_at = ["9.0.9", "10.0.6"]\n'
NOTE_WITH_SUMMARY = '[[note]]\nversion = 20240929\nrows = ["x"]\nsummary = "padstacks"\n'
FORM = (
    '[[form]]\nid = "x"\nkinds = ["kicad_pcb"]\nsince_major = 10\ndescription = "d"\nsources = ["S-0030"]\n'
)


def registered(register: str, pattern: str) -> set[str]:
    return set(re.findall(pattern, (ROOT / register).read_text(encoding="utf-8"), re.MULTILINE))


SOURCES = registered("docs/evidence/sources.md", r"^\| (S-\d{4}) ")
HYPOTHESES = registered("docs/hypotheses.md", r"^\| (H-[A-Z0-9-]+) ")


def token(**fields: object) -> str:
    base: dict[str, object] = {"id": "x", "kinds": ["kicad_pcb"], "path": "x", "since_major": 9,
                               "sources": ["S-0030"]}  # fmt: skip
    base.update(fields)
    body = "".join(f"{k} = {v!r}\n".replace("'", '"') for k, v in base.items() if v is not None)
    return "[[token]]\n" + body


def load(text: str) -> Inventory:
    return load_inventory(HEAD + text, file="t.toml")


# --- schema ---------------------------------------------------------------------------------------


def test_packaged_inventory_loads() -> None:
    kinds = {k for row in INV.tokens for k in row.kinds}
    assert {FileKind.BOARD, FileKind.FOOTPRINT, FileKind.WORKSHEET, FileKind.RULES} <= kinds
    assert INV.collected_at == ("9.0.9", "10.0.6")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (token(colour="red"), "row x: unknown key(s) colour"),
        (token(sources=None), "row x: missing key(s) sources"),
        (token() + token(path="y"), "row x: duplicate id"),
        (token() + token(id="y"), "rows x and y: duplicate kinds, path and value"),
        (token(since_major=7), "row x: since_major 7"),
        (token(since_version=20250222), "since_version 20250222 belongs to major 10"),
        (token(kinds=["kicad_dru"], since_version=20241229), "rules rows have no since_version"),
        (token(until_major=9), "until_major 9 must be a major greater than since_major 9"),
        (token(older_readers="maybe"), "older_readers must be 'reject' or 'ignore'"),
        (token(sources=[]), "row x: sources must not be empty"),
        (token(kinds=["kicad_xyz"]), "unknown kind"),
        ('[[note]]\nversion = 20240929\nrows = ["x"]\nno_row = "no-token-change"\n' + token(), "exactly one"),
        ("[[note]]\nversion = 20240929\n", "note 20240929: exactly one of rows and no_row"),
        ('[[note]]\nversion = 20250401\nno_row = "because"\n', "unknown no_row reason"),
        ('[[note]]\nversion = 20250401\nrows = ["nope"]\n', "unknown row id 'nope'"),
        (NOTE_WITH_SUMMARY + token(), "note 20240929: unknown key(s) summary"),
    ],
)  # fmt: skip
def test_schema_errors(text: str, message: str) -> None:
    with pytest.raises(FormatError) as info:
        load(text)
    assert message in str(info.value) and info.value.file == "t.toml"


def test_foreign_top_level_key_rejected() -> None:
    with pytest.raises(FormatError, match="denylist"):
        load_inventory(HEAD + "[[denylist]]\nname = 1\n")


def test_form_rows_share_ids_with_tokens() -> None:
    with pytest.raises(FormatError, match="duplicate id"):
        load(token() + FORM)


# --- source discipline ----------------------------------------------------------------------------


def test_provenance_sources_and_hypotheses_registered() -> None:
    problems = []
    for row in (*INV.tokens, *INV.forms):
        problems += [f"{row.id}: unregistered source {s}" for s in row.sources if s not in SOURCES]
        if row.hypothesis and row.hypothesis not in HYPOTHESES:
            problems.append(f"{row.id}: unregistered hypothesis {row.hypothesis}")
        eeschema = bool(row.kinds & {FileKind.SCHEMATIC, FileKind.SYMBOL_LIB})
        dated_by = "S-0031" if eeschema else "S-0030"
        if row.since_version is not None and dated_by not in row.sources:
            problems.append(f"{row.id}: a dated row must cite {dated_by}")
    assert not problems, "\n".join(problems)


def test_provenance_detects_unregistered_source() -> None:
    bad = load(token(sources=["S-9999"]))
    assert [s for s in bad.tokens[0].sources if s not in SOURCES] == ["S-9999"]


def test_provenance_keyword_only_rows_are_known() -> None:
    """Rows whose only sources are keyword lists need a committed fuzz result (test_token_results)."""
    keyword_only = [r.id for r in INV.tokens if set(r.sources) <= KEYWORD_SOURCES]
    assert all(r.startswith("wks-") for r in keyword_only), keyword_only


def _keyword_readers(root: Path) -> list[str]:
    pattern = re.compile(r"(pcb|drc_rules|drawing_sheet)\.keywords")
    me = Path(__file__).resolve()
    found = []
    for top in ("tools", "src", "tests"):
        for path in sorted((root / top).rglob("*.py")):
            if path.resolve() != me and pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                found.append(path.relative_to(root).as_posix())
    return found


def test_provenance_no_reader_of_keyword_files(tmp_path: Path) -> None:
    assert _keyword_readers(ROOT) == []
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "x.py").write_text('open("common/pcb.keywords")\n')
    assert _keyword_readers(tmp_path) == ["tools/x.py"]


# --- scope and notes ------------------------------------------------------------------------------


# Dated schematic and symbol-library versions after the 8.0 constants up to the 10.0 constants (S-0031;
# numbers only).
SCH_DATED = [
    20240101, 20240417, 20240602, 20240620, 20240716, 20240812, 20240819, 20241004, 20241209, 20250114,
    20250222, 20250227, 20250318, 20250425, 20250513, 20250610, 20250827, 20250829, 20250901, 20250922,
    20251012, 20251028, 20260101, 20260306,
]  # fmt: skip
SYM_DATED = [20240529, 20240819, 20241209, 20250318, 20250324, 20250829, 20250901, 20250925, 20251024]
DATED_BY_KIND = {FileKind.BOARD: DATED, FileKind.SCHEMATIC: SCH_DATED, FileKind.SYMBOL_LIB: SYM_DATED}


def note_problems(inventory: object) -> list[str]:
    problems: list[str] = []
    notes = inventory.notes  # type: ignore[attr-defined]
    for kind, versions in DATED_BY_KIND.items():
        found = [n.version for n in notes if n.kind == kind]
        problems += [f"{kind.value}: dated version {v} has no note" for v in versions if v not in found]
        if [v for v in found if v in versions] != [v for v in versions if v in found]:
            problems.append(f"{kind.value}: notes are not in version order")
        problems += [f"{kind.value}: note {v} is not a dated version" for v in found if v not in versions]
    return problems


def test_notes_cover_every_dated_version() -> None:
    assert note_problems(INV) == []
    assert {n.kind for n in INV.notes} == set(DATED_BY_KIND)
    dated = [row for row in (*INV.tokens, *INV.forms) if row.since_version is not None]
    for row in dated:
        notes = [n for n in INV.notes if row.id in n.rows]
        assert notes, f"{row.id}: since_version {row.since_version} is not listed by its note"
        for note in notes:
            assert note.version == row.since_version, f"{row.id} is listed by note {note.version}"


def test_dated_version_without_a_note_is_named() -> None:
    import dataclasses

    cut = dataclasses.replace(
        INV, notes=tuple(n for n in INV.notes if (n.kind, n.version) != (FileKind.SCHEMATIC, 20250827))
    )
    assert note_problems(cut) == ["kicad_sch: dated version 20250827 has no note"]


def test_note_kind_rules() -> None:
    row = token(
        kinds=["kicad_sch"],
        path="symbol/body_style",
        since_major=10,
        since_version=20250827,
        sources=["S-0031"],
    )
    good = load(row + '[[note]]\nversion = 20250827\nkind = "kicad_sch"\nrows = ["x"]\n')
    assert good.notes[0].kind == FileKind.SCHEMATIC
    assert (
        load(row + '[[note]]\nversion = 20250827\nno_row = "unconfirmed"\n').notes[0].kind == FileKind.BOARD
    )
    with pytest.raises(FormatError, match="not of kind kicad_sym"):
        load(row + '[[note]]\nversion = 20250827\nkind = "kicad_sym"\nrows = ["x"]\n')
    with pytest.raises(FormatError, match="unknown kind"):
        load('[[note]]\nversion = 20250827\nkind = "kicad_xyz"\nno_row = "unconfirmed"\n')


# --- schematic and symbol-library rows (change c0060, "Schematic and symbol tokens are inventoried")


def test_rows_of_both_schematic_kinds_exist() -> None:
    for kind in (FileKind.SCHEMATIC, FileKind.SYMBOL_LIB):
        rows = [r for r in INV.tokens if kind in r.kinds]
        assert rows and all(r.since_major in (9, 10) and r.sources for r in rows), kind
        assert any(r.since_version is not None for r in rows), kind
        assert all("S-0031" in r.sources and "S-0368" in r.sources for r in rows), kind


def test_symbol_row_matches_inside_a_sheet() -> None:
    from fenolite.backends.kicad.versions import min_version

    row = next(r for r in INV.tokens if r.id == "sym-jumper-pin-groups")
    assert row.since_version is not None and row.since_version > 20241209
    in_sheet = min_version(FileKind.SCHEMATIC, "kicad_sch/lib_symbols/symbol/jumper_pin_groups")
    in_library = min_version(FileKind.SYMBOL_LIB, "kicad_symbol_lib/symbol/jumper_pin_groups")
    assert in_sheet == in_library == row.since_version
    # a schematic row for the same place wins over the symbol-library row
    native = INV.match(FileKind.SCHEMATIC, ("kicad_sch", "lib_symbols", "symbol", "body_styles"))
    assert native is not None and native.id == "sch-lib-body-styles"
    assert INV.match(FileKind.SCHEMATIC, ("kicad_sch", "symbol", "jumper_pin_groups")) is None
    assert INV.match(FileKind.BOARD, ("kicad_sch", "lib_symbols", "symbol", "jumper_pin_groups")) is None


def test_schematic_instance_rows() -> None:
    from fenolite.backends.kicad.versions import min_major, min_version

    assert min_version(FileKind.SCHEMATIC, "kicad_sch/symbol/body_style") == 20250827
    assert min_major(FileKind.SCHEMATIC, "kicad_sch/symbol/in_pos_files") == 10
    assert min_major(FileKind.SCHEMATIC, "kicad_sch/table/cells/table_cell") == 9
    assert min_version(FileKind.SCHEMATIC, "kicad_sch/rectangle/fill/type", value="hatch") == 20250222
    assert min_version(FileKind.SCHEMATIC, "kicad_sch/symbol/unit") is None


def test_notes_carry_no_free_text() -> None:
    for note in INV.notes:
        assert (note.rows == ()) == (note.no_row is not None)


def test_complex_padstack_row_present() -> None:
    row = next(r for r in INV.tokens if r.path == "pad/padstack")
    assert row.kinds == {FileKind.BOARD, FileKind.FOOTPRINT}
    assert (row.since_major, row.since_version) == (9, 20240929)


def test_rules_drift_rows_present() -> None:
    values = {"bridged_mask", "solder_mask_expansion", "solder_paste_abs_margin", "solder_paste_rel_margin",
              "via_dangling", "through_via", "blind_via"}  # fmt: skip
    rows = {r.value: r for r in INV.tokens if FileKind.RULES in r.kinds and r.value in values}
    assert set(rows) == values and {r.since_major for r in rows.values()} == {10}


def test_obsolete_net_table_row_present() -> None:
    row = INV.match(FileKind.BOARD, ["kicad_pcb", "net"])
    assert row is not None and (row.since_major, row.until_major) == (8, 9)
    assert INV.match(FileKind.BOARD, ["kicad_pcb", "segment", "net"]) is None


def test_obsolete_rows_present() -> None:
    paths = {r.path for r in INV.tokens if r.until_major == 9}
    plot = {
        f"pcbplotparams/{n}"
        for n in ("hpglpennumber", "hpglpenspeed", "hpglpendiameter", "plotinvisibletext")
    }
    assert {"/kicad_pcb/net", "zone/net_name", "zone/filled_areas_thickness"} | plot <= paths


def test_worksheet_vocabulary() -> None:
    names = {r.pattern[-1] for r in INV.tokens if FileKind.WORKSHEET in r.kinds}
    assert {"kicad_wks", "page_layout", "drawing_sheet", "generator_version", "face", "color", "maxlen",
            "maxheight", "incrlabel", "setup", "tbtext"} <= names  # fmt: skip
    assert all(r.since_major == 8 for r in INV.tokens if FileKind.WORKSHEET in r.kinds)


def test_rules_rows() -> None:
    rules = [r for r in INV.tokens if FileKind.RULES in r.kinds]
    assert all(r.since_version is None for r in rules)
    floor = [r for r in rules if r.since_major == 9]
    assert floor and all(r.hypothesis == "H-K-TOK-RULES-FLOOR" for r in floor)


def test_dated_rows_are_consistent() -> None:
    for row in INV.tokens:
        if row.since_version is not None:
            assert all(major_for(k, row.since_version) == row.since_major for k in row.kinds), row.id


# --- matching -------------------------------------------------------------------------------------


def test_matching_suffix_under_two_parents() -> None:
    inv = load(token(path="tenting/front", since_major=10))
    for parent in ("setup", "via"):
        assert inv.match(FileKind.BOARD, ["kicad_pcb", parent, "tenting", "front"]) is not None


def test_matching_most_specific_row_wins() -> None:
    inv = load(
        token(id="a", kinds=["kicad_mod"], path="layer")
        + token(id="b", kinds=["kicad_mod"], path="pad/padstack/layer")
    )
    row = inv.match(FileKind.FOOTPRINT, ["footprint", "pad", "padstack", "layer"])
    assert row is not None and row.id == "b"
    plain = inv.match(FileKind.FOOTPRINT, ["footprint", "fp_line", "layer"])
    assert plain is not None and plain.id == "a"


def test_matching_anchored_before_unanchored() -> None:
    inv = load(token(id="a", path="kicad_pcb/net") + token(id="b", path="/kicad_pcb/net"))
    row = inv.match(FileKind.BOARD, ["kicad_pcb", "net"])
    assert row is not None and row.id == "b"
    deeper = inv.match(FileKind.BOARD, ["x", "kicad_pcb", "net"])
    assert deeper is not None and deeper.id == "a"


def test_matching_numeric_head_and_value() -> None:
    inv = load(token(path="/kicad_pcb/layers/#", value="front"))
    assert inv.match(FileKind.BOARD, ["kicad_pcb", "layers", "39"], "front") is not None
    assert inv.match(FileKind.BOARD, ["kicad_pcb", "layers", "39"]) is None
    assert inv.match(FileKind.BOARD, ["kicad_pcb", "layers", "abc"], "front") is None


def test_matching_other_kind_never_matches() -> None:
    inv = load(token(kinds=["kicad_wks"], path="setup", since_major=8))
    assert inv.match(FileKind.BOARD, ["kicad_pcb", "setup"]) is None


def test_matching_form_row_never_matched() -> None:
    assert INV.match(FileKind.BOARD, ["kicad_pcb", "segment", "net"]) is None
    assert INV.form("net-by-name").applies_to == "net"
    with pytest.raises(KeyError):
        INV.form("net-by-number")
