# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edit session of a binary Altium schematic document (capability altium-edit, "Edit session on an
Altium document"; change c0241, task 3.4): ``move``, ``set_property`` and ``delete`` of a part, with the
net-signature guard; ``add_part``, ``annotate``, ``add_wire``, ``add_net_label`` and ``add_power_port``
(change c0499, design D1 to D3).

A part is named by its designator. Its records are the component record and every record it owns, through
``OWNERINDEX``, at any depth (``docs/formats/altium/schematic-records.md``). A move adds whole 10-mil units to
every location key of those records and to the location of each binary pin; a deletion removes them, lowers
by the number removed before it every ``OWNERINDEX`` that points past a removed record, and sets the
header's ``WEIGHT`` to the new count. Wires are not dragged (``H-A-EDIT-SCH``).

The guard: the sheet's net signature, the pins and the identifiers of each local net as Fenolite reads them
(``adapter.connectivity.local_nets``), must be equal before and after the edit unless the session declares
the change (``altium.edit.connectivity``). Every operation is behind its gate in ``SCHEMATIC_GATES``, all off.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from fenolite.backends.altium.cfb import Entry, Storage, write_compound
from fenolite.backends.altium.edit.ops import Refused, new_id
from fenolite.backends.altium.edit.records import keys_of, set_keys
from fenolite.backends.altium.edit.session import EDIT_ISSUE_CODES, Receipt
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.sch import SchDocument, read_schematic
from fenolite.backends.altium.read.sch.framing import deframe, enframe
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.io import atomic_write

OPERATIONS = ("move", "set_property", "delete", "add_part", "annotate", "create")
SCHEMATIC_GATES: Mapping[str, bool] = MappingProxyType(dict.fromkeys(OPERATIONS, False))
ROWS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        **dict.fromkeys(("move", "set_property", "delete"), ("H-A-EDIT-SCH", "H-A-EDIT-KIT")),
        **dict.fromkeys(("add_part", "annotate", "create"), ("H-A-EDIT-SCH-ADD", "H-A-EDIT-KIT")),
    }
)
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-EDIT-KIT", "H-A-EDIT-SCH", "H-A-EDIT-SCH-ADD"))
UNIT_NM = 254_000
"""One schematic unit, 10 mil, in nanometres."""
PIN_RECORD = 2
_LOCATION = re.compile(r"^(LOCATION|CORNER)\.(X|Y)$|^(X|Y)\d+$")


@dataclass(frozen=True, slots=True)
class Part:
    designator: str


@dataclass
class _Sheet:
    """The frames of ``FileHeader``: ``header`` and one ``(kind, payload)`` per record."""

    header: bytes
    frames: list[tuple[int, bytes]]

    def props(self, index: int) -> dict[str, str]:
        kind, payload = self.frames[index]
        return {} if kind != 0 else keys_of(payload.rstrip(b"\0"))

    def set(self, index: int, changes: Mapping[str, str]) -> None:
        kind, payload = self.frames[index]
        nul = payload.endswith(b"\0")
        self.frames[index] = (kind, set_keys(payload.rstrip(b"\0"), changes) + (b"\0" if nul else b""))


def _owned(sheet: _Sheet, root: int) -> list[int]:
    """``root`` and every record it owns, at any depth, in stream order."""
    owner: dict[int, int] = {}
    for index in range(len(sheet.frames)):
        value = sheet.props(index).get("OWNERINDEX")
        if value is not None and value.lstrip("-").isdigit():
            owner[index] = int(value)
        elif sheet.frames[index][0] == 1 and index > 0:
            owner[index] = _pin_owner(sheet, index)
    found = {root}
    changed = True
    while changed:
        changed = False
        for index, parent in owner.items():
            if parent in found and index not in found:
                found.add(index)
                changed = True
    return sorted(found)


def _pin_owner(sheet: _Sheet, index: int) -> int:
    """A binary pin has no ``OWNERINDEX``: it belongs to the nearest component record before it."""
    for before in range(index - 1, -1, -1):
        if sheet.props(before).get("RECORD") == "1":
            return before
    return -1


def _part(sheet: _Sheet, designator: str) -> int:
    found: list[int] = []
    for index in range(len(sheet.frames)):
        props = sheet.props(index)
        if props.get("RECORD") == "34" and props.get("TEXT") == designator:
            owner = props.get("OWNERINDEX", "")
            if owner.isdigit():
                found.append(int(owner))
    if len(found) != 1:
        raise Refused(
            "altium.edit.assertion", f"{len(found)} parts are named {designator!r}, not one", "FileHeader"
        )
    return found[0]


def _shift_pin(payload: bytes, du: int, dv: int) -> bytes:
    d = payload[12]
    at = 18 + d
    x, y = struct.unpack_from("<2h", payload, at)
    out = bytearray(payload)
    struct.pack_into("<2h", out, at, x + du, y + dv)
    return bytes(out)


def _units(dx: int, dy: int) -> tuple[int, int]:
    if dx % UNIT_NM or dy % UNIT_NM:
        raise Refused("altium.edit.assertion", "a schematic move is a whole number of 10-mil units")
    return dx // UNIT_NM, dy // UNIT_NM


def _shift(sheet: _Sheet, indices: list[int], du: int, dv: int) -> None:
    for index in indices:
        kind, payload = sheet.frames[index]
        if kind == 1:
            sheet.frames[index] = (kind, _shift_pin(payload, du, dv))
            continue
        changes: dict[str, str] = {}
        for key, value in sheet.props(index).items():
            match = _LOCATION.match(key)
            if match and value.lstrip("-").isdigit():
                axis = match.group(2) or match.group(3)
                changes[key] = str(int(value) + (du if axis == "X" else dv))
        if changes:
            sheet.set(index, changes)


def move(sheet: _Sheet, part: Part, dx: int, dy: int) -> None:
    du, dv = _units(dx, dy)
    _shift(sheet, _owned(sheet, _part(sheet, part.designator)), du, dv)


def set_property(sheet: _Sheet, part: Part, name: str, value: str, old: str) -> None:
    owner = _part(sheet, part.designator)
    found = [
        index
        for index in _owned(sheet, owner)
        if sheet.props(index).get("RECORD") == "41"
        and sheet.props(index).get("NAME", "").lower() == name.lower()
    ]
    if len(found) != 1:
        raise Refused("altium.edit.assertion", f"{part.designator} holds {len(found)} parameters {name!r}")
    held = sheet.props(found[0]).get("TEXT", "")
    if held != old:
        raise Refused(
            "altium.edit.assertion", f"{name} of {part.designator} is {held!r}, not the stated {old!r}"
        )
    sheet.set(found[0], {"TEXT": value})


def delete(sheet: _Sheet, part: Part) -> None:
    removed = set(_owned(sheet, _part(sheet, part.designator)))
    kept = [i for i in range(len(sheet.frames)) if i not in removed]
    frames = [sheet.frames[i] for i in kept]
    sheet.frames[:] = frames
    for new, _old in enumerate(kept):
        owner = sheet.props(new).get("OWNERINDEX")
        if owner is not None and owner.isdigit():
            shift = sum(1 for r in removed if r < int(owner))
            if shift:
                sheet.set(new, {"OWNERINDEX": str(int(owner) - shift)})
    _weight(sheet)


def _weight(sheet: _Sheet) -> None:
    """The header's ``WEIGHT``: the record count."""
    nul = sheet.header.endswith(b"\0")
    sheet.header = set_keys(sheet.header.rstrip(b"\0"), {"WEIGHT": str(len(sheet.frames))}) + (
        b"\0" if nul else b""
    )


# --- additions (change c0499) ---------------------------------------------------------------------

Point = tuple[int, int]
"""A point of a sheet in nanometres, in Altium's frame of the sheet (X right, Y up), a whole number of 10-mil
units."""
_FRAC = re.compile(r"_FRAC$")
_POINTS = re.compile(r"^(X|Y)\d+(_FRAC)?$|^LOCATIONCOUNT$")
WRITTEN: Mapping[str, tuple[tuple[str, str], ...]] = MappingProxyType(
    {
        "27": (("RECORD", "27"), ("OWNERPARTID", "-1"), ("LINEWIDTH", "1"), ("COLOR", "8388608")),
        "25": (("RECORD", "25"), ("OWNERPARTID", "-1"), ("LOCATION.X", "0"), ("LOCATION.Y", "0"),
               ("TEXT", ""), ("FONTID", "1"), ("COLOR", "8388608")),
        "17": (("RECORD", "17"), ("OWNERPARTID", "-1"), ("LOCATION.X", "0"), ("LOCATION.Y", "0"),
               ("STYLE", "2"), ("ORIENTATION", "0"), ("SHOWNETNAME", "T"), ("TEXT", ""), ("FONTID", "1"),
               ("COLOR", "8388608")),
        "29": (("RECORD", "29"), ("OWNERPARTID", "-1"), ("LOCATION.X", "0"), ("LOCATION.Y", "0"),
               ("COLOR", "8388608")),
    }
)  # fmt: skip
"""The forms of a new wire, net label, power port and junction when the sheet holds no record of the kind:
those of ``schdoc`` (wires, labels and power ports) and ``drawn`` (junctions), the forms Fenolite's builds
write (``schematic-records.md``, "What the writer sets")."""


def _unit(value: int, what: str) -> int:
    if value % UNIT_NM:
        raise Refused("altium.edit.assertion", f"{what} is not a whole number of 10-mil units")
    return value // UNIT_NM


def _at(point: Point, what: str) -> tuple[int, int]:
    return _unit(point[0], what), _unit(point[1], what)


def _ids(sheet: _Sheet) -> set[str]:
    return {v.upper() for i in range(len(sheet.frames)) if (v := sheet.props(i).get("UNIQUEID"))}


def _designators(sheet: _Sheet) -> set[str]:
    return {
        p["TEXT"]
        for i in range(len(sheet.frames))
        if (p := sheet.props(i)).get("RECORD") == "34" and "TEXT" in p and p.get("OWNERINDEX", "").isdigit()
    }


def _drop(payload: bytes, dropped: Callable[[str], bool]) -> bytes:
    """A record's text without the keys for which ``dropped`` (given the upper-case key) holds."""
    nul = payload.endswith(b"\0")
    pieces = payload.rstrip(b"\0").split(b"|")
    kept = [p for p in pieces if not (b"=" in p and dropped(p.partition(b"=")[0].decode("latin-1").upper()))]
    return b"|".join(kept) + (b"\0" if nul else b"")


def load(data: bytes, file: str = "") -> _Sheet:
    """The frames of the binary sheet ``data``."""
    compound = open_compound(data, file=file)
    stream = next(p for p in compound.streams() if p.upper() == "FILEHEADER")
    frames = deframe(compound.read(stream), where=stream)
    return _Sheet(frames[0].payload, [(f.kind, f.payload) for f in frames[1:]])


def add_part(
    sheet: _Sheet, source: _Sheet, designator: str, new_designator: str | None, at: Point | None
) -> str:
    """Append the part ``designator`` of ``source`` with every record it owns (D1); its designator."""
    name = new_designator or re.sub(r"\d+$|$", "?", designator, count=1)
    if new_designator is not None and new_designator in _designators(sheet):
        raise Refused(
            "altium.edit.assertion", f"the sheet holds a part {new_designator!r} already", "FileHeader"
        )
    du, dv = (0, 0) if at is None else _units(*at)
    root = _part(source, designator)
    owned = _owned(source, root)
    base = len(sheet.frames)
    placed = {old: base + k for k, old in enumerate(owned)}
    taken = _ids(sheet)
    for old in owned:
        kind, payload = source.frames[old]
        sheet.frames.append((kind, payload))
        if kind != 0:
            continue
        index = len(sheet.frames) - 1
        props = source.props(old)
        changes: dict[str, str] = {}
        owner = props.get("OWNERINDEX", "")
        if owner.isdigit() and int(owner) in placed:
            changes["OWNERINDEX"] = str(placed[int(owner)])
        if "UNIQUEID" in props:
            changes["UNIQUEID"] = new_id(taken)
        if props.get("RECORD") == "34" and owner == str(root):
            changes["TEXT"] = name
        if changes:
            sheet.set(index, changes)
    _shift(sheet, list(placed.values()), du, dv)
    _weight(sheet)
    return name


def annotate(sheet: _Sheet, part: Part, designator: str, old: str, others: Mapping[str, set[str]]) -> None:
    """Set the text of the part's designator record (D2); ``others`` holds the designators of each other
    sheet of the project."""
    root = _part(sheet, part.designator)
    [index] = [
        i
        for i in _owned(sheet, root)
        if sheet.props(i).get("RECORD") == "34" and sheet.props(i).get("OWNERINDEX") == str(root)
    ]  # fmt: skip
    held = sheet.props(index).get("TEXT", "")
    if held != old:
        raise Refused(
            "altium.edit.assertion",
            f"the designator of {part.designator} is {held!r}, not the stated {old!r}",
        )
    if designator in _designators(sheet):
        raise Refused(
            "altium.edit.assertion", f"another part of the sheet is named {designator!r}", "FileHeader"
        )
    for name, refs in others.items():
        if designator in refs:
            raise Refused(
                "altium.edit.assertion", f"the sheet {name} of the project holds {designator!r}", name
            )
    sheet.set(index, {"TEXT": designator})


def _template(sheet: _Sheet, record: str, text: str | None = None) -> bytes:
    """A new record of kind ``record``: a copy of the first of the sheet (of the same ``TEXT`` first), with
    no ``_FRAC`` key, else the written form."""
    found = [i for i in range(len(sheet.frames)) if sheet.props(i).get("RECORD") == record]
    same = [i for i in found if text is not None and sheet.props(i).get("TEXT") == text]
    if same or found:
        return _drop(sheet.frames[(same or found)[0]][1], lambda key: _FRAC.search(key) is not None)
    return b"|" + b"|".join(f"{k}={v}".encode("ascii") for k, v in WRITTEN[record]) + b"\0"


def _append(sheet: _Sheet, payload: bytes, changes: Mapping[str, str]) -> None:
    keys = keys_of(payload.rstrip(b"\0"))
    given = dict(changes)
    if "UNIQUEID" in keys:
        given["UNIQUEID"] = new_id(_ids(sheet))
    sheet.frames.append((0, payload))
    sheet.set(len(sheet.frames) - 1, given)
    _weight(sheet)


def _segments(sheet: _Sheet) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    out: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for i in range(len(sheet.frames)):
        p = sheet.props(i)
        if p.get("RECORD") != "27":
            continue
        count = int(p.get("LOCATIONCOUNT", "0") or 0)
        points = [(int(p.get(f"X{n}", "0")), int(p.get(f"Y{n}", "0"))) for n in range(1, count + 1)]
        out += list(zip(points, points[1:], strict=False))
    return out


def _inside(point: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> bool:
    """``point`` on the segment ``a``–``b`` and at neither end."""
    (x, y), (ax, ay), (bx, by) = point, a, b
    if point in (a, b) or (bx - ax) * (y - ay) != (by - ay) * (x - ax):
        return False
    return min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by)


def add_wire(sheet: _Sheet, points: list[Point]) -> None:
    """A wire through ``points`` (D3), and a junction at each end that lies inside another wire's segment."""
    if len(points) < 2:
        raise Refused("altium.edit.assertion", "a wire has two points or more")
    units = [_at(p, "a wire point") for p in points]
    segments = _segments(sheet)
    template = _drop(_template(sheet, "27"), lambda key: _POINTS.match(key) is not None)
    changes = {"LOCATIONCOUNT": str(len(units))}
    for n, (x, y) in enumerate(units, start=1):
        changes |= {f"X{n}": str(x), f"Y{n}": str(y)}
    _append(sheet, template, changes)
    junctions = {
        (int(p.get("LOCATION.X", "0")), int(p.get("LOCATION.Y", "0")))
        for i in range(len(sheet.frames))
        if (p := sheet.props(i)).get("RECORD") == "29"
    }
    for end in (units[0], units[-1]):
        if end not in junctions and any(_inside(end, a, b) for a, b in segments):
            _append(sheet, _template(sheet, "29"), {"LOCATION.X": str(end[0]), "LOCATION.Y": str(end[1])})
            junctions.add(end)


def add_mark(
    sheet: _Sheet, record: str, text: str, at: Point, orientation: int, style: str | None = None
) -> None:
    """A net label (record 25) or a power port (record 17) at ``at`` (D3)."""
    x, y = _at(at, "the location")
    payload = _template(sheet, record, text if record == "17" else None)
    keys = keys_of(payload.rstrip(b"\0"))
    changes = {"LOCATION.X": str(x), "LOCATION.Y": str(y), "TEXT": text}
    if orientation or "ORIENTATION" in keys:
        changes["ORIENTATION"] = str(orientation % 4)
    if style is not None:
        changes["STYLE"] = style
    _append(sheet, payload, changes)


def _project_sheets(project: Path, file: str) -> tuple[dict[str, set[str]], bool]:
    """The designators of each sheet of the project but ``file``, and whether ``file`` is a repeated sheet."""
    from fenolite.backends.altium.adapter.netlist import NetOptions, SheetInput, resolve
    from fenolite.backends.altium.read.project import load_project

    loaded = load_project(project)
    sheets: list[SheetInput] = []
    for item in loaded.documents:
        if item.document.kind == "schematic" and item.present and item.file is not None:
            sheets.append(
                SheetInput(item.file.name, "", read_schematic(item.file.read_bytes(), file=item.file.name))
            )
    resolved = resolve(sheets, NetOptions.from_project(loaded), [])
    repeated = any(
        i.repeated and resolved.sheets[i.sheet].input.file.lower() == file.lower() for i in resolved.instances
    )
    others = {
        data.input.file: {g.ref for g in data.groups}
        for data in resolved.sheets
        if data.input.file.lower() != file.lower()
    }
    return others, repeated


def net_signature(
    document: SchDocument, renames: Mapping[str, str] | None = None
) -> frozenset[tuple[frozenset[tuple[str, str]], tuple[str, ...]]]:
    """Each local net of the sheet as its pins (designator, pin) and its identifiers' texts; ``renames``
    maps a designator to the one an annotation gave it (change c0499, D2)."""
    names = dict(renames or {})
    from fenolite.backends.altium.adapter.connectivity import local_nets
    from fenolite.backends.altium.adapter.parts import part_groups

    groups = part_groups(document)
    out: set[tuple[frozenset[tuple[str, str]], tuple[str, ...]]] = set()
    for net in local_nets(document, groups):
        pins = frozenset(
            (names.get(groups[p.group].ref, groups[p.group].ref), p.designator) for p in net.pins
        )
        out.add((pins, tuple(sorted(i.text for i in net.idents))))
    return frozenset(out)


@dataclass
class SchematicSession:
    path: Path
    data: bytes
    gates: Mapping[str, bool] = field(default_factory=lambda: SCHEMATIC_GATES)
    queued: list[tuple[str, str, Callable[[_Sheet], None]]] = field(default_factory=lambda: [])
    declared: bool = False
    project: Path | None = None
    """The ``.PrjPcb`` whose other sheets ``annotate`` checks designators against (change c0499)."""
    renames: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    """Each annotated designator's new text, which the net-signature guard accepts."""
    _others: dict[str, set[str]] | None = None

    def move(self, part: Part, dx: int, dy: int) -> SchematicSession:
        self.queued.append(("move", f"move {part.designator}", lambda s: move(s, part, dx, dy)))
        return self

    def set_property(self, part: Part, name: str, value: str, *, old: str) -> SchematicSession:
        label = f"set {name} of {part.designator} to {value!r}"
        self.queued.append(("set_property", label, lambda s: set_property(s, part, name, value, old)))
        return self

    def delete(self, part: Part) -> SchematicSession:
        self.queued.append(("delete", f"delete {part.designator}", lambda s: delete(s, part)))
        return self

    def add_part(
        self, from_doc: str | Path | bytes, designator: str, *, new_designator: str | None = None,
        at: Point | None = None,
    ) -> SchematicSession:  # fmt: skip
        """Copy the part ``designator`` of the binary sheet ``from_doc`` into this one, as ``new_designator``
        (else its number replaced by ``?``), moved by ``at`` (nm, whole 10-mil units) (change c0499, D1)."""
        data = from_doc if isinstance(from_doc, bytes) else Path(from_doc).read_bytes()

        def run(sheet: _Sheet) -> None:
            add_part(sheet, load(data), designator, new_designator, at)

        label = f"add the part {designator} as {new_designator or designator}"
        self.queued.append(("add_part", label, run))
        return self

    def annotate(self, part: Part, designator: str, *, old: str) -> SchematicSession:
        """Give the part ``part`` the designator ``designator``, stating its old text ``old``; a designator
        that another part of the sheet, or of the ``project=`` of ``open``, holds refuses (change c0499,
        D2)."""

        def run(sheet: _Sheet) -> None:
            annotate(sheet, part, designator, old, self._project_others())

        self.renames[part.designator] = designator
        self.queued.append(("annotate", f"annotate {part.designator} as {designator}", run))
        return self

    def add_wire(self, points: list[Point]) -> SchematicSession:
        """A wire through ``points``; a junction where an end lies inside another wire (change c0499, D3)."""
        given = list(points)
        self.queued.append(("create", f"add a wire of {len(given)} points", lambda s: add_wire(s, given)))
        return self

    def add_net_label(self, text: str, at: Point, *, orientation: int = 0) -> SchematicSession:
        """A net label ``text`` at ``at`` (change c0499, D3)."""
        self.queued.append(
            ("create", f"add the net label {text}", lambda s: add_mark(s, "25", text, at, orientation))
        )
        return self

    def add_power_port(
        self, text: str, at: Point, *, orientation: int = 0, style: str | None = None
    ) -> SchematicSession:
        """A power port ``text`` at ``at``; ``style`` ``None`` takes the style of the template (change c0499,
        D3)."""
        label = f"add the power port {text}"
        self.queued.append(("create", label, lambda s: add_mark(s, "17", text, at, orientation, style)))
        return self

    def _project_others(self) -> dict[str, set[str]]:
        if self.project is None:
            return {}
        if self._others is None:
            others, repeated = _project_sheets(self.project, self.path.name)
            if repeated:
                message = f"{self.path.name} is a repeated sheet; its designators take a channel suffix"
                raise Refused("altium.edit.assertion", message, self.path.name)
            self._others = others
        return self._others

    def declare_connectivity(self) -> SchematicSession:
        """Allow a change of the sheet's net signature."""
        self.declared = True
        return self

    def commit(self, out: str | Path, *, backup: bool = True) -> Receipt:
        labels = tuple(label for _, label, _ in self.queued)
        closed = [(gate, label) for gate, label, _ in self.queued if not self.gates.get(gate, False)]
        if closed:
            issues = tuple(
                _issue(
                    "altium.edit.gate",
                    f"{label}: the gate of {gate} is off; rows {', '.join(ROWS[gate])} "
                    "are not confirmed by the kit",
                )
                for gate, label in closed
            )
            return Receipt(False, None, None, issues, labels, evidence=EVIDENCE)
        compound = open_compound(self.data, file=self.path.name)
        stream = next(p for p in compound.streams() if p.upper() == "FILEHEADER")
        frames = deframe(compound.read(stream), where=stream)
        sheet = load(self.data, self.path.name)
        for _gate, label, run in self.queued:
            try:
                run(sheet)
            except Refused as refusal:
                issue = _issue(refusal.code, f"{label}: {refusal.message}", refusal.where)
                return Receipt(False, None, None, (issue,), labels, evidence=EVIDENCE)
        body = enframe([(frames[0].kind, sheet.header), *sheet.frames])

        def walk(entries: tuple[Entry, ...], path: str) -> tuple[Entry, ...]:
            built: list[Entry] = []
            for entry in entries:
                if isinstance(entry, Storage):
                    built.append(Storage(entry.name, walk(entry.entries, f"{path}{entry.name}/")))
                else:
                    built.append((entry[0], body if f"{path}{entry[0]}" == stream else entry[1]))
            return tuple(built)

        data = write_compound(walk(compound.tree(), ""))
        try:
            after = read_schematic(data, file=self.path.name)
        except FormatError as error:
            issue = _issue("altium.edit.readback", f"the edited sheet does not read back: {error}")
            return Receipt(False, None, None, (issue,), labels, evidence=EVIDENCE)
        before = read_schematic(self.data, file=self.path.name)
        if not self.declared and net_signature(before, self.renames) != net_signature(after):
            issue = _issue(
                "altium.edit.connectivity",
                "the net signature of the sheet changed, and the session does not declare it",
                hint="SchematicSession.declare_connectivity()",
            )
            return Receipt(False, None, None, (issue,), labels, evidence=EVIDENCE)
        target = Path(out)
        receipt = atomic_write(target, data, backup=backup)
        return Receipt(True, target, receipt.sha256, (), labels, receipt.backup_path, EVIDENCE)


def _issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    severity = EDIT_ISSUE_CODES[code]
    return Issue(code, severity if isinstance(severity, str) else severity[0], message, where, hint)


def open_schematic(
    path: str | Path, *, gates: Mapping[str, bool] | None = None, project: str | Path | None = None
) -> SchematicSession:
    target = Path(path)
    data = target.read_bytes()
    document = read_schematic(data, file=target.name)
    if document.form != "binary":
        raise ValueError(f"{target.name}: a schematic session opens the binary form only")
    gated = MappingProxyType({**SCHEMATIC_GATES, **(gates or {})})
    return SchematicSession(target, data, gated, project=None if project is None else Path(project))


__all__ = ["EVIDENCE", "OPERATIONS", "ROWS", "SCHEMATIC_GATES", "Part", "SchematicSession", "net_signature",
           "open_schematic"]  # fmt: skip
