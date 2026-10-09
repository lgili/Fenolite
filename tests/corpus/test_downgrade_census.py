# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad 10.0.6 demo files of format 10 written for KiCad 9 (change c0162, the design's measurements 1
and 2; capability kicad-version-gating, "Downgrade edits").

Measurement 1: of the 18 demo boards, two have a format of major 10. With the source-major refusal of
``check_target`` bypassed, ``write_board(target=9)`` refuses each with ``LossyWriteError``, every issue a
droppable too-new token (counts per inventory row below), and with ``allow_lossy`` the slot-level drop of
the writer removes the outermost opaque node that holds a token: 746 and 134 nodes, one ``setup`` among
them. The written boards read back equal to the source at level 5. Measurement 2: of the 114 demo sheets,
ten have a format of major 10, with the too-new tokens per row below. The resolver's own counts (task 2.2)
are those of ``RESOLVED``: no ``setup`` is removed.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from _corpus import manifest_items

import fenolite.backends.kicad.pcb as pcb
from fenolite.backends.kicad import resolver, sch
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import (
    FileKind,
    LossyWriteError,
    check_emittable,
    major_for,
)
from fenolite.checks.equivalence import Tolerances, compare_designs
from fenolite.model.canonical import to_data
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
BOARDS = "kicad-demo-10-0-6-pcb-"
SHEETS = "kicad-demo-10-0-6-sch-"
HEADER = "kicad.version.header-too-new"
TEN_BOARDS = {"01": "CM5_MINIMA_3", "12": "pic_programmer"}
"""The demo boards of format major 10; the 16 others are of major 9."""
TOO_NEW: dict[str, dict[str, int]] = {
    "01": {
        "capping": 1, "covering": 1, "filling": 1, "footprint-duplicate-pad-numbers-are-jumpers": 112,
        "plugging": 1, "tenting-back": 634, "tenting-front": 634,
    },
    "12": {
        "capping": 1, "covering": 1, "filling": 1, "footprint-duplicate-pad-numbers-are-jumpers": 63,
        "footprint-units": 63, "plugging": 1, "point": 7, "tenting-back": 1, "tenting-front": 1,
    },
}  # fmt: skip
"""The too-new tokens of each board for target 9, per inventory row (measurement 1)."""
SLOT_DROP: dict[str, dict[str, int]] = {
    "01": {"duplicate_pad_numbers_are_jumpers": 112, "setup": 1, "tenting": 633},
    "12": {"duplicate_pad_numbers_are_jumpers": 63, "point": 7, "setup": 1, "units": 63},
}
"""The opaque nodes the slot-level drop removes, per head: 746 and 134."""
TEN_SHEETS: dict[str, dict[str, int]] = {
    "002": {"sch-lib-power-global": 3, "sym-jumpers-duplicate": 7},
    "003": {"sch-lib-power-global": 5, "sym-jumpers-duplicate": 12},
    "004": {"sch-lib-power-global": 2, "sym-jumpers-duplicate": 3},
    "005": {"sch-lib-power-global": 2, "sym-jumpers-duplicate": 6},
    "006": {"sch-lib-power-global": 2, "sym-jumpers-duplicate": 6},
    "007": {"sch-lib-power-global": 3, "sym-jumpers-duplicate": 15},
    "008": {"sch-lib-power-global": 3, "sym-jumpers-duplicate": 13},
    "009": {"sch-lib-power-global": 2, "sym-jumpers-duplicate": 8},
    "039": {
        "sch-lib-in-pos-files": 21, "sch-lib-power-global": 3, "sch-symbol-body-style": 105,
        "sch-symbol-in-pos-files": 105, "sym-jumpers-duplicate": 21,
    },
    "040": {
        "sch-lib-body-styles": 1, "sch-lib-in-pos-files": 8, "sch-lib-power-global": 2,
        "sch-symbol-body-style": 19, "sch-symbol-in-pos-files": 19, "sym-jumpers-duplicate": 8,
    },
}  # fmt: skip
"""The too-new tokens of the ten sheets of major 10 for target 9, per row, besides the header (measurement
2): 124 ``body_style``, 124 ``in_pos_files``, 99 ``duplicate_pin_numbers_are_jumpers``, 29 ``in_pos_files``
of a library symbol, 27 ``power global`` and 1 ``body_styles``."""
_VERSION = re.compile(rb"\(version (\d+)\)")


def _items(prefix: str) -> dict[str, Path]:
    return {
        item.id.removeprefix(prefix): item.path
        for item in manifest_items("rt0")
        if item.id.startswith(prefix)
    }


def _version(path: Path) -> int:
    with path.open("rb") as handle:
        found = _VERSION.search(handle.read(256))
    assert found is not None, path.name
    return int(found.group(1))


def _row(hint: str) -> str:
    return hint.split(" ", 2)[1]


@cache
def _source(key: str) -> Design:
    path = _items(BOARDS)[key]
    return pcb.read_board(path)


def _bypassed(monkeypatch: pytest.MonkeyPatch) -> None:
    """``write_board`` without the source-major refusal: what the writer did before the resolver."""
    monkeypatch.setattr(pcb, "check_target", lambda info, target, **_: None)


def test_boards_of_major_ten() -> None:
    items = manifest_items("rt0")
    boards = [i for i in items if i.id.startswith(BOARDS)]
    assert len(boards) == 18
    missing = [i.id for i in boards if not i.path.is_file()]
    if missing:
        pytest.skip(f"corpus items missing from the cache: {', '.join(missing)}")
    found = {
        i.id.removeprefix(BOARDS): i.path.stem
        for i in boards
        if major_for(FileKind.BOARD, _version(i.path)) == 10
    }
    assert found == TEN_BOARDS


@pytest.mark.parametrize("key", sorted(TEN_BOARDS))
def test_too_new_tokens(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Measurement 1: every issue of the refused write is a droppable too-new token."""
    _bypassed(monkeypatch)
    with pytest.raises(LossyWriteError) as refused:
        pcb.write_board(_source(key), target=9)
    assert refused.value.droppable
    assert {i.code for i in refused.value.issues} == {"kicad.token.too-new"}
    assert dict(Counter(_row(i.hint) for i in refused.value.issues)) == TOO_NEW[key]


@pytest.mark.parametrize("key", sorted(TEN_BOARDS))
def test_slot_level_drop(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Measurement 1: the slot-level drop removes ``setup``, and the board reads back equal at level 5."""
    _bypassed(monkeypatch)
    source = _source(key)
    written = pcb.write_board(source, target=9, allow_lossy=True)
    dropped = [i for i in written.issues if i.code == "kicad.board.dropped-too-new"]
    heads = Counter(i.where.rsplit("/", 1)[1].split("[", 1)[0] for i in dropped)
    assert dict(heads) == SLOT_DROP[key]
    again = pcb.read_board(written.text)
    report = compare_designs(source, again, level=5, tolerances=Tolerances(0, 0, 0), frame="absolute")
    assert report.equivalent, report.differences[:5]


RESOLVED: dict[str, dict[tuple[str, str], int]] = {
    "01": {
        ("capping", "same"): 1, ("covering", "same"): 1, ("filling", "same"): 1, ("plugging", "same"): 1,
        ("footprint-duplicate-pad-numbers-are-jumpers", "same"): 112,
        ("tenting-back", "rewrite"): 1, ("tenting-front", "rewrite"): 1,
        ("tenting-back", "same"): 633, ("tenting-front", "same"): 633,
    },
    "12": {
        ("capping", "same"): 7, ("covering", "same"): 7, ("filling", "same"): 7, ("plugging", "same"): 7,
        ("footprint-duplicate-pad-numbers-are-jumpers", "same"): 63, ("footprint-units", "presentation"): 63,
        ("net-by-name", "rewrite"): 725, ("point", "presentation"): 7,
        ("tenting-back", "rewrite"): 1, ("tenting-front", "rewrite"): 1,
    },
}  # fmt: skip
"""The resolver's edits per row and action (task 2.2). The tokens of measurement 1 are all there: the
setup's tenting is rewritten and the 633 pad tentings of ``CM5_MINIMA_3`` (both sides ``none``) dropped
as ``same``; the via protection of ``pic_programmer`` is counted on its seven vias, which the writer
emits in 9's form, besides its setup; ``net-by-name`` counts the references written by number (its source
is of format 20260206, ``CM5_MINIMA_3``'s 20250513 still numbers its nets)."""


@pytest.mark.parametrize("key", sorted(TEN_BOARDS))
def test_resolved_at_the_node(key: str) -> None:
    """Scenario "Setup kept": the downgrade keeps ``setup`` and edits each construct where it is; the
    board reads back equal to the source at level 5."""
    source = _source(key)
    edits: list[resolver.Edit] = []
    written = pcb.write_board(source, target=9, downgrade=True, allow_lossy=True, edits=edits)
    tree = parse(written.text)
    setup = tree.find("setup")
    assert setup is not None and setup.find("pcbplotparams") is not None
    tenting = setup.find("tenting")
    assert tenting is not None and [a.text for a in tenting.atoms()] == ["front", "back"]
    assert written.text.count("(tenting") == 1
    assert dict(Counter((e.row, e.action) for e in edits)) == RESOLVED[key]
    assert not [i for i in check_emittable(tree, FileKind.BOARD, 9) if i.severity == "error"]
    again = pcb.read_board(written.text)
    report = compare_designs(source, again, level=5, tolerances=Tolerances(0, 0, 0), frame="absolute")
    assert report.equivalent, report.differences[:5]


SHEET_ACTIONS: dict[str, str] = {
    "sch-lib-body-styles": "presentation", "sch-lib-in-pos-files": "same", "sch-lib-power-global": "rewrite",
    "sch-symbol-body-style": "rewrite", "sch-symbol-in-pos-files": "same", "sym-jumpers-duplicate": "same",
}  # fmt: skip
"""The resolver's action on every token of the ten sheets (task 2.3): no design loss."""


@pytest.mark.parametrize("key", sorted(TEN_SHEETS))
def test_sheets_retargeted(key: str) -> None:
    """Each sheet of major 10 re-targeted to 9: one edit per token of measurement 2, and the read-back
    holds the model of the source."""
    path = _items(SHEETS)[key]
    if not path.is_file():
        pytest.skip(f"corpus item {SHEETS}{key} is missing from the cache")
    sheet = sch.read_schematic(path)
    edits: list[resolver.Edit] = []
    text = sch.retarget_schematic(sheet, target=9, downgrade=True, edits=edits)
    expected = {(row, SHEET_ACTIONS[row]): count for row, count in TEN_SHEETS[key].items()}
    assert dict(Counter((e.row, e.action) for e in edits)) == expected
    again = sch.read_schematic(text, file=path.name)
    assert _model(to_data(again)) == _model(to_data(sheet))


def _model(value: object) -> object:
    if isinstance(value, dict):
        return {k: _model(v) for k, v in value.items() if k not in ("provenance", "ext")}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [_model(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    return value


def test_sheets_of_major_ten() -> None:
    """Measurement 2: the ten sheets of major 10 and their too-new tokens for target 9."""
    sheets = _items(SHEETS)
    assert len(sheets) == 114
    found: dict[str, dict[str, int]] = {}
    for key, path in sorted(sheets.items()):
        if not path.is_file():
            pytest.skip(f"corpus item {SHEETS}{key} is missing from the cache")
        if major_for(FileKind.SCHEMATIC, _version(path)) != 10:
            continue
        issues = [i for i in check_emittable(parse(path.read_text(encoding="utf-8")), FileKind.SCHEMATIC, 9)]
        errors = [i for i in issues if i.severity == "error"]
        assert [i.code for i in errors].count(HEADER) == 1
        found[key] = dict(sorted(Counter(_row(i.hint) for i in errors if i.code != HEADER).items()))
    assert found == TEN_SHEETS
