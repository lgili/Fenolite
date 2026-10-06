# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Channels of repeated sheets on the public project sets (capability altium-import, "Channel
designators"; ``H-A-IMP-RPT-BOARD``, ``H-A-IMP-RPT-FORMAT``; change c0083). Only counts and designators
of the sets are printed; no content of a corpus file is kept."""

from __future__ import annotations

import tomllib
from collections import Counter
from pathlib import PureWindowsPath

import pytest
from _corpus import MANIFEST, CorpusItem, manifest_items, require

from fenolite.backends.altium.adapter.board import read_board
from fenolite.backends.altium.adapter.circuit import CircuitImport, build_circuit
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.adapter.netlist import NetOptions, SheetInput, resolve
from fenolite.backends.altium.adapter.project import BoardInput, ProjectInput, import_project
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.project import read_project
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.core.errors import Issue

pytestmark = pytest.mark.needs_corpus
SHA = "0" * 64
CHANNEL_SET = "altium-set:02"
"""The one set of the corpus with a sheet that several sheet symbols name."""


def _sets() -> dict[str, list[CorpusItem]]:
    found: dict[str, list[CorpusItem]] = {}
    for item in manifest_items("altium-import"):
        (name,) = [use for use in item.uses if use.startswith("altium-set:")]
        found.setdefault(name, []).append(item)
    return dict(sorted(found.items()))


def _kind(item: CorpusItem) -> str:
    return item.path.suffix.lower().lstrip(".")


def _load(items: list[CorpusItem]) -> tuple[NetOptions, tuple[SheetInput, ...], PcbDocument]:
    (project_item,) = [item for item in items if _kind(item) == "prjpcb"]
    (board_item,) = [item for item in items if _kind(item) == "pcbdoc"]
    by_name = {item.path.name.casefold(): item for item in items if _kind(item) == "schdoc"}
    project = read_project(require(project_item).read_bytes(), file=project_item.id)
    sheets: list[SheetInput] = []
    for listed in project.documents:
        if listed.kind == "schematic":
            item = by_name[PureWindowsPath(listed.path).name.casefold()]
            document = read_schematic(require(item).read_bytes(), file=item.id)
            sheets.append(SheetInput(item.path.name, SHA, document))
    board = read_pcbdoc(require(board_item).read_bytes(), file=board_item.id)
    return NetOptions.from_project(project), tuple(sheets), board


def _circuit(options: NetOptions, sheets: tuple[SheetInput, ...]) -> tuple[CircuitImport, list[Issue]]:
    issues: list[Issue] = []
    resolved = resolve(sheets, options, issues)
    return build_circuit(resolved, Ids("altium_schdoc", EVIDENCE), issues), issues


def test_the_channel_set_is_in_the_manifest() -> None:
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"]
    assert any(CHANNEL_SET in row.get("uses", []) for row in rows)


def test_format_gives_the_board_designators() -> None:
    """The schematic alone, named by the project's designator format, against the board's designators."""
    options, sheets, document = _load(_sets()[CHANNEL_SET])
    built, issues = _circuit(options, sheets)
    assert options.channel_format and options.room_style is not None
    assert built.repeated and built.channel_sources == {"format": len(built.repeated)}
    assert not [i for i in issues if i.code == "altium.import.channel-naming"]
    refs = Counter(component.ref for component in built.circuit.components)
    assert [ref for ref, count in refs.items() if count > 1 and ref] == []
    parts = read_board(document, file="board", sha256=SHA, ids=Ids("altium_pcbdoc", EVIDENCE))
    own = {component.id: component.ref for component in parts.components}
    named = {component.id: component.ref for component in built.circuit.components}
    channels = other = 0
    for footprint in parts.board.footprints:
        record = parts.links.get(footprint.id)
        target = built.by_path.get(record.source_unique_id or "") if record is not None else None
        if target is None or target not in built.repeated:
            continue
        channels += 1
        other += named[target] != own[footprint.component_id]
    print(f"{CHANNEL_SET}: {channels} channel components linked, {other} named otherwise by the board")
    assert channels == len(built.repeated) and other == 0


def test_designators_of_the_board() -> None:
    """The project import: every channel component is linked to one board component and takes its
    designator; no reference is held twice."""
    options, sheets, document = _load(_sets()[CHANNEL_SET])
    issues: list[Issue] = []
    project = ProjectInput(
        "set", options=options, sheets=sheets, board=BoardInput("board.PcbDoc", SHA, document)
    )
    design = import_project(project, issues=issues)
    refs = Counter(component.ref for component in design.circuit.components if component.ref)
    assert [ref for ref, count in refs.items() if count > 1] == []
    assert design.board is not None
    board_refs = {
        component.ref
        for component in design.circuit.components
        if component.id in {footprint.component_id for footprint in design.board.footprints}
    }
    assert {ref for ref in board_refs if ref.startswith("D9_")} == {f"D9_{n}" for n in range(1, 13)}


@pytest.mark.parametrize("name", [n for n in _sets() if n != CHANNEL_SET])
def test_sets_without_channels_are_unchanged(name: str) -> None:
    """A project whose sheets are each named once has no channel, whatever its format says."""
    options, sheets, _ = _load(_sets()[name])
    built, issues = _circuit(options, sheets)
    assert built.repeated == set() and built.channel_sources == {}
    assert not [i for i in issues if i.code in ("altium.import.channels", "altium.import.channel-naming")]
