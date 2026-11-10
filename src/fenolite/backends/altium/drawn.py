# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn sheets as native Altium records (c0276), with explicit loss and connectivity checks.

Record forms are those already recorded in docs/formats/altium/schematic-records.md. Choices of
colours and text placement reuse schdoc; application acceptance remains H-A-DRAWN-WRITE, INFERRED.
All coordinate arithmetic uses integer counts of 1/100000 of a ten-mil unit.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

import fenolite.backends.altium.drawn_carrier as drawn_carrier
import fenolite.backends.altium.drawn_harness as drawn_harness
import fenolite.backends.altium.drawn_read as drawn_read
import fenolite.backends.altium.schdoc as schdoc
from fenolite.backends.altium.altsym import HIDDEN, NM_PER_MIL, STEPS, AltiumSymbol
from fenolite.backends.altium.ascii import Field, TextForm, format_record, text_problem
from fenolite.backends.altium.hierarchy import ProjectSheets, SheetFile, SheetLink
from fenolite.backends.altium.layout import (
    SHEET_SIZES,
    HarnessBlock,
    PartSpec,
    PlacedPart,
    SheetPlan,
    SheetSize,
)
from fenolite.backends.altium.project import unique_id
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.drawn import DrawnInstance, DrawnSchematic, DrawnSheet, DrawnSheetRef, DrawnSymbol
from fenolite.model.drawn_connect import (
    UnitInfo,
    bus_group_parts,
    bus_vector,
    component_path,
    coverage,
    expand,
    instances,
    issue,
)

if TYPE_CHECKING:
    from fenolite.backends.altium.adapter.netlist import Resolved
    from fenolite.backends.altium.read.sch import SchDocument

Record = list[Field]
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-DRAWN-WRITE",))
UNIT_SCALE = 100_000
# One native fractional unit is 127/50 nm (the existing schematic-records.md unit).
NM_NUMERATOR, NM_DENOMINATOR = 50, 127
PORT_WIDTH = 100 * 10_000
"""The width of a written port: 100 mil in file units."""
PORT_NM = 100 * NM_PER_MIL
_IO = {"input": "2", "output": "1", "bidirectional": "3", "tri_state": "3"}
_COORD = re.compile(r"(?:LOCATION|CORNER)\.X|X[0-9]+")
_BUS_MEMBER = re.compile(r"^(.+?)([0-9]+)$")


def _aliases(drawn: DrawnSchematic, sheet: DrawnSheet) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, tuple[str, ...]] = {}
    for other in drawn.sheets:
        for alias in other.bus_aliases:
            aliases.setdefault(alias.name, alias.members)
    aliases.update((alias.name, alias.members) for alias in sheet.bus_aliases)
    return aliases


def _group_members(text: str, aliases: Mapping[str, tuple[str, ...]]) -> tuple[str, tuple[str, ...]] | None:
    """The name and entries of a named bus group ``text`` that is no native bus vector: ``UART{TX, RX}``
    gives ``UART`` and ``TX``, ``RX``; ``None`` for anything else."""
    parts = bus_group_parts(text)
    if parts is None or not parts[0] or bus_vector(text) is not None:
        return None
    members = expand(text, aliases)
    prefix = parts[0] + "."
    if not members or any(not member.startswith(prefix) for member in members):
        return None
    return parts[0], tuple(member[len(prefix) :] for member in members)


def _native_buses(
    drawn: DrawnSchematic, sheet: DrawnSheet, where: str, issues: list[Issue], harness: bool = False
) -> DrawnSheet:
    """Lower only bus-anchored identifiers, preserving the exact scalar member set (S-0301). With ``harness``
    a named bus group of a hierarchical label or a sheet pin is kept: it is written as a harness."""
    aliases = _aliases(drawn, sheet)
    harnesses = harness

    def on(at: Point, segments: Sequence[tuple[Point, Point]]) -> bool:
        return any(
            (at.x - a.x) * (b.y - a.y) == (at.y - a.y) * (b.x - a.x)
            and min(a.x, b.x) <= at.x <= max(a.x, b.x)
            and min(a.y, b.y) <= at.y <= max(a.y, b.y)
            for a, b in segments
        )

    def name(text: str, at: Point, locator: str, harness: bool = False) -> str:
        if not on(at, sheet.bus_segments()) or on(at, sheet.segments()):
            return text
        if harness and harnesses and _group_members(text, aliases) is not None:
            return text  # a harness (change c0470, ``drawn_harness``)
        if (
            harness
            and harnesses
            and (empty := bus_group_parts(text)) is not None
            and empty[0]
            and not empty[1]
        ):
            return text  # a harness type that no connector defines: an empty group (change c0470)
        members = expand(text, aliases)
        if members is None or (bus_vector(text) is not None and text not in aliases):
            return text
        parsed = [_BUS_MEMBER.fullmatch(member) for member in members]
        if not parsed or any(match is None for match in parsed):
            raise FormatError(f"bus {text!r} has no exact native bus vector; a signal harness is required",
                              locator=locator)  # fmt: skip
        pairs = [(match[1], int(match[2])) for match in parsed if match is not None]
        prefix, first = pairs[0]
        indices = sorted({index for _, index in pairs})
        replacement = f"{prefix}[{indices[0]}..{indices[-1]}]"
        if (
            any(stem != prefix for stem, _ in pairs)
            or len(indices) != len(members)
            or indices[-1] - indices[0] + 1 != len(indices)
            or set(expand(replacement, {}) or ()) != set(members)
        ):
            raise FormatError(f"bus {text!r} has no exact native bus vector; a signal harness is required",
                              locator=locator)  # fmt: skip
        if first == indices[-1] and len(indices) > 1:
            replacement = f"{prefix}[{indices[-1]}..{indices[0]}]"
        issues.append(
            Issue(
                "altium.not-lowered",
                "info",
                f"bus identifier {text!r} is written as native bus vector {replacement!r}; "
                "drawn identifier text is changed, scalar members are preserved",
                where=locator,
            )
        )
        return replacement

    return replace(
        sheet,
        labels=tuple(
            replace(
                label,
                text=name(
                    label.text,
                    label.at,
                    f"{where}.label[{index}]",
                    label.kind in ("local", "hierarchical"),
                ),
            )
            for index, label in enumerate(sheet.labels)
        ),
        sheet_refs=tuple(
            replace(
                ref,
                pins=tuple(
                    replace(
                        pin, name=name(pin.name, pin.at, f"{where}.sheet_ref.{ref.key}.pin[{index}]", True)
                    )
                    for index, pin in enumerate(ref.pins)
                ),
            )
            for ref in sheet.sheet_refs
        ),
    )


class DrawnLossError(FenoliteError):
    """A drawn point needs a rounding that the caller has not accepted."""

    cli_code = "FEN-7001"
    hint = "review the named point, then use --allow-lossy to accept its reported rounding"

    def __init__(self, finding: Issue) -> None:
        self.issues = (finding,)
        super().__init__(finding.message)


class _DrawnStyleLoss(DrawnLossError):
    """A new explicit drawn style has no proved native lowering."""

    hint = "review the named source style, then use --allow-lossy to accept its reported loss"


def _style_losses(sheet: DrawnSheet, where: str) -> tuple[Issue, ...]:
    styles: list[tuple[str, str]] = []
    for kind, items in (("symbol", sheet.symbols), ("power", sheet.powers)):
        for index, item in enumerate(items):
            for field in item.fields:
                if field.font is not None:
                    styles.append((f"{kind}[{index}].fields.{field.name}.font", "font"))
    for index, label in enumerate(sheet.labels):
        if label.font is not None:
            styles.append((f"label[{index}].font", "font"))
        if label.justify is not None:
            styles.append((f"label[{index}].justify", "justification"))
    for ref in sheet.sheet_refs:
        base = f"sheet_ref.{ref.key}"
        for prop in ref.properties:
            styles.append((f"{base}.properties.{prop.name}", "custom sheet property text/pose/effects"))
        for field in ref.fields:
            styles.append((f"{base}.fields.{field.name}", "sheet-property pose/effects"))
        for index, pin in enumerate(ref.pins):
            if pin.font is not None:
                styles.append((f"{base}.pin[{index}].font", "font"))
            if pin.justify is not None:
                styles.append((f"{base}.pin[{index}].justify", "justification"))
    return tuple(
        Issue(
            "altium.not-lowered",
            "info",
            f"explicit drawn {kind} at {where}.{path} has no proved Altium lowering",
            where=f"{where}.{path}",
            hint=_DrawnStyleLoss.hint,
        )
        for path, kind in styles
    )


def _round(value: int, divisor: int) -> int:
    sign = -1 if value < 0 else 1
    return sign * ((abs(value) * 2 + divisor) // (2 * divisor))


def _fields(key: str, value: int) -> Record:
    sign = -1 if value < 0 else 1
    whole, fraction = divmod(abs(value), UNIT_SCALE)
    return [(key, str(sign * whole)), *([(f"{key}_FRAC", str(sign * fraction))] if fraction else [])]


def _value(record: Mapping[str, str], key: str) -> int:
    return int(record.get(key, "0")) * UNIT_SCALE + int(record.get(f"{key}_FRAC", "0"))


def _turn(x: int, y: int, rotation: int, mirror: str = "") -> tuple[int, int]:
    for _ in range(rotation % 4):
        x, y = -y, x
    if mirror == "x":
        y = -y
    elif mirror == "y":
        x = -x
    return x, y


POWER_LIBRARY = "AltiumPower"
"""The library of the KiCad power symbols that stand for Altium power port styles (change c0470,
``drawn_read.POWER_LIBRARY``)."""
POWER_STYLES: tuple[str, ...] = (
    "circle", "arrow", "bar", "wave", "power_ground", "signal_ground", "earth", "gost_arrow",
    "gost_power_ground", "gost_earth", "gost_bar",
)  # fmt: skip
"""``STYLE`` 0 to 10 of a power port (``drawn_read.POWER_STYLES``)."""
TITLE_NAMES = {
    "title": "Title", "revision": "Revision", "date": "Date", "organization": "CompanyName",
    "doc_id": "DocumentNumber", "responsible": "DrawnBy", "approver": "ApprovedBy",
}  # fmt: skip
"""Title-block field → the document parameter a sheet template shows (``drawn_read.TITLE_PARAMETERS``)."""
HARNESS_GROWTH = 2_000
"""How far, in mil, a sheet without free space for a harness block grows to the right (change c0470)."""
HARNESS_GROWTHS = 3
"""How often it grows before the drawing is refused."""
_MODELLED = frozenset(
    {None, "0", "1", "2", "15", "16", "17", "18", "22", "25", "26", "27", "29", "31", "32", "33", "34", "37",
     "41"}
)  # fmt: skip
"""The ``RECORD`` of a root record that an opaque item must not hold: a drawn item or the framework writes
it."""
_OWNERS = frozenset({"OWNERINDEX", "OWNERINDEXADDITIONALLIST", "OWNERINDEXADDITIONALRECORD"})
_COLUMNS = {"left": 0, "right": 2}
_ROWS = {"bottom": 0, "top": 2}
_FLIP = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}


def _justification(words: Sequence[str], turn: int) -> int:
    """The ``JUSTIFICATION`` of a parameter (``docs/formats/altium/sheet-template.md``: 0 bottom left to 8
    top right) that shows the KiCad justification ``words`` at quarter turn ``turn``: Altium anchors a text
    turned by two or three quarters at its opposite corner, so the words flip (change c0470)."""
    if turn % 4 >= 2:
        words = [_FLIP.get(word, word) for word in words]
    column = next((_COLUMNS[word] for word in words if word in _COLUMNS), 1)
    row = next((_ROWS[word] for word in words if word in _ROWS), 1)
    return row * 3 + column


def _orientation(quarter: int, mirror: str) -> int:
    """The ``ORIENTATION`` of a component turned ``quarter`` quarter turns and then mirrored (KiCad order).
    Altium mirrors the part about its vertical axis before it turns it (``drawn_read._mirror``): ``y`` at an
    even orientation, ``x`` at an odd one. A mirror about X is a mirror about Y turned by a half turn
    (change c0470)."""
    if not mirror:
        return quarter % 4
    turn = (quarter + 2) % 4 if mirror == "x" else quarter % 4
    return turn if turn % 2 == 0 else (turn + 2) % 4


class _Sheet:
    def __init__(
        self,
        plan: SheetPlan,
        issues: list[Issue],
        allow_lossy: bool,
        form: TextForm,
        carry: bool = False,
        harness: bool | None = None,
    ) -> None:
        self.plan = plan
        self.carry = carry
        self.harness = carry if harness is None else harness
        """Whether a KiCad bus group that crosses a sheet is written as a signal harness (``drawn_harness``):
        always in a conversion, and in a build (change c0470)."""
        self.height = plan.size.height * 10_000
        self.issues = issues
        self.allow_lossy = allow_lossy
        self.form: TextForm = form
        self.records: list[Record] = []
        self.poses: list[PlacedPart] = []
        self.origin = ""
        """With ``carry``, the key of the KiCad sheet of which this sheet is one instance's copy (c0470)."""
        self.origin_file = ""
        self.origin_parts: dict[str, str] = {}
        self.bodies: Mapping[str, AltiumSymbol] = {}
        """With ``carry``, the own body of a component, by reference, whose instance differs from the library
        symbol of its link (change c0470)."""
        self.spellings: Mapping[tuple[int, int], str] = {}
        """With ``carry``, the own text of each net label that the reader wrote in the letter case of another
        label of its net (``drawn_read.one_spelling``), by its position (change c0470)."""
        self.lone_harness: Mapping[tuple[str, str], str] = {}
        """With ``carry``, the ``HARNESSTYPE`` of each sheet entry that the carrier keeps, by (sheet name,
        entry name) (change c0470): the type of an entry drawn as the empty group ``NAME{}``, or "" for an
        entry whose record holds none."""
        self.sheet_fields: Mapping[str, Mapping[str, str]] = {}
        """The Altium fields and sheet records carried for this sheet (change c0473)."""
        self.definitions: Mapping[str, str] = {}
        """With ``carry``, the KiCad library text of this sheet's carried opaque symbol definitions."""
        self.power_in: Mapping[str, frozenset[str]] = {}
        """Per component path, the numbers of its KiCad power-input pins (the circuit's pin types)."""
        self.hidden_pins: list[tuple[str, Point, str]] = []
        """With ``carry``, the net, sheet point and locator of each hidden power pin whose net its name gives:
        KiCad joins such a pin to that net, Altium joins no hidden pin by its name (S-0185), so a carried
        power port stands at its end (change c0470)."""
        self.coordinates: dict[int, set[int]] = {}
        """Each coordinate ``point`` wrote (fraction units, Y from the top) and the nm lengths it came
        from."""
        self.harness_types: Mapping[tuple[str, ...], str] = {}
        """With ``carry``, the harness type of each set of entries that a carried connector holds (c0470)."""
        self.aliases: Mapping[str, tuple[str, ...]] = {}
        self.groups: list[drawn_harness.GroupEnd] = []
        self.harness_buses: set[int] = set()
        """The KiCad buses of ``groups``, written as signal harness lines."""
        """With ``carry``, each port and sheet entry written for a KiCad bus group (``drawn_harness``)."""

    def group(self, text: str) -> tuple[str, str] | None:
        """With ``carry``, the name and harness type of a port or sheet entry of the bus group ``text``
        (``drawn_harness``); ``None`` when ``text`` is no named bus group."""
        found = _group_members(text, self.aliases) if self.harness else None
        if found is None:
            return None
        return found[0], drawn_harness.harness_type(found[1])

    def mils(self, at: Point, where: str) -> tuple[int, int]:
        x, y = self.point(at, where)
        if x % drawn_harness.MIL or y % drawn_harness.MIL:
            raise FormatError(
                "a point of a bus group is off the 1-mil grid; no harness is written", locator=where
            )
        return x // drawn_harness.MIL, y // drawn_harness.MIL

    def networks(self, sheet: DrawnSheet, where: str) -> None:
        """With ``carry``, the harness of each named bus group of ``sheet``'s hierarchical labels and sheet
        pins (``drawn_harness.GroupEnd``): the ends that its KiCad buses join, written as one harness."""
        ends: list[tuple[Point, str, str]] = []

        def new(text: str) -> bool:  # a KiCad bus group, not an Altium harness type that a carrier holds
            group = bus_group_parts(text)
            return self.group(text) is not None and (
                group is None or sorted_entries(group[1]) not in self.harness_types
            )

        for index, label in enumerate(sheet.labels):
            if label.kind == "hierarchical" and new(label.text):
                ends.append((label.at, label.text, f"{where}.label[{index}]"))
        for ref in sheet.sheet_refs:
            for index, pin in enumerate(ref.pins):
                if new(pin.name):
                    ends.append((pin.at, pin.name, f"{where}.sheet_ref.{ref.key}.pin[{index}]"))
        if not ends:
            return

        def on(at: Point, line: Sequence[Point]) -> bool:
            pairs = zip(line, line[1:], strict=False)
            return any(drawn_harness.on_segment((at.x, at.y), (a.x, a.y), (b.x, b.y)) for a, b in pairs)

        buses = list(sheet.buses)
        owner = list(range(len(buses) + len(ends)))

        def root(index: int) -> int:
            while owner[index] != index:
                owner[index] = owner[owner[index]]
                index = owner[index]
            return index

        for i, line in enumerate(buses):
            for j in range(i):
                if any(on(p, buses[j]) for p in line) or any(on(p, line) for p in buses[j]):
                    owner[root(i)] = root(j)
        for k, (at, _, _) in enumerate(ends):
            for i, line in enumerate(buses):
                if on(at, line):
                    owner[root(len(buses) + k)] = root(i)
        groups: dict[int, list[int]] = {}
        for k in range(len(ends)):
            groups.setdefault(root(len(buses) + k), []).append(k)
        label_texts = {label.text for label in sheet.labels}
        by_key: dict[tuple[tuple[str, ...], str], int] = {}
        for number, members in groups.items():
            # KiCad joins the bus groups on one bus by their member names: one harness, named by each
            found = [_group_members(ends[k][1], self.aliases) for k in members]
            first = ends[members[0]]
            entries = found[0][1] if found[0] is not None else ()
            if any(item is None or item[1] != entries for item in found):
                texts = ", ".join(sorted({ends[k][1] for k in members}))
                raise FormatError(f"one KiCad bus joins the bus groups {texts}", locator=first[2])
            names = tuple(dict.fromkeys(item[0] for item in found if item is not None))
            if len(names) > drawn_harness.STUB // 100:
                raise FormatError("one KiCad bus joins more than three bus group names", locator=first[2])
            lines = [i for i in range(len(buses)) if root(i) == number]
            self.harness_buses.update(lines)
            network = tuple(tuple(self.mils(p, f"{where}.bus[{i}]") for p in buses[i]) for i in lines)
            starts = {p for line in network for p in line}
            starts.update(self.mils(ends[k][0], ends[k][2]) for k in members)
            present = tuple(e for e in entries if any(f"{group}.{e}" in label_texts for group in names))
            kind = drawn_harness.harness_type(entries)
            # a bus between sheet entries whose members no label of this sheet names needs no block
            through = len(members) > 1 and not present
            end = drawn_harness.GroupEnd(
                tuple(sorted(starts)),
                network,
                names,
                present or entries,
                kind,
                first[2],
                through=through,
            )
            if not through and (names, kind) in by_key:
                # one connector block of a harness on a sheet joins every end of its name there
                earlier = self.groups[by_key[(names, kind)]]
                self.groups[by_key[(names, kind)]] = replace(
                    earlier,
                    starts=tuple(sorted(set(earlier.starts) | starts)),
                    network=(*earlier.network, *network),
                )
            else:
                if not through:
                    by_key[(names, kind)] = len(self.groups)
                self.groups.append(end)

    def harness_blocks(
        self,
        paper: str = "",
    ) -> tuple[
        list[HarnessBlock],
        list[tuple[tuple[int, int], tuple[int, int]]],
        list[tuple[tuple[int, int], ...]],
        drawn_carrier.Json | None,
    ]:
        """The block of each harness (``drawn_harness.place_all``), with its member wires and labels
        written here, the lines of the blocks and of the KiCad buses, and what the carrier lists for the
        reader: the block's items to drop and the buses whose harness line it reads as a bus."""
        if not self.groups:
            return [], [], [], None
        size = (self.plan.size.width, self.plan.size.height)
        blocked = [end for end in self.groups if not end.through]
        placements = drawn_harness.place_all(blocked, self.records, self.height, size) if blocked else []
        grew = False
        for _ in range(HARNESS_GROWTHS):
            if not isinstance(placements, drawn_harness.GroupEnd):
                break
            # a full sheet grows to the right, where nothing is drawn; its height, and so every written
            # point, stays (change c0470)
            size = (size[0] + HARNESS_GROWTH, size[1])
            placements = drawn_harness.place_all(blocked, self.records, self.height, size)
            if not isinstance(placements, drawn_harness.GroupEnd):
                grew = True
                self.plan = replace(self.plan, size=SheetSize("custom", size[0], size[1], None))
                self.issues.append(
                    Issue(
                        "altium.sheet-custom",
                        "warning",
                        f"the sheet has no free space for a harness block; a custom sheet of {size[0]} x "
                        f"{size[1]} mil is written",
                        where=self.groups[0].where,
                    )
                )
        if isinstance(placements, drawn_harness.GroupEnd):
            raise FormatError(
                f"no free space for the harness block of bus group {placements.names[0]!r}",
                locator=placements.where,
            )
        blocks: list[HarnessBlock] = []
        lines: list[tuple[tuple[int, int], tuple[int, int]]] = []
        drop: drawn_carrier.Json = {
            "wires": [], "labels": [], "connectors": [], "lines": [], "networks": [], "ends": []
        }  # fmt: skip
        if grew and paper:
            drop["paper"] = paper
        polylines: list[tuple[tuple[int, int], ...]] = []

        def nm(point: tuple[int, int]) -> Point:
            return Point(point[0] * NM_PER_MIL, point[1] * NM_PER_MIL)

        def xy(point: tuple[int, int]) -> list[int]:
            return [point[0] * NM_PER_MIL, point[1] * NM_PER_MIL]

        for end in self.groups:
            if end.through:  # its harness lines alone join its entries (change c0470)
                drop["ends"] += [{"at": xy(p)} for p in end.starts]
                for line in end.network:
                    polylines.append(line)
                    drop["networks"].append({"pts": [xy(p) for p in line]})
        for end, placed in zip(blocked, placements, strict=True):
            blocks.append(placed.block)
            lines += placed.lines
            drop["ends"] += [{"at": xy(p)} for p in end.starts]
            for line in end.network:
                polylines.append(line)
                drop["networks"].append({"pts": [xy(p) for p in line]})
            block = placed.block
            drop["connectors"].append({"at": xy((block.x, block.y))})
            for start, stop in (*placed.lines, block.line):
                drop["lines"].append({"pts": [xy(start), xy(stop)]})
            for index, (start, stop, entry) in enumerate(placed.stubs):
                locator = f"{end.where}.harness[{index}]"
                self.polyline((nm(start), nm(stop)), False, locator)
                drop["wires"].append({"pts": [xy(start), xy(stop)]})
                # each name of the harness labels the member's wire, 100 mil apart from its far end
                back = -100 if stop[0] > start[0] else 100
                for number, name in enumerate(end.names):
                    text = drawn_carrier.altium_text(f"{name}.{entry}")
                    at = (stop[0] + number * back, stop[1])
                    self.identifier(text, nm(at), 0, "local", "", locator)
                    drop["labels"].append({"text": text, "at": xy(at)})
        return blocks, lines, polylines, {key: value for key, value in drop.items() if value}

    def native(self, at: Point, where: str) -> tuple[int, int]:
        """The native point of ``at``: its fields ``X`` and ``Y`` as ``location`` writes them."""
        x, y = self.point(at, where)
        return x, self.height - y

    def point(self, at: Point, where: str) -> tuple[int, int]:
        values = (at.x * NM_NUMERATOR, at.y * NM_NUMERATOR)
        if any(value % NM_DENOMINATOR for value in values):
            finding = issue(
                "drawn.coordinate-rounded",
                f"drawn point ({at.x}, {at.y}) nm at {where} needs rounding to Altium's 127/50 nm step",
                where,
                DrawnLossError.hint,
            )
            if not self.allow_lossy:
                raise DrawnLossError(finding)
            self.issues.append(finding)
        found = tuple(_round(value, NM_DENOMINATOR) for value in values)
        for length, value in zip((at.x, at.y), found, strict=True):
            self.coordinates.setdefault(value, set()).add(length)
        return found  # type: ignore[return-value]

    def exact(self) -> dict[int, int]:
        """Each written coordinate that only one length off the 127/50 nm step was rounded to, and that
        length: the reader puts it back (change c0470, task 5.4). A coordinate also written from another
        length is left rounded."""
        found: dict[int, int] = {}
        for value, lengths in self.coordinates.items():
            if len(lengths) == 1:
                (length,) = lengths
                if length * NM_NUMERATOR % NM_DENOMINATOR:
                    found[value] = length
        return found

    def location(self, at: Point, where: str, name: str = "LOCATION") -> Record:
        x, y = self.point(at, where)
        return [*_fields(f"{name}.X", x), *_fields(f"{name}.Y", self.height - y)]

    def add(self, record: Record, where: str = "", read: bool = False) -> int:
        # Sheet record is inserted by schdoc, so the first explicit record has native index 1.
        # A parameter text is held to the rule its plan applied (``project.parameters_of``, read=True).
        # ``read``: a record an Altium document held, written again with the reader's rule (change c0470).
        parameter = dict(record).get("RECORD") == "41"
        for key, value in record:
            try:
                format_record([(key, "")])
            except ValueError as error:
                raise FormatError(str(error), locator=where or f"record[{len(self.records)}]") from None
            loose = parameter and key == "TEXT"
            # a conversion (``carry``) writes the text its source holds, with its ``%UTF8%`` twin
            held = loose or read or self.carry
            problem = text_problem(value, form=self.form, parameter=loose, read=held) if value else None
            if problem is not None:
                raise FormatError(
                    f"Altium field {key}: {problem}", locator=where or f"record[{len(self.records)}]"
                )
        self.records.append(record)
        return len(self.records)

    def component(self, spec: PartSpec, symbol: DrawnSymbol, where: str, symbol_index: int = -1) -> None:
        anchor_x, anchor_y = self.point(symbol.at, where)
        quarter = symbol.rotation // 90_000_000
        if symbol.mirror:
            self.issues.append(Issue("altium.not-lowered", "info", "the component mirror is carried by "
                                     "absolute child geometry; its native mirror metadata is unverified",
                                     where=where))  # fmt: skip
        comp_gfx = self.sheet_fields.get(f"comp_gfx:{symbol_index}", {})
        pose_key = f"{symbol.at.x},{symbol.at.y},{symbol.rotation},{symbol.mirror}"
        use_carried_gfx = comp_gfx.get("POSE") == pose_key and bool(comp_gfx.get("RECORDS"))
        origin = 1_000_000
        placed = PlacedPart(spec, origin, origin, (0, 0, 0, 0), symbol.unit)
        offset = len(self.records) + 1
        for original in schdoc.component_records(placed):
            record = dict(original)
            if use_carried_gfx and record.get("RECORD") in {"6", "7", "8", "13", "14"}:
                continue
            points: dict[str, Record] = {}
            for key in record:
                if not _COORD.fullmatch(key):
                    continue
                ykey = key.replace(".X", ".Y") if ".X" in key else "Y" + key[1:]
                x, y = _turn(
                    _value(record, key) - origin * 10_000,
                    _value(record, ykey) - origin * 10_000,
                    quarter,
                    symbol.mirror,
                )
                points[key] = [*_fields(key, anchor_x + x), *_fields(ykey, self.height - anchor_y + y)]
            coordinates = {k for values in points.values() for k, _ in values}
            coordinates |= {key for key in record if key.endswith("_FRAC") and key[:-5] in coordinates}
            output: Record = []
            consumed: set[str] = set()
            for key, value in original:
                if key in points:
                    output.extend(points[key])
                    consumed.update(k for k, _ in points[key])
                    continue
                if key in coordinates or key in consumed:
                    continue
                if key == "OWNERINDEX":
                    value = str(int(value) + offset)
                elif key == "PINCONGLOMERATE":
                    number = int(value)
                    dx, dy = _turn(*STEPS[number & 3], quarter, symbol.mirror)
                    direction = next(k for k, vector in STEPS.items() if vector == (dx, dy))
                    value = str((number & ~3) | direction)
                output.append((key, value))
            if record.get("RECORD") == "2" and self.carry:
                self.hidden_pin(spec, dict(output), f"{where}.pin")
            if record.get("RECORD") == "1":
                output.append(("ORIENTATION", str(_orientation(quarter, symbol.mirror))))
                if symbol.mirror:
                    output.append(("ISMIRRORED", "T"))
            if record.get("RECORD") == "14":
                rectangle = dict(output)
                x0, x1 = sorted((_value(rectangle, "LOCATION.X"), _value(rectangle, "CORNER.X")))
                y0, y1 = sorted((_value(rectangle, "LOCATION.Y"), _value(rectangle, "CORNER.Y")))
                output = [(key, value) for key, value in output
                          if not key.startswith(("LOCATION.", "CORNER."))]  # fmt: skip
                output += [*_fields("LOCATION.X", x0), *_fields("LOCATION.Y", y0),
                           *_fields("CORNER.X", x1), *_fields("CORNER.Y", y1)]  # fmt: skip
            name = record.get("NAME", "")
            field_name = {"Designator": "Reference", "Comment": "Value"}.get(name, name)
            pose = next((p for p in symbol.fields if p.name == field_name), None)
            if pose is not None and record.get("RECORD") in {"34", "41"}:
                output = [
                    (k, v)
                    for k, v in output
                    if not k.startswith("LOCATION.")
                    and k not in {"ORIENTATION", "ISHIDDEN", "JUSTIFICATION", "ISMIRRORED"}
                ]
                output += self.location(pose.at, f"{where}.fields.{field_name}")
                turn = pose.rotation // 90_000_000
                output.append(("ORIENTATION", str(turn)))
                words = pose.justify.split()
                justification = _justification(words, turn)
                if justification:
                    output.append(("JUSTIFICATION", str(justification)))
                if "mirror" in words:
                    output.append(("ISMIRRORED", "T"))
                if pose.hide:
                    output.append(("ISHIDDEN", "T"))
            if record.get("RECORD") == "34" and "DESIGNATOR_FONTID" in comp_gfx:
                output = [(k, comp_gfx["DESIGNATOR_FONTID"] if k == "FONTID" else v) for k, v in output]
            if record.get("RECORD") == "41" and name == "Comment" and "COMMENT_FONTID" in comp_gfx:
                output = [(k, comp_gfx["COMMENT_FONTID"] if k == "FONTID" else v) for k, v in output]
            if record.get("RECORD") == "41" and name == "Comment" and comp_gfx.get("COMMENT_EMPTY") == "T":
                output = [(k, "" if k == "TEXT" else v) for k, v in output]
            self.add(output)
            if record.get("RECORD") == "1" and use_carried_gfx:
                for gfx_line in comp_gfx["RECORDS"].splitlines():
                    gfx_fields: Record = []
                    for item in gfx_line.strip().split("|"):
                        if not item:
                            continue
                        k, sep, v = item.partition("=")
                        if sep and k:
                            gfx_fields.append((k, str(offset) if k == "OWNERINDEX" and v == "@0" else v))
                    if gfx_fields:
                        self.add(gfx_fields, f"{where}.gfx", read=True)
        self.poses.append(
            replace(placed, x=symbol.at.x // NM_PER_MIL, y=symbol.at.y // NM_PER_MIL, rotation=quarter)
        )

    def hidden_pin(self, spec: PartSpec, pin: Mapping[str, str], where: str) -> None:
        """Note the written pin ``pin`` of ``spec`` in ``hidden_pins`` when it is a hidden KiCad power-input
        pin, which KiCad joins to the global net its name gives."""
        conglomerate = int(pin.get("PINCONGLOMERATE", "0"))
        name, number = pin.get("NAME", ""), pin.get("DESIGNATOR", "")
        if not conglomerate & HIDDEN or not name or number not in self.power_in.get(spec.key, ()):
            return
        dx, dy = STEPS[conglomerate & 3]
        length = _value(pin, "PINLENGTH")
        x = _value(pin, "LOCATION.X") + dx * length
        y = self.height - (_value(pin, "LOCATION.Y") + dy * length)
        at = Point(round(x * NM_DENOMINATOR / NM_NUMERATOR), round(y * NM_DENOMINATOR / NM_NUMERATOR))
        self.hidden_pins.append((name, at, f"{where}.{pin.get('DESIGNATOR', '')}"))

    def title_block(self, pairs: Sequence[tuple[str, str]], where: str) -> None:
        """The title block as document parameters (change c0470): each field by the parameter name a sheet
        template shows (``drawn_read.TITLE_PARAMETERS``), each ``param.<name>`` as ``<name>``."""
        for name, text in pairs:
            if not text:
                continue
            parameter = TITLE_NAMES.get(name) or name.removeprefix("param.")
            self.add(
                [
                    ("RECORD", "41"),
                    ("OWNERPARTID", "-1"),
                    *_fields("LOCATION.X", 0),
                    *_fields("LOCATION.Y", 0),
                    ("COLOR", schdoc.TEXT_COLOR),
                    ("FONTID", "1"),
                    ("ISHIDDEN", "T"),
                    ("TEXT", text),
                    ("NAME", parameter),
                ],
                f"{where}.title_block.{name}",
            )

    def polyline(self, points: Sequence[Point], bus: bool, where: str) -> None:
        record: Record = [
            ("RECORD", "26" if bus else "27"),
            ("OWNERPARTID", "-1"),
            ("LINEWIDTH", schdoc.BUS_WIDTH if bus else "1"),
            ("COLOR", schdoc.TEXT_COLOR),
            ("LOCATIONCOUNT", str(len(points))),
        ]
        for index, point in enumerate(points, 1):
            x, y = self.point(point, f"{where}.pts[{index - 1}]")
            record += [*_fields(f"X{index}", x), *_fields(f"Y{index}", self.height - y)]
        self.add(record)

    def _port_width(
        self,
        name: str,
        at: Point,
        rotation: int,
        held: Mapping[str, str],
        wires: Sequence[tuple[Point, ...]],
    ) -> int:
        if not self.sheet_fields:
            return PORT_WIDTH
        if "WIDTH" in held and held["WIDTH"].lstrip("-").isdigit():
            frac = int(held["WIDTH_FRAC"]) if held.get("WIDTH_FRAC", "").lstrip("-").isdigit() else 0
            cand = int(held["WIDTH"]) * UNIT_SCALE + frac
        else:
            cand = max(35, 10 * -(-(7 * len(name) + 15) // 10)) * UNIT_SCALE
        if cand <= PORT_WIDTH:
            return PORT_WIDTH
        quarter = rotation // 90_000_000 % 4
        width_nm = round(cand * NM_DENOMINATOR / NM_NUMERATOR)
        step = {0: (width_nm, 0), 1: (0, -width_nm), 2: (-width_nm, 0), 3: (0, width_nm)}[quarter]
        far = (at.x + step[0], at.y + step[1])
        near = (at.x, at.y)
        segments = [(a, b) for line in wires for a, b in zip(line, line[1:], strict=False)]
        if any(drawn_harness.on_segment(far, (a.x, a.y), (b.x, b.y)) for a, b in segments):
            return PORT_WIDTH
        if quarter in (2, 3) and not any(
            drawn_harness.on_segment(near, (a.x, a.y), (b.x, b.y)) for a, b in segments
        ):
            return PORT_WIDTH
        return cand

    def identifier(
        self,
        name: str,
        at: Point,
        rotation: int,
        kind: str,
        shape: str,
        where: str,
        uid: str = "",
        style: int = 2,
        harness: str = "",
        *,
        held: Mapping[str, str] = MappingProxyType({}),
        port_width: int = PORT_WIDTH,
    ) -> None:
        x, y = self.point(at, where)
        location = [*_fields("LOCATION.X", x), *_fields("LOCATION.Y", self.height - y)]
        default_color = (
            schdoc.SYMBOL_COLOR
            if self.sheet_fields and kind in ("hierarchical", "global")
            else schdoc.TEXT_COLOR
        )
        color = held.get("COLOR", default_color)
        font_id = held.get("FONTID", "1")
        record: Record = [
            ("RECORD", {"local": "25", "hierarchical": "18", "global": "17"}[kind]),
            ("OWNERPARTID", "-1"),
            *location,
            ("COLOR", color),
            ("FONTID", font_id),
        ]
        quarter = rotation // 90_000_000
        if kind == "local":
            record += [("TEXT", name), ("ORIENTATION", str(quarter))]
            if "JUSTIFICATION" in held:
                record.append(("JUSTIFICATION", held["JUSTIFICATION"]))
        elif kind == "global":
            record += [
                ("TEXT", name),
                ("STYLE", str(style)),
                ("ORIENTATION", str(quarter)),
                ("SHOWNETNAME", "T"),
            ]
            if uid:  # the stand-in of a carried KiCad item (change c0470, design D4)
                record.append(("UNIQUEID", uid))
        else:
            # A port's two hot ends stay on the label's axis; the drawn point is always one end.
            width = port_width
            if quarter == 2:
                x -= width
            elif quarter == 3:
                y += width
            height = (
                int(held["HEIGHT"]) * UNIT_SCALE
                + (int(held["HEIGHT_FRAC"]) if held.get("HEIGHT_FRAC", "").lstrip("-").isdigit() else 0)
                if "HEIGHT" in held and held["HEIGHT"].lstrip("-").isdigit()
                else 10 * UNIT_SCALE
            )
            port_style = held.get("STYLE", "4" if quarter % 2 else "0")
            record = [(k, v) for k, v in record if not k.startswith("LOCATION.")]
            record += [
                *_fields("LOCATION.X", x),
                *_fields("LOCATION.Y", self.height - y),
                ("NAME", name),
                ("STYLE", port_style),
                *_fields("WIDTH", width),
                *_fields("HEIGHT", height),
                ("IOTYPE", _IO.get(shape, "0")),
                *(
                    [
                        ("AREACOLOR", held.get("AREACOLOR", "8437759" if shape == "input" else schdoc.ENTRY_FILL)),
                        ("TEXTCOLOR", held.get("TEXTCOLOR", schdoc.SYMBOL_COLOR)),
                    ]
                    if self.sheet_fields
                    else []
                ),
                *([("ALIGNMENT", held["ALIGNMENT"])] if "ALIGNMENT" in held else []),
                *([("BORDERWIDTH", held["BORDERWIDTH"])] if "BORDERWIDTH" in held else []),
                *([("HARNESSTYPE", harness)] if harness else []),
                ("UNIQUEID", unique_id(where)),
            ]
        self.add(record)

    def reference(self, ref: DrawnSheetRef, child_file: str, where: str, ref_index: int = -1) -> None:
        held = self.sheet_fields.get(f"ref:{ref_index}", {})
        x, y = self.point(ref.at, where + ".at")
        width, height = self.point(Point(ref.size.w, ref.size.h), where + ".size")
        owner = self.add(
            [
                ("RECORD", "15"),
                ("OWNERPARTID", "-1"),
                *_fields("LOCATION.X", x),
                *_fields("LOCATION.Y", self.height - y),
                *_fields("XSIZE", width),
                *_fields("YSIZE", height),
                ("COLOR", held.get("COLOR", schdoc.SYMBOL_COLOR)),
                ("AREACOLOR", held.get("AREACOLOR", schdoc.SYMBOL_FILL)),
                ("ISSOLID", "T"),
                ("SYMBOLTYPE", "Normal"),
                ("UNIQUEID", unique_id(where)),
            ]
        )
        for index, pin in enumerate(ref.pins):
            entry_name, harness_type = pin.name, ""
            group = bus_group_parts(pin.name) if self.harness_types or self.lone_harness else None
            held_h = self.lone_harness.get((ref.name, group[0])) if group is not None else None
            if group is not None and held_h is not None:  # the record's own HARNESSTYPE, carried (c0470)
                entry_name, harness_type = group[0], held_h
            elif group is not None and sorted_entries(group[1]) in self.harness_types:
                # an entry of a harness type: the extractor names it by its group of entries (c0470)
                entry_name, harness_type = group[0], self.harness_types[sorted_entries(group[1])]
            elif (lowered := self.group(pin.name)) is not None:
                entry_name, harness_type = lowered  # a KiCad bus group: a harness (``drawn_harness``)
            px, py = self.point(pin.at, f"{where}.pin[{index}]")
            if px == x:
                side, distance = 0, py - y
            elif px == x + width:
                side, distance = 1, py - y
            elif py == y:
                side, distance = 2, px - x
            elif py == y + height:
                side, distance = 3, px - x
            else:
                self.issues.append(
                    issue(
                        "drawn.sheet-pin-unmatched",
                        f"{pin.name} is not on its Altium sheet symbol edge",
                        where,
                    )
                )
                continue
            whole, fraction = divmod(distance, UNIT_SCALE * 10)
            self.add(
                [
                    ("RECORD", "16"),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", "-1"),
                    ("NAME", drawn_carrier.altium_text(entry_name) if self.carry else entry_name),
                    *([("HARNESSTYPE", harness_type)] if harness_type else []),
                    ("SIDE", str(side)),
                    ("DISTANCEFROMTOP", str(whole)),
                    *([("DISTANCEFROMTOP_FRAC1", str(fraction))] if fraction else []),
                    ("IOTYPE", _IO.get(pin.shape, "0")),
                    ("COLOR", held.get(f"ENTRY_COLOR:{index}", schdoc.SYMBOL_COLOR)),
                    ("AREACOLOR", held.get(f"ENTRY_AREACOLOR:{index}", schdoc.ENTRY_FILL)),
                    ("TEXTCOLOR", held.get(f"ENTRY_TEXTCOLOR:{index}", schdoc.SYMBOL_COLOR)),
                    ("TEXTFONTID", held.get(f"ENTRY_TEXTFONTID:{index}", "1")),
                    ("TEXTSTYLE", "Full"),
                    ("ARROWKIND", schdoc.ENTRY_ARROW),
                ]
            )
        name_x = int(held["NAME_X"]) if held.get("NAME_X", "").lstrip("-").isdigit() else x
        name_y = (
            int(held["NAME_Y"])
            if held.get("NAME_Y", "").lstrip("-").isdigit()
            else (self.height - y + (12 * UNIT_SCALE if self.sheet_fields else 0))
        )
        file_x = int(held["FILE_X"]) if held.get("FILE_X", "").lstrip("-").isdigit() else x
        file_y = int(held["FILE_Y"]) if held.get("FILE_Y", "").lstrip("-").isdigit() else (self.height - y)
        for record, text, tx, ty, font_id, color in (
            ("32", ref.name, name_x, name_y, held.get("NAME_FONTID", "1"), held.get("NAME_COLOR", schdoc.TEXT_COLOR)),
            ("33", child_file, file_x, file_y, held.get("FILE_FONTID", "1"), held.get("FILE_COLOR", schdoc.TEXT_COLOR)),
        ):
            self.add(
                [
                    ("RECORD", record),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", "-1"),
                    *_fields("LOCATION.X", tx),
                    *_fields("LOCATION.Y", ty),
                    ("TEXT", text),
                    ("FONTID", font_id),
                    ("COLOR", color),
                ]
            )

    def drawing(
        self,
        sheet: DrawnSheet,
        instance: DrawnInstance,
        specs: Mapping[str, PartSpec],
        files: Mapping[str, str],
        symbol_overrides: Mapping[str, tuple[str, AltiumSymbol]],
    ) -> SheetPlan:
        where = instance.path or "root"
        base_size = self.plan.size
        sheet_rec: Record | None = None
        sheet_lines = self.sheet_fields.get("__sheet__", {}).get("RECORDS", "").splitlines()
        template_idx = -1
        for line in sheet_lines:
            if line.startswith("|RECORD=31|") and sheet_rec is None:
                parsed_31: Record = []
                for item in line.strip().split("|"):
                    if not item:
                        continue
                    k, sep, v = item.partition("=")
                    if sep and k and k.upper() != "FILEVERSIONINFO":
                        parsed_31.append((k, v))
                if parsed_31:
                    sheet_rec = parsed_31
            elif line.startswith("|RECORD=39|") and self.form == "binary":
                t_fields: Record = []
                for item in line.strip().split("|"):
                    if not item:
                        continue
                    k, sep, v = item.partition("=")
                    if sep and k:
                        t_fields.append((k, v))
                if t_fields:
                    template_idx = self.add(t_fields, f"{where}.template", read=True)
            elif template_idx > 0 and "|OWNERINDEX=@0" in line and self.form == "binary":
                if line.startswith("|RECORD=30|") and "|EMBEDIMAGE=T" in line:
                    continue
                c_fields: Record = []
                for item in line.strip().split("|"):
                    if not item:
                        continue
                    k, sep, v = item.partition("=")
                    if sep and k:
                        c_fields.append((k, str(template_idx) if k == "OWNERINDEX" and v == "@0" else v))
                if c_fields:
                    self.add(c_fields, f"{where}.template", read=True)
            else:
                template_idx = -1
        if sheet.bus_aliases:
            self.issues.append(Issue("altium.not-lowered", "info", "bus alias declarations are not written "
                                     "as native alias metadata; the written pin partition remains guarded",
                                     where=where))  # fmt: skip
        if sheet.title_block:  # a build writes the title block too (change c0470)
            self.title_block(sheet.title_block, where)
        symbols: dict[str, drawn_carrier.Json] = {}
        for index, symbol in enumerate(sheet.symbols):
            spec = specs.get(instance.component(symbol.part))
            if spec is not None and self.origin:
                self.origin_parts[spec.ref] = symbol.part
            if spec is not None and self.carry and (symbol.fields or symbol.symbol):
                # keyed by the designator Altium reads back, not the shared part name (c0470)
                symbols[f"{spec.ref}:{symbol.unit}"] = drawn_carrier.symbol_value(symbol)
            if spec is not None and 1 <= symbol.unit <= spec.body.parts:
                if symbol.symbol:
                    alias = symbol_overrides.get(symbol.symbol)
                    if alias is None:
                        raise FormatError(
                            f"unresolved Altium drawn unit alias {symbol.symbol}", locator=where
                        )
                    library, body = alias
                    spec = replace(spec, library=library, symbol=body.lib_ref, body=body)
                elif (own := self.bodies.get(spec.ref)) is not None:
                    spec = replace(spec, body=own)  # its own body, under its link's name (c0470)
                self.component(spec, symbol, f"{where}.symbol[{index}]", index)
        self.networks(sheet, where)
        for kind, polylines in (("wire", sheet.wires), ("bus", sheet.buses)):
            for index, points in enumerate(polylines):
                if kind == "bus" and index in self.harness_buses:
                    continue  # a harness line (``drawn_harness``)
                self.polyline(points, kind == "bus", f"{where}.{kind}[{index}]")
        for index, junction in enumerate(sheet.junctions):
            self.add(
                [
                    ("RECORD", "29"),
                    ("OWNERPARTID", "-1"),
                    *self.location(junction.at, f"{where}.junction[{index}]"),
                    ("COLOR", schdoc.TEXT_COLOR),
                ]
            )
        for index, entry in enumerate(sheet.bus_entries):
            end = entry.end
            self.add(
                [
                    ("RECORD", "37"),
                    ("OWNERPARTID", "-1"),
                    *self.location(entry.at, f"{where}.bus_entry[{index}].at"),
                    *self.location(end, f"{where}.bus_entry[{index}].end", "CORNER"),
                    ("LINEWIDTH", "1"),
                    ("COLOR", schdoc.BUS_COLOR),
                ]
            )
        for index, at in enumerate(sheet.no_connects):
            self.add(
                [
                    ("RECORD", "22"),
                    ("OWNERPARTID", "-1"),
                    *self.location(at, f"{where}.no_connect[{index}]"),
                    ("COLOR", schdoc.NO_ERC_COLOR),
                    ("ISACTIVE", "T"),
                    ("SUPPRESSALL", "T"),
                    ("SYMBOL", schdoc.NO_ERC_SYMBOL),
                ]
            )
        stand_ins: dict[str, drawn_carrier.Json] = {}
        flags: list[drawn_carrier.Json] = []
        written: list[drawn_carrier.Json] = []
        # KiCad joins a local label to the hierarchical label of its name on its sheet; Altium joins a net
        # label to no port (H-A-IMP-DUP-NAME), so such a local label is written as a port (change c0470)
        ports = {label.text for label in sheet.labels if self.carry and label.kind == "hierarchical"}
        # likewise a local label joins the power symbol of its name on its sheet, and Altium joins a net
        # label to no power port (H-A-IMP-DUP-NAME): it is written as a power port, a stand-in (c0470)
        powers = {power.net for power in sheet.powers if self.carry} | {net for net, _, _ in self.hidden_pins}
        for index, label in enumerate(sheet.labels):
            at = f"{where}.label[{index}]"
            held_label = self.sheet_fields.get(
                f"label_at:{label.kind}:{label.at.x},{label.at.y}"
            ) or self.sheet_fields.get(f"label:{index}", {})
            kind = "hierarchical" if label.kind == "local" and label.text in ports else label.kind
            if label.kind == "local" and label.text in powers and label.text not in ports:
                kind = "global"
            # a power port stands for a KiCad global label: the carrier keeps its kind and shape (c0470)
            uid = unique_id(at) if self.carry and kind == "global" else ""
            own = self.spellings.get((label.at.x, label.at.y))
            group = bus_group_parts(label.text) if own is not None else None
            named = label.text if group is None else group[0]  # a label on a harness: ``NAME{A B}``
            lowered = self.group(label.text) if kind in ("local", "hierarchical") else None
            if own is not None and own.casefold() == named.casefold() and kind == "local":
                text = drawn_carrier.altium_text(own)  # its own letter case and text (c0470)
            elif lowered is not None and kind == "local":
                text = drawn_carrier.altium_text(lowered[0]) if self.carry else lowered[0]
            else:
                text = drawn_carrier.altium_text(label.text) if self.carry else label.text
            port_name = lowered[0] if lowered is not None and kind == "hierarchical" else text
            p_width = (
                self._port_width(port_name, label.at, label.rotation, held_label, sheet.wires)
                if kind == "hierarchical"
                else PORT_WIDTH
            )
            if self.carry and kind != "global":
                # a port has two hot ends along it: the reader may meet either (c0470)
                w_nm = round(p_width * NM_DENOMINATOR / NM_NUMERATOR)
                step = {0: (w_nm, 0), 1: (0, -w_nm), 2: (-w_nm, 0), 3: (0, w_nm)}
                dx, dy = step[label.rotation // 90_000_000 % 4]
                other = Point(label.at.x + dx, label.at.y + dy) if kind == "hierarchical" else None
                written.append(drawn_carrier.written_label(label, other))
            if lowered is not None and kind == "hierarchical":  # a KiCad bus group: a port of a harness
                self.identifier(
                    lowered[0],
                    label.at,
                    label.rotation,
                    kind,
                    label.shape,
                    at,
                    harness=lowered[1],
                    held=held_label,
                    port_width=p_width,
                )
                continue
            self.identifier(
                text, label.at, label.rotation, kind, label.shape, at, uid, held=held_label, port_width=p_width
            )
            if uid:
                stand_ins[uid] = {"label": {**drawn_carrier.label_value(label), "text": label.text}}
        for net, point, at in self.hidden_pins:
            uid = unique_id(at)
            self.identifier(net, point, 0, "global", "", at, uid)
            stand_ins[uid] = {"pin": net}
        for index, power in enumerate(sheet.powers):
            at = f"{where}.power[{index}]"
            library, _, style = power.symbol.partition(":")
            if self.carry and style == drawn_carrier.POWER_FLAG:
                flags.append(drawn_carrier.flag_value(power))  # a power flag names no net (c0470)
                continue
            native = library == POWER_LIBRARY and style in POWER_STYLES
            uid = unique_id(at) if self.carry and not native else ""
            self.identifier(
                drawn_carrier.altium_text(power.net) if self.carry else power.net,
                power.at, power.rotation, "global", "", at, uid,
                POWER_STYLES.index(style) if native else 2,
                held=self.sheet_fields.get(f"power_style:{index}", {}),
            )  # fmt: skip
            if uid:
                stand_ins[uid] = {"power": {**drawn_carrier.power_value(power), "net": power.net}}
                continue
            if power.fields or power.mirror:
                self.issues.append(
                    Issue(
                        "altium.not-lowered",
                        "info",
                        "the native power port uses its own glyph and text placement; source field poses "
                        "and mirror metadata are not represented",
                        where=f"{where}.power[{index}]",
                    )
                )
        refs: list[drawn_carrier.Json] = []
        for ref_idx, ref in enumerate(sheet.sheet_refs):
            child = "/".join((*instance.keys, ref.key))
            if child in files:
                self.reference(ref, files[child], f"{where}.sheet_ref.{ref.key}", ref_idx)
                if self.carry:
                    refs.append(drawn_carrier.sheet_ref_value(ref))
        carried: list[str] = []
        for index, opaque in enumerate(sheet.opaques):
            if not opaque.altium and self.carry:
                carried.append(opaque.kicad)  # the carrier of design D4 (change c0470)
                continue
            if not opaque.altium:
                self.issues.append(
                    issue(
                        "drawn.opaque-dropped",
                        f"opaque item {index} of {sheet.key} has no Altium record text",
                        f"{where}.opaque[{index}]",
                    )
                )
                continue
            natives: list[int] = []
            lines = opaque.altium.splitlines()
            for number, line in enumerate(lines):
                fields: Record = []
                keys: set[str] = set()
                for item in line.strip().split("|"):
                    if not item:
                        continue
                    key, separator, value = item.partition("=")
                    if not separator or not key:
                        raise FormatError(
                            "opaque Altium text needs |KEY=value fields", locator=f"{where}.opaque[{index}]"
                        )
                    if key.upper() in keys:
                        raise FormatError(
                            f"opaque Altium record repeats field {key!r}",
                            locator=f"{where}.opaque[{index}]",
                        )
                    keys.add(key.upper())
                    fields.append((key, value))
                owner = dict(fields).get("OWNERINDEX", "")
                # a carried subtree (changes c0470 and c0471, drawn_read.subtree_text): a child names its
                # owner's line with ``@<line>``
                child = number > 0 and owner.startswith("@")
                if child:
                    line_number = int(owner[1:]) if owner[1:].isdigit() else -1
                    if not 0 <= line_number < len(natives):
                        raise FormatError(
                            "opaque Altium child names no earlier line", locator=f"{where}.opaque[{index}]"
                        )
                    fields = [(k, str(natives[line_number]) if k == "OWNERINDEX" else v) for k, v in fields]
                harness = number == 0 and drawn_read.is_harness_text(opaque.altium)
                if (not child and not harness and dict(fields).get("RECORD") in _MODELLED) or any(
                    key.upper() in _OWNERS
                    and not (child and key.upper() in ("OWNERINDEX", "OWNERINDEXADDITIONALLIST"))
                    for key, _ in fields
                ):
                    raise FormatError(
                        "opaque Altium text must be a root graphic, without ownership, electrical or "
                        "framework-owned records",
                        locator=f"{where}.opaque[{index}]",
                    )
                natives.append(
                    self.add(
                        fields,
                        f"{where}.opaque[{index}]",
                        read=self.carry or len(lines) > 1 or harness,
                    )
                )
        blocks, lines, harness_lines, generated = self.harness_blocks(sheet.paper)
        junctions = [drawn_carrier.junction_value(j) for j in sheet.junctions if self.carry and j.diameter]
        origin = (
            drawn_carrier.origin_value(self.origin, self.origin_file, self.origin_parts)
            if self.origin
            else None
        )
        exact = self.exact() if self.carry else None
        found = drawn_carrier.carrier(
            carried,
            flags,
            stand_ins,
            symbols,
            junctions,
            written,
            refs,
            origin,
            exact,
            generated,
            self.definitions if self.carry else None,
            sheet.bus_aliases if self.carry else (),
        )
        for index, part in enumerate(drawn_carrier.parts(found.value()) if found is not None else ()):
            self.add(
                [
                    ("RECORD", "41"),
                    ("OWNERPARTID", "-1"),
                    *_fields("LOCATION.X", 0),
                    *_fields("LOCATION.Y", 0),
                    ("COLOR", schdoc.TEXT_COLOR),
                    ("FONTID", "1"),
                    ("ISHIDDEN", "T"),
                    ("TEXT", part),
                    ("NAME", drawn_carrier.part_name(index)),
                ],
                f"{where}.carrier",
            )
        return replace(
            self.plan,
            parts=tuple(self.poses),
            stubs=(),
            no_connects=(),
            symbols=(),
            ports=(),
            harnesses=tuple(blocks),
            lines=tuple(lines),
            polylines=tuple(harness_lines),
            class_marks=(),
            buses=(),
            composition=None,
            drawn_records=tuple(tuple(record) for record in self.records),
            sheet_record=tuple(sheet_rec) if sheet_rec is not None and self.plan.size == base_size else None,
        )


def _carried_harnesses(drawn: DrawnSchematic) -> dict[str, SchDocument]:
    """Per sheet key, the document of the harness records that its opaque items carry (change c0470)."""
    found: dict[str, SchDocument] = {}
    for sheet in drawn.sheets:
        texts = [o.altium for o in sheet.opaques if o.altium and drawn_read.is_harness_text(o.altium)]
        if texts:
            found[sheet.key] = drawn_read.carried_document(texts)
    return found


def carried(
    fields: Mapping[str, Mapping[str, str]],
) -> tuple[dict[tuple[str, str], str], dict[tuple[int, int], str]]:
    """From the Altium fields that a sheet's carrier keeps (``drawn_read``, change c0470): the
    ``HARNESSTYPE`` of sheet entries by (sheet name, entry name) (``harness:<sheet>:<entry>``, "" for an
    entry whose record holds none) and the own text of net labels by position (``text:<x>,<y>``)."""
    harness: dict[tuple[str, str], str] = {}
    spellings: dict[tuple[int, int], str] = {}
    for name, value in fields.items():
        kind, _, rest = name.partition(":")
        if kind == "harness" and "HARNESSTYPE" in value:
            ref, _, entry = rest.rpartition(":")
            if ref and entry:
                harness[(ref, entry)] = value["HARNESSTYPE"]
        elif kind == "text" and "TEXT" in value:
            x, _, y = rest.partition(",")
            if x.lstrip("-").isdigit() and y.lstrip("-").isdigit():
                spellings[(int(x), int(y))] = value["TEXT"]
    return harness, spellings


def sorted_entries(entries: Sequence[str]) -> tuple[str, ...]:
    """The key of a harness type by its entries: their names in code-point order."""
    return tuple(sorted(entries))


def _harness_types(documents: Sequence[SchDocument]) -> dict[tuple[str, ...], str]:
    """The harness type of each set of entries (``sorted_entries``: two connectors of a type can list its
    entries in other orders, and the documents of the two ways come in other orders, change c0470)."""
    from fenolite.backends.altium.read.sch import HarnessConnector, HarnessType

    names: dict[str, str] = {}
    for document in documents:
        for connector in document.of_type(HarnessConnector):
            kind = next((c.text for c in document.children_of(connector) if isinstance(c, HarnessType)), "")
            if kind:
                names.setdefault(kind.casefold(), kind)
    members = drawn_read.harness_members(documents)
    return {
        sorted_entries(entries): names[kind] for kind, entries in members.items() if kind in names and entries
    }


def _without_stand_ins(
    sheet: DrawnSheet, state: _Sheet, stand_ins: drawn_read.HarnessStandIns, where: str
) -> DrawnSheet:
    """``sheet`` without the items that its carried harness records stand for in KiCad (change c0470): the
    bus of a signal harness (which KiCad cuts into two-point segments), the labels of connector entries and
    harness ports. The records are written again, and the extractor draws these items from them."""
    segments = [(a, b) for line in stand_ins.buses for a, b in zip(line, line[1:], strict=False)]

    def is_stand_in(points: Sequence[tuple[int, int]]) -> bool:
        if tuple(points) in stand_ins.buses:
            return True
        return bool(points) and all(
            any(drawn_harness.on_segment(a, c, d) and drawn_harness.on_segment(b, c, d) for c, d in segments)
            for a, b in zip(points, points[1:], strict=False)
        )

    buses = tuple(
        points
        for index, points in enumerate(sheet.buses)
        if not is_stand_in([state.native(at, f"{where}.bus[{index}]") for at in points])
    )
    labels = tuple(
        label
        for index, label in enumerate(sheet.labels)
        if (label.text, state.native(label.at, f"{where}.label[{index}]")) not in stand_ins.labels
    )
    return replace(sheet, buses=buses, labels=labels)


def sheet_size(paper: str) -> SheetSize | None:
    """The Altium sheet of a drawn sheet's ``paper``: a named style (``drawn_read.SHEET_STYLES``), or a
    custom size ``custom:<width>x<height>`` in nm on the 10-mil file unit (change c0470); ``None`` else."""
    found = next((size for size in SHEET_SIZES if size.name == paper), None)
    if found is not None:
        return found
    for style, (units_x, units_y, name) in enumerate(drawn_read.SHEET_STYLES):
        if name and name == paper:
            return SheetSize(name, units_x * 10, units_y * 10, style)
    if not paper.startswith("custom:"):
        return None
    width, _, height = paper.removeprefix("custom:").partition("x")
    try:
        nm = (int(width), int(height))
    except ValueError:
        return None
    unit = 10 * NM_PER_MIL
    if any(value <= 0 or value % unit for value in nm):
        return None
    return SheetSize("custom", nm[0] // NM_PER_MIL, nm[1] // NM_PER_MIL, None)


def lower_drawn(
    drawn: DrawnSchematic,
    design: Design,
    planned: ProjectSheets,
    *,
    name: str,
    issues: list[Issue],
    allow_lossy: bool = False,
    form: TextForm = "binary",
    symbol_overrides: Mapping[str, tuple[str, AltiumSymbol]] = MappingProxyType({}),
    carry: bool = False,
    harness: bool | None = None,
    definitions: Mapping[str, Mapping[str, str]] = MappingProxyType({}),
    fields: Mapping[str, Mapping[str, Mapping[str, str]]] = MappingProxyType({}),
    bodies: Mapping[str, AltiumSymbol] = MappingProxyType({}),
) -> ProjectSheets:
    """One native sheet per drawn instance, retaining generated module sheets and their records. With
    ``carry`` (a conversion, change c0470) a KiCad item without Altium text travels in the sheet's
    ``Fenolite.KiCad.Sheet`` parameter (``drawn_carrier``) instead of giving ``drawn.opaque-dropped``;
    ``definitions`` holds, per drawn sheet key, the library text of its opaque symbols' definitions,
    ``fields`` the Altium fields that the carrier of a sheet keeps (``carried``), and ``bodies`` the own
    body of a component, by reference, whose instance differs from its library symbol. ``harness`` (by
    default ``carry``) writes a KiCad bus group that crosses a sheet as a signal harness."""
    harness = carry if harness is None else harness
    found, walk_issues = instances(drawn)
    issues.extend(walk_issues)
    specs = {part.spec.key: part.spec for sheet in planned.sheets for part in sheet.plan.parts}
    units = {
        key: UnitInfo(
            spec.body.parts,
            frozenset(
                part
                for part in range(1, spec.body.parts + 1)
                if any(pin.designator in spec.nets and pin.part in (0, part) for pin in spec.body.pins)
            ),
        )
        for key, spec in specs.items()
    }
    issues.extend(coverage(drawn, design.circuit, units))
    power_in = {
        component_path(c): frozenset(p.number for p in c.pins if p.etype == "power_in")
        for c in design.circuit.components
    }
    for instance in found:
        sheet = drawn.sheet(instance.sheet)
        if sheet is not None:
            losses = _style_losses(sheet, instance.path or "root")
            if losses and not allow_lossy:
                raise _DrawnStyleLoss(losses[0])
            issues.extend(losses)
    generated = {sheet.module or "": sheet for sheet in planned.sheets}
    harnesses = _carried_harnesses(drawn)
    members = drawn_read.harness_members(list(harnesses.values()))
    harness_types = _harness_types(list(harnesses.values()))
    # a root that stands for no source document: its sheets are top documents of their own names (c0470)
    tops = fields.get(drawn.root, {}).get(drawn_read.TOPS_KEY, {}).get(drawn_read.TOPS_FIELD) == "T"
    files: dict[str, str] = {}
    for instance in found:
        sheet = drawn.sheet(instance.sheet)
        if sheet is not None and sheet.generated and instance.module in generated:
            files[instance.path] = generated[instance.module].file
        elif tops and len(instance.keys) == 1:
            files[instance.path] = f"{instance.sheet}.SchDoc"
        else:
            files[instance.path] = (
                f"{name}.SchDoc" if not instance.keys else f"{name}_drawn_{unique_id(instance.path)}.SchDoc"
            )
    counts = Counter(instance.sheet for instance in found)
    channels = channel_sheets(found, drawn, specs) if carry else {}
    firsts = {key: next(i for i in found if i.sheet == key) for key in channels}
    for instance in found:  # a channel is drawn by the one sheet of its first channel
        if instance.sheet in firsts:
            files[instance.path] = files[firsts[instance.sheet].path]
    for key, count in sorted(counts.items()):
        if count > 1 and key not in channels:
            issues.append(
                issue(
                    "drawn.altium-repeat-flattened",
                    f"sheet {key} is written as {count} Altium instances",
                    key,
                )
            )
    written: list[SheetFile] = []
    for instance in found:
        sheet = drawn.sheet(instance.sheet)
        if sheet is None or (tops and not instance.keys):
            continue
        if instance.sheet in firsts and instance is not firsts[instance.sheet]:
            continue
        if sheet.generated:
            source = generated.get(instance.module)
            if source is None:
                issues.append(
                    issue(
                        "drawn.sheet-unknown",
                        f"no generated Altium module sheet for {instance.module}",
                        instance.module,
                    )
                )
            else:
                written.append(source)
                written.extend(
                    s for s in planned.sheets if s.module and s.module.startswith(instance.module + "/")
                )
            continue
        size = sheet_size(sheet.paper)
        if size is None:
            raise FormatError(f"Altium drawn sheet {sheet.key}: unsupported paper {sheet.paper!r}")
        base = SheetPlan(size, (), ())
        state = _Sheet(base, issues, allow_lossy, form, carry, harness)
        state.harness_types = harness_types
        state.aliases = _aliases(drawn, sheet)
        state.definitions = definitions.get(sheet.key, {})
        state.sheet_fields = fields.get(sheet.key, {})
        state.lone_harness, state.spellings = carried(fields.get(sheet.key, {}))
        state.power_in = power_in
        state.origin = sheet.key if carry and counts[instance.sheet] > 1 and sheet.key not in channels else ""
        state.origin_file = instance.ref.file if instance.ref is not None else ""
        if sheet.key in harnesses:
            stand_ins = drawn_read.harness_stand_ins(harnesses[sheet.key], members)
            sheet = _without_stand_ins(sheet, state, stand_ins, instance.path or "root")
        sheet = _native_buses(drawn, sheet, instance.path or "root", issues, harness)
        state.bodies = bodies
        own = channels.get(instance.sheet, {})
        written_specs = {**specs, **{k: replace(specs[k], ref=d) for k, d in own.items()}} if own else specs
        plan = state.drawing(sheet, instance, written_specs, files, symbol_overrides)
        top = not instance.keys or (tops and len(instance.keys) == 1)
        written.append(
            SheetFile(
                files[instance.path], plan, instance.module or None, None if top else unique_id(instance.path)
            )
        )
    repeated_files = frozenset(
        files[instance.path]
        for instance in found
        if counts[instance.sheet] > 1 and instance.sheet not in channels
    )
    bindings = _canonical_local_bindings(written, design, repeated_files)
    written = _global_local_names(written, issues, bindings=bindings)
    links = sheet_links(found, drawn, specs, channels, tops=tops) if carry else ()
    return ProjectSheets("modules" if len(written) > 1 else "flat", tuple(written), links)


def channel_sheets(
    found: Sequence[DrawnInstance], drawn: DrawnSchematic, specs: Mapping[str, PartSpec]
) -> dict[str, dict[str, str]]:
    """Per drawn sheet that several instances show and that Altium holds as one sheet of several channels
    (change c0470), the designator of its record per component path: every part of every instance is
    named ``<designator>_<designator of the instance's sheet symbol>``, the names of a channel under the
    format of ``prjpcb.CHANNEL_KEYS`` (``docs/formats/altium/connectivity.md``, "Channels"). A sheet with
    sheets below it, or a part named otherwise, keeps one Altium sheet per instance."""
    groups: dict[str, list[DrawnInstance]] = {}
    for instance in found:
        groups.setdefault(instance.sheet, []).append(instance)
    found_channels: dict[str, dict[str, str]] = {}
    for key, group in groups.items():
        sheet = drawn.sheet(key)
        if len(group) < 2 or sheet is None or sheet.generated or sheet.sheet_refs:
            continue
        rooms = [instance.names[-1] if instance.names else "" for instance in group]
        if not all(rooms) or len(set(rooms)) != len(rooms):
            continue
        designators: dict[str, str] = {}
        per_part: dict[str, str] = {}
        for symbol in sheet.symbols:
            for instance, room in zip(group, rooms, strict=True):
                spec = specs.get(instance.component(symbol.part))
                suffix = f"_{room}"
                if spec is None or not spec.ref.endswith(suffix) or spec.ref == suffix:
                    break
                designator = spec.ref.removesuffix(suffix)
                if per_part.setdefault(symbol.part, designator) != designator:
                    break
                designators[instance.component(symbol.part)] = designator
            else:
                continue
            break
        else:
            if len(set(per_part.values())) == len(per_part):
                found_channels[key] = designators
    return found_channels


def sheet_links(
    found: Sequence[DrawnInstance],
    drawn: DrawnSchematic,
    specs: Mapping[str, PartSpec],
    channels: Mapping[str, Mapping[str, str]],
    *,
    tops: bool = False,
) -> tuple[SheetLink, ...]:
    """How each drawn component links to its sheet record (``SheetLink``, change c0470): through the unique
    ids that ``_Sheet.reference`` gives the sheet symbols of its instance, from the top sheet (the first
    level is the top documents of a project without a root, ``tops``)."""
    firsts = {key: next(i for i in found if i.sheet == key) for key in channels}
    links: dict[str, SheetLink] = {}
    units: dict[str, int] = {}
    for instance in found:
        sheet = drawn.sheet(instance.sheet)
        if sheet is None or sheet.generated:
            continue
        start = 1 if tops else 0
        symbols = "\\".join(
            unique_id(f"{'/'.join(instance.keys[:level]) or 'root'}.sheet_ref.{instance.keys[level]}")
            for level in range(start, len(instance.keys))
        )
        names = "\\".join(instance.names[start:])
        own = channels.get(instance.sheet)
        for symbol in sheet.symbols:
            spec = specs.get(instance.component(symbol.part))
            if spec is None or (spec.ref in units and symbol.unit >= units[spec.ref]):
                continue
            units[spec.ref] = symbol.unit
            if own is None:
                links[spec.ref] = SheetLink(spec.ref, symbols, names, spec.unique_id, spec.ref)
                continue
            first = specs.get(firsts[instance.sheet].component(symbol.part))
            designator = own.get(instance.component(symbol.part), spec.ref)
            shared = first.unique_id if first is not None else spec.unique_id
            links[spec.ref] = SheetLink(spec.ref, symbols, names, shared, designator, channel=True)
    return tuple(links.values())


def _canonical_local_bindings(
    sheets: Sequence[SheetFile],
    design: Design,
    repeated_files: frozenset[str],
) -> dict[tuple[str, str], str]:
    """Prove complete physical bindings before choosing a repeated local label's visible name.

    An isolated native sheet may project a cross-sheet global net. A local candidate must match
    the entire canonical group. Ambiguity keeps the existing scope-preserving fallback path.
    """
    if not repeated_files:
        return {}
    components = [component for component in design.circuit.components if not component.board_only]
    references = [component.ref for component in components]
    if len(set(references)) != len(references):
        return {}
    refs = {component.id: component.ref for component in components}
    code_pins = {(component.ref, pin.number) for component in components for pin in component.pins}
    code_groups: list[tuple[str, frozenset[tuple[str, str]]]] = []
    for net in design.circuit.nets:
        if any(pin.component_id not in refs for pin in net.members):
            return {}
        group = frozenset((refs[pin.component_id], pin.pin) for pin in net.members)
        if len(group) != len(net.members) or not group <= code_pins:
            return {}
        if group:
            code_groups.append((net.name, group))
    assigned = Counter(pin for _, group in code_groups for pin in group)
    if any(count != 1 for count in assigned.values()):
        return {}
    code_groups.extend(("", frozenset({pin})) for pin in code_pins - assigned.keys())
    name_counts = Counter(net.name.casefold() for net in design.circuit.nets)
    records = [[dict(fields) for fields in schdoc.schdoc_records(sheet.plan)] for sheet in sheets]
    native_names = {
        record.get("TEXT", record.get("NAME", "")).casefold()
        for sheet_records in records
        for record in sheet_records
        if record.get("RECORD") in {"17", "18", "25"}
    }
    holders: dict[str, set[int]] = {}
    for index, sheet_records in enumerate(records):
        for record in sheet_records:
            if record.get("RECORD") == "25":
                holders.setdefault(record.get("TEXT", ""), set()).add(index)
    shared = {name for name, indices in holders.items() if len(indices) > 1}
    candidates: dict[tuple[str, str], str] = {}
    for sheet in sheets:
        if sheet.file not in repeated_files or sheet.plan.drawn_records is None:
            continue
        try:
            resolved, actual = _read_native({sheet.file: schdoc.write_schdoc(sheet.plan)})
        except (FenoliteError, ValueError, OSError):
            continue
        expected = planned_coverage(ProjectSheets("flat", (sheet,)))
        if actual != expected or len({(ref, unit) for ref, unit, _ in actual.units}) != len(actual.units):
            continue
        physical = {(ref, pin) for ref, _, numbers in actual.units for pin in numbers}
        if not physical <= code_pins:
            continue
        native_refs = {value: resolved.refs[key] for key, value in resolved.component_ids.items()}
        groups = [
            (net, frozenset((native_refs[pin.component], pin.designator) for pin in net.pins))
            for net in resolved.netlist.nets
        ]
        memberships = Counter(pin for _, group in groups for pin in group)
        if any(count != 1 for count in memberships.values()) or not memberships.keys() <= physical:
            continue
        partition = {group for _, group in groups}
        partition.update(frozenset({pin}) for pin in physical - memberships.keys())
        projected = [group & physical for _, group in code_groups if group & physical]
        if len(projected) != len(set(projected)) or partition != set(projected):
            continue
        labels = {
            dict(record).get("TEXT", "")
            for record in sheet.plan.drawn_records
            if dict(record).get("RECORD") == "25"
        }
        for label in labels & shared:
            matching = [
                group
                for net, group in groups
                if label.casefold() in {value.casefold() for value in (net.name, *net.aliases)}
            ]
            if len(matching) != 1:
                continue
            canonical = [name for name, group in code_groups if group == matching[0]]
            if len(canonical) != 1:
                continue
            name = canonical[0]
            if (
                not name
                or name_counts[name.casefold()] != 1
                or name.casefold() in native_names
                or text_problem(name, form="ascii") is not None
                or re.search(r"[{}\[\]/]", name)
            ):
                continue
            candidates[(sheet.file, label)] = name
    counts = Counter(name.casefold() for name in candidates.values())
    return {key: name for key, name in candidates.items() if counts[name.casefold()] == 1}


def _global_local_names(
    sheets: list[SheetFile],
    issues: list[Issue],
    *,
    bindings: Mapping[tuple[str, str], str] = MappingProxyType({}),
) -> list[SheetFile]:
    """Preserve local partitions under source-verified Automatic/Global, without guessing another mode."""
    if len(sheets) <= 1:
        return sheets
    records = [[dict(record) for record in schdoc.schdoc_records(sheet.plan)] for sheet in sheets]
    if any(record.get("RECORD") == "16" for record in records[0]) or any(
        record.get("RECORD") == "18" for sheet in records for record in sheet
    ):
        return sheets  # Automatic selects Hierarchical or Flat; local names already have sheet scope.
    taken = {
        record.get("TEXT", record.get("NAME", "")).casefold()
        for sheet in records
        for record in sheet
        if record.get("RECORD") in {"17", "18", "25"}
    }
    taken.update(value.casefold() for value in bindings.values())
    occurrences: dict[str, set[int]] = {}
    for index, sheet_records in enumerate(records):
        for record in sheet_records:
            if record.get("RECORD") == "25":
                occurrences.setdefault(record.get("TEXT", ""), set()).add(index)
    shared = {name for name, holders in occurrences.items() if len(holders) > 1}
    result: list[SheetFile] = []
    for sheet in sheets:
        original = sheet.plan.drawn_records
        if original is None:
            result.append(sheet)
            continue
        names = sorted(
            {
                dict(record).get("TEXT", "")
                for record in original
                if dict(record).get("RECORD") == "25" and dict(record).get("TEXT", "") in shared
            }
        )
        prefix = f"__local_{unique_id(sheet.file)}_"
        while any((prefix + name).casefold() in taken for name in names):
            prefix += "_"
        replacements = {name: bindings.get((sheet.file, name), prefix + name) for name in names}
        taken.update(value.casefold() for value in replacements.values())
        for name, replacement in replacements.items():
            issues.append(
                Issue(
                    "altium.not-lowered",
                    "info",
                    f"local label {name!r} is written as {replacement!r} to preserve its sheet scope when "
                    "Automatic selects Global; drawn label text is changed",
                    where=f"{sheet.file}:{name}",
                )
            )
        rewritten = tuple(
            tuple((key, replacements.get(value, value) if key == "TEXT" else value) for key, value in record)
            if dict(record).get("RECORD") == "25"
            else record
            for record in original
        )
        result.append(replace(sheet, plan=replace(sheet.plan, drawn_records=rewritten)))
    return result


@dataclass(frozen=True)
class NativeCoverage:
    """The intended native documents, unit pin tables and footprint maps; no persisted model field."""

    files: tuple[str, ...]
    units: tuple[tuple[str, int, tuple[str, ...]], ...]
    pad_maps: tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]


def planned_coverage(planned: ProjectSheets) -> NativeCoverage:
    """Coverage before the native producer runs, including units whose pins are all unconnected."""
    units: list[tuple[str, int, tuple[str, ...]]] = []
    maps: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {}
    for sheet in planned.sheets:
        for placed in sheet.plan.parts:
            spec = placed.spec
            pins = tuple(sorted(pin.designator for pin in spec.body.pins if pin.part in (0, placed.part)))
            units.append((spec.ref, placed.part, pins))
            maps[spec.ref] = tuple(sorted(spec.pin_pads))
    return NativeCoverage(tuple(sorted(s.file for s in planned.sheets)), tuple(sorted(units)),
                          tuple(sorted(maps.items())))  # fmt: skip


def _read_native(files: Mapping[str, bytes]) -> tuple[Resolved, NativeCoverage]:
    from fenolite.backends.altium.adapter.netlist import SheetInput, resolve
    from fenolite.backends.altium.read import sch

    sheets = [SheetInput(name, "", sch.read_schematic(data, file=name))
              for name, data in sorted(files.items()) if name.lower().endswith(".schdoc")]  # fmt: skip
    if not sheets or any(
        document.document.sheet is None
        or any(
            drawn_read.record_class(record) == "UnknownRecord"
            for record in document.document.of_type(sch.UnknownRecord)
        )
        or any(i.severity in {"warning", "error"} for i in document.document.issues)
        for document in sheets
    ):
        raise FormatError("the written Altium drawing has no verifiable native document set")
    diagnostics: list[Issue] = []
    resolved = resolve(sheets, issues=diagnostics)
    if any(i.severity in {"warning", "error"} for i in diagnostics):
        raise FormatError("the written Altium drawing has unresolved connectivity: "
                          + "; ".join(i.message for i in diagnostics))  # fmt: skip
    units: list[tuple[str, int, tuple[str, ...]]] = []
    maps: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {}
    for key in resolved.component_ids:
        instance, group = key
        sheet = resolved.sheets[resolved.instances[instance].sheet]
        parts = sheet.groups[group]
        ref = resolved.refs.get(key, "")
        if not ref:
            raise FormatError("the written Altium drawing has an unnamed component")
        for part in parts.parts:
            pins = tuple(sorted(pin.designator for pin in sheet.input.document.shown_children(part)
                                if isinstance(pin, sch.Pin)))  # fmt: skip
            units.append((ref, part.current_part, pins))
        maps[ref] = tuple(sorted(parts.pin_pads))
    coverage = NativeCoverage(tuple(sorted(sheet.file for sheet in sheets)), tuple(sorted(units)),
                              tuple(sorted(maps.items())))  # fmt: skip
    return resolved, coverage


def native_coverage(files: Mapping[str, bytes]) -> NativeCoverage:
    """The coverage of bytes already checked by the builder, for the CLI's final-write guard."""
    return _read_native(files)[1]


def readback_issues(
    files: Mapping[str, bytes], design: Design, *, expected: NativeCoverage
) -> tuple[Issue, ...]:
    """Check actual native coverage and logical pin partitions before returning any candidate bytes."""
    from fenolite.model.drawn_connect import DrawnNet, DrawnNetlist, compare

    def refused(message: str) -> tuple[Issue, ...]:
        return (Issue("build.schematic-netlist-differs", "error", message),)

    try:
        resolved, actual = _read_native(files)
    except (FenoliteError, ValueError, OSError) as error:
        return refused(f"the written Altium drawing cannot be verified: {error}")
    if actual != expected:
        return refused("the written Altium drawing changed its document, component/unit/pin coverage "
                       "or footprint pin map; nothing is written")  # fmt: skip
    by_ref = {component.ref: component_path(component) for component in design.circuit.components}
    if any(ref not in by_ref for ref, _unit, _pins in actual.units):
        return refused("the written Altium drawing contains a component outside the circuit")
    mapping = {native: by_ref[resolved.refs[key]] for key, native in resolved.component_ids.items()}
    nets = tuple(
        DrawnNet(net.name, tuple(sorted((mapping[p.component], p.designator) for p in net.pins)), net.aliases)
        for net in resolved.netlist.nets
    )
    pins = tuple(sorted({(by_ref[ref], pin) for ref, _unit, numbers in actual.units for pin in numbers}))
    # Altium's native electrical designators are logical pins. Its physical pin maps were sealed
    # separately above; compare logical native connections with the same logical circuit domain.
    circuit = replace(design.circuit, components=tuple(replace(c, pin_pad_map=())
                                                       for c in design.circuit.components))  # fmt: skip
    differences = compare(DrawnNetlist(nets, pins), circuit)
    return tuple(
        Issue("build.schematic-netlist-differs", "error", found.message, where=found.where, hint=found.hint)
        if found.severity == "error"
        else found
        for found in differences
    )


__all__ = [
    "carried",
    "EVIDENCE",
    "DrawnLossError",
    "NativeCoverage",
    "lower_drawn",
    "native_coverage",
    "planned_coverage",
    "readback_issues",
]
