# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The follow-up facts of change c0074 on the running ``kicad-cli`` (capability kicad-oracle, "Follow-up
facts are probed"): the schematic's drawing-sheet key, the distance across which KiCad closes a board
outline, edge items inside footprints, the export options a preset can give, and stitching that avoids
rule areas and the board edge."""

from __future__ import annotations

import _followcases as fc
import pytest
from _probes import major, run

from fenolite.backends.kicad.outline import CHAIN_GAP, board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.exports import preset

pytestmark = pytest.mark.needs_kicad
SHEET_OUTCOMES = {"relative": "present", "kiprjmod": "present", "absent": "absent", "board-only": "absent"}
EQUAL_OPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("gerbers", "use_drill_file_origin"),  # the blink sets no drill and place origin
        ("gerbers", "exclude_value"),  # no value text lies on a plotted layer
        ("drill", "origin"),  # no drill and place origin either
        ("drill", "oval_format"),  # no oval hole
        ("pos", "exclude_dnp"),  # no part is marked do-not-populate
        ("pos", "use_drill_file_origin"),
    }
)
"""``(kind, key)`` of the preset keys whose run writes the same files as the default run on the blink:
the option exists and is accepted, and this board has nothing for it to change."""


@pytest.mark.parametrize("case", sorted(fc.SHEET_KEYS))
def test_schematic_sheet(case: str) -> None:
    assert run(f"wks-sch-key-{case}") == SHEET_OUTCOMES[case]


def test_outline_chain() -> None:
    assert run("outline-gap-9999") == "absent", "KiCad does not close a 9.999 µm gap"
    assert run("outline-gap-10001") == "present", "KiCad closes a 10.001 µm gap"
    at_limit = run("outline-gap-10000")
    assert at_limit == ("absent" if major() >= 10 else "present")
    # Fenolite says "open" from 10 µm on: the safe answer for 9.0, and never open where a major closes
    for gap in fc.GAPS:
        closed = bool(board_outline(read_board(fc.gap_board(gap))).rings)
        assert closed == (gap < CHAIN_GAP)
        if run(f"outline-gap-{gap}") == "present":
            assert not closed, f"board_outline closes a {gap} nm gap that KiCad {major()} leaves open"


def test_footprint_edges() -> None:
    assert run("outline-fp-edge-closes") == "present"
    assert run("outline-fp-edge-cutout") == "present"


@pytest.mark.parametrize("kind", fc.HELP_KINDS)
def test_export_options_exist(kind: str) -> None:
    for option in fc.OPTIONS[kind]:
        assert run(f"help-pcb-export-{kind}-{option.lstrip('-')}") == "present", option
    # every option a preset can give is one of the probed options, and none is forbidden
    given: set[str] = set()
    for key, line in fc.VARIANTS[kind].items():
        text = f'schema = "{preset.PRESET_SCHEMA}"\n[{kind}]\n{line}\n'
        args = preset.arguments(kind, preset.read_preset(text), stem="b", layers=("F.Cu",))
        given |= {a for a in args if a.startswith("--")}
        assert key in preset.TABLES[kind]
    assert given <= set(fc.OPTIONS[kind]) and not given & set(preset.FORBIDDEN)
    assert set(fc.VARIANTS[kind]) == set(preset.TABLES[kind])


@pytest.mark.parametrize(
    ("kind", "key"), [(kind, key) for kind in fc.HELP_KINDS for key in fc.VARIANTS[kind]]
)
def test_export_options_change_the_files(kind: str, key: str) -> None:
    expected = "equal" if (kind, key) in EQUAL_OPTIONS else "different"
    assert run(f"export-option-{kind}-{key}") == expected


def test_stitch() -> None:
    (avoided, clean), (control, flagged) = fc.stitch_reports()
    assert clean is not None and flagged is not None
    ours, theirs = fc.stitch_vias(avoided), fc.stitch_vias(control)
    assert len(theirs) > len(ours) > 0
    for kind in ("items_not_allowed", "copper_edge_clearance"):
        assert fc.names_uuid(flagged, kind, set(theirs)), f"the control fence has no {kind}"
        assert not fc.names_uuid(clean, kind, set(ours)), f"a stitch via has {kind}"
    assert run("stitch-avoid") == "equal"
