# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Channels of repeated sheets on the public project sets (capability altium-import, "Channel
designators", "Channel nets", "Pin-to-pad map of a footprint model"; ``H-A-IMP-RPT-BOARD``,
``H-A-IMP-RPT-FORMAT``, ``H-A-IMP-RPT-NETS``, ``H-A-IMP-PINMAP``; change c0083). Only counts and designators
of the sets are printed; no content of a corpus file is kept."""

from __future__ import annotations

import dataclasses
import tomllib
from collections import Counter
from pathlib import PureWindowsPath
from types import SimpleNamespace

import pytest
from _corpus import MANIFEST, CorpusItem, heavy_enabled, manifest_items, require

from fenolite.backends.altium.adapter.board import read_board
from fenolite.backends.altium.adapter.circuit import CircuitImport, build_circuit
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.adapter.netlist import NetOptions, SheetInput, resolve
from fenolite.backends.altium.adapter.project import BoardInput, ProjectInput, import_project
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.project import read_project
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.base import PadAssignment, PadNetList
from fenolite.checks.assignment_compare import NO_NET, compare, model_netlist
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


def _elements(
    built: CircuitImport, document: PcbDocument, *, mapped: bool = True
) -> tuple[PadNetList, PadNetList]:
    """The schematic's elements, with or without the pin-to-pad maps of its components, and the board's."""
    circuit = built.circuit
    if not mapped:
        plain = tuple(dataclasses.replace(component, pin_pad_map=()) for component in circuit.components)
        circuit = dataclasses.replace(circuit, components=plain)
    parts = read_board(document, file="board", sha256=SHA, ids=Ids("altium_pcbdoc", EVIDENCE))
    refs = {component.id: component.ref for component in parts.components}
    pads = tuple(
        PadAssignment(f"{refs[footprint.component_id]}-{pad.number}", pad.net_id or NO_NET)
        for footprint in parts.board.footprints
        for pad in footprint.pads
        if pad.number
    )
    return model_netlist(SimpleNamespace(circuit=circuit)), PadNetList("pcb", pads)  # type: ignore[arg-type]


def test_nets_of_the_channels_agree_with_the_board() -> None:
    """``H-A-IMP-RPT-NETS`` for channels of several sheet symbols: no pin of the repeated sheet is covered
    by the schematic only, and none is on another net than its pad."""
    options, sheets, document = _load(_sets()[CHANNEL_SET])
    built, _ = _circuit(options, sheets)
    pair = compare(*_elements(built, document))
    channel_refs = {c.ref for c in built.circuit.components if c.id in built.repeated}
    assert len(channel_refs) == len(built.repeated) == 84

    def of_channel(element: str) -> bool:
        return element.rpartition("-")[0] in channel_refs

    only_schematic = [u.element for u in pair.only_a if of_channel(u.element)]
    differing = [d.element for d in pair.differences if of_channel(d.element)]
    pads_only = sum(of_channel(u.element) for u in pair.only_b)
    print(
        f"{CHANNEL_SET}: channel pins only in the schematic {len(only_schematic)}, on another net "
        f"{len(differing)}; pads of channel components without a pin {pads_only}"
    )
    assert only_schematic == [] and differing == []


@pytest.mark.parametrize("name", list(_sets()))
def test_pin_map_never_uncovers_an_element(name: str) -> None:
    """``H-A-IMP-PINMAP``: with the maps applied, no set has more elements on one side only, and no more
    differences."""
    items = _sets()[name]
    if any(item.heavy for item in items) and not heavy_enabled():
        pytest.skip(f"{name} holds a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    options, sheets, document = _load(items)
    built, issues = _circuit(options, sheets)
    plain = compare(*_elements(built, document, mapped=False))
    mapped = compare(*_elements(built, document))
    pairs = sum(len(component.pin_pad_map) for component in built.circuit.components)
    partial = sum(
        key == "pin_pads"
        for component in built.circuit.components
        for key, _value in (component.ext["altium"].payload if component.ext else ())
    )
    print(
        f"{name}: map pairs {pairs}, records kept in the bag {partial}; one side only "
        f"{len(plain.only_a) + len(plain.only_b)} -> {len(mapped.only_a) + len(mapped.only_b)}, common "
        f"{plain.common} -> {mapped.common}, differences {len(plain.differences)} -> "
        f"{len(mapped.differences)}"
    )
    assert len(mapped.only_a) + len(mapped.only_b) <= len(plain.only_a) + len(plain.only_b)
    assert len(mapped.differences) <= len(plain.differences) and mapped.common >= plain.common
    assert bool(partial) == any(i.code == "altium.import.pin-map" for i in issues)
    if name == CHANNEL_SET:
        # ``H-A-IMP-PINMAP-MULTI`` (change c0123): two of its pins list two and four pads, and each pad is
        # an element; before that change the row read 694 common, 7, 31 and 2, with two records in a bag
        assert (mapped.common - plain.common, pairs, partial) == (10, 11, 0)
        assert (mapped.common, len(mapped.only_a), len(mapped.only_b), len(mapped.differences)) == (
            698,
            7,
            27,
            2,
        )
        several = [c for c in built.circuit.components if any(len(p) > 1 for p in c.pin_pads().values())]
        assert sorted(len(pads) for c in several for pads in c.pin_pads().values() if len(pads) > 1) == [2, 4]
