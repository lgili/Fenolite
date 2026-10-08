# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium import on public files (capability altium-import, "Altium project sets agree" and "Component
body records"; change c0043).

test_project_sets: for every project set of the manifest, the netlist that the adapter computes from
the sheets equals the pad netlist of the set's PCB document, for every linked component. The report holds
counts and row ids only: no part name and no net name of a corpus file is printed.

test_bodies_identity: the body storages of every fetched PCB document and library decode and encode
back byte for byte, and every body's overall height is at least its standoff.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import PureWindowsPath

import pytest
from _corpus import MANIFEST, CorpusItem, corpus_items, heavy_enabled, manifest_items, require

from fenolite.backends.altium.adapter import connectivity as geo
from fenolite.backends.altium.adapter.netlist import NetOptions, Resolved, SheetInput, resolve
from fenolite.backends.altium.read.bodies import encode, read_bodies
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import BODY, PadRecord, RawPrimitive
from fenolite.backends.altium.read.project import read_project
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.core.errors import Issue

SHA = "0" * 64
KNOWN_DIFF = "altium-import:known-diff"
KNOWN_DIFFS = {"altium-set:02": 6}
"""Per set that carries ``altium-import:known-diff``, its count of differing groups; the cause is in the
notes of the set's project-file row and in ``docs/formats/altium/connectivity.md``. Set 02: two pins of two
four-pin components are unwired on their sheet (no wire within 15 units of either) and carry a net in the
PCB document. Each such pin gives three differing groups: the net without it, the pin alone, and the PCB
document's net with it."""
BODY_STORAGES = (("ComponentBodies6", False), ("ShapeBasedComponentBodies6", True))


def _sets() -> dict[str, list[CorpusItem]]:
    found: dict[str, list[CorpusItem]] = {}
    for item in manifest_items("altium-import"):
        (name,) = [use for use in item.uses if use.startswith("altium-set:")]
        found.setdefault(name, []).append(item)
    return dict(sorted(found.items()))


SETS = _sets()


@dataclass(frozen=True)
class SetResult:
    """The counts of one set: no value of a corpus file."""

    sheets: int
    instances: int
    scope: str
    nets: int
    pcb_nets: int
    linked_by_path: int
    linked_by_designator: int
    unlinked: int
    equal_members: int
    equal_names: int
    differing: int
    pads_without_pin: int
    pins_without_pad: int
    census: tuple[tuple[str, int], ...]


def _kind(item: CorpusItem) -> str:
    return item.id.rsplit("-", 2)[1]


def _crossings(wires: geo.Lines, junctions: set[geo.Pt]) -> int:
    """Pairs of wire segments of two wires that cross at a point interior to both, without a junction on
    it. Wires are drawn along the axes, so only a horizontal and a vertical segment are counted."""
    found = 0
    flat = [(n, a, b) for n, a, b in wires.segments if a[1] == b[1] and a[0] != b[0]]
    upright = [(n, a, b) for n, a, b in wires.segments if a[0] == b[0] and a[1] != b[1]]
    for n, a, b in flat:
        low, high = sorted((a[0], b[0]))
        for m, c, d in upright:
            bottom, top = sorted((c[1], d[1]))
            point = (c[0], a[1])
            found += n != m and low < c[0] < high and bottom < a[1] < top and point not in junctions
    return found


def _census(resolved: Resolved) -> tuple[tuple[str, int], ...]:
    """How often the rules that the hypotheses name are exercised by the sheets of a set."""
    found: Counter[str] = Counter()
    for sheet in resolved.sheets:
        found["harness-connectors"] += len(sheet.connectors)
        found["bus-identifiers"] += len(sheet.bus_idents)
        for net in sheet.nets:
            kinds = {ident.kind for ident in net.idents}
            found["nets-with-port-and-power"] += {"port", "power"} <= kinds
            found["nets-with-label-and-power"] += {"label", "power"} <= kinds
            found["off-sheet-connectors"] += sum(ident.kind == "offsheet" for ident in net.idents)
            found["no-connect-marks"] += net.no_connect
        labels = {i.text.casefold() for net in sheet.nets for i in net.idents if i.kind == "label"}
        powers = {i.text.casefold() for net in sheet.nets for i in net.idents if i.kind == "power"}
        found["label-and-power-of-one-name"] += len(labels & powers)
        document = sheet.input.document
        wires = geo.wire_lines(document)
        ends = [end for line in wires.lines for end in (line[0], line[-1])]
        vertices = {vertex for line in wires.lines for vertex in line}
        found["wire-ends-inside-other-wires"] += sum(
            1 for number, line in enumerate(wires.lines) for end in (line[0], line[-1])
            if any(other != number for other in wires.at(end)) and ends.count(end) == 1
        )  # fmt: skip
        found["junctions"] += len(document.junctions())
        found["crossings-without-a-junction"] += _crossings(
            wires, {geo.pt(j.location) for j in document.junctions()}
        )
        spelled = {i.text for net in sheet.nets for i in net.idents if i.kind == "label"}
        found["labels-that-differ-by-letter-case"] += len(spelled) - len(
            {text.casefold() for text in spelled}
        )
        texts = [i.text.casefold() for net in sheet.nets for i in net.idents if i.kind == "label"]
        found["labels-that-repeat-a-name"] += len(texts) - len(set(texts))
        for group in sheet.groups:
            for pin in group.shown:
                point = geo.pt(pin.hot_end)
                found["pin-ends-inside-segments"] += bool(wires.at(point)) and point not in vertices
        for port in document.ports():
            far = geo.port_ends(port)[1]
            found["ports-wired-at-the-far-end"] += bool(wires.at(far))
            found["ports-wired-at-the-location"] += bool(wires.at(geo.pt(port.location)))
        harness_names = {name.casefold() for _node, name in sheet.harness_labels}
        found["dotted-harness-labels"] += sum(
            1 for text in sheet.labels if "." in text and text.rpartition(".")[0] in harness_names
        )
    found["unnamed-nets"] = sum(
        net.name.startswith("Net") and not net.aliases for net in resolved.netlist.nets
    )
    found["harnesses"] = len(resolved.netlist.harnesses)
    found["buses"] = len(resolved.netlist.buses)
    found["instances-of-repeated-sheets"] = len(resolved.instances) - len(
        {i.sheet for i in resolved.instances}
    )
    return tuple(sorted(found.items()))


def compare(resolved: Resolved, document: PcbDocument) -> SetResult:
    """Compare the two partitions of (component, pad) pairs into nets, for the linked components. A pin is
    its pads through the pin-to-pad map of its footprint model (its own designator by default); a pair is
    compared when the sheets hold the pin and the PCB document the pad."""
    by_path: dict[str, str] = {}
    by_ref: dict[str, list[str]] = {}
    pads_of_pin: dict[tuple[str, str], tuple[str, ...]] = {}
    pin_table: dict[str, set[str]] = {}
    for (instance_index, number), native in resolved.component_ids.items():
        instance = resolved.instances[instance_index]
        group = resolved.sheets[instance.sheet].groups[number]
        prefix = "".join(f"\\{uid}" for uid in instance.uids)
        for unique in group.unique_ids:
            by_path.setdefault(f"{prefix}\\{unique}", native)
        by_ref.setdefault(group.ref, []).append(native)
        mapped = dict(group.pin_pads)
        for pin in group.pins:
            pads = mapped.get(pin.designator, (pin.designator,))
            pads_of_pin[(native, pin.designator)] = pads
            pin_table.setdefault(native, set()).update(pads)
    link: dict[int, str] = {}
    by_designator = unlinked = 0
    for index, component in enumerate(document.components):
        target = by_path.get(component.source_unique_id or "")
        if target is None:
            candidates = by_ref.get(component.source_designator or "", [])
            if component.source_designator and len(candidates) == 1:
                target = candidates[0]
                by_designator += 1
        if target is None:
            unlinked += 1
        else:
            link[index] = target
    board: dict[tuple[str, str], str | None] = {}
    pads_without_pin = 0
    for pad in document.pads:
        if not isinstance(pad, PadRecord) or pad.prefix.component not in link or not pad.name:
            continue
        key = (link[pad.prefix.component], pad.name)
        if pad.name not in pin_table.get(key[0], set()):
            pads_without_pin += 1
            continue
        name = document.net_name(pad.prefix.net)
        if board.get(key) is None:
            board[key] = name
    linked = set(link.values())
    sheets: dict[tuple[str, str], int] = {}
    names: dict[int, str] = {}
    pins_without_pad = 0
    for number, net in enumerate(resolved.netlist.nets):
        names[number] = net.name
        for pin in net.pins:
            if pin.component not in linked:
                continue
            for pad in pads_of_pin.get((pin.component, pin.designator), (pin.designator,)):
                if (pin.component, pad) in board:
                    sheets[(pin.component, pad)] = number
                else:
                    pins_without_pad += 1
    mine: dict[int, set[tuple[str, str]]] = {}
    theirs: dict[str, set[tuple[str, str]]] = {}
    lone_mine: set[frozenset[tuple[str, str]]] = set()
    lone_theirs: set[frozenset[tuple[str, str]]] = set()
    for key, name in board.items():
        if key in sheets:
            mine.setdefault(sheets[key], set()).add(key)
        else:
            lone_mine.add(frozenset({key}))
        if name is not None:
            theirs.setdefault(name, set()).add(key)
        else:
            lone_theirs.add(frozenset({key}))
    left = {frozenset(group) for group in mine.values()} | lone_mine
    right = {frozenset(group) for group in theirs.values()} | lone_theirs
    equal_names = sum(1 for number, group in mine.items() if theirs.get(names[number]) == group)
    return SetResult(
        sheets=len(resolved.sheets),
        instances=len(resolved.instances),
        scope=resolved.netlist.scope,
        nets=len(resolved.netlist.nets),
        pcb_nets=len(document.nets),
        linked_by_path=len(link) - by_designator,
        linked_by_designator=by_designator,
        unlinked=unlinked,
        equal_members=len({frozenset(g) for g in mine.values()} & {frozenset(g) for g in theirs.values()}),
        equal_names=equal_names,
        differing=len(left ^ right),
        pads_without_pin=pads_without_pin,
        pins_without_pad=pins_without_pad,
        census=_census(resolved),
    )


def run_set(items: list[CorpusItem]) -> tuple[SetResult, list[Issue]]:
    """Read the sheets that the set's project file lists, in document order, and its PCB document, each
    apart, and compare them."""
    (project_item,) = [item for item in items if _kind(item) == "prjpcb"]
    (board_item,) = [item for item in items if _kind(item) == "pcbdoc"]
    sheets_by_name = {item.path.name.casefold(): item for item in items if _kind(item) == "schdoc"}
    project = read_project(require(project_item).read_bytes(), file=project_item.id)
    sheets: list[SheetInput] = []
    for listed in project.documents:
        if listed.kind != "schematic":
            continue
        item = sheets_by_name.get(PureWindowsPath(listed.path).name.casefold())
        assert item is not None, f"{project_item.id}: document {listed.index} is no row of the set"
        # The file name stays in memory: sheet symbols name their sheets by it. It is never printed.
        document = read_schematic(require(item).read_bytes(), file=item.id)
        sheets.append(SheetInput(item.path.name, SHA, document))
    assert len(sheets) == len(sheets_by_name), f"{project_item.id}: a sheet row is not listed by the project"
    issues: list[Issue] = []
    resolved = resolve(sheets, NetOptions.from_project(project), issues)
    document = read_pcbdoc(require(board_item).read_bytes(), file=board_item.id)
    return compare(resolved, document), issues


def report(name: str, items: list[CorpusItem], result: SetResult, issues: list[Issue]) -> str:
    (project_item,) = [item for item in items if _kind(item) == "prjpcb"]
    codes = Counter(issue.code.removeprefix("altium.import.") for issue in issues)
    census = ", ".join(f"{key} {count}" for key, count in result.census if count)
    return (
        f"{name} ({project_item.id}): sheets {result.sheets}, instances {result.instances}, scope "
        f"{result.scope}, nets {result.nets} (PCB document {result.pcb_nets}), components linked by path "
        f"{result.linked_by_path}, by designator {result.linked_by_designator}, unlinked {result.unlinked}, "
        f"nets equal by members {result.equal_members}, also by name {result.equal_names}, differing "
        f"groups {result.differing}, pads without a pin {result.pads_without_pin}, pins without a pad "
        f"{result.pins_without_pad}; issues {dict(sorted(codes.items()))}; census: {census}"
    )


def test_sets_of_the_manifest_cover_three_repositories() -> None:
    """Runs without the corpus: the sets come from the manifest alone."""
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"]
    repositories = set()
    for row in rows:
        if any(use.startswith("altium-set:") for use in row["uses"]) and "-prjpcb-" in row["id"]:
            parts = [part for part in row["url"].split("/")[3:] if part != "media"]
            repositories.add(tuple(parts[:2]))
    assert len(SETS) >= 3 and len(repositories) >= 3


@pytest.mark.needs_corpus
@pytest.mark.parametrize("name", list(SETS))
def test_project_sets(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    items = SETS[name]
    if any(item.heavy for item in items) and not heavy_enabled():
        pytest.skip(f"{name} holds a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    result, issues = run_set(items)
    with capsys.disabled():
        print("\n" + report(name, items, result, issues))
    assert result.unlinked == 0 and result.linked_by_path >= 0.95 * (
        result.linked_by_path + result.linked_by_designator
    )
    (project_item,) = [item for item in items if _kind(item) == "prjpcb"]
    if KNOWN_DIFF in project_item.uses:
        assert name in KNOWN_DIFFS, f"{name}: {KNOWN_DIFF} without a recorded count"
        assert result.differing == KNOWN_DIFFS[name], f"{name}: the count of differing groups changed"
        return
    assert result.differing == 0, f"{name}: {result.differing} groups of pads differ between sheets and PCB"


@pytest.mark.needs_corpus
def test_bodies_identity(capsys: pytest.CaptureFixture[str]) -> None:
    """bodies_identity: every body storage is rebuilt byte for byte, and every body that frames has an
    overall height of at least its standoff (H-A-IMP-BODY)."""
    lines: list[str] = []
    total = 0
    for item in corpus_items("altium-pcbdoc"):
        document = read_pcbdoc(require(item).read_bytes(), file=item.id)
        counts: list[int] = []
        for storage, shape_based in BODY_STORAGES:
            data = document.storages.get(storage, {}).get("Data", b"")
            issues: list[Issue] = []
            records = read_bodies(data, shape_based=shape_based, storage=storage, issues=issues)
            assert encode(records) == data and issues == [], (item.id, storage)
            for record in records:
                assert record.framed and record.tail == b"", (item.id, storage, record.index)
                overall, standoff = record.overall_height, record.standoff_height
                assert overall is not None and standoff is not None and overall >= standoff, (
                    item.id,
                    record.index,
                )
                assert record.component is None or record.component < len(document.components)
            counts.append(len(records))
        assert counts[0] == counts[1], item.id
        total += counts[0]
        lines.append(f"{item.id}: {counts[0]} bodies in each storage")
    for item in corpus_items("altium-pcblib"):
        library = read_pcblib(require(item).read_bytes(), file=item.id)
        count = 0
        for footprint in library.footprints:
            for primitive in footprint.primitives:
                if isinstance(primitive, RawPrimitive) and primitive.type == BODY:
                    records = read_bodies(primitive.raw, storage=footprint.storage)
                    assert encode(records) == primitive.raw and all(r.framed for r in records), item.id
                    count += len(records)
        total += count
        lines.append(f"{item.id}: {count} bodies")
    with capsys.disabled():
        print("\n" + "\n".join(lines))
    assert total > 0


# --- the items of a component (capability altium-import, "Graphics, fields and texts of a component") ----

ITEM_ROWS = [item for item in manifest_items("rta") if "-pcbdoc-" in item.id]
ITEM_KINDS = ("tracks", "arcs", "fills", "regions", "texts")


@pytest.mark.needs_corpus
@pytest.mark.parametrize("item", ITEM_ROWS, ids=lambda item: item.id)
def test_footprint_items_conserve_the_census(item: CorpusItem, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "The census is conserved on the corpus" (``H-A-IMP-FPGFX``; change c0126): on every public
    PCB document with the use ``rta``, the mapped and the unmapped counts of each kind add up to the
    reader's record count, every primitive that carries the index of a component with a readable position
    is an item of its footprint or one of the two counted cases (a primitive on an internal plane, an arc
    or a region without a shape), and the category ``footprint-graphics`` holds the plane primitives alone.
    Prints the number of graphics, fields and texts per document for the evidence page (``-s``). Counts
    only: no name and no value of a document is printed."""
    from collections import Counter

    from _boards import census

    from fenolite.backends.altium.adapter.board import read_board
    from fenolite.backends.altium.adapter.copper import owned_primitives
    from fenolite.backends.altium.adapter.evidence import EVIDENCE
    from fenolite.backends.altium.adapter.ids import Ids

    path = require(item)
    data = path.read_bytes()
    document = read_pcbdoc(data, file=path.name)
    parts = read_board(document, file=path.name, sha256=SHA, ids=Ids("altium_pcbdoc", EVIDENCE))
    for kind in ITEM_KINDS:
        assert parts.census.total(kind) == len(getattr(document, kind)), kind
    owned = owned_primitives(document)
    carried = sum(len(getattr(held, kind)) for held in owned.values() for kind in ITEM_KINDS)
    footprints = [fp for fp in parts.board.footprints if "board_only" not in fp.attributes]
    graphics = sum(len(fp.graphics) for fp in footprints)
    fields = sum(len(fp.fields) for fp in footprints)
    texts = sum(len(fp.texts) for fp in footprints)
    layers = Counter(
        "copper"
        if g.layer.endswith(".Cu")
        else g.layer.split(".")[0]
        if g.layer.startswith("Mech.")
        else g.layer
        for fp in footprints
        for g in fp.graphics
    )
    left = parts.census.categories().get("footprint-graphics", 0)
    entry = {
        "carried": carried,
        "graphics": graphics,
        "fields": fields,
        "texts": texts,
        "footprint_graphics_left": left,
        "by_layer": dict(sorted(layers.items())),
    }
    census("altium-import", f"{item.id}:footprint-items", entry)
    with capsys.disabled():
        print(f"\n{item.id}: {entry}")
    # every carried primitive is an item of its footprint: measured on 2026-10-08 on the eight documents
    # (16 647 primitives; none on an internal plane, none without a shape, no component without a position)
    assert graphics + fields + texts == carried
    assert left == 0
    assert (
        len({g.id for fp in footprints for g in (*fp.graphics, *fp.texts, *fp.fields)})
        == graphics + texts + fields
    )
