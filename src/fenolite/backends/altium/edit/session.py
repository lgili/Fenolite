# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edit session of an Altium PCB document and its commit (capability altium-edit, "Edit session on an
Altium document", "Operations gated by their hypotheses", "Commit gates"; change c0241, design Decision 5).

``Session`` queues operations; nothing is read or written until ``commit``. The commit then:

1. refuses every operation whose gate is off (``altium.edit.gate``, naming the gate and its rows), before
   any edit is made;
2. makes the operations in order on the document's records; a failed assertion or a missing template
   refuses (``altium.edit.assertion``, ``altium.edit.no-template``);
3. reads the result back strictly, and compares it with the input: a changed stream outside the edited
   storages, or a record changed beyond what the operations declared, refuses
   (``altium.edit.unexpected-change``); so does a change of the copper connectivity
   (``edit.connectivity``) that the session did not declare (``altium.edit.connectivity``, naming the nets),
   and any new ``error`` of the integrity check (``altium.edit.integrity``);
4. writes the file atomically, keeping the previous one as ``<name>.bak`` (``core.io.atomic_write``).

A refused commit writes nothing; its ``Receipt`` holds the issues and exit code 5.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from fenolite.backends.altium.edit import connectivity, integrity, ops
from fenolite.backends.altium.edit.ops import Component, Item, Point, Polygon, Refused
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprops import parse_blocks
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.io import atomic_write

OPERATIONS = ("delete", "move", "rotate", "flip", "set_property", "clone", "add_component", "remap_layer",
              "set_rule", "set_outline", "create")  # fmt: skip
ROWS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "delete": ("H-A-EDIT-DELETE", "H-A-EDIT-SHAPE", "H-A-EDIT-KIT"),
        "move": ("H-A-EDIT-MOVE", "H-A-EDIT-SHAPE", "H-A-EDIT-KIT"),
        "rotate": ("H-A-EDIT-ROTATE", "H-A-EDIT-KIT"),
        "flip": ("H-A-EDIT-FLIP", "H-A-EDIT-KIT"),
        "set_property": ("H-A-EDIT-PROPERTY", "H-A-EDIT-KIT"),
        "clone": ("H-A-EDIT-CLONE", "H-A-EDIT-IDS", "H-A-EDIT-KIT"),
        "add_component": ("H-A-EDIT-ADD", "H-A-EDIT-IDS", "H-A-EDIT-KIT"),
        "remap_layer": ("H-A-EDIT-LAYER", "H-A-EDIT-KIT"),
        "set_rule": ("H-A-EDIT-RULE", "H-A-EDIT-KIT"),
        "set_outline": ("H-A-EDIT-SHAPE", "H-A-EDIT-KIT"),
        "create": ("H-A-EDIT-CREATE", "H-A-EDIT-IDS", "H-A-EDIT-KIT"),
    }
)
"""The rows of ``docs/hypotheses.md`` each operation rests on."""
GATES: Mapping[str, bool] = MappingProxyType(dict.fromkeys(OPERATIONS, False))
"""One gate per operation, all off: a gate is set only by a recorded Part J phase B case (task 4.2)."""
EDIT_ISSUE_CODES: Mapping[str, Severity | tuple[Severity, ...]] = MappingProxyType(
    {
        "altium.edit.gate": "error",
        "altium.edit.assertion": "error",
        "altium.edit.no-template": "error",
        "altium.edit.readback": "error",
        "altium.edit.unexpected-change": "error",
        "altium.edit.connectivity": "error",
        "altium.edit.integrity": ("error", "warning"),
    }
)
HYPOTHESES = tuple(sorted({row for rows in ROWS.values() for row in rows}))
EVIDENCE = Evidence(Level.INFERRED, hypotheses=HYPOTHESES)
"""``INFERRED``: no operation's phase B case has run; the writes are experimental and gated off."""


@dataclass(frozen=True, slots=True)
class Receipt:
    """What a commit did: ``written`` and the file's path and SHA-256 when it wrote, the issues either way."""

    written: bool
    path: Path | None
    sha256: str | None
    issues: tuple[Issue, ...]
    operations: tuple[str, ...]
    backup: Path | None = None
    evidence: Evidence = EVIDENCE

    @property
    def exit_code(self) -> int:
        return 5 if any(i.severity == "error" for i in self.issues) else 0


@dataclass(frozen=True, slots=True)
class _Queued:
    gate: str
    label: str
    run: Callable[[State], None]


def _issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    severity = EDIT_ISSUE_CODES[code]
    return Issue(code, severity if isinstance(severity, str) else severity[0], message, where, hint)


@dataclass
class Session:
    """The edits queued on one PCB document (``open``)."""

    path: Path
    data: bytes
    gates: Mapping[str, bool] = field(default_factory=lambda: GATES)
    queued: list[_Queued] = field(default_factory=lambda: list[_Queued]())
    declared_nets: set[str] = field(default_factory=lambda: set[str]())

    def _queue(self, gate: str, label: str, run: Callable[[State], None]) -> Session:
        self.queued.append(_Queued(gate, label, run))
        return self

    # --- operations -------------------------------------------------------------------------------------

    def delete(self, item: Item) -> Session:
        return self._queue("delete", f"delete {ops.describe(item)}", lambda s: ops.delete(s, item))

    def move(self, item: Item, dx: int, dy: int, *, expect: Mapping[str, object] | None = None) -> Session:
        """Move ``item`` by ``(dx, dy)`` nanometres; ``expect`` states other old values (``width``, ...)."""
        given = dict(expect or {})
        label = f"move {ops.describe(item)} by ({dx / 1e6:g}, {dy / 1e6:g}) mm"
        return self._queue("move", label, lambda s: ops.move(s, item, dx, dy, given))

    def rotate(self, item: Component, degrees: float, *, old_rotation: float) -> Session:
        label = f"rotate {ops.describe(item)} by {degrees:g}°"
        return self._queue("rotate", label, lambda s: ops.rotate(s, item, degrees, old_rotation))

    def flip(self, item: Component, *, old_side: str = "TOP") -> Session:
        return self._queue("flip", f"flip {ops.describe(item)}", lambda s: ops.flip(s, item, old_side))

    def set_property(self, item: Item, key: str, value: object, *, old: object) -> Session:
        label = f"set {key} of {ops.describe(item)} to {value!r}"
        return self._queue("set_property", label, lambda s: ops.set_property(s, item, key, value, old))

    def clone(self, item: Item, **changes: object) -> Session:
        return self._queue("clone", f"clone {ops.describe(item)}", lambda s: ops.clone(s, item, changes))

    def add_component(
        self, from_doc: Path | bytes, ref: str, *, designator: str | None = None, at: Point | None = None,
        nets: Mapping[str, str] | None = None,
    ) -> Session:  # fmt: skip
        """Copy the component ``ref`` of the PCB document ``from_doc`` into this one, as ``designator``, at
        ``at``; ``nets`` gives a net per pad name."""
        data = from_doc if isinstance(from_doc, bytes) else Path(from_doc).read_bytes()
        given = dict(nets or {})

        def run(state: State) -> None:
            ops.add_component(state, State.of(data), ref, new_designator=designator, at=at, nets=given)

        return self._queue("add_component", f"add the component {ref} as {designator or ref}", run)

    def remap_layer(self, old: str, new: str) -> Session:
        return self._queue("remap_layer", f"remap {old} to {new}", lambda s: ops.remap_layer(s, old, new))

    def set_rule(self, name: str, key: str, value: str, *, old: str) -> Session:
        label = f"set {key} of the rule {name!r} to {value}"
        return self._queue("set_rule", label, lambda s: ops.set_rule(s, name, key, value, old))

    def set_outline(self, item: Polygon, outline: Sequence[Point], *, old: Sequence[Point]) -> Session:
        """Give the polygon ``item`` the outline ``outline`` (line vertices, nanometres), stating its old
        vertices ``old``; its pour is removed (change c0452)."""
        new, held = list(outline), list(old)
        label = f"set the outline of {ops.describe(item)} to {len(new)} vertices"
        return self._queue("set_outline", label, lambda s: ops.set_outline(s, item, new, held))

    def add_arc(
        self, centre: Point, radius: int, start: float, end: float, *, width: int, layer: str,
        net: str | None = None,
    ) -> Session:  # fmt: skip
        """Add a free arc of ``centre`` and ``radius`` (nm) from ``start`` to ``end`` degrees."""
        label = f"add an arc of radius {radius / 1e6:g} mm on {layer}"

        def run(state: State) -> None:
            ops.add_arc(state, centre, radius, (start, end), width=width, layer=layer, net=net)

        return self._queue("create", label, run)

    def add_fill(
        self, corner: Point, opposite: Point, *, layer: str, net: str | None = None, rotation: float = 0.0
    ) -> Session:
        """Add a free fill between two opposite corners (nm)."""
        label = f"add a fill on {layer}"

        def run(state: State) -> None:
            ops.add_fill(state, corner, opposite, layer=layer, net=net, rotation=rotation)

        return self._queue("create", label, run)

    def add_region(self, outline: Sequence[Point], *, layer: str, net: str | None = None) -> Session:
        """Add a free region of the outline ``outline`` (nm, no closing vertex)."""
        points = list(outline)
        label = f"add a region of {len(points)} vertices on {layer}"
        return self._queue("create", label, lambda s: ops.add_region(s, points, layer=layer, net=net))

    def add_polygon(self, name: str, outline: Sequence[Point], *, layer: str, net: str) -> Session:
        """Add the polygon ``name`` of the outline ``outline`` (nm), without its pour."""
        points = list(outline)
        label = f"add the polygon {name} on {layer}"
        return self._queue("create", label, lambda s: ops.add_polygon(s, name, points, layer=layer, net=net))

    def declare_connectivity(self, *nets: str) -> Session:
        """Allow a change of the connectivity of ``nets`` (a short between two of them, or a net split or
        joined)."""
        self.declared_nets |= set(nets)
        return self

    # --- commit ---------------------------------------------------------------------------------------

    def apply(self) -> tuple[State | None, list[Issue]]:
        """The edited state, or ``None`` and the issues of the gates, assertions and templates."""
        closed = [q for q in self.queued if not self.gates.get(q.gate, False)]
        if closed:
            return None, [
                _issue("altium.edit.gate", f"{q.label}: the gate of {q.gate} is off; rows "
                       f"{', '.join(ROWS[q.gate])} are not confirmed by the kit", hint="edit.GATES")
                for q in closed
            ]  # fmt: skip
        state = State.of(self.data, file=self.path.name)
        for queued in self.queued:
            try:
                queued.run(state)
            except Refused as refusal:
                return None, [_issue(refusal.code, f"{queued.label}: {refusal.message}", refusal.where)]
        return state, []

    def commit(self, out: str | Path, *, backup: bool = True) -> Receipt:
        labels = tuple(q.label for q in self.queued)
        state, issues = self.apply()
        if state is None:
            return Receipt(False, None, None, tuple(issues), labels)
        written, issues = verify(self.data, state, declared_nets=self.declared_nets, file=self.path.name)
        if written is None:
            return Receipt(False, None, None, tuple(issues), labels)
        target = Path(out)
        receipt = atomic_write(target, written, backup=backup)
        return Receipt(True, target, receipt.sha256, tuple(issues), labels, receipt.backup_path)


def _records(data: bytes) -> dict[str, Counter[bytes]]:
    """Every record of every storage an operation can edit, as a multiset, per storage."""
    state = State.of(data)
    out: dict[str, Counter[bytes]] = {}
    for storage in (*ops.COMPONENT_STORAGES, "Components6", "Polygons6", "Rules6", "Nets6",
                    "UniqueIDPrimitiveInformation", "WideStrings6"):  # fmt: skip
        if state.has(storage):
            out[state.name(storage)] = Counter(state.get(storage))
    return out


def verify(
    original: bytes, state: State, *, declared_nets: set[str], file: str = ""
) -> tuple[bytes | None, list[Issue]]:
    """The commit gates on the edited ``state`` of ``original``: the bytes to write, or ``None``, and the
    issues (the integrity check's new warnings are kept when the bytes are written)."""
    data = state.data()
    try:
        after = read_pcbdoc(data, file=file, strict=True)
    except FormatError as error:
        return None, [_issue("altium.edit.readback", f"the edited document does not read back: {error}")]
    before = read_pcbdoc(original, file=file)
    found: list[Issue] = []
    source = State.of(original)
    touched = {name.upper() for name in state.touched}
    for path in state.changed_streams(source.streams):
        if path.split("/", 1)[0].upper() not in touched:
            found.append(_issue("altium.edit.unexpected-change", f"the stream {path} changed", path))
    old, new = _records(original), _records(data)
    for name in sorted(set(old) | set(new)):
        removed = old.get(name, Counter[bytes]()) - new.get(name, Counter[bytes]())
        added = new.get(name, Counter[bytes]()) - old.get(name, Counter[bytes]())
        stated_removed = Counter({raw: n for (s, raw), n in state.removed.items() if s == name})
        stated_added = Counter({raw: n for (s, raw), n in state.added.items() if s == name})
        if removed != stated_removed or added != stated_added:
            found.append(
                _issue(
                    "altium.edit.unexpected-change",
                    f"{name}: {sum(removed.values())} records removed and {sum(added.values())} added, "
                    f"where the operations declared {sum(stated_removed.values())} "
                    f"and {sum(stated_added.values())}",
                    f"{name}/Data",
                )
            )
    for nets, sentence in connectivity.changes(connectivity.signature(before), connectivity.signature(after)):
        if not set(nets) <= declared_nets:
            found.append(
                _issue(
                    "altium.edit.connectivity",
                    f"{sentence}, and the session does not declare it",
                    hint=f"Session.declare_connectivity({', '.join(map(repr, nets))})",
                )
            )
    compound = State.of(data).document()[1]
    had = {(i.code, i.message) for i in integrity.check_pcbdoc(original, file=file)}
    for finding in integrity.check_document(after, compound):
        if (finding.code, finding.message) in had:
            continue
        code = "altium.edit.integrity"
        found.append(Issue(code, finding.severity if finding.severity in ("error", "warning") else "warning",
                           f"{finding.code}: {finding.message}", finding.where, finding.hint))  # fmt: skip
    if any(i.severity == "error" for i in found):
        return None, found
    return data, found


def open_document(path: str | Path, *, gates: Mapping[str, bool] | None = None) -> Session:
    """A session on the PCB document at ``path``; ``gates`` replaces ``GATES`` (for the kit and the tests
    only: a gate is opened by its phase B case, not by a caller)."""
    target = Path(path)
    data = target.read_bytes()
    read_pcbdoc(data, file=target.name)
    return Session(target, data, MappingProxyType({**GATES, **(gates or {})}))


def unique_id_entries(data: bytes) -> list[dict[str, str]]:
    """The entries of ``UniqueIDPrimitiveInformation`` of the PCB document ``data`` (for the tests)."""
    state = State.of(data)
    if not state.has("UniqueIDPrimitiveInformation"):
        return []
    raw = b"".join(state.get("UniqueIDPrimitiveInformation"))
    return [dict(r.fields) for r in parse_blocks(raw, where="u")[0]]


__all__ = [
    "EDIT_ISSUE_CODES",
    "EVIDENCE",
    "GATES",
    "HYPOTHESES",
    "OPERATIONS",
    "ROWS",
    "Receipt",
    "Session",
    "open_document",
    "unique_id_entries",
    "verify",
]
