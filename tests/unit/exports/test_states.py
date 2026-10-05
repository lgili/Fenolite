# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The states of manifest entries (capability manufacturing-exports, "Artefact states"; change c0065)."""

from __future__ import annotations

import dataclasses

from hypothesis import given
from hypothesis import strategies as st

from fenolite.core.evidence import Level
from fenolite.exports.manifest import STATES, ArtifactEntry, file_entry
from fenolite.exports.states import DERIVED, PENDING, RULES, StageMap, assign, rank, role_of

KICAD = "KICAD-VERIFIED"
BOARD = file_entry("board.kicad_pcb", "kicad_pcb", b"board")
SHEET = file_entry("board.kicad_sch", "kicad_sch", b"sheet")
PROJECT = file_entry("board.kicad_pro", "kicad_pro", b"{}")
RULES_FILE = file_entry("board.kicad_dru", "kicad_dru", b"(version 1)")
FP_TABLE = file_entry("fp-lib-table", "lib-table", b"(fp_lib_table)")
SYM_TABLE = file_entry("sym-lib-table", "lib-table", b"(sym_lib_table)")
FOOTPRINT = file_entry("lib/Mini.pretty/R.kicad_mod", "kicad_mod", b"(footprint)")
SYMBOLS = file_entry("lib/Mini.kicad_sym", "kicad_sym", b"(kicad_symbol_lib)")
MODEL = file_entry("lib/Mini.pretty/r.step", "file", b"ISO-10303-21;")
GERBER = file_entry("fab/g/b-F_Cu.gbr", "gerbers", b"G04", layer="F.Cu", from_={"board": BOARD.sha256})
BOM = file_entry("fab/bom.csv", "bom", b"ref", from_={"board": BOARD.sha256, "schematic": SHEET.sha256})
DESIGN = (BOARD, SHEET, PROJECT, RULES_FILE, FP_TABLE, SYM_TABLE, FOOTPRINT, SYMBOLS, MODEL)
ALL = (*DESIGN, GERBER, BOM)
PASSING: StageMap = {
    "model.validate": ("ok", "INFERRED"),
    "copper.clearance": ("ok", "INFERRED"),
    "roundtrip": ("ok", "CORPUS-VERIFIED"),
    "drc.kicad": ("ok", KICAD),
}
SHEETS = {SHEET.path: True}


def _current(entries: tuple[ArtifactEntry, ...] = ALL) -> dict[str, str]:
    return {item.path: item.sha256 for item in entries}


def _states(stages: StageMap, **overrides: object) -> dict[str, ArtifactEntry]:
    options: dict[str, object] = {"sheets_ok": SHEETS, "current": _current(), **overrides}
    found = assign(ALL, stages=stages, **options)  # type: ignore[arg-type]
    assert [item.path for item in found] == [item.path for item in ALL]
    return {item.path: item for item in found}


def test_ladder_of_the_board() -> None:
    found = _states(PASSING)
    board = found[BOARD.path]
    assert (board.state, board.stale, board.held) == ("native-verified", False, "")
    for item in (PROJECT, RULES_FILE, FP_TABLE, FOOTPRINT):  # what KiCad loaded to judge the board
        assert found[item.path].state == "native-verified" and found[item.path].held == ""
    # a file that is no KiCad design file: nothing is known to load it, so the DRC says nothing about it
    assert (found[MODEL.path].state, found[MODEL.path].held) == ("checked", "")


def test_a_failed_rung_stops_the_ladder() -> None:
    found = _states({**PASSING, "roundtrip": ("errors", "CORPUS-VERIFIED")})
    assert found[BOARD.path].state == "checked"  # although drc.kicad is ok
    assert found[BOARD.path].held == "roundtrip-ok: roundtrip reported errors"
    assert found[PROJECT.path].state == "checked" and found[PROJECT.path].held == (
        "native-verified: the board is checked"
    )
    assert found[GERBER.path].state == "checked"


def test_drc_below_kicad_verified() -> None:
    found = _states({**PASSING, "drc.kicad": ("ok", "UNVERIFIED")})
    assert found[BOARD.path].state == "roundtrip-ok"
    assert found[BOARD.path].held == "native-verified: drc.kicad is UNVERIFIED, below KICAD-VERIFIED"
    found = _states({**PASSING, "drc.kicad": ("ok", Level.ALTIUM_VERIFIED_KIT.value)})
    assert found[BOARD.path].state == "roundtrip-ok"  # the rule names one level, not "at least"


def test_missing_and_skipped_stages() -> None:
    without = {name: value for name, value in PASSING.items() if name != "drc.kicad"}
    assert _states(without)[BOARD.path].held == "native-verified: drc.kicad did not run"
    found = _states({**PASSING, "copper.clearance": ("skipped", "UNVERIFIED")})
    assert {item.state for item in found.values()} == {"generated"}
    assert found[BOARD.path].held == "checked: copper.clearance was skipped"
    assert found[GERBER.path].held == "checked: the board is generated"


def test_schematic_side_waits_for_the_erc() -> None:
    with_erc = {**PASSING, "erc.kicad": ("ok", KICAD)}
    for stages in (PASSING, with_erc):
        found = _states(stages)
        assert found[SHEET.path].state == "roundtrip-ok"
        assert found[SYMBOLS.path].state == found[SYM_TABLE.path].state == "checked"
        for item in (SHEET, SYMBOLS, SYM_TABLE):
            assert found[item.path].held == (
                "native-verified: erc.kicad is not a stage of this version of Fenolite"
            )
    assert set(PENDING) == {"sheet", "schematic-support"}
    assert all("native-verified" not in [rule.state for rule in RULES[role]] for role in PENDING)


def test_sheet_roundtrip() -> None:
    found = _states(PASSING, sheets_ok={SHEET.path: False})
    assert (found[SHEET.path].state, found[SHEET.path].held) == ("checked", "roundtrip-ok: RT1 failed")
    found = _states(PASSING, sheets_ok={})
    assert found[SHEET.path].held == "roundtrip-ok: RT1 was not judged"
    assert found[BOM.path].state == "checked"  # its sources are checked; it never needs more


def test_derived_file_of_a_checked_board() -> None:
    found = _states(PASSING)
    gerber = found[GERBER.path]
    assert (gerber.state, gerber.stale, gerber.held) == ("checked", False, "")
    assert found[BOM.path].state == "checked"


def test_stale_artefact() -> None:
    old = dataclasses.replace(GERBER, from_={"board": "0" * 64})
    found = assign((BOARD, old), stages=PASSING, sheets_ok={}, current=_current())
    assert (found[1].state, found[1].stale) == ("generated", True)
    assert found[1].held == "checked: the board changed since the file was made"
    edited = {**_current(), GERBER.path: "f" * 64}
    found = assign((BOARD, GERBER), stages=PASSING, sheets_ok={}, current=edited)
    assert (found[1].state, found[1].stale) == ("generated", True)
    gone = assign((GERBER,), stages=PASSING, sheets_ok={}, current=_current())  # no board is listed
    assert (gone[0].state, gone[0].stale) == ("generated", True)


def test_a_derived_file_without_a_source_claims_nothing() -> None:
    bare = dataclasses.replace(GERBER, from_={})
    other = dataclasses.replace(GERBER, path="fab/x.csv", from_={"netlist": "1" * 64})
    found = assign(
        (BOARD, bare, other), stages=PASSING, sheets_ok={}, current={**_current(), other.path: other.sha256}
    )
    assert (found[1].state, found[1].stale, found[1].held) == (
        "generated", False, "checked: no source is recorded",
    )  # fmt: skip
    assert (found[2].state, found[2].held) == ("generated", "checked: the source 'netlist' is not known")


def test_a_changed_design_file_stays_generated() -> None:
    found = _states(PASSING, current={**_current(), BOARD.path: "e" * 64})
    assert found[BOARD.path].state == "generated" and found[BOARD.path].stale is False
    assert found[PROJECT.path].state == "checked"  # it follows the board, which is not native-verified
    assert found[GERBER.path].stale is True


def test_no_check_no_claim() -> None:
    found = _states({})
    assert {item.state for item in found.values()} == {"generated"}
    assert not any(item.stale for item in found.values())
    assert found[BOARD.path].held == "checked: model.validate did not run"


def test_roles_and_ranks() -> None:
    assert [rank(state) for state in STATES] == [0, 1, 2, 3, 4]
    assert [role_of(item) for item in ALL] == [
        "board", "sheet", "board-support", "board-support", "board-support", "schematic-support",
        "board-support", "schematic-support", "other", "derived", "derived",
    ]  # fmt: skip
    assert frozenset({"gerbers", "drill", "pos", "ipcd356", "bom", "pnp", "render"}) == DERIVED
    assert not any(rule.state == "oracle-verified" for rules in RULES.values() for rule in rules)


STATUS = st.sampled_from(["ok", "errors", "skipped"])
LEVELS = st.sampled_from([level.value for level in Level])
NAMES = ["model.validate", "copper.clearance", "roundtrip", "drc.kicad", "erc.kicad", "erc.lite", "render"]
STAGES = st.dictionaries(st.sampled_from(NAMES), st.tuples(STATUS, LEVELS))
HASHES = st.sampled_from(["0" * 64, BOARD.sha256, SHEET.sha256, GERBER.sha256])


@st.composite
def _cases(draw: st.DrawFn) -> tuple[tuple[ArtifactEntry, ...], StageMap, dict[str, bool], dict[str, str]]:
    stages = draw(STAGES)
    sources = draw(st.dictionaries(st.sampled_from(["board", "schematic", "netlist"]), HASHES))
    extra = dataclasses.replace(GERBER, path="fab/extra.gbr", from_=sources)
    entries = draw(st.permutations([*ALL, extra]).map(tuple))
    sheets = draw(st.dictionaries(st.just(SHEET.path), st.booleans()))
    current = _current(entries)
    for path in draw(st.sets(st.sampled_from(sorted(current)))):
        current[path] = "9" * 64
    return entries, stages, sheets, current


def _ok(stages: StageMap, name: str, level: str = "") -> bool:
    found = stages.get(name)
    return found is not None and found[0] == "ok" and (not level or found[1] == level)


@given(_cases())
def test_states_never_exceed_what_the_stages_give(
    case: tuple[tuple[ArtifactEntry, ...], StageMap, dict[str, bool], dict[str, str]],
) -> None:
    entries, stages, sheets, current = case
    found = assign(entries, stages=stages, sheets_ok=sheets, current=current)
    assert [item.path for item in found] == [item.path for item in entries]
    checked = _ok(stages, "model.validate") and _ok(stages, "copper.clearance")
    native = checked and _ok(stages, "roundtrip") and _ok(stages, "drc.kicad", KICAD)
    for before, item in zip(entries, found, strict=True):
        role = role_of(item)
        assert dataclasses.replace(item, state="generated", stale=False, held="") == dataclasses.replace(
            before, state="generated", stale=False, held=""
        )  # nothing else than the state, the stale flag and the reason changes
        assert item.state != "oracle-verified"
        assert item.state == "generated" or current[item.path] == item.sha256
        assert item.state == "generated" or checked
        assert (item.held == "") == (item.state == RULES[role][-1].state and role not in PENDING)
        if role == "derived":
            assert rank(item.state) <= rank("checked")
            assert not item.stale or item.state == "generated"
        else:
            assert item.stale is False
        if role == "board":
            assert rank(item.state) <= rank("checked") or _ok(stages, "roundtrip")
        if role == "sheet":
            assert rank(item.state) <= rank("checked") or sheets.get(item.path) is True
        if role in PENDING or role == "other":
            assert rank(item.state) < rank("native-verified")
        if item.state == "native-verified":
            assert native and current[BOARD.path] == BOARD.sha256
    if not stages:
        assert {item.state for item in found} == {"generated"}
