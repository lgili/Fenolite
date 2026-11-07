# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edit session of a binary Altium schematic document (capability altium-edit, "Edit session on an
Altium document"; change c0241, task 3.4): ``move``, ``set_property`` and ``delete`` of a part, with the
net-signature guard.

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
from fenolite.backends.altium.edit.ops import Refused
from fenolite.backends.altium.edit.records import keys_of, set_keys
from fenolite.backends.altium.edit.session import EDIT_ISSUE_CODES, Receipt
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.sch import SchDocument, read_schematic
from fenolite.backends.altium.read.sch.framing import deframe, enframe
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.io import atomic_write

OPERATIONS = ("move", "set_property", "delete")
SCHEMATIC_GATES: Mapping[str, bool] = MappingProxyType(dict.fromkeys(OPERATIONS, False))
ROWS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    dict.fromkeys(OPERATIONS, ("H-A-EDIT-SCH", "H-A-EDIT-KIT"))
)
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-EDIT-KIT", "H-A-EDIT-SCH"))
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


def move(sheet: _Sheet, part: Part, dx: int, dy: int) -> None:
    if dx % UNIT_NM or dy % UNIT_NM:
        raise Refused("altium.edit.assertion", "a schematic move is a whole number of 10-mil units")
    du, dv = dx // UNIT_NM, dy // UNIT_NM
    for index in _owned(sheet, _part(sheet, part.designator)):
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
    nul = sheet.header.endswith(b"\0")
    sheet.header = set_keys(sheet.header.rstrip(b"\0"), {"WEIGHT": str(len(frames))}) + (
        b"\0" if nul else b""
    )


def net_signature(document: SchDocument) -> frozenset[tuple[frozenset[tuple[str, str]], tuple[str, ...]]]:
    """Each local net of the sheet as its pins (designator, pin) and its identifiers' texts."""
    from fenolite.backends.altium.adapter.connectivity import local_nets
    from fenolite.backends.altium.adapter.parts import part_groups

    groups = part_groups(document)
    out: set[tuple[frozenset[tuple[str, str]], tuple[str, ...]]] = set()
    for net in local_nets(document, groups):
        pins = frozenset((groups[p.group].ref, p.designator) for p in net.pins)
        out.add((pins, tuple(sorted(i.text for i in net.idents))))
    return frozenset(out)


@dataclass
class SchematicSession:
    path: Path
    data: bytes
    gates: Mapping[str, bool] = field(default_factory=lambda: SCHEMATIC_GATES)
    queued: list[tuple[str, str, Callable[[_Sheet], None]]] = field(default_factory=lambda: [])
    declared: bool = False

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
        sheet = _Sheet(frames[0].payload, [(f.kind, f.payload) for f in frames[1:]])
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
        if not self.declared and net_signature(before) != net_signature(after):
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


def open_schematic(path: str | Path, *, gates: Mapping[str, bool] | None = None) -> SchematicSession:
    target = Path(path)
    data = target.read_bytes()
    document = read_schematic(data, file=target.name)
    if document.form != "binary":
        raise ValueError(f"{target.name}: a schematic session opens the binary form only")
    return SchematicSession(target, data, MappingProxyType({**SCHEMATIC_GATES, **(gates or {})}))


__all__ = ["EVIDENCE", "OPERATIONS", "ROWS", "SCHEMATIC_GATES", "Part", "SchematicSession", "net_signature",
           "open_schematic"]  # fmt: skip
